from datetime import datetime, timezone
from app.extensions import db


class Fund(db.Model):
    __tablename__ = "funds"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    purpose = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="ACTIVE", nullable=False)  # ACTIVE, PARTIALLY_USED, FULLY_ALLOCATED, SETTLED, ARCHIVED
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
    person = db.relationship("Person", back_populates="funds")
    receipts = db.relationship("Receipt", back_populates="fund", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    def __repr__(self) -> str:
        return f"<Fund {self.id}: {self.title} (Person {self.person_id})>"
