import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db, csrf
from app.models.voice_note import VoiceNote
from app.models.location import Location
from app.services.audit_service import log_audit_event

sync_bp = Blueprint("sync", __name__)


@sync_bp.route("/sw.js", methods=["GET"])
def service_worker():
    """Serve Service Worker at root scope."""
    response = make_response(send_from_directory(os.path.join(current_app.root_path, "static"), "sw.js"))
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@sync_bp.route("/manifest.json", methods=["GET"])
def manifest():
    """Serve Web App Manifest."""
    response = make_response(send_from_directory(os.path.join(current_app.root_path, "static"), "manifest.json"))
    response.headers["Content-Type"] = "application/manifest+json"
    return response


@sync_bp.route("/offline", methods=["GET"])
def offline():
    """Serve offline shell fallback page."""
    return render_template("offline.html")


@sync_bp.route("/api/sync/drafts", methods=["POST"])
@csrf.exempt
@login_required
def sync_draft():
    """
    Idempotent offline draft synchronization endpoint.
    Accepts pending client drafts and stores them as unreviewed VoiceNotes/Memos.
    CRITICAL SAFETY: Offline drafts are NEVER represented as confirmed ledger transactions.
    Duplicate submissions with the same client_draft_id return existing record without duplication.
    """
    client_draft_id = request.form.get("client_draft_id", "").strip()
    if not client_draft_id:
        return jsonify({"error": "client_draft_id is required for idempotent sync"}), 400

    # 1. Check for existing draft with this idempotency key
    existing_note = VoiceNote.query.filter_by(user_id=current_user.id, client_draft_id=client_draft_id).first()
    if existing_note:
        return jsonify({
            "status": "ALREADY_SYNCED",
            "message": "Draft was already synchronized.",
            "note_id": existing_note.id,
            "client_draft_id": client_draft_id,
        }), 200

    # 2. Extract Fields
    title = request.form.get("title", "").strip() or "Offline Draft Note"
    text_note = request.form.get("text_note", "").strip() or None
    captured_at_str = request.form.get("captured_at")
    
    if captured_at_str:
        try:
            captured_at = datetime.fromisoformat(captured_at_str.replace("Z", "+00:00"))
        except Exception:
            captured_at = datetime.now(timezone.utc)
    else:
        captured_at = datetime.now(timezone.utc)

    # 3. Optional Location
    location_id = None
    lat = request.form.get("latitude")
    lng = request.form.get("longitude")
    if lat and lng:
        try:
            loc = Location(
                user_id=current_user.id,
                latitude=float(lat),
                longitude=float(lng),
                accuracy_meters=float(request.form.get("accuracy", 0)),
                user_label="Offline Capture Location",
            )
            db.session.add(loc)
            db.session.flush()
            location_id = loc.id
        except Exception:
            location_id = None

    # 4. Optional Audio File Storage
    audio_path = None
    duration = None
    audio_file = request.files.get("audio_file")
    if audio_file and audio_file.filename:
        user_audio_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "audio", str(current_user.id))
        os.makedirs(user_audio_dir, exist_ok=True)

        filename = f"{secure_filename(client_draft_id)}.webm"
        file_path = os.path.join(user_audio_dir, filename)
        audio_file.save(file_path)
        audio_path = os.path.join("audio", str(current_user.id), filename)

    # 5. Persist VoiceNote with client_draft_id
    vn = VoiceNote(
        user_id=current_user.id,
        title=title,
        text_note=text_note,
        captured_at=captured_at,
        audio_storage_path=audio_path,
        duration_seconds=duration,
        mime_type="audio/webm" if audio_path else None,
        status="UNREVIEWED",
        location_id=location_id,
        client_draft_id=client_draft_id,
    )
    db.session.add(vn)
    db.session.commit()

    log_audit_event(
        user_id=current_user.id,
        entity_type="VoiceNote",
        entity_id=vn.id,
        action="SYNC_OFFLINE_DRAFT",
        after_snapshot={
            "client_draft_id": client_draft_id,
            "title": vn.title,
            "status": "UNREVIEWED",
        },
    )

    return jsonify({
        "status": "SUCCESS",
        "message": "Draft successfully saved as unreviewed note.",
        "note_id": vn.id,
        "client_draft_id": client_draft_id,
    }), 201
