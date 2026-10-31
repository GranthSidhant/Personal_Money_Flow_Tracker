import io
import json
import pytest
from datetime import datetime, timezone
import openpyxl
from app.extensions import db
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.expense import Expense
from app.services.report_service import (
    get_monthly_cashflow_trend,
    generate_transactions_csv,
    generate_excel_workbook,
    export_user_json_backup,
)
from app.services.allocation_service import record_expense_with_allocations


def test_monthly_cashflow_trend_service(app, sample_user):
    """Verify monthly cashflow service returns proper trend data."""
    with app.app_context():
        mother = Person(user_id=sample_user, name="Mother")
        db.session.add(mother)
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=mother.id, title="Household")
        db.session.add(fund)
        db.session.flush()

        rec = Receipt(
            user_id=sample_user,
            fund_id=fund.id,
            amount_paise=200000,
            received_at=datetime.now(timezone.utc),
        )
        db.session.add(rec)
        db.session.commit()

        trend = get_monthly_cashflow_trend(sample_user, months=6)
        assert len(trend) == 6
        # Current month should include the 2,000 received
        current_month = trend[-1]
        assert current_month["money_in_paise"] >= 200000


def test_reports_page_and_csv_export(client, app, sample_user):
    """Test /reports endpoint and /reports/export/csv endpoint."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    # 1. Reports dashboard view
    resp = client.get("/reports")
    assert resp.status_code == 200
    assert b"Financial Reports &amp; Analytics" in resp.data or b"Financial Reports & Analytics" in resp.data
    assert b"Monthly Cashflow Trend" in resp.data

    # 2. CSV export
    csv_resp = client.get("/reports/export/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.content_type
    assert b"Transaction Type,Date,Title / Description" in csv_resp.data


def test_excel_export_service(app, sample_user):
    """Test generating a multi-sheet Excel workbook using openpyxl."""
    with app.app_context():
        brother = Person(user_id=sample_user, name="Brother")
        db.session.add(brother)
        db.session.flush()

        fund = Fund(user_id=sample_user, person_id=brother.id, title="Stationery")
        db.session.add(fund)
        db.session.flush()

        rec = Receipt(
            user_id=sample_user,
            fund_id=fund.id,
            amount_paise=50000,
            received_at=datetime.now(timezone.utc),
        )
        db.session.add(rec)
        db.session.commit()

        buf = generate_excel_workbook(sample_user)
        assert isinstance(buf, io.BytesIO)

        # Verify workbook can be read by openpyxl
        wb = openpyxl.load_workbook(buf)
        assert "Financial Summary" in wb.sheetnames
        assert "Expenses" in wb.sheetnames
        assert "Receipts" in wb.sheetnames
        assert "Settlements" in wb.sheetnames

        ws_rec = wb["Receipts"]
        assert ws_rec.max_row >= 2  # header + receipt row


def test_json_backup_user_scoped(app, sample_user):
    """Verify JSON backup only exports data belonging to the authenticated user."""
    with app.app_context():
        # User 1 person
        p1 = Person(user_id=sample_user, name="User1 Person")
        # User 2 person
        p2 = Person(user_id=999, name="User2 Person")
        db.session.add_all([p1, p2])
        db.session.commit()

        backup = export_user_json_backup(sample_user)
        assert backup["user_id"] == sample_user
        assert backup["version"] == "1.0"
        people_names = [p["name"] for p in backup["data"]["people"]]
        assert "User1 Person" in people_names
        assert "User2 Person" not in people_names
