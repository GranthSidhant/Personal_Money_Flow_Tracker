import pytest
from datetime import datetime, timezone
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.expense import Expense
from app.models.expense_allocation import ExpenseAllocation
from app.services.balance_service import get_fund_balance
from app.services.allocation_service import validate_allocations, record_expense_with_allocations
from app.extensions import db


def test_allocation_sum_must_equal_expense_total(app, sample_user):
    """Allocation sum mismatch must be rejected with ValueError."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        db.session.add(mother)
        db.session.flush()
        fund = Fund(user_id=sample_user, person_id=mother.id, title="Groceries")
        db.session.add(fund)
        db.session.flush()
        receipt = Receipt(user_id=sample_user, fund_id=fund.id, amount_paise=500000, received_at=datetime.now(timezone.utc))
        db.session.add(receipt)
        db.session.commit()
        fund_id = fund.id

        # Total is ₹1,000 (100,000 paise), but allocation is ₹800 (80,000 paise)
        with pytest.raises(ValueError, match="Allocation mismatch"):
            validate_allocations(
                user_id=sample_user,
                total_amount_paise=100000,
                allocations_data=[{
                    "source_type": "FUND",
                    "fund_id": fund_id,
                    "allocated_amount_paise": 80000,
                }]
            )


def test_no_silent_overdraw(app, sample_user):
    """Cannot allocate more than available balance in a fund without explicit shortfall allocation."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        db.session.add(mother)
        db.session.flush()
        # Fund only has ₹1,000 (100,000 paise)
        fund = Fund(user_id=sample_user, person_id=mother.id, title="Groceries")
        db.session.add(fund)
        db.session.flush()
        receipt = Receipt(user_id=sample_user, fund_id=fund.id, amount_paise=100000, received_at=datetime.now(timezone.utc))
        db.session.add(receipt)
        db.session.commit()
        fund_id = fund.id

        # Attempt to spend ₹1,500 exclusively from this fund
        with pytest.raises(ValueError, match="only has .* available"):
            validate_allocations(
                user_id=sample_user,
                total_amount_paise=150000,
                allocations_data=[{
                    "source_type": "FUND",
                    "fund_id": fund_id,
                    "allocated_amount_paise": 150000,
                }]
            )


def test_multi_source_allocation_with_pocket_money_shortfall(app, sample_user):
    """Verify an expense split across multiple funds and pocket money."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        father = Person(user_id=sample_user, name="Father")
        db.session.add_all([mother, father])
        db.session.flush()

        fund_m = Fund(user_id=sample_user, person_id=mother.id, title="Mother Fund")
        fund_f = Fund(user_id=sample_user, person_id=father.id, title="Father Fund")
        db.session.add_all([fund_m, fund_f])
        db.session.flush()
        rec_m = Receipt(user_id=sample_user, fund_id=fund_m.id, amount_paise=200000, received_at=datetime.now(timezone.utc))
        rec_f = Receipt(user_id=sample_user, fund_id=fund_f.id, amount_paise=150000, received_at=datetime.now(timezone.utc))
        db.session.add_all([rec_m, rec_f])
        db.session.commit()
        fm_id, ff_id = fund_m.id, fund_f.id

        # Total ₹3,000: ₹1,500 from Mother, ₹1,000 from Father, ₹500 from Pocket Money (reimbursement expected)
        expense = record_expense_with_allocations(
            user_id=sample_user,
            title="Shared Household Appliances",
            total_amount_paise=300000,
            category_id=None,
            expense_at=datetime.now(timezone.utc),
            allocations_data=[
                {"source_type": "FUND", "fund_id": fm_id, "allocated_amount_paise": 150000},
                {"source_type": "FUND", "fund_id": ff_id, "allocated_amount_paise": 100000},
                {"source_type": "POCKET_MONEY", "fund_id": None, "allocated_amount_paise": 50000, "reimbursement_expected": True},
            ]
        )

        assert expense.id is not None
        assert len(expense.allocations.all()) == 3

        # Check recalculated balances:
        # Mother: 2,000 - 1,500 = 500 (50,000 paise)
        bal_m = get_fund_balance(fm_id, sample_user)
        assert bal_m["spent_total_paise"] == 150000
        assert bal_m["balance_paise"] == 50000

        # Father: 1,500 - 1,000 = 500 (50,000 paise)
        bal_f = get_fund_balance(ff_id, sample_user)
        assert bal_f["spent_total_paise"] == 100000
        assert bal_f["balance_paise"] == 50000
