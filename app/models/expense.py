from datetime import datetime, timezone
from app.extensions import db


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    total_amount_paise = db.Column(db.Integer, nullable=False)  # Integer paise > 0
    expense_at = db.Column(db.DateTime(timezone=True), nullable=False)
    merchant = db.Column(db.String(150), nullable=True)  # e.g., D-Mart, Amazon, Local Chemist
    payment_method = db.Column(db.String(50), nullable=True)  # UPI, Card, Cash, Bank Transfer
    reference_id = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    receipt_file_id = db.Column(db.Integer, nullable=True)  # For file attachment
    origin_type = db.Column(db.String(50), default="MANUAL", nullable=False)  # MANUAL, AI_DRAFT, VOICE_NOTE
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
    category = db.relationship("Category", back_populates="expenses")
    allocations = db.relationship("ExpenseAllocation", back_populates="expense", cascade="all, delete-orphan", lazy="dynamic")
    bank_transactions = db.relationship("BankTransaction", foreign_keys="BankTransaction.linked_expense_id", overlaps="linked_expense", lazy="dynamic")

    @property
    def is_fully_personal(self) -> bool:
        """True if all allocations are from Pocket Money."""
        allocs = self.allocations.all()
        return all(a.source_type == "POCKET_MONEY" for a in allocs)

    def __repr__(self) -> str:
        return f"<Expense {self.id}: '{self.title}' ({self.total_amount_paise} paise)>"
