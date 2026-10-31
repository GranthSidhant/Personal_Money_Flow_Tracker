from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Email
from app.extensions import db
from app.models.person import Person
from app.services.balance_service import get_person_summary, get_all_people_summaries
from app.services.audit_service import log_audit_event

people_bp = Blueprint("people", __name__, url_prefix="/people")


class PersonForm(FlaskForm):
    name = StringField(
        "Full Name",
        validators=[DataRequired(message="Name is required."), Length(max=150)],
        render_kw={"placeholder": "e.g. Mother, Father, Alex, Riya"}
    )
    relationship = StringField(
        "Relationship",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "e.g. Parent, Friend, Colleague, Roommate"}
    )
    phone = StringField(
        "Phone Number",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "e.g. +91 9876543210"}
    )
    email = StringField(
        "Email",
        validators=[Optional(), Email(message="Enter a valid email address.")],
        render_kw={"placeholder": "e.g. alex@example.com"}
    )
    notes = TextAreaField(
        "Notes",
        validators=[Optional()],
        render_kw={"placeholder": "Optional details or reminders...", "rows": 3}
    )
    submit = SubmitField("Save Person")


@people_bp.route("/")
@login_required
def index():
    show_archived = request.args.get("archived", "0") == "1"
    summaries = get_all_people_summaries(current_user.id, include_archived=show_archived)
    return render_template(
        "people/index.html",
        summaries=summaries,
        show_archived=show_archived
    )


@people_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = PersonForm()
    if form.validate_on_submit():
        person = Person(
            user_id=current_user.id,
            name=form.name.data.strip(),
            relationship=form.relationship.data.strip() if form.relationship.data else None,
            phone=form.phone.data.strip() if form.phone.data else None,
            email=form.email.data.strip().lower() if form.email.data else None,
            notes=form.notes.data.strip() if form.notes.data else None,
        )
        db.session.add(person)
        db.session.commit()

        log_audit_event(
            user_id=current_user.id,
            entity_type="PERSON",
            entity_id=person.id,
            action="CREATE",
            after_snapshot={"name": person.name, "relationship": person.relationship}
        )
        db.session.commit()

        flash(f"Added {person.name} successfully.", "success")
        return redirect(url_for("people.index"))

    return render_template("people/form.html", form=form, title="Add New Person")


@people_bp.route("/<int:person_id>")
@login_required
def detail(person_id: int):
    person = Person.query.filter_by(id=person_id, user_id=current_user.id).first_or_404()
    summary = get_person_summary(person.id, current_user.id)
    return render_template("people/detail.html", person=person, summary=summary)


@people_bp.route("/<int:person_id>/edit", methods=["GET", "POST"])
@login_required
def edit(person_id: int):
    person = Person.query.filter_by(id=person_id, user_id=current_user.id).first_or_404()
    form = PersonForm(obj=person)

    if form.validate_on_submit():
        person.name = form.name.data.strip()
        person.relationship = form.relationship.data.strip() if form.relationship.data else None
        person.phone = form.phone.data.strip() if form.phone.data else None
        person.email = form.email.data.strip().lower() if form.email.data else None
        person.notes = form.notes.data.strip() if form.notes.data else None

        log_audit_event(
            user_id=current_user.id,
            entity_type="PERSON",
            entity_id=person.id,
            action="UPDATE",
            after_snapshot={"name": person.name}
        )
        db.session.commit()

        flash(f"Updated {person.name}'s details.", "success")
        return redirect(url_for("people.detail", person_id=person.id))

    return render_template("people/form.html", form=form, title=f"Edit {person.name}", person=person)


@people_bp.route("/<int:person_id>/archive", methods=["POST"])
@login_required
def archive(person_id: int):
    person = Person.query.filter_by(id=person_id, user_id=current_user.id).first_or_404()
    person.archived_at = datetime.now(timezone.utc)
    log_audit_event(
        user_id=current_user.id,
        entity_type="PERSON",
        entity_id=person.id,
        action="ARCHIVE"
    )
    db.session.commit()
    flash(f"Archived {person.name}.", "info")
    return redirect(url_for("people.index"))


@people_bp.route("/<int:person_id>/unarchive", methods=["POST"])
@login_required
def unarchive(person_id: int):
    person = Person.query.filter_by(id=person_id, user_id=current_user.id).first_or_404()
    person.archived_at = None
    log_audit_event(
        user_id=current_user.id,
        entity_type="PERSON",
        entity_id=person.id,
        action="UNARCHIVE"
    )
    db.session.commit()
    flash(f"Restored {person.name} from archive.", "success")
    return redirect(url_for("people.index"))
