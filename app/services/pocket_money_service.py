from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import func
from app.extensions import db
from app.models.pocket_money_entry import PocketMoneyEntry
from app.models.audit_event import AuditEvent
from app.services.audit_service import log_audit_event


def get_pocket_money_balance(user_id: int) -> Dict[str, Any]:
    """
    Calculate the user's Pocket Money balance from the ledger.
    Pocket Money is the logical personal-money ledger.
    Credits: OPENING_BALANCE, INCOME, FUND_TRANSFER, REIMBURSEMENT
    Debits: EXPENSE, ADJUSTMENT_DEBIT
    """
    # 1. Opening balance
    opening_paise = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "OPENING_BALANCE")
        .scalar()
    )

    # 2. Personal Income / Allowance
    income_paise = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "INCOME")
        .scalar()
    )

    # 3. Transfers from Entrusted Funds
    transfers_paise = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "FUND_TRANSFER")
        .scalar()
    )

    # 4. Reimbursements received from People
    reimbursements_paise = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "REIMBURSEMENT")
        .scalar()
    )

    # 5. Expenses / Personal Outflow funded by Pocket Money
    expenses_paise = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "EXPENSE")
        .scalar()
    )

    # 6. Adjustments
    adjustments_credit = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "ADJUSTMENT_CREDIT")
        .scalar()
    )
    adjustments_debit = (
        db.session.query(func.coalesce(func.sum(PocketMoneyEntry.amount_paise), 0))
        .filter(PocketMoneyEntry.user_id == user_id, PocketMoneyEntry.entry_type == "ADJUSTMENT_DEBIT")
        .scalar()
    )

    total_credits = opening_paise + income_paise + transfers_paise + reimbursements_paise + adjustments_credit
    total_debits = expenses_paise + adjustments_debit
    current_balance_paise = total_credits - total_debits

    return {
        "current_balance_paise": current_balance_paise,
        "total_credits_paise": total_credits,
        "total_debits_paise": total_debits,
        "opening_balance_paise": opening_paise,
        "income_total_paise": income_paise,
        "transfers_from_funds_paise": transfers_paise,
        "reimbursements_received_paise": reimbursements_paise,
        "expenses_total_paise": expenses_paise,
        "adjustments_net_paise": adjustments_credit - adjustments_debit,
    }


def add_pocket_money_entry(
    user_id: int,
    entry_type: str,
    amount_paise: int,
    description: str,
    occurred_at: Optional[datetime] = None,
    related_fund_id: Optional[int] = None,
    related_expense_id: Optional[int] = None,
    related_settlement_id: Optional[int] = None,
    transfer_group_id: Optional[str] = None,
) -> PocketMoneyEntry:
    """Create and persist an auditable Pocket Money ledger entry."""
    if amount_paise <= 0:
        raise ValueError("Pocket money entry amount must be strictly positive.")

    valid_types = {
        "OPENING_BALANCE",
        "INCOME",
        "EXPENSE",
        "FUND_TRANSFER",
        "REIMBURSEMENT",
        "ADJUSTMENT_CREDIT",
        "ADJUSTMENT_DEBIT",
    }
    if entry_type not in valid_types:
        raise ValueError(f"Invalid entry type '{entry_type}'. Must be one of {valid_types}.")

    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)

    entry = PocketMoneyEntry(
        user_id=user_id,
        entry_type=entry_type,
        amount_paise=amount_paise,
        description=description,
        occurred_at=occurred_at,
        related_fund_id=related_fund_id,
        related_expense_id=related_expense_id,
        related_settlement_id=related_settlement_id,
        transfer_group_id=transfer_group_id,
    )
    db.session.add(entry)
    db.session.flush()

    log_audit_event(
        user_id=user_id,
        entity_type="POCKET_MONEY_ENTRY",
        entity_id=entry.id,
        action="CREATE",
        after_snapshot={
            "entry_type": entry_type,
            "amount_paise": amount_paise,
            "description": description,
        },
    )

    return entry
