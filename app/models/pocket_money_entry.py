from datetime import datetime, timezone
from app.extensions import db


class PocketMoneyEntry(db.Model):
    __tablename__ = "pocket_money_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = db.Column(db.String(30), nullable=False)  # OPENING_BALANCE, INCOME, EXPENSE, FUND_TRANSFER, REIMBURSEMENT, ADJUSTMENT
    amount_paise = db.Column(db.Integer, nullable=False)  # Integer paise > 0
    related_fund_id = db.Column(db.Integer, db.ForeignKey("funds.id", ondelete="SET NULL"), nullable=True, index=True)
    related_expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id", ondelete="CASCADE"), nullable=True, index=True)
    related_settlement_id = db.Column(db.Integer, db.ForeignKey("settlements.id", ondelete="CASCADE"), nullable=True, index=True)
    transfer_group_id = db.Column(db.String(64), nullable=True, index=True)
    description = db.Column(db.String(255), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", backref="pocket_money_entries")
    fund = db.relationship("Fund", backref="pocket_money_entries")
    expense = db.relationship("Expense", backref="pocket_money_entries")
    settlement = db.relationship("Settlement", back_populates="pocket_entries")

    @property
    def is_credit(self) -> bool:
        """Credits increase pocket money."""
        return self.entry_type in ("OPENING_BALANCE", "INCOME", "FUND_TRANSFER", "REIMBURSEMENT")

    @property
    def is_debit(self) -> bool:
        """Debits decrease pocket money."""
        return self.entry_type in ("EXPENSE",)

    def __repr__(self) -> str:
        return f"<PocketMoneyEntry {self.id}: {self.entry_type} {self.amount_paise} paise>"
