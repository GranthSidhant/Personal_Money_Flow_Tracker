from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.settlement import Settlement
from app.models.fund import Fund
from app.models.person import Person
from app.models.bank_account import BankAccount
from app.services.balance_service import get_fund_balance
from app.services.settlement_service import (
    execute_transfer_to_pocket,
    execute_return_to_provider,
    execute_reimbursement,
    get_outstanding_receivable,
)
from app.utils.money import rupees_to_paise, format_inr

settlements_bp = Blueprint("settlements", __name__)


@settlements_bp.route("/settlements")
@login_required
def index():
    """Settlement history and actions view."""
    filter_type = request.args.get("type", "ALL").upper()
    
    query = Settlement.query.filter_by(user_id=current_user.id)
    if filter_type != "ALL":
        query = query.filter(Settlement.settlement_type == filter_type)
    
    settlements = query.order_by(Settlement.settlement_at.desc(), Settlement.id.desc()).all()

    # Calculate overall summary metrics
    all_settlements = Settlement.query.filter_by(user_id=current_user.id).all()
    transfers_total = sum(s.amount_paise for s in all_settlements if s.settlement_type == "TRANSFER_TO_POCKET")
    returns_total = sum(s.amount_paise for s in all_settlements if s.settlement_type == "RETURN_TO_PROVIDER")
    reimbursements_total = sum(s.amount_paise for s in all_settlements if s.settlement_type == "REIMBURSEMENT")
    total_receivable = get_outstanding_receivable(current_user.id)

    return render_template(
        "settlements/index.html",
        settlements=settlements,
        filter_type=filter_type,
        transfers_total=transfers_total,
        returns_total=returns_total,
        reimbursements_total=reimbursements_total,
        total_receivable=total_receivable,
    )


@settlements_bp.route("/settlements/transfer-to-pocket", methods=["GET", "POST"])
@login_required
def transfer_to_pocket():
    """Transfer unused money from an active fund to Pocket Money with permission."""
    preselected_fund_id = request.args.get("fund_id", type=int)

    if request.method == "POST":
        fund_id = int(request.form.get("fund_id", 0))
        amount_str = request.form.get("amount", "0")
        notes = request.form.get("notes", "").strip()
        date_str = request.form.get("settlement_at")

        try:
            amount_paise = rupees_to_paise(amount_str)
            settlement_at = (
                datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                if date_str
                else datetime.now(timezone.utc)
            )

            execute_transfer_to_pocket(
                user_id=current_user.id,
                fund_id=fund_id,
                amount_paise=amount_paise,
                notes=notes,
                settlement_at=settlement_at,
            )
            flash("Transferred to Pocket Money successfully.", "success")
            return redirect(url_for("settlements.index"))
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            flash(f"Error executing transfer: {str(e)}", "danger")

    # Fetch active funds with available balance
    funds = Fund.query.filter_by(user_id=current_user.id, status="ACTIVE").all()
    funds_data = []
    for f in funds:
        bal = get_fund_balance(f.id, current_user.id)
        if bal["balance_paise"] > 0 or f.id == preselected_fund_id:
            funds_data.append({
                "fund": f,
                "available_paise": bal["balance_paise"],
                "display": f"{f.title} ({f.person.name}) - Available: {format_inr(bal['balance_paise'])}",
            })

    return render_template(
        "settlements/transfer_form.html",
        funds=funds_data,
        preselected_fund_id=preselected_fund_id,
    )


@settlements_bp.route("/settlements/return", methods=["GET", "POST"])
@login_required
def return_to_provider():
    """Return unused entrusted fund money back to the person who gave it."""
    preselected_fund_id = request.args.get("fund_id", type=int)

    if request.method == "POST":
        fund_id = int(request.form.get("fund_id", 0))
        amount_str = request.form.get("amount", "0")
        notes = request.form.get("notes", "").strip()
        date_str = request.form.get("settlement_at")
        bank_account_id = request.form.get("bank_account_id")
        bank_id = int(bank_account_id) if bank_account_id and bank_account_id.isdigit() else None

        try:
            amount_paise = rupees_to_paise(amount_str)
            settlement_at = (
                datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                if date_str
                else datetime.now(timezone.utc)
            )

            execute_return_to_provider(
                user_id=current_user.id,
                fund_id=fund_id,
                amount_paise=amount_paise,
                notes=notes,
                settlement_at=settlement_at,
                bank_account_id=bank_id,
            )
            flash("Returned money to provider recorded successfully.", "success")
            return redirect(url_for("settlements.index"))
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            flash(f"Error recording return: {str(e)}", "danger")

    funds = Fund.query.filter_by(user_id=current_user.id, status="ACTIVE").all()
    funds_data = []
    for f in funds:
        bal = get_fund_balance(f.id, current_user.id)
        if bal["balance_paise"] > 0 or f.id == preselected_fund_id:
            funds_data.append({
                "fund": f,
                "available_paise": bal["balance_paise"],
                "display": f"{f.title} ({f.person.name}) - Available: {format_inr(bal['balance_paise'])}",
            })

    bank_accounts = BankAccount.query.filter_by(user_id=current_user.id, archived_at=None).all()

    return render_template(
        "settlements/return_form.html",
        funds=funds_data,
        bank_accounts=bank_accounts,
        preselected_fund_id=preselected_fund_id,
    )


@settlements_bp.route("/settlements/reimbursement", methods=["GET", "POST"])
@login_required
def reimbursement():
    """Record reimbursement from a person for recoverable personal contributions."""
    preselected_person_id = request.args.get("person_id", type=int)

    if request.method == "POST":
        person_id = int(request.form.get("person_id", 0))
        amount_str = request.form.get("amount", "0")
        notes = request.form.get("notes", "").strip()
        date_str = request.form.get("settlement_at")
        bank_account_id = request.form.get("bank_account_id")
        bank_id = int(bank_account_id) if bank_account_id and bank_account_id.isdigit() else None

        try:
            amount_paise = rupees_to_paise(amount_str)
            settlement_at = (
                datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                if date_str
                else datetime.now(timezone.utc)
            )

            execute_reimbursement(
                user_id=current_user.id,
                person_id=person_id,
                amount_paise=amount_paise,
                notes=notes,
                settlement_at=settlement_at,
                bank_account_id=bank_id,
            )
            flash("Reimbursement recorded and credited to Pocket Money.", "success")
            return redirect(url_for("settlements.index"))
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            flash(f"Error recording reimbursement: {str(e)}", "danger")

    people = Person.query.filter_by(user_id=current_user.id, archived_at=None).all()
    people_data = []
    for p in people:
        receivable = get_outstanding_receivable(current_user.id, p.id)
        people_data.append({
            "person": p,
            "receivable_paise": receivable,
            "display": f"{p.name} - Receivable: {format_inr(receivable)}",
        })

    bank_accounts = BankAccount.query.filter_by(user_id=current_user.id, archived_at=None).all()

    return render_template(
        "settlements/reimbursement_form.html",
        people=people_data,
        bank_accounts=bank_accounts,
        preselected_person_id=preselected_person_id,
    )
