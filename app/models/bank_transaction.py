from datetime import datetime, timezone
from app.extensions import db


class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = db.Column(db.String(30), nullable=False)  # CREDIT, DEBIT, TRANSFER_IN, TRANSFER_OUT, REVERSAL
    amount_paise = db.Column(db.Integer, nullable=False)  # Integer paise > 0
    transaction_at = db.Column(db.DateTime(timezone=True), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    reference_id = db.Column(db.String(100), nullable=True)  # Bank ref or UPI ref
    person_id = db.Column(db.Integer, db.ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = db.Column(db.Integer, nullable=True)
    linked_receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_settlement_id = db.Column(db.Integer, nullable=True)
    transfer_group_id = db.Column(db.String(64), nullable=True, index=True)  # Paired internal transfers
    classification_status = db.Column(db.String(30), default="UNCLASSIFIED", nullable=False)  # UNCLASSIFIED, CLASSIFIED, EXCLUDED
    notes = db.Column(db.Text, nullable=True)
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
    bank_account = db.relationship("BankAccount", back_populates="transactions")
    person = db.relationship("Person", back_populates="bank_transactions")
    linked_receipt = db.relationship("Receipt")
    linked_expense = db.relationship("Expense")

    @property
    def is_credit(self) -> bool:
        return self.transaction_type in ("CREDIT", "TRANSFER_IN")

    @property
    def is_debit(self) -> bool:
        return self.transaction_type in ("DEBIT", "TRANSFER_OUT")

    def __repr__(self) -> str:
        return f"<BankTransaction {self.id}: {self.transaction_type} {self.amount_paise} paise in Account {self.bank_account_id}>"
