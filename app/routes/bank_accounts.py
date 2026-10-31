from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, Optional
from app.extensions import db
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.utils.money import rupees_to_paise
from app.services.bank_balance_service import calculate_bank_account_balance, get_all_bank_accounts_summary, get_combined_bank_balances
from app.services.audit_service import log_audit_event

bank_accounts_bp = Blueprint("bank_accounts", __name__, url_prefix="/bank-accounts")


class BankAccountForm(FlaskForm):
    account_nickname = StringField(
        "Account Nickname",
        validators=[DataRequired(message="Nickname is required."), Length(max=100)],
        render_kw={"placeholder": "e.g. Kotak Primary, SBI Savings, Salary Account"}
    )
    bank_name = StringField(
        "Bank Name",
        validators=[DataRequired(message="Bank name is required."), Length(max=100)],
        render_kw={"placeholder": "e.g. Kotak Mahindra Bank, State Bank of India, HDFC"}
    )
    account_type = SelectField(
        "Account Type",
        choices=[("SAVINGS", "Savings Account"), ("CURRENT", "Current Account"), ("SALARY", "Salary Account"), ("OTHER", "Other")],
        default="SAVINGS"
    )
    masked_identifier = StringField(
        "Masked Identifier (Last 4 digits)",
        validators=[Optional(), Length(max=20)],
        render_kw={"placeholder": "e.g. **** 4321"}
    )
    opening_balance = StringField(
        "Opening Balance (₹)",
        default="0.00",
        validators=[DataRequired(message="Opening balance is required.")],
        render_kw={"placeholder": "0.00", "step": "0.01", "type": "number"}
    )
    opening_balance_date = DateTimeLocalField(
        "Opening Balance As Of",
        default=lambda: datetime.now(timezone.utc),
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Opening date is required.")]
    )
    notes = TextAreaField(
        "Notes",
        validators=[Optional()],
        render_kw={"placeholder": "Optional bank account notes...", "rows": 2}
    )
    submit = SubmitField("Save Account")


@bank_accounts_bp.route("/")
@login_required
def index():
    show_archived = request.args.get("archived", "0") == "1"
    summaries = get_all_bank_accounts_summary(current_user.id, include_archived=show_archived)
    combined_balance = get_combined_bank_balances(current_user.id)
    
    # Recent bank transactions across accounts
    recent_transactions = (
        BankTransaction.query.filter_by(user_id=current_user.id)
        .order_by(BankTransaction.transaction_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "bank_accounts/index.html",
        summaries=summaries,
        combined_balance=combined_balance,
        recent_transactions=recent_transactions,
        show_archived=show_archived
    )


@bank_accounts_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = BankAccountForm()
    if form.validate_on_submit():
        try:
            opening_paise = rupees_to_paise(form.opening_balance.data)
        except Exception:
            flash("Invalid opening balance amount.", "danger")
            return render_template("bank_accounts/form.html", form=form)

        account = BankAccount(
            user_id=current_user.id,
            account_nickname=form.account_nickname.data.strip(),
            bank_name=form.bank_name.data.strip(),
            account_type=form.account_type.data,
            masked_identifier=form.masked_identifier.data.strip() if form.masked_identifier.data else None,
            opening_balance_paise=opening_paise,
            opening_balance_date=form.opening_balance_date.data,
            notes=form.notes.data.strip() if form.notes.data else None,
        )
        db.session.add(account)
        db.session.commit()

        log_audit_event(
            user_id=current_user.id,
            entity_type="BANK_ACCOUNT",
            entity_id=account.id,
            action="CREATE",
            after_snapshot={"nickname": account.account_nickname, "opening_paise": opening_paise}
        )
        db.session.commit()

        flash(f"Bank account '{account.account_nickname}' added.", "success")
        return redirect(url_for("bank_accounts.index"))

    return render_template("bank_accounts/form.html", form=form, title="Add Bank Account")


@bank_accounts_bp.route("/<int:account_id>")
@login_required
def detail(account_id: int):
    account = BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    balance_info = calculate_bank_account_balance(account.id, current_user.id)
    transactions = account.transactions.order_by(BankTransaction.transaction_at.desc()).all()
    return render_template(
        "bank_accounts/detail.html",
        account=account,
        balance_info=balance_info,
        transactions=transactions
    )


@bank_accounts_bp.route("/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
def edit(account_id: int):
    account = BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    form = BankAccountForm(obj=account)

    if form.validate_on_submit():
        account.account_nickname = form.account_nickname.data.strip()
        account.bank_name = form.bank_name.data.strip()
        account.account_type = form.account_type.data
        account.masked_identifier = form.masked_identifier.data.strip() if form.masked_identifier.data else None
        account.notes = form.notes.data.strip() if form.notes.data else None

        log_audit_event(
            user_id=current_user.id,
            entity_type="BANK_ACCOUNT",
            entity_id=account.id,
            action="UPDATE",
            after_snapshot={"nickname": account.account_nickname}
        )
        db.session.commit()

        flash(f"Updated '{account.account_nickname}'.", "success")
        return redirect(url_for("bank_accounts.detail", account_id=account.id))

    return render_template("bank_accounts/form.html", form=form, title=f"Edit {account.account_nickname}", account=account)


@bank_accounts_bp.route("/<int:account_id>/archive", methods=["POST"])
@login_required
def archive(account_id: int):
    account = BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    account.archived_at = datetime.now(timezone.utc)
    log_audit_event(
        user_id=current_user.id,
        entity_type="BANK_ACCOUNT",
        entity_id=account.id,
        action="ARCHIVE"
    )
    db.session.commit()
    flash(f"Archived '{account.account_nickname}'.", "info")
    return redirect(url_for("bank_accounts.index"))
