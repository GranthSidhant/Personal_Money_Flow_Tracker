def test_unauthenticated_dashboard_redirects(client):
    """Protected routes must redirect unauthenticated visitors to login."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_unauthenticated_profile_redirects(client):
    """User profile must require authentication."""
    response = client.get("/auth/profile", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_authenticated_dashboard_access(client, sample_user):
    """Authenticated user must be able to view their dashboard."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Total Money In" in response.data


def test_user_session_isolation(client, app, sample_user, sample_user_b):
    """Ensure session of User A does not expose User B's profile details."""
    # Login as User A
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    response = client.get("/auth/profile")
    assert response.status_code == 200
    assert b"test@example.com" in response.data
    assert b"user2@example.com" not in response.data


def test_cross_user_financial_isolation(client, app, sample_user, sample_user_b):
    """User A must not be able to view or access User B's people, funds, or bank accounts."""
    from app.models.person import Person
    from app.models.fund import Fund
    from app.models.bank_account import BankAccount
    from app.extensions import db
    from datetime import datetime, timezone

    # Create private records for User B
    with app.app_context():
        person_b = Person(user_id=sample_user_b, name="Private Counterparty B")
        db.session.add(person_b)
        db.session.flush()

        fund_b = Fund(user_id=sample_user_b, person_id=person_b.id, title="Secret Fund B")
        acc_b = BankAccount(
            user_id=sample_user_b,
            account_nickname="Secret Bank B",
            bank_name="Swiss Bank",
            opening_balance_paise=10000000,
            opening_balance_date=datetime.now(timezone.utc),
        )
        db.session.add_all([fund_b, acc_b])
        db.session.commit()

        p_id, f_id, a_id = person_b.id, fund_b.id, acc_b.id

    # Log in as User A
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # 1. User A tries to view User B's person detail
    resp_person = client.get(f"/people/{p_id}")
    assert resp_person.status_code == 404

    # 2. User A tries to view User B's fund detail
    resp_fund = client.get(f"/funds/{f_id}")
    assert resp_fund.status_code == 404

    # 3. User A tries to view User B's bank account detail
    resp_acc = client.get(f"/bank-accounts/{a_id}")
    assert resp_acc.status_code == 404

    # 4. User A checks their People and Bank list: User B's records must NOT appear
    people_page = client.get("/people")
    assert b"Private Counterparty B" not in people_page.data

    bank_page = client.get("/bank-accounts")
    assert b"Secret Bank B" not in bank_page.data

