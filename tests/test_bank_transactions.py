from datetime import datetime, timezone
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.services.bank_balance_service import calculate_bank_account_balance
from app.services.bank_reconciliation_service import record_internal_transfer, link_transaction_to_receipt
from app.extensions import db


def test_bank_credits_debits_and_balance(client, app, sample_user):
    """Verify manual credits and debits correctly adjust bank account balance."""
    with app.app_context():
        account = BankAccount(
            user_id=sample_user,
            account_nickname="Kotak Primary",
            bank_name="Kotak",
            opening_balance_paise=1000000,  # ₹10,000.00
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add(account)
        db.session.commit()
        acc_id = account.id

    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # 1. Record Credit: +₹2,000.00
    client.post(
        "/bank-transactions/new",
        data={
            "bank_account_id": acc_id,
            "transaction_type": "CREDIT",
            "amount": "2000.00",
            "transaction_at": "2026-10-15T10:30",
            "description": "Credit from Father",
        },
        follow_redirects=True,
    )

    # 2. Record Debit: -₹500.00
    client.post(
        "/bank-transactions/new",
        data={
            "bank_account_id": acc_id,
            "transaction_type": "DEBIT",
            "amount": "500.00",
            "transaction_at": "2026-10-15T14:30",
            "description": "Groceries purchase",
        },
        follow_redirects=True,
    )

    with app.app_context():
        bal = calculate_bank_account_balance(acc_id, sample_user)
        # Expected: 10,000 + 2,000 - 500 = 11,500 rupees = 1,150,000 paise
        assert bal["total_credits_paise"] == 200000
        assert bal["total_debits_paise"] == 50000
        assert bal["current_balance_paise"] == 1150000


def test_own_account_internal_transfer(client, app, sample_user):
    """Verify internal transfers between own accounts create paired entries atomically."""
    with app.app_context():
        acc1 = BankAccount(
            user_id=sample_user,
            account_nickname="Source Account",
            bank_name="Bank A",
            opening_balance_paise=500000,  # ₹5,000
            opening_balance_date=datetime.now(timezone.utc),
        )
        acc2 = BankAccount(
            user_id=sample_user,
            account_nickname="Dest Account",
            bank_name="Bank B",
            opening_balance_paise=100000,  # ₹1,000
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([acc1, acc2])
        db.session.commit()
        id1, id2 = acc1.id, acc2.id

        # Transfer ₹2,000 from Bank A to Bank B
        debit_tx, credit_tx = record_internal_transfer(
            user_id=sample_user,
            source_account_id=id1,
            dest_account_id=id2,
            amount_paise=200000,
            transaction_at=datetime.now(timezone.utc),
            description="Moving savings",
        )
        db.session.commit()

        assert debit_tx.transfer_group_id == credit_tx.transfer_group_id
        assert debit_tx.transaction_type == "TRANSFER_OUT"
        assert credit_tx.transaction_type == "TRANSFER_IN"
        assert debit_tx.amount_paise == 200000
        assert credit_tx.amount_paise == 200000

        # Check calculated balances
        bal1 = calculate_bank_account_balance(id1, sample_user)
        bal2 = calculate_bank_account_balance(id2, sample_user)
        # Source: 5,000 - 2,000 = 3,000 (300,000 paise)
        assert bal1["current_balance_paise"] == 300000
        # Dest: 1,000 + 2,000 = 3,000 (300,000 paise)
        assert bal2["current_balance_paise"] == 300000


def test_link_bank_transaction_to_receipt(client, app, sample_user):
    """Verify linking a credit bank transaction to an incoming receipt without duplication."""
    with app.app_context():
        person = Person(user_id=sample_user, name="Father")
        account = BankAccount(
            user_id=sample_user,
            account_nickname="Kotak",
            bank_name="Kotak",
            opening_balance_paise=0,
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([person, account])
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=person.id, title="College Fund")
        db.session.add(fund)
        db.session.flush()

        receipt = Receipt(
            user_id=sample_user,
            fund_id=fund.id,
            amount_paise=200000,
            received_at=datetime.now(timezone.utc),
        )
        tx = BankTransaction(
            user_id=sample_user,
            bank_account_id=account.id,
            transaction_type="CREDIT",
            amount_paise=200000,
            transaction_at=datetime.now(timezone.utc),
            description="Credit Father",
            classification_status="UNCLASSIFIED",
        )
        db.session.add_all([receipt, tx])
        db.session.commit()

        # Link tx to receipt
        linked_tx = link_transaction_to_receipt(tx.id, receipt.id, sample_user)
        db.session.commit()

        assert linked_tx.linked_receipt_id == receipt.id
        assert linked_tx.classification_status == "CLASSIFIED"
        assert linked_tx.person_id == person.id
