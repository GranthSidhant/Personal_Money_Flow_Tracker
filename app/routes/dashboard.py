from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models.receipt import Receipt
from app.models.expense import Expense
from app.models.bank_transaction import BankTransaction
from app.services.balance_service import get_all_people_summaries, get_total_entrusted_balance
from app.services.bank_balance_service import get_all_bank_accounts_summary, get_combined_bank_balances
from app.services.allocation_service import get_spending_by_category
from app.services.pocket_money_service import get_pocket_money_balance

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def index():
    # Dynamic calculations for Dashboard metrics
    total_received_paise = (
        db.session.query(func.coalesce(func.sum(Receipt.amount_paise), 0))
        .filter(Receipt.user_id == current_user.id)
        .scalar()
    )

    total_spent_paise = (
        db.session.query(func.coalesce(func.sum(Expense.total_amount_paise), 0))
        .filter(Expense.user_id == current_user.id)
        .scalar()
    )

    current_entrusted_paise = get_total_entrusted_balance(current_user.id)
    combined_bank_paise = get_combined_bank_balances(current_user.id)
    people_summaries = get_all_people_summaries(current_user.id)
    category_breakdown = get_spending_by_category(current_user.id)

    pocket_money_info = get_pocket_money_balance(current_user.id)
    pocket_money_paise = pocket_money_info["current_balance_paise"]

    # Recent activity items for Dashboard
    recent_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_at.desc()).limit(3).all()
    recent_receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(Receipt.received_at.desc()).limit(3).all()

    recent_activity = []
    for exp in recent_expenses:
        linked_sources = [a.fund.person.name if a.fund and a.fund.person else "Pocket Money" for a in exp.allocations]
        recent_activity.append({
            "title": f"{exp.title} ({', '.join(set(linked_sources))})",
            "date": exp.expense_at,
            "type": "EXPENSE",
            "amount_paise": exp.total_amount_paise,
        })
    for rec in recent_receipts:
        recent_activity.append({
            "title": f"Received from {rec.fund.person.name}",
            "date": rec.received_at,
            "type": "RECEIPT",
            "amount_paise": rec.amount_paise,
        })
    recent_activity.sort(key=lambda x: x["date"], reverse=True)

    return render_template(
        "dashboard/index.html",
        user=current_user,
        total_money_in=total_received_paise,
        total_spent=total_spent_paise,
        current_balance=current_entrusted_paise,
        pocket_money=pocket_money_paise,
        combined_bank_balance=combined_bank_paise,
        people_summaries=people_summaries,
        category_breakdown=category_breakdown,
        recent_activity=recent_activity[:4],
    )
