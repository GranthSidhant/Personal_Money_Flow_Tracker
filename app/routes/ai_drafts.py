from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone

from app.models.ai_draft import AIDraft
from app.models.voice_note import VoiceNote
from app.models.person import Person
from app.models.fund import Fund
from app.models.category import Category
from app.services.ai_service import (
    get_ai_status,
    create_ai_draft_from_note,
    approve_ai_draft,
    reject_ai_draft,
)
from app.utils.money import rupees_to_paise, format_inr

ai_drafts_bp = Blueprint("ai_drafts", __name__)


@ai_drafts_bp.route("/ai-inbox", methods=["GET"])
@login_required
def index():
    status_filter = request.args.get("status", "PENDING_REVIEW").strip().upper()
    valid_statuses = ["ALL", "PENDING_REVIEW", "APPROVED", "REJECTED"]
    if status_filter not in valid_statuses:
        status_filter = "PENDING_REVIEW"

    query = AIDraft.query.filter_by(user_id=current_user.id)
    if status_filter != "ALL":
        query = query.filter_by(status=status_filter)

    drafts = query.order_by(AIDraft.created_at.desc()).all()

    counts = {
        "pending": AIDraft.query.filter_by(user_id=current_user.id, status="PENDING_REVIEW").count(),
        "approved": AIDraft.query.filter_by(user_id=current_user.id, status="APPROVED").count(),
        "rejected": AIDraft.query.filter_by(user_id=current_user.id, status="REJECTED").count(),
    }
    counts["all"] = sum(counts.values())

    ai_status = get_ai_status()

    # Also fetch unreviewed voice notes that haven't been processed into AI drafts yet
    unprocessed_notes = VoiceNote.query.filter_by(user_id=current_user.id).filter(
        ~VoiceNote.ai_drafts.any()
    ).order_by(VoiceNote.captured_at.desc()).limit(10).all()

    return render_template(
        "ai_drafts/index.html",
        drafts=drafts,
        status_filter=status_filter,
        counts=counts,
        ai_status=ai_status,
        unprocessed_notes=unprocessed_notes,
    )


@ai_drafts_bp.route("/voice-notes/<int:note_id>/process-ai", methods=["POST"])
@login_required
def process_note(note_id):
    consent = request.form.get("consent_given") == "yes" or request.form.get("consent") == "1"
    include_location = request.form.get("include_location") in ("yes", "1", "on")

    if not consent:
        flash("You must explicitly give consent to process note content through the AI extractor.", "danger")
        return redirect(url_for("voice_notes.index"))

    try:
        draft = create_ai_draft_from_note(
            user_id=current_user.id,
            voice_note_id=note_id,
            include_location=include_location,
            explicit_consent=True,
        )
        flash("AI Draft created successfully. Please review and approve before adding to your ledger.", "success")
        return redirect(url_for("ai_drafts.review", draft_id=draft.id))
    except Exception as e:
        flash(f"Failed to process note: {str(e)}", "danger")
        return redirect(url_for("voice_notes.index"))


@ai_drafts_bp.route("/ai-drafts/<int:draft_id>/review", methods=["GET"])
@login_required
def review(draft_id):
    draft = AIDraft.query.filter_by(id=draft_id, user_id=current_user.id).first_or_404()
    people = Person.query.filter_by(user_id=current_user.id).filter(Person.archived_at.is_(None)).order_by(Person.name.asc()).all()
    funds = Fund.query.filter_by(user_id=current_user.id).filter(Fund.status != "ARCHIVED").order_by(Fund.title.asc()).all()
    categories = Category.query.filter((Category.user_id == current_user.id) | (Category.user_id.is_(None))).order_by(Category.name.asc()).all()

    payload = draft.payload

    return render_template(
        "ai_drafts/review.html",
        draft=draft,
        payload=payload,
        people=people,
        funds=funds,
        categories=categories,
    )


@ai_drafts_bp.route("/ai-drafts/<int:draft_id>/approve", methods=["POST"])
@login_required
def approve(draft_id):
    tx_type = request.form.get("transaction_type", "EXPENSE").strip().upper()
    amount_str = request.form.get("amount", "0").strip()

    try:
        amount_rupees = float(amount_str)
        amount_paise = rupees_to_paise(amount_rupees)
    except ValueError:
        flash("Please enter a valid amount.", "danger")
        return redirect(url_for("ai_drafts.review", draft_id=draft_id))

    approval_data = {
        "transaction_type": tx_type,
        "amount_paise": amount_paise,
        "date": request.form.get("date"),
        "payment_method": request.form.get("payment_method", "Cash"),
        "notes": request.form.get("notes", ""),
        "description": request.form.get("description", ""),
    }

    if tx_type == "RECEIPT":
        person_id_val = request.form.get("person_id")
        approval_data["person_id"] = int(person_id_val) if person_id_val else None
        approval_data["new_person_name"] = request.form.get("new_person_name", "").strip()

        fund_id_val = request.form.get("fund_id")
        approval_data["fund_id"] = int(fund_id_val) if fund_id_val else None
        approval_data["new_fund_name"] = request.form.get("new_fund_name", "").strip()

    elif tx_type == "EXPENSE":
        approval_data["title"] = request.form.get("title", "").strip() or "Approved Voice Expense"
        cat_id_val = request.form.get("category_id")
        approval_data["category_id"] = int(cat_id_val) if cat_id_val else None
        approval_data["merchant"] = request.form.get("merchant", "").strip()
        approval_data["source_type"] = request.form.get("source_type", "POCKET_MONEY")
        fund_id_val = request.form.get("expense_fund_id")
        approval_data["fund_id"] = int(fund_id_val) if (approval_data["source_type"] == "FUND" and fund_id_val) else None
        approval_data["is_recoverable"] = request.form.get("is_recoverable") in ("yes", "1", "true")

    try:
        ok, msg, entity_info = approve_ai_draft(
            user_id=current_user.id,
            draft_id=draft_id,
            approval_data=approval_data,
        )
        flash(msg, "success")
        return redirect(url_for("ai_drafts.index", status="APPROVED"))
    except Exception as e:
        flash(f"Approval error: {str(e)}", "danger")
        return redirect(url_for("ai_drafts.review", draft_id=draft_id))


@ai_drafts_bp.route("/ai-drafts/<int:draft_id>/reject", methods=["POST"])
@login_required
def reject(draft_id):
    reason = request.form.get("reason", "").strip()
    try:
        reject_ai_draft(user_id=current_user.id, draft_id=draft_id, reason=reason)
        flash(f"AI Draft #{draft_id} rejected.", "info")
    except Exception as e:
        flash(f"Error rejecting draft: {str(e)}", "danger")

    return redirect(url_for("ai_drafts.index"))
