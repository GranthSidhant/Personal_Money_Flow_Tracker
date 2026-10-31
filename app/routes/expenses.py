from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.category import Category, ensure_default_categories
from app.models.fund import Fund
from app.models.person import Person
from app.models.expense import Expense
from app.models.expense_allocation import ExpenseAllocation
from app.models.bank_account import BankAccount
from app.models.receipt import Receipt
from app.models.bank_transaction import BankTransaction
from app.utils.money import rupees_to_paise, format_inr
from app.services.allocation_service import record_expense_with_allocations, get_spending_by_category, get_recoverable_contributions_total
from app.services.balance_service import get_fund_balance
from app.services.audit_service import log_audit_event

expenses_bp = Blueprint("expenses", __name__)


@expenses_bp.route("/expenses")
@expenses_bp.route("/transactions")
@login_required
def index():
    """All transactions view matching UI.png Card 4."""
    tab = request.args.get("tab", "all").lower()
    
    # 1. Fetch Expenses
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_at.desc()).all()
    # 2. Fetch Receipts (Money In)
    receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(Receipt.received_at.desc()).all()
    # 3. Fetch Bank internal transfers
    transfers = (
        BankTransaction.query.filter_by(user_id=current_user.id)
        .filter(BankTransaction.transaction_type == "TRANSFER_OUT")
        .order_by(BankTransaction.transaction_at.desc())
        .all()
    )

    # Build unified transaction list
    all_activities = []
    for exp in expenses:
        linked_sources = [a.fund.person.name if a.fund and a.fund.person else "Pocket Money" for a in exp.allocations]
        linked_to_str = ", ".join(set(linked_sources))
        all_activities.append({
            "id": exp.id,
            "type": "EXPENSE",
            "date": exp.expense_at,
            "description": exp.title,
            "category": exp.category.name if exp.category else "Uncategorized",
            "linked_to": linked_to_str,
            "amount_paise": exp.total_amount_paise,
            "view_url": url_for("expenses.detail", expense_id=exp.id),
        })

    for rec in receipts:
        all_activities.append({
            "id": rec.id,
            "type": "RECEIPT",
            "date": rec.received_at,
            "description": f"Received for {rec.fund.title}",
            "category": "Fund Deposit",
            "linked_to": rec.fund.person.name if rec.fund.person else "Direct",
            "amount_paise": rec.amount_paise,
            "view_url": url_for("funds.detail", fund_id=rec.fund_id),
        })

    for tr in transfers:
        all_activities.append({
            "id": tr.id,
            "type": "TRANSFER",
            "date": tr.transaction_at,
            "description": tr.description,
            "category": "Internal Transfer",
            "linked_to": tr.bank_account.account_nickname,
            "amount_paise": tr.amount_paise,
            "view_url": url_for("bank_accounts.detail", account_id=tr.bank_account_id),
        })

    # Sort descending by date
    all_activities.sort(key=lambda x: x["date"], reverse=True)

    if tab == "expenses":
        displayed_activities = [a for a in all_activities if a["type"] == "EXPENSE"]
    elif tab == "money_in":
        displayed_activities = [a for a in all_activities if a["type"] == "RECEIPT"]
    elif tab == "transfers":
        displayed_activities = [a for a in all_activities if a["type"] == "TRANSFER"]
    else:
        displayed_activities = all_activities

    return render_template(
        "expenses/index.html",
        activities=displayed_activities,
        current_tab=tab,
    )


@expenses_bp.route("/expenses/new", methods=["GET", "POST"])
@login_required
def new():
    ensure_default_categories()
    categories = Category.query.filter((Category.user_id == current_user.id) | (Category.user_id.is_(None))).order_by(Category.name.asc()).all()
    funds = Fund.query.filter_by(user_id=current_user.id, status="ACTIVE").order_by(Fund.created_at.desc()).all()
    bank_accounts = BankAccount.query.filter_by(user_id=current_user.id, archived_at=None).order_by(BankAccount.account_nickname.asc()).all()

    # Calculate fund balances for helper display
    funds_with_balance = []
    for f in funds:
        bal = get_fund_balance(f.id, current_user.id)
        funds_with_balance.append({
            "fund": f,
            "available_paise": bal["balance_paise"],
            "display": f"{f.title} ({f.person.name}) - Bal: {format_inr(bal['balance_paise'])}"
        })

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount_str = request.form.get("amount", "").strip()
        category_id = request.form.get("category_id", type=int)
        expense_at_str = request.form.get("expense_at")
        merchant = request.form.get("merchant", "").strip()
        payment_account_id = request.form.get("payment_account_id", type=int)
        payment_method = request.form.get("payment_method", "Card")
        description = request.form.get("description", "").strip()
        
        # Funding source mode
        funding_mode = request.form.get("funding_mode", "single_fund")

        try:
            total_amount_paise = rupees_to_paise(amount_str)
            if total_amount_paise <= 0:
                raise ValueError("Amount must be greater than zero.")
        except Exception as e:
            flash(f"Invalid amount: {str(e)}", "danger")
            return render_template("expenses/form.html", categories=categories, funds=funds_with_balance, bank_accounts=bank_accounts)

        try:
            expense_at = datetime.fromisoformat(expense_at_str) if expense_at_str else datetime.now(timezone.utc)
        except Exception:
            expense_at = datetime.now(timezone.utc)

        allocations_data = []

        if funding_mode == "single_fund":
            fund_id = request.form.get("fund_id", type=int)
            if not fund_id:
                flash("Please select a funding source.", "danger")
                return render_template("expenses/form.html", categories=categories, funds=funds_with_balance, bank_accounts=bank_accounts)

            # Check if fund has enough balance or if shortfall should go to Pocket Money
            fund_bal = get_fund_balance(fund_id, current_user.id)["balance_paise"]
            if total_amount_paise <= fund_bal:
                # Fully covered by fund
                allocations_data.append({
                    "source_type": "FUND",
                    "fund_id": fund_id,
                    "allocated_amount_paise": total_amount_paise,
                    "reimbursement_expected": False,
                })
            else:
                # Fund shortfall: split fund available + Pocket Money shortfall
                reimbursement_expected = request.form.get("shortfall_reimbursement") == "1"
                shortfall_paise = total_amount_paise - fund_bal
                if fund_bal > 0:
                    allocations_data.append({
                        "source_type": "FUND",
                        "fund_id": fund_id,
                        "allocated_amount_paise": fund_bal,
                        "reimbursement_expected": False,
                    })
                allocations_data.append({
                    "source_type": "POCKET_MONEY",
                    "fund_id": None,
                    "allocated_amount_paise": shortfall_paise if fund_bal > 0 else total_amount_paise,
                    "reimbursement_expected": reimbursement_expected,
                })

        elif funding_mode == "pocket_money":
            reimbursement_expected = request.form.get("reimbursement_expected") == "1"
            allocations_data.append({
                "source_type": "POCKET_MONEY",
                "fund_id": None,
                "allocated_amount_paise": total_amount_paise,
                "reimbursement_expected": reimbursement_expected,
            })

        elif funding_mode == "multi_split":
            # Read dynamic split allocation rows
            split_sources = request.form.getlist("split_source[]")
            split_funds = request.form.getlist("split_fund_id[]")
            split_amounts = request.form.getlist("split_amount[]")
            split_reimburse = request.form.getlist("split_reimbursement[]")

            for i in range(len(split_sources)):
                s_type = split_sources[i]
                amt_str = split_amounts[i] if i < len(split_amounts) else "0"
                if not amt_str or amt_str == "0":
                    continue
                a_paise = rupees_to_paise(amt_str)
                f_id = int(split_funds[i]) if i < len(split_funds) and split_funds[i] and split_funds[i] != "0" else None
                reimb = (split_reimburse[i] == "1") if i < len(split_reimburse) else False

                allocations_data.append({
                    "source_type": s_type,
                    "fund_id": f_id if s_type == "FUND" else None,
                    "allocated_amount_paise": a_paise,
                    "reimbursement_expected": reimb,
                })

        try:
            expense = record_expense_with_allocations(
                user_id=current_user.id,
                title=title,
                total_amount_paise=total_amount_paise,
                category_id=category_id if category_id and category_id != 0 else None,
                expense_at=expense_at,
                allocations_data=allocations_data,
                merchant=merchant if merchant else None,
                payment_method=payment_method,
                description=description if description else None,
                bank_account_id=payment_account_id if payment_account_id and payment_account_id != 0 else None,
            )
            flash(f"Recorded expense '{expense.title}' of {format_inr(expense.total_amount_paise)}.", "success")
            return redirect(url_for("expenses.detail", expense_id=expense.id))
        except ValueError as err:
            flash(str(err), "danger")
            return render_template("expenses/form.html", categories=categories, funds=funds_with_balance, bank_accounts=bank_accounts)

    return render_template(
        "expenses/form.html",
        categories=categories,
        funds=funds_with_balance,
        bank_accounts=bank_accounts,
    )


@expenses_bp.route("/expenses/<int:expense_id>")
@login_required
def detail(expense_id: int):
    """Transaction Detail & Map preview matching UI.png Card 7."""
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    allocations = expense.allocations.all()
    linked_bank_tx = expense.bank_transactions.first()

    return render_template(
        "expenses/detail.html",
        expense=expense,
        allocations=allocations,
        linked_bank_tx=linked_bank_tx,
    )


@expenses_bp.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete(expense_id: int):
    """Delete an expense and reverse its allocations."""
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    title = expense.title
    total = expense.total_amount_paise

    log_audit_event(
        user_id=current_user.id,
        entity_type="EXPENSE",
        entity_id=expense.id,
        action="DELETE",
        before_snapshot={"title": title, "total_amount_paise": total}
    )
    db.session.delete(expense)
    db.session.commit()

    flash(f"Expense '{title}' deleted. Fund balances have been recalculated.", "info")
    return redirect(url_for("expenses.index"))
