import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from werkzeug.utils import secure_filename
from flask import current_app
from app.extensions import db
from app.models.voice_note import VoiceNote
from app.models.location import Location
from app.models.expense import Expense
from app.services.audit_service import log_audit_event


ALLOWED_AUDIO_EXTENSIONS = {"webm", "ogg", "wav", "mp3", "m4a", "mp4"}


def get_audio_upload_dir(user_id: int) -> str:
    """Return secure absolute path to user's audio upload directory."""
    base_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "..", "uploads")
    user_audio_dir = os.path.join(base_dir, "audio", str(user_id))
    os.makedirs(user_audio_dir, exist_ok=True)
    return user_audio_dir


def create_voice_note(
    user_id: int,
    title: str,
    audio_file=None,
    text_note: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    mime_type: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    accuracy_meters: Optional[float] = None,
    user_label: Optional[str] = None,
    captured_at: Optional[datetime] = None,
) -> VoiceNote:
    """
    Save an audio recording or text note fallback, with optional consented location.
    """
    if not title or not title.strip():
        title = f"Voice Note - {datetime.now(timezone.utc).strftime('%b %d, %I:%M %p')}"

    if captured_at is None:
        captured_at = datetime.now(timezone.utc)

    # 1. Handle optional location
    location_id = None
    if latitude is not None and longitude is not None:
        loc = Location(
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            user_label=user_label.strip() if user_label else None,
            captured_at=captured_at,
        )
        db.session.add(loc)
        db.session.flush()
        location_id = loc.id

    # 2. Handle audio file
    storage_path = None
    if audio_file and hasattr(audio_file, "filename") and audio_file.filename:
        upload_dir = get_audio_upload_dir(user_id)
        ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else "webm"
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            ext = "webm"
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        target_path = os.path.join(upload_dir, unique_filename)
        audio_file.save(target_path)
        # Store relative storage key
        storage_path = os.path.join("audio", str(user_id), unique_filename).replace("\\", "/")

    # 3. Create VoiceNote
    voice_note = VoiceNote(
        user_id=user_id,
        audio_storage_path=storage_path,
        title=title.strip(),
        text_note=text_note.strip() if text_note else None,
        duration_seconds=duration_seconds,
        mime_type=mime_type or "audio/webm",
        captured_at=captured_at,
        status="UNREVIEWED",
        location_id=location_id,
    )
    db.session.add(voice_note)
    db.session.flush()

    log_audit_event(
        user_id=user_id,
        entity_type="VOICE_NOTE",
        entity_id=voice_note.id,
        action="CREATE",
        after_snapshot={
            "title": voice_note.title,
            "has_audio": bool(storage_path),
            "has_location": bool(location_id),
            "status": voice_note.status,
        },
    )

    db.session.commit()
    return voice_note


def get_unreviewed_voice_notes(user_id: int) -> List[VoiceNote]:
    """Retrieve all pending unreviewed voice notes for the user."""
    return (
        VoiceNote.query.filter_by(user_id=user_id, status="UNREVIEWED")
        .order_by(VoiceNote.captured_at.desc())
        .all()
    )


def attach_voice_note_to_expense(user_id: int, voice_note_id: int, expense_id: int) -> VoiceNote:
    """Link a voice note to an existing expense and update status to LINKED."""
    vn = VoiceNote.query.filter_by(id=voice_note_id, user_id=user_id).first()
    if not vn:
        raise ValueError("Voice note not found or unauthorized.")

    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        raise ValueError("Expense not found or unauthorized.")

    vn.linked_expense_id = expense.id
    vn.status = "LINKED"

    log_audit_event(
        user_id=user_id,
        entity_type="VOICE_NOTE",
        entity_id=vn.id,
        action="LINK_TO_EXPENSE",
        after_snapshot={"expense_id": expense.id},
    )

    db.session.commit()
    return vn


def delete_voice_note(user_id: int, voice_note_id: int) -> None:
    """Delete a voice note and remove its audio file safely from storage."""
    vn = VoiceNote.query.filter_by(id=voice_note_id, user_id=user_id).first()
    if not vn:
        raise ValueError("Voice note not found.")

    if vn.audio_storage_path:
        base_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "..", "uploads")
        full_path = os.path.join(base_dir, vn.audio_storage_path.replace("/", os.sep))
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except OSError:
                pass

    log_audit_event(
        user_id=user_id,
        entity_type="VOICE_NOTE",
        entity_id=vn.id,
        action="DELETE",
        before_snapshot={"title": vn.title, "status": vn.status},
    )

    db.session.delete(vn)
    db.session.commit()
