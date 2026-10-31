from datetime import datetime, timezone
from app.models.bank_account import BankAccount
from app.models.user import User
from app.services.bank_balance_service import calculate_bank_account_balance, get_combined_bank_balances
from app.extensions import db


def test_create_and_archive_bank_account(client, app, sample_user):
    """Verify creating, editing, and archiving multiple bank accounts."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # 1. Create Kotak Bank account
    resp = client.post(
        "/bank-accounts/new",
        data={
            "account_nickname": "Kotak Savings",
            "bank_name": "Kotak Mahindra Bank",
            "account_type": "SAVINGS",
            "masked_identifier": "**** 4321",
            "opening_balance": "26500.00",
            "opening_balance_date": "2026-10-01T09:00",
            "notes": "Primary account",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Kotak Savings" in resp.data

    # 2. Create SBI account
    resp2 = client.post(
        "/bank-accounts/new",
        data={
            "account_nickname": "SBI Secondary",
            "bank_name": "State Bank of India",
            "account_type": "SAVINGS",
            "masked_identifier": "**** 9876",
            "opening_balance": "12300.00",
            "opening_balance_date": "2026-10-01T09:00",
            "notes": "Secondary account",
        },
        follow_redirects=True,
    )
    assert resp2.status_code == 200
    assert b"SBI Secondary" in resp2.data

    with app.app_context():
        accounts = BankAccount.query.filter_by(user_id=sample_user).all()
        assert len(accounts) == 2
        kotak = BankAccount.query.filter_by(account_nickname="Kotak Savings", user_id=sample_user).first()
        assert kotak.opening_balance_paise == 2650000

        # Check combined balance
        combined = get_combined_bank_balances(sample_user)
        assert combined == 2650000 + 1230000

    # 3. Archive an account
    with app.app_context():
        sbi = BankAccount.query.filter_by(account_nickname="SBI Secondary", user_id=sample_user).first()
        sbi_id = sbi.id

    archive_resp = client.post(f"/bank-accounts/{sbi_id}/archive", follow_redirects=True)
    assert archive_resp.status_code == 200

    with app.app_context():
        sbi_refreshed = db.session.get(BankAccount, sbi_id)
        assert sbi_refreshed.is_archived
        # Active combined balance should now only include Kotak
        active_combined = get_combined_bank_balances(sample_user)
        assert active_combined == 2650000
