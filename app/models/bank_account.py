from datetime import datetime, timezone
from app.extensions import db


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_nickname = db.Column(db.String(100), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50), default="SAVINGS", nullable=False)  # SAVINGS, CURRENT, OTHER
    masked_identifier = db.Column(db.String(20), nullable=True)  # e.g., "**** 4321"
    opening_balance_paise = db.Column(db.Integer, default=0, nullable=False)
    opening_balance_date = db.Column(db.DateTime(timezone=True), nullable=False)
    currency = db.Column(db.String(10), default="INR", nullable=False)
    notes = db.Column(db.Text, nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
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
    transactions = db.relationship("BankTransaction", back_populates="bank_account", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def __repr__(self) -> str:
        return f"<BankAccount {self.id}: {self.account_nickname} ({self.bank_name})>"
