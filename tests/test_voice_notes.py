import io
import os
import pytest
from datetime import datetime, timezone
from werkzeug.datastructures import FileStorage
from app.extensions import db
from app.models.voice_note import VoiceNote
from app.models.location import Location
from app.models.expense import Expense
from app.models.user import User
from app.services.voice_note_service import (
    create_voice_note,
    get_unreviewed_voice_notes,
    attach_voice_note_to_expense,
    delete_voice_note,
)


def test_create_voice_note_with_audio_and_location(app, sample_user):
    """Verify creating a voice note with audio and consented location."""
    with app.app_context():
        # Simulated audio file
        audio_content = b"RIFFfake_webm_audio_bytes"
        file_storage = FileStorage(
            stream=io.BytesIO(audio_content),
            filename="memo.webm",
            content_type="audio/webm",
        )

        vn = create_voice_note(
            user_id=sample_user,
            title="D-Mart Groceries Memo",
            audio_file=file_storage,
            duration_seconds=12.4,
            mime_type="audio/webm",
            latitude=19.0760,
            longitude=72.8777,
            accuracy_meters=15.0,
            user_label="Mumbai Supermarket",
        )

        assert vn.id is not None
        assert vn.status == "UNREVIEWED"
        assert vn.duration_seconds == 12.4
        assert vn.audio_storage_path is not None
        assert vn.location_id is not None

        # Verify location record
        loc = Location.query.get(vn.location_id)
        assert loc.latitude == 19.0760
        assert loc.longitude == 72.8777
        assert loc.user_id == sample_user


def test_text_fallback_note(app, sample_user):
    """Verify manual text memo fallback when mic is unavailable."""
    with app.app_context():
        vn = create_voice_note(
            user_id=sample_user,
            title="Quick Cash Memo",
            text_note="Paid ₹120 for auto rickshaw cash fare",
        )

        assert vn.id is not None
        assert vn.audio_storage_path is None
        assert vn.text_note == "Paid ₹120 for auto rickshaw cash fare"
        assert vn.status == "UNREVIEWED"


def test_authenticated_audio_streaming(client, app, sample_user):
    """Verify audio stream route requires authentication and enforces user isolation."""
    with app.app_context():
        audio_content = b"test_audio_sample_bytes"
        file_storage = FileStorage(
            stream=io.BytesIO(audio_content),
            filename="test_stream.webm",
            content_type="audio/webm",
        )
        vn = create_voice_note(
            user_id=sample_user,
            title="Stream Test",
            audio_file=file_storage,
        )
        vn_id = vn.id

    # 1. Unauthenticated request redirects
    unauth_resp = client.get(f"/voice-notes/{vn_id}/audio")
    assert unauth_resp.status_code == 302

    # 2. Authenticated user can stream
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )
    auth_resp = client.get(f"/voice-notes/{vn_id}/audio")
    assert auth_resp.status_code == 200
    assert auth_resp.data == b"test_audio_sample_bytes"


def test_attach_voice_note_to_expense(app, sample_user):
    """Verify linking a voice note to an expense transitions status to LINKED."""
    with app.app_context():
        exp = Expense(
            user_id=sample_user,
            title="Chemist Medicine",
            total_amount_paise=45000,
            expense_at=datetime.now(timezone.utc),
        )
        vn = create_voice_note(
            user_id=sample_user,
            title="Medicine receipt note",
            text_note="Bought paracetamol and cough syrup",
        )
        db.session.add(exp)
        db.session.commit()
        exp_id, vn_id = exp.id, vn.id

        attach_voice_note_to_expense(sample_user, vn_id, exp_id)

        updated_vn = VoiceNote.query.get(vn_id)
        assert updated_vn.status == "LINKED"
        assert updated_vn.linked_expense_id == exp_id


def test_delete_voice_note_cleans_file(app, sample_user):
    """Verify deleting voice note removes the audio file from disk."""
    with app.app_context():
        file_storage = FileStorage(
            stream=io.BytesIO(b"file_to_be_deleted"),
            filename="delete_me.webm",
            content_type="audio/webm",
        )
        vn = create_voice_note(
            user_id=sample_user,
            title="Temporary Audio",
            audio_file=file_storage,
        )
        vn_id = vn.id
        rel_path = vn.audio_storage_path

        base_dir = app.config.get("UPLOAD_FOLDER") or os.path.join(app.root_path, "..", "uploads")
        full_path = os.path.join(base_dir, rel_path.replace("/", os.sep))
        assert os.path.exists(full_path)

        delete_voice_note(sample_user, vn_id)

        # DB row deleted
        assert VoiceNote.query.get(vn_id) is None
        # File on disk removed
        assert not os.path.exists(full_path)
