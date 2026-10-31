from datetime import datetime, timezone
from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # Nullable for system defaults
    name = db.Column(db.String(100), nullable=False)
    category_type = db.Column(db.String(50), default="EXPENSE", nullable=False)  # EXPENSE, INCOME, etc.
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    expenses = db.relationship("Expense", back_populates="category", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Category {self.id}: {self.name}>"


DEFAULT_EXPENSE_CATEGORIES = [
    "Groceries",
    "Food & Drinks",
    "Household",
    "Shopping",
    "Travel & Transport",
    "Education & College",
    "Bills & Utilities",
    "Medical & Health",
    "Entertainment",
    "Subscriptions",
    "Personal",
    "Others",
]


def ensure_default_categories():
    """Ensure standard global/default categories exist in the database."""
    for cat_name in DEFAULT_EXPENSE_CATEGORIES:
        existing = Category.query.filter_by(user_id=None, name=cat_name).first()
        if not existing:
            db.session.add(Category(user_id=None, name=cat_name, category_type="EXPENSE"))
    db.session.commit()
