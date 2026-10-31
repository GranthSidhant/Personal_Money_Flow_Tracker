import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models.user import User
from app.models.person import Person
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.expense import Expense
from app.models.voice_note import VoiceNote
from app.models.ai_draft import AIDraft
from app.services.ai_service import (
    create_ai_draft_from_note,
    approve_ai_draft,
    reject_ai_draft,
)
from app.services.balance_service import get_fund_balance
from app.services.pocket_money_service import add_pocket_money_entry


def test_ai_draft_creation_consent_required(app, sample_user):
    """Explicit consent is required to process notes through AI."""
    with app.app_context():
        user = User.query.get(sample_user)
        vn = VoiceNote(
            user_id=user.id,
            title="Doctor Visit",
            text_note="Spent 500 at clinic",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        # Without consent should raise ValueError
        with pytest.raises(ValueError, match="Explicit user consent is required"):
            create_ai_draft_from_note(
                user_id=user.id,
                voice_note_id=vn.id,
                explicit_consent=False,
            )


def test_ai_draft_heuristic_extraction_receipt(app, sample_user):
    """Heuristic extraction handles incoming receipts and never alters ledger automatically."""
    with app.app_context():
        user = User.query.get(sample_user)
        initial_receipts_count = Receipt.query.filter_by(user_id=user.id).count()

        vn = VoiceNote(
            user_id=user.id,
            title="Money from Mother",
            text_note="Received ₹2,000 from Mother for grocery fund",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft = create_ai_draft_from_note(
            user_id=user.id,
            voice_note_id=vn.id,
            explicit_consent=True,
        )

        assert draft.id is not None
        assert draft.status == "PENDING_REVIEW"
        payload = draft.payload
        assert payload["transaction_type"] == "RECEIPT"
        assert payload["amount_paise"] == 200000  # ₹2,000
        assert payload["person_name"] == "Mother"

        # Approval boundary: ledger must NOT have been changed yet!
        assert Receipt.query.filter_by(user_id=user.id).count() == initial_receipts_count


def test_ai_draft_heuristic_extraction_expense(app, sample_user):
    """Heuristic extraction handles expenses and detects category/amount safely."""
    with app.app_context():
        user = User.query.get(sample_user)
        initial_expense_count = Expense.query.filter_by(user_id=user.id).count()

        vn = VoiceNote(
            user_id=user.id,
            title="Pharmacy Purchase",
            text_note="Spent 350 at chemist for medicine",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft = create_ai_draft_from_note(
            user_id=user.id,
            voice_note_id=vn.id,
            explicit_consent=True,
        )

        assert draft.status == "PENDING_REVIEW"
        payload = draft.payload
        assert payload["transaction_type"] == "EXPENSE"
        assert payload["amount_paise"] == 35000  # ₹350
        assert payload["category"] == "Healthcare"

        # Approval boundary: ledger untouched
        assert Expense.query.filter_by(user_id=user.id).count() == initial_expense_count


def test_ai_draft_approval_receipt_creates_ledger(app, sample_user):
    """Explicit approval creates valid Receipt and Fund records with provenance."""
    with app.app_context():
        user = User.query.get(sample_user)
        vn = VoiceNote(
            user_id=user.id,
            title="Transfer from Father",
            text_note="Father sent me 5000 rupees",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft = create_ai_draft_from_note(user_id=user.id, voice_note_id=vn.id, explicit_consent=True)

        ok, msg, entity_info = approve_ai_draft(
            user_id=user.id,
            draft_id=draft.id,
            approval_data={
                "transaction_type": "RECEIPT",
                "amount_paise": 500000,
                "new_person_name": "Father",
                "new_fund_name": "Father General Fund",
                "payment_method": "UPI",
                "notes": "Monthly allocation from Father",
            },
        )

        assert ok is True
        assert entity_info["entity_type"] == "Receipt"

        # Verify DB changes
        db.session.refresh(draft)
        assert draft.status == "APPROVED"
        assert draft.approved_at is not None

        receipt = Receipt.query.get(entity_info["entity_id"])
        assert receipt is not None
        assert receipt.amount_paise == 500000
        assert "Approved from AI Draft" in receipt.notes

        # Verify fund balance updated
        bal = get_fund_balance(user_id=user.id, fund_id=receipt.fund_id)
        assert bal["balance_paise"] == 500000


def test_ai_draft_approval_expense_creates_ledger(app, sample_user):
    """Explicit approval of an expense creates Expense with AI_DRAFT provenance."""
    with app.app_context():
        user = User.query.get(sample_user)
        add_pocket_money_entry(user_id=user.id, entry_type="OPENING_BALANCE", amount_paise=100000, description="Starting balance")

        vn = VoiceNote(
            user_id=user.id,
            title="Snacks",
            text_note="Spent 200 on evening snacks",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft = create_ai_draft_from_note(user_id=user.id, voice_note_id=vn.id, explicit_consent=True)

        ok, msg, entity_info = approve_ai_draft(
            user_id=user.id,
            draft_id=draft.id,
            approval_data={
                "transaction_type": "EXPENSE",
                "title": "Evening Snacks",
                "amount_paise": 20000,
                "source_type": "POCKET_MONEY",
                "payment_method": "Cash",
            },
        )

        assert ok is True
        db.session.refresh(draft)
        assert draft.status == "APPROVED"

        expense = Expense.query.get(entity_info["entity_id"])
        assert expense is not None
        assert expense.origin_type == "AI_DRAFT"
        assert expense.total_amount_paise == 20000

        # Voice note linked to expense
        db.session.refresh(vn)
        assert vn.linked_expense_id == expense.id
        assert vn.status == "LINKED"


def test_ai_draft_duplicate_approval_prevention(app, sample_user):
    """Duplicate approval of the same draft is strictly blocked."""
    with app.app_context():
        user = User.query.get(sample_user)
        add_pocket_money_entry(user_id=user.id, entry_type="OPENING_BALANCE", amount_paise=100000, description="Starting balance")

        vn = VoiceNote(
            user_id=user.id,
            title="Coffee",
            text_note="Spent 100 on coffee",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft = create_ai_draft_from_note(user_id=user.id, voice_note_id=vn.id, explicit_consent=True)

        # First approval succeeds
        approve_ai_draft(
            user_id=user.id,
            draft_id=draft.id,
            approval_data={
                "transaction_type": "EXPENSE",
                "title": "Coffee",
                "amount_paise": 10000,
                "source_type": "POCKET_MONEY",
            },
        )

        # Second approval must fail with duplicate prevention error
        with pytest.raises(ValueError, match="already been approved"):
            approve_ai_draft(
                user_id=user.id,
                draft_id=draft.id,
                approval_data={
                    "transaction_type": "EXPENSE",
                    "title": "Coffee duplicate",
                    "amount_paise": 10000,
                    "source_type": "POCKET_MONEY",
                },
            )


def test_ai_draft_rejection(app, sample_user):
    """Rejection marks draft as REJECTED and blocks subsequent approval."""
    with app.app_context():
        user = User.query.get(sample_user)
        vn = VoiceNote(
            user_id=user.id,
            title="Random Chatter",
            text_note="Not an expense, just testing microphone",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft = create_ai_draft_from_note(user_id=user.id, voice_note_id=vn.id, explicit_consent=True)
        reject_ai_draft(user_id=user.id, draft_id=draft.id, reason="Not a financial note")

        db.session.refresh(draft)
        assert draft.status == "REJECTED"

        # Attempt to approve rejected draft must fail
        with pytest.raises(ValueError, match="Cannot approve a rejected AI draft"):
            approve_ai_draft(
                user_id=user.id,
                draft_id=draft.id,
                approval_data={"transaction_type": "EXPENSE", "amount_paise": 1000},
            )


def test_ai_draft_cross_user_isolation(app, sample_user, sample_user_b):
    """Users cannot view, approve, or reject other users' drafts."""
    with app.app_context():
        u1 = User.query.get(sample_user)
        u2 = User.query.get(sample_user_b)

        vn = VoiceNote(
            user_id=u1.id,
            title="User 1 Note",
            text_note="Spent 500",
            captured_at=datetime.now(timezone.utc),
        )
        db.session.add(vn)
        db.session.commit()

        draft1 = create_ai_draft_from_note(user_id=u1.id, voice_note_id=vn.id, explicit_consent=True)

        # User 2 cannot approve User 1's draft
        with pytest.raises(ValueError, match="AI Draft not found or access denied"):
            approve_ai_draft(
                user_id=u2.id,
                draft_id=draft1.id,
                approval_data={"transaction_type": "EXPENSE", "amount_paise": 50000},
            )

        # User 2 cannot reject User 1's draft
        with pytest.raises(ValueError, match="AI Draft not found or access denied"):
            reject_ai_draft(user_id=u2.id, draft_id=draft1.id)
