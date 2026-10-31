import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import func
from app.extensions import db
from app.models.settlement import Settlement
from app.models.pocket_money_entry import PocketMoneyEntry
from app.models.fund import Fund
from app.models.person import Person
from app.models.expense import Expense
from app.models.expense_allocation import ExpenseAllocation
from app.models.bank_transaction import BankTransaction
from app.models.bank_account import BankAccount
from app.services.balance_service import get_fund_balance
from app.services.audit_service import log_audit_event
from app.utils.money import format_inr


def execute_transfer_to_pocket(
    user_id: int,
    fund_id: int,
    amount_paise: int,
    notes: Optional[str] = None,
    settlement_at: Optional[datetime] = None,
) -> Settlement:
    """
    Transfer unused money from an entrusted fund to Pocket Money with permission.
    Atomic double entry:
    1. Reduces fund's available balance via Settlement(TRANSFER_TO_POCKET).
    2. Increases Pocket Money via PocketMoneyEntry(FUND_TRANSFER).
    """
    if amount_paise <= 0:
        raise ValueError("Transfer amount must be strictly positive.")

    fund = Fund.query.filter_by(id=fund_id, user_id=user_id).first()
    if not fund:
        raise ValueError(f"Fund {fund_id} not found or unauthorized.")

    # Validate against current available fund balance
    bal = get_fund_balance(fund_id, user_id)
    available_paise = bal["balance_paise"]
    if amount_paise > available_paise:
        raise ValueError(
            f"Transfer amount ({format_inr(amount_paise)}) exceeds available fund balance ({format_inr(available_paise)})."
        )

    if settlement_at is None:
        settlement_at = datetime.now(timezone.utc)

    transfer_group_id = str(uuid.uuid4())

    # 1. Create Settlement
    settlement = Settlement(
        user_id=user_id,
        person_id=fund.person_id,
        fund_id=fund.id,
        settlement_type="TRANSFER_TO_POCKET",
        amount_paise=amount_paise,
        settlement_at=settlement_at,
        notes=notes.strip() if notes else None,
    )
    db.session.add(settlement)
    db.session.flush()

    # 2. Create PocketMoneyEntry (atomic paired entry)
    pocket_entry = PocketMoneyEntry(
        user_id=user_id,
        entry_type="FUND_TRANSFER",
        amount_paise=amount_paise,
        description=f"Transfer from {fund.title} ({fund.person.name})",
        occurred_at=settlement_at,
        related_fund_id=fund.id,
        related_settlement_id=settlement.id,
        transfer_group_id=transfer_group_id,
    )
    db.session.add(pocket_entry)

    log_audit_event(
        user_id=user_id,
        entity_type="SETTLEMENT",
        entity_id=settlement.id,
        action="TRANSFER_TO_POCKET",
        after_snapshot={
            "fund_id": fund_id,
            "person_id": fund.person_id,
            "amount_paise": amount_paise,
            "transfer_group_id": transfer_group_id,
        },
    )

    db.session.commit()
    return settlement


def execute_return_to_provider(
    user_id: int,
    fund_id: int,
    amount_paise: int,
    notes: Optional[str] = None,
    settlement_at: Optional[datetime] = None,
    bank_account_id: Optional[int] = None,
) -> Settlement:
    """
    Return unused entrusted money from a fund back to the person who provided it.
    Reduces the fund's balance.
    If bank_account_id is given, creates a linked DEBIT BankTransaction.
    """
    if amount_paise <= 0:
        raise ValueError("Return amount must be strictly positive.")

    fund = Fund.query.filter_by(id=fund_id, user_id=user_id).first()
    if not fund:
        raise ValueError(f"Fund {fund_id} not found or unauthorized.")

    bal = get_fund_balance(fund_id, user_id)
    available_paise = bal["balance_paise"]
    if amount_paise > available_paise:
        raise ValueError(
            f"Return amount ({format_inr(amount_paise)}) exceeds available fund balance ({format_inr(available_paise)})."
        )

    if settlement_at is None:
        settlement_at = datetime.now(timezone.utc)

    settlement = Settlement(
        user_id=user_id,
        person_id=fund.person_id,
        fund_id=fund.id,
        settlement_type="RETURN_TO_PROVIDER",
        amount_paise=amount_paise,
        settlement_at=settlement_at,
        notes=notes.strip() if notes else None,
    )
    db.session.add(settlement)
    db.session.flush()

    if bank_account_id:
        bank_acc = BankAccount.query.filter_by(id=bank_account_id, user_id=user_id).first()
        if bank_acc:
            bank_tx = BankTransaction(
                user_id=user_id,
                bank_account_id=bank_acc.id,
                transaction_type="DEBIT",
                amount_paise=amount_paise,
                transaction_at=settlement_at,
                description=f"Return unused money from fund: {fund.title}",
                person_id=fund.person_id,
                linked_settlement_id=settlement.id,
                classification_status="CLASSIFIED",
                notes=notes,
            )
            db.session.add(bank_tx)

    log_audit_event(
        user_id=user_id,
        entity_type="SETTLEMENT",
        entity_id=settlement.id,
        action="RETURN_TO_PROVIDER",
        after_snapshot={
            "fund_id": fund_id,
            "person_id": fund.person_id,
            "amount_paise": amount_paise,
            "bank_account_id": bank_account_id,
        },
    )

    db.session.commit()
    return settlement


def execute_reimbursement(
    user_id: int,
    person_id: int,
    amount_paise: int,
    notes: Optional[str] = None,
    settlement_at: Optional[datetime] = None,
    related_expense_id: Optional[int] = None,
    bank_account_id: Optional[int] = None,
) -> Settlement:
    """
    Record reimbursement from a person for personal recoverable contributions.
    Increases Pocket Money.
    If bank_account_id is given, creates a linked CREDIT BankTransaction.
    """
    if amount_paise <= 0:
        raise ValueError("Reimbursement amount must be strictly positive.")

    person = Person.query.filter_by(id=person_id, user_id=user_id).first()
    if not person:
        raise ValueError(f"Person {person_id} not found or unauthorized.")

    receivable = get_outstanding_receivable(user_id, person_id)
    if amount_paise > receivable:
        raise ValueError(
            f"Reimbursement amount ({format_inr(amount_paise)}) exceeds outstanding receivable ({format_inr(receivable)}) for {person.name}."
        )

    if settlement_at is None:
        settlement_at = datetime.now(timezone.utc)

    settlement = Settlement(
        user_id=user_id,
        person_id=person_id,
        related_expense_id=related_expense_id,
        settlement_type="REIMBURSEMENT",
        amount_paise=amount_paise,
        settlement_at=settlement_at,
        notes=notes.strip() if notes else None,
    )
    db.session.add(settlement)
    db.session.flush()

    # Credit to Pocket Money
    pocket_entry = PocketMoneyEntry(
        user_id=user_id,
        entry_type="REIMBURSEMENT",
        amount_paise=amount_paise,
        description=f"Reimbursement from {person.name}",
        occurred_at=settlement_at,
        related_expense_id=related_expense_id,
        related_settlement_id=settlement.id,
    )
    db.session.add(pocket_entry)

    # Optional bank account credit
    if bank_account_id:
        bank_acc = BankAccount.query.filter_by(id=bank_account_id, user_id=user_id).first()
        if bank_acc:
            bank_tx = BankTransaction(
                user_id=user_id,
                bank_account_id=bank_acc.id,
                transaction_type="CREDIT",
                amount_paise=amount_paise,
                transaction_at=settlement_at,
                description=f"Reimbursement received: {person.name}",
                person_id=person_id,
                linked_settlement_id=settlement.id,
                classification_status="CLASSIFIED",
                notes=notes,
            )
            db.session.add(bank_tx)

    log_audit_event(
        user_id=user_id,
        entity_type="SETTLEMENT",
        entity_id=settlement.id,
        action="REIMBURSEMENT",
        after_snapshot={
            "person_id": person_id,
            "amount_paise": amount_paise,
            "related_expense_id": related_expense_id,
            "bank_account_id": bank_account_id,
        },
    )

    db.session.commit()
    return settlement


def get_outstanding_receivable(user_id: int, person_id: Optional[int] = None) -> int:
    """
    Calculate outstanding reimbursement amount owed by a person (or across all people).
    Formula: Recoverable personal contributions - Reimbursements received.
    """
    # 1. Total recoverable contributions
    alloc_query = (
        db.session.query(func.coalesce(func.sum(ExpenseAllocation.allocated_amount_paise), 0))
        .filter(
            ExpenseAllocation.user_id == user_id,
            ExpenseAllocation.source_type == "POCKET_MONEY",
            ExpenseAllocation.reimbursement_expected.is_(True),
        )
    )
    if person_id:
        alloc_query = alloc_query.filter(ExpenseAllocation.person_id == person_id)
    recoverable_total = alloc_query.scalar()

    # 2. Total reimbursements received
    reimb_query = (
        db.session.query(func.coalesce(func.sum(Settlement.amount_paise), 0))
        .filter(
            Settlement.user_id == user_id,
            Settlement.settlement_type == "REIMBURSEMENT",
        )
    )
    if person_id:
        reimb_query = reimb_query.filter(Settlement.person_id == person_id)
    reimbursed_total = reimb_query.scalar()

    return max(0, recoverable_total - reimbursed_total)


def revert_settlement(user_id: int, settlement_id: int) -> None:
    """
    Revert a settlement record and its linked pocket money or bank entries.
    """
    settlement = Settlement.query.filter_by(id=settlement_id, user_id=user_id).first()
    if not settlement:
        raise ValueError(f"Settlement {settlement_id} not found.")

    log_audit_event(
        user_id=user_id,
        entity_type="SETTLEMENT",
        entity_id=settlement.id,
        action="DELETE",
        before_snapshot={
            "settlement_type": settlement.settlement_type,
            "amount_paise": settlement.amount_paise,
            "person_id": settlement.person_id,
            "fund_id": settlement.fund_id,
        },
    )

    db.session.delete(settlement)
    db.session.commit()
