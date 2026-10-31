from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models.receipt import Receipt
from app.models.bank_transaction import BankTransaction
from app.services.balance_service import get_all_people_summaries, get_total_entrusted_balance
from app.services.bank_balance_service import get_all_bank_accounts_summary, get_combined_bank_balances

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

    current_entrusted_paise = get_total_entrusted_balance(current_user.id)
    combined_bank_paise = get_combined_bank_balances(current_user.id)
    people_summaries = get_all_people_summaries(current_user.id)

    # In Phase 2: total spent and pocket money will dynamically expand in Phase 3 & 4
    total_spent_paise = 0
    pocket_money_paise = 0

    recent_receipts = (
        Receipt.query.filter_by(user_id=current_user.id)
        .order_by(Receipt.received_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard/index.html",
        user=current_user,
        total_money_in=total_received_paise,
        total_spent=total_spent_paise,
        current_balance=current_entrusted_paise,
        pocket_money=pocket_money_paise,
        combined_bank_balance=combined_bank_paise,
        people_summaries=people_summaries,
        recent_receipts=recent_receipts,
    )
