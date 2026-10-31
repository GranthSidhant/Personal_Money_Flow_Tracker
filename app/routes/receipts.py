from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, RadioField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, Optional
from app.extensions import db
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.utils.money import rupees_to_paise
from app.services.audit_service import log_audit_event

receipts_bp = Blueprint("receipts", __name__, url_prefix="/receipts")


class ReceiptForm(FlaskForm):
    mode = RadioField(
        "Fund Option",
        choices=[("new_fund", "Create a new fund"), ("existing_fund", "Add to an existing fund")],
        default="new_fund"
    )
    person_id = SelectField("Person / Sender", coerce=int, validators=[Optional()])
    new_fund_title = StringField("New Fund Title", validators=[Optional(), Length(max=150)], render_kw={"placeholder": "e.g. October Groceries"})
    existing_fund_id = SelectField("Select Existing Fund", coerce=int, validators=[Optional()])
    
    amount = StringField(
        "Amount Received (₹)",
        validators=[DataRequired(message="Enter the amount received.")],
        render_kw={"placeholder": "e.g. 2000.00", "step": "0.01", "type": "number"}
    )
    received_at = DateTimeLocalField(
        "Date & Time Received",
        default=lambda: datetime.now(timezone.utc),
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Date and time are required.")]
    )
    payment_method = SelectField(
        "Payment Method",
        choices=[("UPI", "UPI"), ("Bank Transfer", "Bank Transfer"), ("Cash", "Cash"), ("Cheque", "Cheque"), ("Other", "Other")],
        default="UPI"
    )
    bank_account_id = SelectField("Deposit to Bank Account (Optional)", coerce=int, validators=[Optional()])
    reference_id = StringField("Reference / UPI Transaction ID", validators=[Optional(), Length(max=100)], render_kw={"placeholder": "e.g. UPI/402918291028"})
    notes = TextAreaField("Notes / Purpose", validators=[Optional()], render_kw={"placeholder": "Optional transaction notes...", "rows": 2})
    submit = SubmitField("Save Receipt")


@receipts_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = ReceiptForm()

    people = Person.query.filter_by(user_id=current_user.id, archived_at=None).order_by(Person.name.asc()).all()
    funds = Fund.query.filter_by(user_id=current_user.id, status="ACTIVE").order_by(Fund.created_at.desc()).all()
    bank_accounts = BankAccount.query.filter_by(user_id=current_user.id, archived_at=None).order_by(BankAccount.account_nickname.asc()).all()

    form.person_id.choices = [(0, "-- Select Person --")] + [(p.id, p.name) for p in people]
    form.existing_fund_id.choices = [(0, "-- Select Fund --")] + [(f.id, f"{f.title} ({f.person.name})") for f in funds]
    form.bank_account_id.choices = [(0, "-- None (Record receipt only) --")] + [(b.id, f"{b.account_nickname} ({b.bank_name})") for b in bank_accounts]

    # Handle query param pre-fills
    preselected_fund_id = request.args.get("fund_id", type=int)
    if request.method == "GET" and preselected_fund_id:
        form.mode.data = "existing_fund"
        form.existing_fund_id.data = preselected_fund_id

    if form.validate_on_submit():
        try:
            amount_paise = rupees_to_paise(form.amount.data)
            if amount_paise <= 0:
                flash("Amount must be greater than zero.", "danger")
                return render_template("receipts/form.html", form=form)
        except Exception:
            flash("Please enter a valid numeric amount.", "danger")
            return render_template("receipts/form.html", form=form)

        target_fund = None

        if form.mode.data == "new_fund":
            person_id = form.person_id.data
            if not person_id or person_id == 0:
                flash("Please select a person for the new fund.", "danger")
                return render_template("receipts/form.html", form=form)

            person = Person.query.filter_by(id=person_id, user_id=current_user.id).first()
            if not person:
                flash("Invalid person selected.", "danger")
                return render_template("receipts/form.html", form=form)

            fund_title = form.new_fund_title.data.strip() if form.new_fund_title.data else f"{person.name}'s Fund"
            target_fund = Fund(
                user_id=current_user.id,
                person_id=person.id,
                title=fund_title,
                purpose=form.notes.data.strip() if form.notes.data else None,
                status="ACTIVE"
            )
            db.session.add(target_fund)
            db.session.flush()

            log_audit_event(
                user_id=current_user.id,
                entity_type="FUND",
                entity_id=target_fund.id,
                action="CREATE",
                after_snapshot={"title": target_fund.title, "person_id": person.id}
            )
        else:
            fund_id = form.existing_fund_id.data
            if not fund_id or fund_id == 0:
                flash("Please select an existing fund.", "danger")
                return render_template("receipts/form.html", form=form)

            target_fund = Fund.query.filter_by(id=fund_id, user_id=current_user.id).first()
            if not target_fund:
                flash("Invalid fund selected.", "danger")
                return render_template("receipts/form.html", form=form)

        # Create Receipt record
        receipt = Receipt(
            user_id=current_user.id,
            fund_id=target_fund.id,
            amount_paise=amount_paise,
            received_at=form.received_at.data,
            payment_method=form.payment_method.data,
            reference_id=form.reference_id.data.strip() if form.reference_id.data else None,
            notes=form.notes.data.strip() if form.notes.data else None
        )
        db.session.add(receipt)
        db.session.flush()

        log_audit_event(
            user_id=current_user.id,
            entity_type="RECEIPT",
            entity_id=receipt.id,
            action="CREATE",
            after_snapshot={"amount_paise": amount_paise, "fund_id": target_fund.id}
        )

        # If user chose to link a bank account credit atomically:
        bank_acc_id = form.bank_account_id.data
        if bank_acc_id and bank_acc_id != 0:
            bank_acc = BankAccount.query.filter_by(id=bank_acc_id, user_id=current_user.id).first()
            if bank_acc:
                bank_tx = BankTransaction(
                    user_id=current_user.id,
                    bank_account_id=bank_acc.id,
                    transaction_type="CREDIT",
                    amount_paise=amount_paise,
                    transaction_at=form.received_at.data,
                    description=f"Credit received for {target_fund.title}",
                    reference_id=form.reference_id.data.strip() if form.reference_id.data else None,
                    person_id=target_fund.person_id,
                    linked_receipt_id=receipt.id,
                    classification_status="CLASSIFIED",
                    notes=form.notes.data.strip() if form.notes.data else None,
                )
                db.session.add(bank_tx)
                db.session.flush()

                log_audit_event(
                    user_id=current_user.id,
                    entity_type="BANK_TRANSACTION",
                    entity_id=bank_tx.id,
                    action="CREDIT_LINKED",
                    after_snapshot={"linked_receipt_id": receipt.id, "amount_paise": amount_paise}
                )

        db.session.commit()
        flash(f"Receipt recorded successfully in fund '{target_fund.title}'.", "success")
        return redirect(url_for("funds.detail", fund_id=target_fund.id))

    return render_template("receipts/form.html", form=form)
