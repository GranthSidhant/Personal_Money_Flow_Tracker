from datetime import datetime, timezone
from app.extensions import db


class VoiceNote(db.Model):
    __tablename__ = "voice_notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    audio_storage_path = db.Column(db.String(255), nullable=True)  # Relative path in secure uploads/
    title = db.Column(db.String(150), nullable=False)
    text_note = db.Column(db.Text, nullable=True)
    transcript = db.Column(db.Text, nullable=True)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=False)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    duration_seconds = db.Column(db.Float, nullable=True)
    mime_type = db.Column(db.String(64), default="audio/webm", nullable=True)
    status = db.Column(db.String(40), default="UNREVIEWED", nullable=False)  # UNREVIEWED, TRANSCRIBED, LINKED, ARCHIVED, REJECTED
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", backref="voice_notes")
    location = db.relationship("Location")
    linked_expense = db.relationship("Expense", backref=db.backref("voice_notes", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<VoiceNote {self.id}: '{self.title}' [{self.status}]>"
