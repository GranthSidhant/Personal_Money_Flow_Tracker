from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from app.extensions import db
from app.models.fund import Fund
from app.models.person import Person
from app.services.balance_service import get_fund_balance
from app.services.audit_service import log_audit_event

funds_bp = Blueprint("funds", __name__, url_prefix="/funds")


class FundForm(FlaskForm):
    person_id = SelectField("Person / Source", coerce=int, validators=[DataRequired(message="Select a person.")])
    title = StringField(
        "Fund Title",
        validators=[DataRequired(message="Title is required."), Length(max=150)],
        render_kw={"placeholder": "e.g. October Groceries, College Supplies, Shared Travel"}
    )
    purpose = TextAreaField(
        "Purpose / Description",
        validators=[Optional()],
        render_kw={"placeholder": "Describe what this fund is intended for...", "rows": 3}
    )
    status = SelectField(
        "Status",
        choices=[
            ("ACTIVE", "Active"),
            ("PARTIALLY_USED", "Partially Used"),
            ("FULLY_ALLOCATED", "Fully Allocated"),
            ("SETTLED", "Settled"),
            ("ARCHIVED", "Archived"),
        ],
        default="ACTIVE",
    )
    submit = SubmitField("Save Fund")


@funds_bp.route("/")
@login_required
def index():
    status_filter = request.args.get("status")
    query = Fund.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    funds = query.order_by(Fund.created_at.desc()).all()
    fund_list = []
    for f in funds:
        bal = get_fund_balance(f.id, current_user.id)
        fund_list.append({"fund": f, **bal})

    return render_template("funds/index.html", funds=fund_list, current_status=status_filter)


@funds_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = FundForm()
    people = Person.query.filter_by(user_id=current_user.id, archived_at=None).order_by(Person.name.asc()).all()
    form.person_id.choices = [(p.id, f"{p.name} ({p.relationship})" if p.relationship else p.name) for p in people]

    # Preselect person if passed in query param
    preselected_person = request.args.get("person_id", type=int)
    if request.method == "GET" and preselected_person:
        form.person_id.data = preselected_person

    if not people:
        flash("Please add at least one person before creating a fund.", "warning")
        return redirect(url_for("people.new"))

    if form.validate_on_submit():
        # Validate that selected person belongs to current user
        person = Person.query.filter_by(id=form.person_id.data, user_id=current_user.id).first()
        if not person:
            flash("Invalid person selected.", "danger")
            return redirect(url_for("funds.new"))

        fund = Fund(
            user_id=current_user.id,
            person_id=person.id,
            title=form.title.data.strip(),
            purpose=form.purpose.data.strip() if form.purpose.data else None,
            status=form.status.data,
        )
        db.session.add(fund)
        db.session.commit()

        log_audit_event(
            user_id=current_user.id,
            entity_type="FUND",
            entity_id=fund.id,
            action="CREATE",
            after_snapshot={"title": fund.title, "person_id": fund.person_id}
        )
        db.session.commit()

        flash(f"Fund '{fund.title}' created for {person.name}.", "success")
        return redirect(url_for("funds.detail", fund_id=fund.id))

    return render_template("funds/form.html", form=form, title="Create New Fund")


@funds_bp.route("/<int:fund_id>")
@login_required
def detail(fund_id: int):
    fund = Fund.query.filter_by(id=fund_id, user_id=current_user.id).first_or_404()
    balance_info = get_fund_balance(fund.id, current_user.id)
    receipts = fund.receipts.order_by(db.desc("received_at")).all()
    return render_template("funds/detail.html", fund=fund, balance_info=balance_info, receipts=receipts)


@funds_bp.route("/<int:fund_id>/edit", methods=["GET", "POST"])
@login_required
def edit(fund_id: int):
    fund = Fund.query.filter_by(id=fund_id, user_id=current_user.id).first_or_404()
    form = FundForm(obj=fund)

    people = Person.query.filter_by(user_id=current_user.id).order_by(Person.name.asc()).all()
    form.person_id.choices = [(p.id, p.name) for p in people]

    if form.validate_on_submit():
        fund.person_id = form.person_id.data
        fund.title = form.title.data.strip()
        fund.purpose = form.purpose.data.strip() if form.purpose.data else None
        fund.status = form.status.data

        log_audit_event(
            user_id=current_user.id,
            entity_type="FUND",
            entity_id=fund.id,
            action="UPDATE",
            after_snapshot={"title": fund.title, "status": fund.status}
        )
        db.session.commit()

        flash(f"Updated fund '{fund.title}'.", "success")
        return redirect(url_for("funds.detail", fund_id=fund.id))

    return render_template("funds/form.html", form=form, title=f"Edit Fund '{fund.title}'", fund=fund)
