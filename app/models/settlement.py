from datetime import datetime, timezone
from app.extensions import db


class Settlement(db.Model):
    __tablename__ = "settlements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    fund_id = db.Column(db.Integer, db.ForeignKey("funds.id", ondelete="SET NULL"), nullable=True, index=True)
    related_expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True)
    settlement_type = db.Column(db.String(30), nullable=False)  # TRANSFER_TO_POCKET, RETURN_TO_PROVIDER, REIMBURSEMENT
    amount_paise = db.Column(db.Integer, nullable=False)  # strictly positive paise > 0
    settlement_at = db.Column(db.DateTime(timezone=True), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", backref="settlements")
    person = db.relationship("Person", backref="settlements")
    fund = db.relationship("Fund", backref="settlements")
    related_expense = db.relationship("Expense", backref="settlements")
    pocket_entries = db.relationship("PocketMoneyEntry", back_populates="settlement", cascade="all, delete-orphan")
    bank_transactions = db.relationship("BankTransaction", foreign_keys="BankTransaction.linked_settlement_id", back_populates="linked_settlement")

    def __repr__(self) -> str:
        return f"<Settlement {self.id}: {self.settlement_type} {self.amount_paise} paise for Person {self.person_id}>"
