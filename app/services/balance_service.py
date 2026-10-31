from typing import Dict, Any, List
from sqlalchemy import func
from app.extensions import db
from app.models.fund import Fund
from app.models.receipt import Receipt
from app.models.person import Person


def get_fund_balance(fund_id: int, user_id: int) -> Dict[str, Any]:
    """
    Calculate the precise financial balance for a specific fund.
    Formula: Total Receipts - Expense Allocations - Transfers to Pocket - Returns
    """
    fund = Fund.query.filter_by(id=fund_id, user_id=user_id).first()
    if not fund:
        return {
            "fund_id": fund_id,
            "receipts_total_paise": 0,
            "spent_total_paise": 0,
            "transferred_to_pocket_paise": 0,
            "returned_paise": 0,
            "balance_paise": 0,
            "receipt_count": 0,
        }

    # Sum of incoming receipts for this fund
    receipts_total = (
        db.session.query(func.coalesce(func.sum(Receipt.amount_paise), 0))
        .filter(Receipt.fund_id == fund_id, Receipt.user_id == user_id)
        .scalar()
    )

    receipt_count = (
        db.session.query(func.count(Receipt.id))
        .filter(Receipt.fund_id == fund_id, Receipt.user_id == user_id)
        .scalar()
    )

    # Sum of expense allocations funded by this fund
    from app.models.expense_allocation import ExpenseAllocation
    spent_total = (
        db.session.query(func.coalesce(func.sum(ExpenseAllocation.allocated_amount_paise), 0))
        .filter(
            ExpenseAllocation.fund_id == fund_id,
            ExpenseAllocation.source_type == "FUND",
            ExpenseAllocation.user_id == user_id,
        )
        .scalar()
    )

    from app.models.settlement import Settlement
    transferred_to_pocket = (
        db.session.query(func.coalesce(func.sum(Settlement.amount_paise), 0))
        .filter(
            Settlement.fund_id == fund_id,
            Settlement.user_id == user_id,
            Settlement.settlement_type == "TRANSFER_TO_POCKET",
        )
        .scalar()
    )

    returned_total = (
        db.session.query(func.coalesce(func.sum(Settlement.amount_paise), 0))
        .filter(
            Settlement.fund_id == fund_id,
            Settlement.user_id == user_id,
            Settlement.settlement_type == "RETURN_TO_PROVIDER",
        )
        .scalar()
    )

    balance_paise = receipts_total - spent_total - transferred_to_pocket - returned_total

    return {
        "fund_id": fund_id,
        "fund_title": fund.title,
        "person_id": fund.person_id,
        "status": fund.status,
        "receipts_total_paise": receipts_total,
        "spent_total_paise": spent_total,
        "transferred_to_pocket_paise": transferred_to_pocket,
        "returned_paise": returned_total,
        "balance_paise": balance_paise,
        "receipt_count": receipt_count,
    }


def get_person_summary(person_id: int, user_id: int) -> Dict[str, Any]:
    """
    Calculate person-level financial summary across all their funds and personal receivables.
    """
    person = Person.query.filter_by(id=person_id, user_id=user_id).first()
    if not person:
        return {
            "person_id": person_id,
            "total_received_paise": 0,
            "total_spent_paise": 0,
            "balance_paise": 0,
            "transferred_to_pocket_paise": 0,
            "returned_paise": 0,
            "outstanding_receivable_paise": 0,
            "funds": [],
        }

    funds = Fund.query.filter_by(person_id=person_id, user_id=user_id).all()
    fund_summaries = []
    total_received = 0
    total_spent = 0
    total_balance = 0
    total_transferred = 0
    total_returned = 0

    for fund in funds:
        f_bal = get_fund_balance(fund.id, user_id)
        fund_summaries.append({
            "fund": fund,
            **f_bal,
        })
        total_received += f_bal["receipts_total_paise"]
        total_spent += f_bal["spent_total_paise"]
        total_balance += f_bal["balance_paise"]
        total_transferred += f_bal["transferred_to_pocket_paise"]
        total_returned += f_bal["returned_paise"]

    # Calculate personal contributions & receivables for this person
    from app.services.settlement_service import get_outstanding_receivable
    outstanding_receivable = get_outstanding_receivable(user_id, person_id)

    return {
        "person": person,
        "total_received_paise": total_received,
        "total_spent_paise": total_spent,
        "balance_paise": total_balance,
        "transferred_to_pocket_paise": total_transferred,
        "returned_paise": total_returned,
        "outstanding_receivable_paise": outstanding_receivable,
        "funds": fund_summaries,
    }


def get_all_people_summaries(user_id: int, include_archived: bool = False) -> List[Dict[str, Any]]:
    """Get summarized balances for all people belonging to the user."""
    query = Person.query.filter_by(user_id=user_id)
    if not include_archived:
        query = query.filter(Person.archived_at.is_(None))
    
    people = query.order_by(Person.name.asc()).all()
    return [get_person_summary(p.id, user_id) for p in people]


def get_total_entrusted_balance(user_id: int) -> int:
    """Calculate the total entrusted money balance across all active funds for the user."""
    active_funds = Fund.query.filter_by(user_id=user_id, status="ACTIVE").all()
    total = 0
    for fund in active_funds:
        total += get_fund_balance(fund.id, user_id)["balance_paise"]
    return total
