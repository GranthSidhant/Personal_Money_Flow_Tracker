from datetime import datetime, timezone
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.services.balance_service import get_fund_balance, get_person_summary
from app.extensions import db


def test_fund_creation_and_independent_balances(client, app, sample_user):
    """Verify that multiple funds remain independent and calculate balances correctly."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother", relationship="Parent")
        db.session.add(mother)
        db.session.commit()
        mother_id = mother.id

    # 1. Create Fund A: "October Groceries"
    resp_fund1 = client.post(
        "/funds/new",
        data={
            "person_id": mother_id,
            "title": "October Groceries",
            "purpose": "Monthly groceries",
            "status": "ACTIVE",
        },
        follow_redirects=True,
    )
    assert resp_fund1.status_code == 200

    # 2. Create Fund B: "Home Repair"
    resp_fund2 = client.post(
        "/funds/new",
        data={
            "person_id": mother_id,
            "title": "Home Repair",
            "purpose": "Plumbing and painting",
            "status": "ACTIVE",
        },
        follow_redirects=True,
    )
    assert resp_fund2.status_code == 200

    with app.app_context():
        funds = Fund.query.filter_by(person_id=mother_id, user_id=sample_user).all()
        assert len(funds) == 2
        f1 = [f for f in funds if f.title == "October Groceries"][0]
        f2 = [f for f in funds if f.title == "Home Repair"][0]

        # Add ₹5,000 to Fund 1 (500,000 paise)
        r1 = Receipt(user_id=sample_user, fund_id=f1.id, amount_paise=500000, received_at=datetime.now(timezone.utc))
        # Add another ₹2,000 to Fund 1 (200,000 paise)
        r2 = Receipt(user_id=sample_user, fund_id=f1.id, amount_paise=200000, received_at=datetime.now(timezone.utc))
        # Add ₹3,000 to Fund 2 (300,000 paise)
        r3 = Receipt(user_id=sample_user, fund_id=f2.id, amount_paise=300000, received_at=datetime.now(timezone.utc))
        db.session.add_all([r1, r2, r3])
        db.session.commit()

        # Check Fund 1: 5,000 + 2,000 = 7,000 (700,000 paise)
        bal1 = get_fund_balance(f1.id, sample_user)
        assert bal1["receipts_total_paise"] == 700000
        assert bal1["balance_paise"] == 700000
        assert bal1["receipt_count"] == 2

        # Check Fund 2: 3,000 (300,000 paise)
        bal2 = get_fund_balance(f2.id, sample_user)
        assert bal2["receipts_total_paise"] == 300000
        assert bal2["balance_paise"] == 300000
        assert bal2["receipt_count"] == 1

        # Check Person Summary: aggregates both funds (7,000 + 3,000 = 10,000)
        p_summary = get_person_summary(mother_id, sample_user)
        assert p_summary["total_received_paise"] == 1000000
        assert p_summary["balance_paise"] == 1000000
        assert len(p_summary["funds"]) == 2
