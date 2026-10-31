from datetime import datetime, timezone
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.expense import Expense
from app.models.category import Category
from app.services.balance_service import get_fund_balance
from app.services.bank_balance_service import calculate_bank_account_balance
from app.services.allocation_service import get_spending_by_category
from app.extensions import db


def test_record_expense_with_bank_debit(client, app, sample_user):
    """Verify recording an expense deducts from fund and creates linked bank debit."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        cat = Category(name="Groceries", user_id=None)
        acc = BankAccount(
            user_id=sample_user,
            account_nickname="Kotak",
            bank_name="Kotak",
            opening_balance_paise=500000,  # ₹5,000 in bank
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([mother, cat, acc])
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=mother.id, title="Mother Groceries")
        db.session.add(fund)
        db.session.flush()
        rec = Receipt(user_id=sample_user, fund_id=fund.id, amount_paise=300000, received_at=datetime.now(timezone.utc))  # ₹3,000 in fund
        db.session.add(rec)
        db.session.commit()
        fund_id, cat_id, acc_id = fund.id, cat.id, acc.id

    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # Post an expense of ₹1,000 funded by Mother Groceries, paid via Kotak
    resp = client.post(
        "/expenses/new",
        data={
            "title": "Weekly Vegetables",
            "amount": "1000.00",
            "category_id": cat_id,
            "funding_mode": "single_fund",
            "fund_id": fund_id,
            "payment_account_id": acc_id,
            "merchant": "D-Mart",
            "description": "Fresh produce",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        # Verify expense recorded
        expense = Expense.query.filter_by(title="Weekly Vegetables", user_id=sample_user).first()
        assert expense is not None
        assert expense.total_amount_paise == 100000

        # Check Fund balance: 3,000 - 1,000 = 2,000 (200,000 paise)
        fund_bal = get_fund_balance(fund_id, sample_user)
        assert fund_bal["spent_total_paise"] == 100000
        assert fund_bal["balance_paise"] == 200000

        # Check Bank balance: 5,000 - 1,000 = 4,000 (400,000 paise)
        bank_bal = calculate_bank_account_balance(acc_id, sample_user)
        assert bank_bal["current_balance_paise"] == 400000

        # Verify linked BankTransaction
        tx = BankTransaction.query.filter_by(linked_expense_id=expense.id, user_id=sample_user).first()
        assert tx is not None
        assert tx.transaction_type == "DEBIT"
        assert tx.amount_paise == 100000


def test_personal_expense_and_deletion_reversal(client, app, sample_user):
    """Verify personal-only expense and that deleting an expense restores fund balance."""
    with app.app_context():
        friend = Person(user_id=sample_user, name="Friend")
        db.session.add(friend)
        db.session.flush()
        fund = Fund(user_id=sample_user, person_id=friend.id, title="Trip Fund")
        db.session.add(fund)
        db.session.flush()
        rec = Receipt(user_id=sample_user, fund_id=fund.id, amount_paise=100000, received_at=datetime.now(timezone.utc))
        db.session.add(rec)
        db.session.commit()
        fund_id = fund.id

    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # 1. Record personal expense funded by Pocket Money
    resp_personal = client.post(
        "/expenses/new",
        data={
            "title": "Movie Ticket",
            "amount": "450.00",
            "funding_mode": "pocket_money",
            "reimbursement_expected": "0",
        },
        follow_redirects=True,
    )
    assert resp_personal.status_code == 200

    with app.app_context():
        movie_exp = Expense.query.filter_by(title="Movie Ticket", user_id=sample_user).first()
        assert movie_exp.is_fully_personal

    # 2. Record fund expense of ₹600 from Trip Fund
    client.post(
        "/expenses/new",
        data={
            "title": "Bus Tickets",
            "amount": "600.00",
            "funding_mode": "single_fund",
            "fund_id": fund_id,
        },
        follow_redirects=True,
    )

    with app.app_context():
        bal = get_fund_balance(fund_id, sample_user)
        assert bal["balance_paise"] == 40000  # 1,000 - 600 = 400 (40,000 paise)
        bus_exp = Expense.query.filter_by(title="Bus Tickets", user_id=sample_user).first()
        bus_id = bus_exp.id

    # 3. Delete the bus expense
    del_resp = client.post(f"/expenses/{bus_id}/delete", follow_redirects=True)
    assert del_resp.status_code == 200

    # 4. Verify fund balance is restored to full ₹1,000
    with app.app_context():
        restored_bal = get_fund_balance(fund_id, sample_user)
        assert restored_bal["spent_total_paise"] == 0
        assert restored_bal["balance_paise"] == 100000
