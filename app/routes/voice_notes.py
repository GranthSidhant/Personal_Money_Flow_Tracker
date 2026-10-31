import os
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.voice_note import VoiceNote
from app.models.expense import Expense
from app.services.voice_note_service import (
    create_voice_note,
    get_unreviewed_voice_notes,
    attach_voice_note_to_expense,
    delete_voice_note,
)

voice_notes_bp = Blueprint("voice_notes", __name__)


@voice_notes_bp.route("/voice-notes")
@login_required
def index():
    """Voice Notes inbox and recorder view."""
    filter_status = request.args.get("status", "UNREVIEWED").upper()
    
    query = VoiceNote.query.filter_by(user_id=current_user.id)
    if filter_status != "ALL":
        query = query.filter(VoiceNote.status == filter_status)

    notes = query.order_by(VoiceNote.captured_at.desc()).all()
    unreviewed_count = VoiceNote.query.filter_by(user_id=current_user.id, status="UNREVIEWED").count()
    recent_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_at.desc()).limit(15).all()

    return render_template(
        "voice_notes/index.html",
        notes=notes,
        unreviewed_count=unreviewed_count,
        filter_status=filter_status,
        recent_expenses=recent_expenses,
    )


@voice_notes_bp.route("/voice-notes/record", methods=["POST"])
@login_required
def record():
    """Upload voice note audio or save text note with optional location."""
    title = request.form.get("title", "")
    text_note = request.form.get("text_note", "")
    audio_file = request.files.get("audio_file")
    duration_str = request.form.get("duration", "0")
    lat_str = request.form.get("latitude")
    lng_str = request.form.get("longitude")
    acc_str = request.form.get("accuracy")
    user_label = request.form.get("user_label")
    captured_str = request.form.get("captured_at")

    try:
        duration = float(duration_str) if duration_str else None
        latitude = float(lat_str) if lat_str else None
        longitude = float(lng_str) if lng_str else None
        accuracy = float(acc_str) if acc_str else None
        captured_at = (
            datetime.fromisoformat(captured_str).replace(tzinfo=timezone.utc)
            if captured_str
            else datetime.now(timezone.utc)
        )

        mime_type = audio_file.mimetype if audio_file else "audio/webm"

        vn = create_voice_note(
            user_id=current_user.id,
            title=title,
            audio_file=audio_file,
            text_note=text_note,
            duration_seconds=duration,
            mime_type=mime_type,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy,
            user_label=user_label,
            captured_at=captured_at,
        )

        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({
                "success": True,
                "id": vn.id,
                "title": vn.title,
                "message": "Voice note saved successfully.",
            })

        flash("Voice note captured and saved to inbox.", "success")
        return redirect(url_for("voice_notes.index"))
    except Exception as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Error saving voice note: {str(e)}", "danger")
        return redirect(url_for("voice_notes.index"))


@voice_notes_bp.route("/voice-notes/<int:note_id>/audio")
@login_required
def stream_audio(note_id: int):
    """Secure authenticated audio download/streaming route."""
    vn = VoiceNote.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    if not vn.audio_storage_path:
        return "Audio not found", 404

    base_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "..", "uploads")
    full_path = os.path.join(base_dir, vn.audio_storage_path.replace("/", os.sep))

    if not os.path.exists(full_path):
        return "Audio file missing from server", 404

    return send_file(
        full_path,
        mimetype=vn.mime_type or "audio/webm",
        as_attachment=False,
    )


@voice_notes_bp.route("/voice-notes/<int:note_id>/link", methods=["POST"])
@login_required
def link_expense(note_id: int):
    """Link a voice note to an existing expense."""
    expense_id = request.form.get("expense_id", type=int)
    if not expense_id:
        flash("Please select an expense to link.", "warning")
        return redirect(url_for("voice_notes.index"))

    try:
        attach_voice_note_to_expense(current_user.id, note_id, expense_id)
        flash("Voice note linked to expense successfully.", "success")
    except Exception as e:
        flash(f"Error linking voice note: {str(e)}", "danger")

    return redirect(url_for("voice_notes.index"))


@voice_notes_bp.route("/voice-notes/<int:note_id>/archive", methods=["POST"])
@login_required
def archive(note_id: int):
    """Archive a voice note."""
    vn = VoiceNote.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    vn.status = "ARCHIVED"
    db.session.commit()
    flash(f"Voice note '{vn.title}' archived.", "info")
    return redirect(url_for("voice_notes.index"))


@voice_notes_bp.route("/voice-notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete(note_id: int):
    """Delete a voice note and remove audio file."""
    try:
        delete_voice_note(current_user.id, note_id)
        flash("Voice note deleted.", "info")
    except Exception as e:
        flash(f"Error deleting voice note: {str(e)}", "danger")
    return redirect(url_for("voice_notes.index"))
