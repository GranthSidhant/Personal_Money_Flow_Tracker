from datetime import datetime, timezone
from app.extensions import db


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False)  # PERSON, FUND, RECEIPT, BANK_ACCOUNT, BANK_TRANSACTION
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # CREATE, UPDATE, ARCHIVE, UNARCHIVE, DELETE, LINK, UNLINK
    before_snapshot_json = db.Column(db.Text, nullable=True)
    after_snapshot_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.id}: {self.action} on {self.entity_type} {self.entity_id}>"
