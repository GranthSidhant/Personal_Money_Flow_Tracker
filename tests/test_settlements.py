import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.settlement import Settlement
from app.models.pocket_money_entry import PocketMoneyEntry
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.services.balance_service import get_fund_balance
from app.services.pocket_money_service import get_pocket_money_balance
from app.services.allocation_service import record_expense_with_allocations
from app.services.settlement_service import (
    execute_transfer_to_pocket,
    execute_return_to_provider,
    execute_reimbursement,
    get_outstanding_receivable,
)


def test_transfer_to_pocket_atomic(app, sample_user):
    """
    Partial transfer reduces the fund and increases Pocket Money by the same amount.
    Both ledger sides are committed atomically.
    Internal transfer is not counted as new income.
    """
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        db.session.add(mother)
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=mother.id, title="Trip Advance")
        db.session.add(fund)
        db.session.flush()

        receipt = Receipt(
            user_id=sample_user,
            fund_id=fund.id,
            amount_paise=300000,  # ₹3,000 received
            received_at=datetime.now(timezone.utc),
        )
        db.session.add(receipt)
        db.session.commit()
        fund_id = fund.id

        # 1. Verify initial state
        initial_fund_bal = get_fund_balance(fund_id, sample_user)
        assert initial_fund_bal["balance_paise"] == 300000

        initial_pocket = get_pocket_money_balance(sample_user)
        assert initial_pocket["current_balance_paise"] == 0

        # 2. Transfer ₹1,000 from fund to Pocket Money
        settlement = execute_transfer_to_pocket(
            user_id=sample_user,
            fund_id=fund_id,
            amount_paise=100000,
            notes="Permission given to keep remaining trip allowance",
        )

        assert settlement.id is not None
        assert settlement.settlement_type == "TRANSFER_TO_POCKET"
        assert settlement.amount_paise == 100000

        # 3. Check updated fund balance: 3,000 - 1,000 = 2,000 (200,000 paise)
        fund_bal_after = get_fund_balance(fund_id, sample_user)
        assert fund_bal_after["transferred_to_pocket_paise"] == 100000
        assert fund_bal_after["balance_paise"] == 200000

        # 4. Check Pocket Money balance: increases by ₹1,000
        pocket_after = get_pocket_money_balance(sample_user)
        assert pocket_after["current_balance_paise"] == 100000
        assert pocket_after["transfers_from_funds_paise"] == 100000
        assert pocket_after["income_total_paise"] == 0  # NOT counted as external income


def test_transfer_exceeding_fund_balance_rejected(app, sample_user):
    """Cannot transfer more than available entrusted balance."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        db.session.add(mother)
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=mother.id, title="Small Fund")
        db.session.add(fund)
        db.session.flush()

        receipt = Receipt(
            user_id=sample_user,
            fund_id=fund.id,
            amount_paise=50000,  # ₹500
            received_at=datetime.now(timezone.utc),
        )
        db.session.add(receipt)
        db.session.commit()
        fund_id = fund.id

        with pytest.raises(ValueError, match="exceeds available fund balance"):
            execute_transfer_to_pocket(
                user_id=sample_user,
                fund_id=fund_id,
                amount_paise=60000,  # ₹600 (exceeds ₹500)
            )


def test_return_unused_money_with_bank_debit(app, sample_user):
    """Return unused money reduces fund balance and creates linked BankTransaction DEBIT."""
    with app.app_context():
        brother = Person(user_id=sample_user, name="Brother")
        acc = BankAccount(
            user_id=sample_user,
            account_nickname="Kotak",
            bank_name="Kotak",
            opening_balance_paise=1000000,  # ₹10,000
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([brother, acc])
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=brother.id, title="Laptop Accessories")
        db.session.add(fund)
        db.session.flush()

        receipt = Receipt(
            user_id=sample_user,
            fund_id=fund.id,
            amount_paise=200000,  # ₹2,000 received
            received_at=datetime.now(timezone.utc),
        )
        db.session.add(receipt)
        db.session.commit()
        fund_id, acc_id = fund.id, acc.id

        # Return ₹800 to Brother via Kotak bank account
        settlement = execute_return_to_provider(
            user_id=sample_user,
            fund_id=fund_id,
            amount_paise=80000,
            notes="Returned remaining unspent amount via UPI",
            bank_account_id=acc_id,
        )

        assert settlement.settlement_type == "RETURN_TO_PROVIDER"
        assert settlement.amount_paise == 80000

        # Check fund balance: 2,000 - 800 = 1,200 (120,000 paise)
        fund_bal = get_fund_balance(fund_id, sample_user)
        assert fund_bal["returned_paise"] == 80000
        assert fund_bal["balance_paise"] == 120000

        # Check linked bank debit
        bank_tx = BankTransaction.query.filter_by(linked_settlement_id=settlement.id).first()
        assert bank_tx is not None
        assert bank_tx.transaction_type == "DEBIT"
        assert bank_tx.amount_paise == 80000


def test_partial_reimbursement_flow(app, sample_user):
    """Test recoverable personal contribution followed by partial reimbursement."""
    with app.app_context():
        friend = Person(user_id=sample_user, name="Friend")
        acc = BankAccount(
            user_id=sample_user,
            account_nickname="HDFC",
            bank_name="HDFC",
            opening_balance_paise=500000,
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([friend, acc])
        db.session.commit()
        friend_id, acc_id = friend.id, acc.id

        # User paid ₹1,200 (120,000 paise) from Pocket Money with reimbursement expected for Friend
        expense = record_expense_with_allocations(
            user_id=sample_user,
            title="Concert Tickets",
            total_amount_paise=120000,
            category_id=None,
            expense_at=datetime.now(timezone.utc),
            allocations_data=[{
                "source_type": "POCKET_MONEY",
                "fund_id": None,
                "person_id": friend_id,
                "allocated_amount_paise": 120000,
                "reimbursement_expected": True,
            }]
        )
        db.session.commit()

        # 1. Check outstanding receivable: ₹1,200
        receivable = get_outstanding_receivable(sample_user, friend_id)
        assert receivable == 120000

        # 2. Friend partially reimburses ₹700 (70,000 paise) into HDFC account
        settlement = execute_reimbursement(
            user_id=sample_user,
            person_id=friend_id,
            amount_paise=70000,
            notes="Partial payback via UPI",
            bank_account_id=acc_id,
        )

        assert settlement.settlement_type == "REIMBURSEMENT"
        assert settlement.amount_paise == 70000

        # 3. Check remaining receivable: 1,200 - 700 = 500 (50,000 paise)
        remaining_rec = get_outstanding_receivable(sample_user, friend_id)
        assert remaining_rec == 50000

        # 4. Pocket Money balance increases by ₹700
        pocket = get_pocket_money_balance(sample_user)
        assert pocket["reimbursements_received_paise"] == 70000

        # 5. Excess reimbursement must be rejected
        with pytest.raises(ValueError, match="exceeds outstanding receivable"):
            execute_reimbursement(
                user_id=sample_user,
                person_id=friend_id,
                amount_paise=60000,  # ₹600 when only ₹500 is outstanding
            )
