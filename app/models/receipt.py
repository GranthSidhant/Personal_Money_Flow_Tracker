from datetime import datetime, timezone
from app.extensions import db


class Receipt(db.Model):
    __tablename__ = "receipts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fund_id = db.Column(db.Integer, db.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_paise = db.Column(db.Integer, nullable=False)  # Integer paise > 0
    received_at = db.Column(db.DateTime(timezone=True), nullable=False)
    payment_method = db.Column(db.String(50), nullable=True)  # UPI, Bank Transfer, Cash, Other
    reference_id = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    fund = db.relationship("Fund", back_populates="receipts")

    def __repr__(self) -> str:
        return f"<Receipt {self.id}: {self.amount_paise} paise in Fund {self.fund_id}>"
