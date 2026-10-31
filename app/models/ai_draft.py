import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.extensions import db


class AIDraft(db.Model):
    __tablename__ = "ai_drafts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    voice_note_id = db.Column(db.Integer, db.ForeignKey("voice_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = db.Column(db.String(50), default="gemini", nullable=False)
    model = db.Column(db.String(50), default="gemini-1.5-flash", nullable=False)
    status = db.Column(db.String(30), default="PENDING_REVIEW", nullable=False)  # PENDING_REVIEW, APPROVED, REJECTED, FAILED
    extracted_payload_json = db.Column(db.Text, nullable=False)  # JSON string
    confidence_metadata_json = db.Column(db.Text, nullable=True)
    processing_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    user = db.relationship("User", backref="ai_drafts")
    voice_note = db.relationship("VoiceNote", backref=db.backref("ai_drafts", cascade="all, delete-orphan"))

    @property
    def payload(self) -> Dict[str, Any]:
        """Parse payload JSON into python dictionary."""
        try:
            return json.loads(self.extracted_payload_json) if self.extracted_payload_json else {}
        except Exception:
            return {}

    @property
    def is_pending(self) -> bool:
        return self.status == "PENDING_REVIEW"

    @property
    def is_approved(self) -> bool:
        return self.status == "APPROVED"

    def __repr__(self) -> str:
        return f"<AIDraft {self.id}: Note {self.voice_note_id} [{self.status}]>"
