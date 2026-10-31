from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.pocket_money_entry import PocketMoneyEntry
from app.services.pocket_money_service import get_pocket_money_balance, add_pocket_money_entry
from app.utils.money import rupees_to_paise

pocket_money_bp = Blueprint("pocket_money", __name__)


@pocket_money_bp.route("/pocket-money")
@login_required
def index():
    """Pocket Money ledger view showing balance, breakdown, and entries."""
    balance_info = get_pocket_money_balance(current_user.id)
    entries = (
        PocketMoneyEntry.query.filter_by(user_id=current_user.id)
        .order_by(PocketMoneyEntry.occurred_at.desc(), PocketMoneyEntry.id.desc())
        .all()
    )
    return render_template(
        "pocket_money/index.html",
        balance_info=balance_info,
        entries=entries,
    )


@pocket_money_bp.route("/pocket-money/add", methods=["GET", "POST"])
@login_required
def add():
    """Add personal opening balance or personal income/allowance to Pocket Money."""
    if request.method == "POST":
        entry_type = request.form.get("entry_type", "INCOME")
        amount_str = request.form.get("amount", "0")
        description = request.form.get("description", "").strip()
        date_str = request.form.get("date")

        try:
            amount_paise = rupees_to_paise(amount_str)
            if amount_paise <= 0:
                flash("Amount must be greater than zero.", "danger")
                return redirect(url_for("pocket_money.add"))

            occurred_at = (
                datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                if date_str
                else datetime.now(timezone.utc)
            )

            if not description:
                description = "Opening Balance" if entry_type == "OPENING_BALANCE" else "Personal Allowance / Income"

            add_pocket_money_entry(
                user_id=current_user.id,
                entry_type=entry_type,
                amount_paise=amount_paise,
                description=description,
                occurred_at=occurred_at,
            )
            db.session.commit()
            flash("Pocket Money updated successfully.", "success")
            return redirect(url_for("pocket_money.index"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding pocket money: {str(e)}", "danger")

    return render_template("pocket_money/form.html")


@pocket_money_bp.route("/pocket-money/adjust", methods=["GET", "POST"])
@login_required
def adjust():
    """Record an auditable manual balance adjustment with required reason."""
    if request.method == "POST":
        direction = request.form.get("direction", "credit")  # credit or debit
        entry_type = "ADJUSTMENT_CREDIT" if direction == "credit" else "ADJUSTMENT_DEBIT"
        amount_str = request.form.get("amount", "0")
        reason = request.form.get("reason", "").strip()

        if not reason:
            flash("A reason is mandatory for manual balance adjustments.", "danger")
            return redirect(url_for("pocket_money.adjust"))

        try:
            amount_paise = rupees_to_paise(amount_str)
            if amount_paise <= 0:
                flash("Adjustment amount must be greater than zero.", "danger")
                return redirect(url_for("pocket_money.adjust"))

            add_pocket_money_entry(
                user_id=current_user.id,
                entry_type=entry_type,
                amount_paise=amount_paise,
                description=f"Adjustment: {reason}",
            )
            db.session.commit()
            flash("Pocket Money adjustment recorded.", "info")
            return redirect(url_for("pocket_money.index"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adjusting pocket money: {str(e)}", "danger")

    return render_template("pocket_money/adjust.html")
