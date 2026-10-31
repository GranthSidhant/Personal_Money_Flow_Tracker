from flask import Blueprint, render_template
from flask_login import login_required, current_user

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def index():
    return render_template(
        "dashboard/index.html",
        user=current_user,
        # Placeholder baseline metrics for initial UI verification
        total_money_in=0,
        total_spent=0,
        current_balance=0,
        pocket_money=0,
        recent_transactions=[],
        funds_summary=[]
    )
