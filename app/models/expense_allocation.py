from datetime import datetime, timezone
from app.extensions import db


class ExpenseAllocation(db.Model):
    __tablename__ = "expense_allocations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = db.Column(db.String(30), nullable=False)  # FUND or POCKET_MONEY
    fund_id = db.Column(db.Integer, db.ForeignKey("funds.id", ondelete="CASCADE"), nullable=True, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    allocated_amount_paise = db.Column(db.Integer, nullable=False)  # Must be > 0
    reimbursement_expected = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    expense = db.relationship("Expense", back_populates="allocations")
    fund = db.relationship("Fund")
    person = db.relationship("Person")

    def __repr__(self) -> str:
        return f"<ExpenseAllocation {self.id}: Expense {self.expense_id} -> {self.source_type} ({self.allocated_amount_paise} paise)>"
