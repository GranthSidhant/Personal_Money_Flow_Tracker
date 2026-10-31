import io
import json
import pytest
from app.extensions import db
from app.models.user import User
from app.models.voice_note import VoiceNote
from app.models.location import Location
from app.models.expense import Expense
from app.models.receipt import Receipt


def test_manifest_and_sw_served(client):
    """PWA manifest, service worker, and offline shell are accessible."""
    # 1. Manifest
    r_manifest = client.get("/manifest.json")
    assert r_manifest.status_code == 200
    manifest_data = json.loads(r_manifest.data)
    assert manifest_data["short_name"] == "MoneyFlow"
    assert manifest_data["display"] == "standalone"

    # 2. Service Worker
    r_sw = client.get("/sw.js")
    assert r_sw.status_code == 200
    assert "application/javascript" in r_sw.headers["Content-Type"]
    assert r_sw.headers.get("Service-Worker-Allowed") == "/"

    # 3. Offline fallback page
    r_offline = client.get("/offline")
    assert r_offline.status_code == 200
    assert "currently offline" in r_offline.data.decode("utf-8")


def test_sync_draft_requires_auth(client):
    """Unauthenticated sync requests are redirected or denied."""
    res = client.post("/api/sync/drafts", data={"client_draft_id": "draft_anon_1"})
    # Flask-Login redirects to /auth/login (HTTP 302)
    assert res.status_code == 302


def test_sync_draft_creates_unreviewed_voice_note(app, client, sample_user):
    """Sync creates unreviewed note and never creates automatic ledger transactions."""
    with app.app_context():
        user = User.query.get(sample_user)
        initial_expenses = Expense.query.filter_by(user_id=user.id).count()
        initial_receipts = Receipt.query.filter_by(user_id=user.id).count()

        # Login
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        res = client.post("/api/sync/drafts", data={
            "client_draft_id": "draft_test_101",
            "title": "Offline Grocery Memo",
            "text_note": "Spent ₹800 on groceries offline",
            "captured_at": "2026-10-31T12:00:00Z",
        })

        assert res.status_code == 201
        data = res.get_json()
        assert data["status"] == "SUCCESS"
        assert data["client_draft_id"] == "draft_test_101"

        # Verify DB: voice note created with status UNREVIEWED
        vn = VoiceNote.query.filter_by(user_id=user.id, client_draft_id="draft_test_101").first()
        assert vn is not None
        assert vn.status == "UNREVIEWED"
        assert vn.title == "Offline Grocery Memo"

        # Approval Boundary: offline drafts NEVER write to ledger automatically!
        assert Expense.query.filter_by(user_id=user.id).count() == initial_expenses
        assert Receipt.query.filter_by(user_id=user.id).count() == initial_receipts


def test_sync_draft_idempotency_duplicate_prevention(app, client, sample_user):
    """Duplicate sync requests with same client_draft_id are completely idempotent."""
    with app.app_context():
        user = User.query.get(sample_user)

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        # First sync
        res1 = client.post("/api/sync/drafts", data={
            "client_draft_id": "draft_idempotent_999",
            "title": "Repeated Memo",
            "text_note": "Note content",
        })
        assert res1.status_code == 201
        note_id = res1.get_json()["note_id"]

        # Duplicate sync retry (e.g. network hiccup / browser retry)
        res2 = client.post("/api/sync/drafts", data={
            "client_draft_id": "draft_idempotent_999",
            "title": "Repeated Memo",
            "text_note": "Note content",
        })
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2["status"] == "ALREADY_SYNCED"
        assert data2["note_id"] == note_id

        # Verify only 1 record exists in database
        count = VoiceNote.query.filter_by(user_id=user.id, client_draft_id="draft_idempotent_999").count()
        assert count == 1


def test_sync_draft_with_audio_and_location(app, client, sample_user):
    """Sync handles audio binary upload and coordinates properly."""
    with app.app_context():
        user = User.query.get(sample_user)

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        fake_audio = (io.BytesIO(b"RIFFofflineaudiodata"), "recording.webm")

        res = client.post(
            "/api/sync/drafts",
            data={
                "client_draft_id": "draft_audio_loc_55",
                "title": "Audio Note Offline",
                "text_note": "Spoken memo",
                "audio_file": fake_audio,
                "latitude": "12.9716",
                "longitude": "77.5946",
                "accuracy": "15.0",
            },
            content_type="multipart/form-data",
        )

        assert res.status_code == 201
        vn = VoiceNote.query.filter_by(user_id=user.id, client_draft_id="draft_audio_loc_55").first()
        assert vn is not None
        assert vn.audio_storage_path is not None
        assert vn.location_id is not None

        loc = Location.query.get(vn.location_id)
        assert loc.latitude == pytest.approx(12.9716)
        assert loc.longitude == pytest.approx(77.5946)
