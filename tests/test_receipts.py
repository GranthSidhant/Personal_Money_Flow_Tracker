from datetime import datetime, timezone
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.services.balance_service import get_fund_balance
from app.services.bank_balance_service import calculate_bank_account_balance
from app.extensions import db


def test_receive_money_new_fund_with_bank_credit(client, app, sample_user):
    """Verify receiving money with automatic fund creation and optional bank deposit."""
    with app.app_context():
        father = Person(user_id=sample_user, name="Father")
        account = BankAccount(
            user_id=sample_user,
            account_nickname="Kotak",
            bank_name="Kotak",
            opening_balance_paise=0,
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([father, account])
        db.session.commit()
        father_id, acc_id = father.id, account.id

    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # Submit receipt in new_fund mode with bank deposit
    resp = client.post(
        "/receipts/new",
        data={
            "mode": "new_fund",
            "person_id": father_id,
            "new_fund_title": "Semester Tuition",
            "amount": "25000.50",
            "received_at": "2026-10-15T11:00",
            "payment_method": "UPI",
            "bank_account_id": acc_id,
            "reference_id": "UPI/9988776655",
            "notes": "College fee advance",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        # Verify Fund created
        fund = Fund.query.filter_by(title="Semester Tuition", user_id=sample_user).first()
        assert fund is not None
        assert fund.person_id == father_id

        # Verify Receipt created with exact integer paise
        receipt = Receipt.query.filter_by(fund_id=fund.id, user_id=sample_user).first()
        assert receipt is not None
        # ₹25,000.50 = 2,500,050 paise
        assert receipt.amount_paise == 2500050
        assert receipt.reference_id == "UPI/9988776655"

        # Verify atomic BankTransaction created & linked
        tx = BankTransaction.query.filter_by(linked_receipt_id=receipt.id, user_id=sample_user).first()
        assert tx is not None
        assert tx.amount_paise == 2500050
        assert tx.transaction_type == "CREDIT"
        assert tx.classification_status == "CLASSIFIED"
        assert tx.bank_account_id == acc_id

        # Check bank balance
        bank_bal = calculate_bank_account_balance(acc_id, sample_user)
        assert bank_bal["current_balance_paise"] == 2500050


def test_receive_money_existing_fund(client, app, sample_user):
    """Verify adding a second receipt to an existing fund preserves both receipts."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        db.session.add(mother)
        db.session.flush()
        fund = Fund(user_id=sample_user, person_id=mother.id, title="Household Fund")
        db.session.add(fund)
        db.session.flush()

        r1 = Receipt(user_id=sample_user, fund_id=fund.id, amount_paise=100000, received_at=datetime.now(timezone.utc))
        db.session.add(r1)
        db.session.commit()
        fund_id = fund.id

    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # Add second receipt to existing fund
    resp = client.post(
        "/receipts/new",
        data={
            "mode": "existing_fund",
            "existing_fund_id": fund_id,
            "amount": "1500.00",
            "received_at": "2026-10-16T12:00",
            "payment_method": "Cash",
            "bank_account_id": 0,
            "notes": "Second transfer",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        receipts = Receipt.query.filter_by(fund_id=fund_id, user_id=sample_user).all()
        assert len(receipts) == 2
        # Fund balance: 1,000 + 1,500 = 2,500 (250,000 paise)
        bal = get_fund_balance(fund_id, sample_user)
        assert bal["receipts_total_paise"] == 250000
        assert bal["balance_paise"] == 250000
