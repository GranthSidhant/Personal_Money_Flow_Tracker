from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, Optional
from app.extensions import db
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.person import Person
from app.models.receipt import Receipt
from app.utils.money import rupees_to_paise
from app.services.bank_reconciliation_service import record_internal_transfer, link_transaction_to_receipt, unlink_transaction_from_receipt
from app.services.audit_service import log_audit_event

bank_transactions_bp = Blueprint("bank_transactions", __name__, url_prefix="/bank-transactions")


class BankTransactionForm(FlaskForm):
    bank_account_id = SelectField("Bank Account", coerce=int, validators=[DataRequired(message="Select an account.")])
    transaction_type = SelectField(
        "Transaction Type",
        choices=[
            ("CREDIT", "Credit (Money In)"),
            ("DEBIT", "Debit (Money Out)"),
            ("TRANSFER", "Internal Transfer (Between Own Accounts)"),
        ],
        default="CREDIT"
    )
    dest_account_id = SelectField("Destination Account (for transfer)", coerce=int, validators=[Optional()])
    amount = StringField(
        "Amount (₹)",
        validators=[DataRequired(message="Enter the amount.")],
        render_kw={"placeholder": "e.g. 2000.00", "step": "0.01", "type": "number"}
    )
    transaction_at = DateTimeLocalField(
        "Transaction Date & Time",
        default=lambda: datetime.now(timezone.utc),
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Date and time are required.")]
    )
    description = StringField(
        "Description / Narration",
        validators=[DataRequired(message="Description is required."), Length(max=255)],
        render_kw={"placeholder": "e.g. UPI/Credit from Father, D-Mart payment"}
    )
    reference_id = StringField("Reference / UPI ID", validators=[Optional(), Length(max=100)], render_kw={"placeholder": "Optional reference ID"})
    person_id = SelectField("Associated Person (Optional)", coerce=int, validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()], render_kw={"placeholder": "Optional notes...", "rows": 2})
    submit = SubmitField("Save Transaction")


@bank_transactions_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = BankTransactionForm()
    accounts = BankAccount.query.filter_by(user_id=current_user.id, archived_at=None).order_by(BankAccount.account_nickname.asc()).all()
    people = Person.query.filter_by(user_id=current_user.id, archived_at=None).order_by(Person.name.asc()).all()

    if not accounts:
        flash("Please create a bank account before entering transactions.", "warning")
        return redirect(url_for("bank_accounts.new"))

    form.bank_account_id.choices = [(a.id, f"{a.account_nickname} ({a.bank_name})") for a in accounts]
    form.dest_account_id.choices = [(0, "-- Select Destination --")] + [(a.id, f"{a.account_nickname} ({a.bank_name})") for a in accounts]
    form.person_id.choices = [(0, "-- None --")] + [(p.id, p.name) for p in people]

    # Preselect account if query param provided
    acc_param = request.args.get("account_id", type=int)
    if request.method == "GET" and acc_param:
        form.bank_account_id.data = acc_param

    if form.validate_on_submit():
        try:
            amount_paise = rupees_to_paise(form.amount.data)
            if amount_paise <= 0:
                flash("Amount must be greater than zero.", "danger")
                return render_template("bank_transactions/form.html", form=form)
        except Exception:
            flash("Invalid numeric amount.", "danger")
            return render_template("bank_transactions/form.html", form=form)

        if form.transaction_type.data == "TRANSFER":
            dest_id = form.dest_account_id.data
            if not dest_id or dest_id == 0 or dest_id == form.bank_account_id.data:
                flash("Please select a different destination account for the internal transfer.", "danger")
                return render_template("bank_transactions/form.html", form=form)

            try:
                record_internal_transfer(
                    user_id=current_user.id,
                    source_account_id=form.bank_account_id.data,
                    dest_account_id=dest_id,
                    amount_paise=amount_paise,
                    transaction_at=form.transaction_at.data,
                    description=form.description.data.strip(),
                    reference_id=form.reference_id.data.strip() if form.reference_id.data else None,
                    notes=form.notes.data.strip() if form.notes.data else None,
                )
                db.session.commit()
                flash("Internal transfer recorded atomically between accounts.", "success")
                return redirect(url_for("bank_accounts.detail", account_id=form.bank_account_id.data))
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("bank_transactions/form.html", form=form)

        # Normal Credit / Debit
        person_id = form.person_id.data if form.person_id.data and form.person_id.data != 0 else None
        tx = BankTransaction(
            user_id=current_user.id,
            bank_account_id=form.bank_account_id.data,
            transaction_type=form.transaction_type.data,
            amount_paise=amount_paise,
            transaction_at=form.transaction_at.data,
            description=form.description.data.strip(),
            reference_id=form.reference_id.data.strip() if form.reference_id.data else None,
            person_id=person_id,
            classification_status="UNCLASSIFIED",
            notes=form.notes.data.strip() if form.notes.data else None,
        )
        db.session.add(tx)
        db.session.commit()

        log_audit_event(
            user_id=current_user.id,
            entity_type="BANK_TRANSACTION",
            entity_id=tx.id,
            action="CREATE",
            after_snapshot={"type": tx.transaction_type, "amount_paise": amount_paise}
        )
        db.session.commit()

        flash("Bank transaction recorded successfully.", "success")
        return redirect(url_for("bank_accounts.detail", account_id=form.bank_account_id.data))

    return render_template("bank_transactions/form.html", form=form)


@bank_transactions_bp.route("/unclassified")
@login_required
def unclassified():
    type_filter = request.args.get("type")
    query = BankTransaction.query.filter_by(
        user_id=current_user.id,
        classification_status="UNCLASSIFIED"
    )
    if type_filter:
        query = query.filter_by(transaction_type=type_filter)
        
    transactions = query.order_by(BankTransaction.transaction_at.desc()).all()
    
    # Available unlinked receipts to offer for linking credits
    unlinked_receipts = (
        Receipt.query.filter_by(user_id=current_user.id)
        .order_by(Receipt.received_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "bank_transactions/unclassified.html",
        transactions=transactions,
        unlinked_receipts=unlinked_receipts,
        current_type=type_filter
    )


@bank_transactions_bp.route("/<int:tx_id>/link-receipt", methods=["POST"])
@login_required
def link_receipt(tx_id: int):
    receipt_id = request.form.get("receipt_id", type=int)
    if not receipt_id:
        flash("No receipt selected to link.", "danger")
        return redirect(url_for("bank_transactions.unclassified"))

    try:
        link_transaction_to_receipt(tx_id, receipt_id, current_user.id)
        db.session.commit()
        flash("Bank transaction successfully linked to receipt.", "success")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("bank_transactions.unclassified"))


@bank_transactions_bp.route("/<int:tx_id>/unlink", methods=["POST"])
@login_required
def unlink(tx_id: int):
    try:
        unlink_transaction_from_receipt(tx_id, current_user.id)
        db.session.commit()
        flash("Bank transaction unlinked and returned to unclassified inbox.", "info")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("bank_transactions.unclassified"))
