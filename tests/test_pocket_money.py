import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models.pocket_money_entry import PocketMoneyEntry
from app.services.pocket_money_service import get_pocket_money_balance, add_pocket_money_entry
from app.services.allocation_service import record_expense_with_allocations


def test_pocket_money_opening_and_income(app, sample_user):
    """Verify adding opening balance and income increases pocket money balance."""
    with app.app_context():
        # 1. Opening balance ₹5,000 (500,000 paise)
        add_pocket_money_entry(
            user_id=sample_user,
            entry_type="OPENING_BALANCE",
            amount_paise=500000,
            description="Initial cash in wallet",
        )
        # 2. Monthly allowance ₹2,500 (250,000 paise)
        add_pocket_money_entry(
            user_id=sample_user,
            entry_type="INCOME",
            amount_paise=250000,
            description="Monthly stipend",
        )
        db.session.commit()

        bal = get_pocket_money_balance(sample_user)
        assert bal["current_balance_paise"] == 750000
        assert bal["opening_balance_paise"] == 500000
        assert bal["income_total_paise"] == 250000


def test_pocket_money_expenses_deduct_properly(app, sample_user):
    """Recording an expense funded by Pocket Money creates an expense entry and deducts balance."""
    with app.app_context():
        add_pocket_money_entry(
            user_id=sample_user,
            entry_type="OPENING_BALANCE",
            amount_paise=500000,
            description="Wallet funds",
        )
        db.session.commit()

        # Spend ₹1,500 from Pocket Money
        record_expense_with_allocations(
            user_id=sample_user,
            title="Book Purchase",
            total_amount_paise=150000,
            category_id=None,
            expense_at=datetime.now(timezone.utc),
            allocations_data=[{
                "source_type": "POCKET_MONEY",
                "fund_id": None,
                "allocated_amount_paise": 150000,
                "reimbursement_expected": False,
            }]
        )
        db.session.commit()

        bal = get_pocket_money_balance(sample_user)
        assert bal["expenses_total_paise"] == 150000
        assert bal["current_balance_paise"] == 350000  # 5,000 - 1,500 = 3,500


def test_manual_adjustment_flow(client, app, sample_user):
    """Test web form adjustment with audit reason."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # 1. Add pocket money
    client.post(
        "/pocket-money/add",
        data={
            "entry_type": "INCOME",
            "amount": "1000.00",
            "description": "Salary advance",
        },
        follow_redirects=True,
    )

    # 2. Adjust with debit of ₹150
    adj_resp = client.post(
        "/pocket-money/adjust",
        data={
            "direction": "debit",
            "amount": "150.00",
            "reason": "Lost ₹150 cash from pocket",
        },
        follow_redirects=True,
    )
    assert adj_resp.status_code == 200

    with app.app_context():
        bal = get_pocket_money_balance(sample_user)
        assert bal["current_balance_paise"] == 85000  # ₹850.00
