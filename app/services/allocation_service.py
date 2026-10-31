from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func
from app.extensions import db
from app.models.expense import Expense
from app.models.expense_allocation import ExpenseAllocation
from app.models.fund import Fund
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.services.balance_service import get_fund_balance
from app.services.audit_service import log_audit_event
from app.utils.money import format_inr


def validate_allocations(
    user_id: int,
    total_amount_paise: int,
    allocations_data: List[Dict[str, Any]],
    current_expense_id: Optional[int] = None,
) -> None:
    """
    Strict financial validation:
    1. Sum of allocations must exactly equal the total expense amount.
    2. No silent overdrawing: Each fund must have sufficient available balance.
    3. Proper source validation (FUND requires valid owned fund_id; POCKET_MONEY requires null fund_id).
    """
    if total_amount_paise <= 0:
        raise ValueError("Total expense amount must be greater than zero.")

    if not allocations_data:
        raise ValueError("At least one funding allocation is required.")

    allocated_sum = sum(int(a.get("allocated_amount_paise", 0)) for a in allocations_data)
    if allocated_sum != total_amount_paise:
        diff = total_amount_paise - allocated_sum
        diff_str = format_inr(abs(diff))
        status = "under-allocated" if diff > 0 else "over-allocated"
        raise ValueError(
            f"Allocation mismatch: Total expense is {format_inr(total_amount_paise)}, "
            f"but allocations sum to {format_inr(allocated_sum)} ({status} by {diff_str})."
        )

    for idx, alloc in enumerate(allocations_data):
        amount = int(alloc.get("allocated_amount_paise", 0))
        if amount <= 0:
            raise ValueError(f"Allocation #{idx + 1} amount must be greater than zero.")

        source_type = alloc.get("source_type")
        if source_type not in ("FUND", "POCKET_MONEY"):
            raise ValueError(f"Invalid source type '{source_type}'. Must be FUND or POCKET_MONEY.")

        if source_type == "FUND":
            fund_id = alloc.get("fund_id")
            if not fund_id:
                raise ValueError(f"Allocation #{idx + 1} from FUND requires a selected fund.")

            fund = Fund.query.filter_by(id=fund_id, user_id=user_id).first()
            if not fund:
                raise ValueError(f"Fund #{fund_id} not found or does not belong to you.")

            # Calculate current available balance
            balance_info = get_fund_balance(fund.id, user_id)
            available = balance_info["balance_paise"]

            # If editing an existing expense, credit back any prior allocation from this fund
            if current_expense_id:
                prior_alloc = ExpenseAllocation.query.filter_by(
                    expense_id=current_expense_id,
                    fund_id=fund.id,
                    source_type="FUND",
                    user_id=user_id
                ).first()
                if prior_alloc:
                    available += prior_alloc.allocated_amount_paise

            if amount > available:
                shortfall = amount - available
                raise ValueError(
                    f"Fund '{fund.title}' only has {format_inr(available)} available. "
                    f"Cannot allocate {format_inr(amount)}. "
                    f"Please allocate the shortfall ({format_inr(shortfall)}) to Pocket Money or another fund."
                )

        elif source_type == "POCKET_MONEY":
            # For Pocket Money, fund_id must be None
            alloc["fund_id"] = None


def record_expense_with_allocations(
    user_id: int,
    title: str,
    total_amount_paise: int,
    category_id: Optional[int],
    expense_at: datetime,
    allocations_data: List[Dict[str, Any]],
    merchant: Optional[str] = None,
    payment_method: Optional[str] = None,
    reference_id: Optional[str] = None,
    description: Optional[str] = None,
    bank_account_id: Optional[int] = None,
) -> Expense:
    """
    Atomically records an expense and its multi-source allocations with audit logging.
    If bank_account_id is provided, also creates a linked DEBIT BankTransaction.
    """
    validate_allocations(user_id, total_amount_paise, allocations_data)

    expense = Expense(
        user_id=user_id,
        category_id=category_id,
        title=title.strip(),
        total_amount_paise=total_amount_paise,
        expense_at=expense_at,
        merchant=merchant.strip() if merchant else None,
        payment_method=payment_method,
        reference_id=reference_id.strip() if reference_id else None,
        description=description.strip() if description else None,
    )
    db.session.add(expense)
    db.session.flush()

    for alloc in allocations_data:
        allocation_record = ExpenseAllocation(
            user_id=user_id,
            expense_id=expense.id,
            source_type=alloc["source_type"],
            fund_id=alloc.get("fund_id"),
            allocated_amount_paise=int(alloc["allocated_amount_paise"]),
            reimbursement_expected=bool(alloc.get("reimbursement_expected", False)),
        )
        db.session.add(allocation_record)

    # Optional atomic bank debit
    if bank_account_id:
        bank_acc = BankAccount.query.filter_by(id=bank_account_id, user_id=user_id).first()
        if bank_acc:
            bank_tx = BankTransaction(
                user_id=user_id,
                bank_account_id=bank_acc.id,
                transaction_type="DEBIT",
                amount_paise=total_amount_paise,
                transaction_at=expense_at,
                description=f"Payment for {expense.title}",
                reference_id=reference_id.strip() if reference_id else None,
                category_id=category_id,
                linked_expense_id=expense.id,
                classification_status="CLASSIFIED",
                notes=description.strip() if description else None,
            )
            db.session.add(bank_tx)

    log_audit_event(
        user_id=user_id,
        entity_type="EXPENSE",
        entity_id=expense.id,
        action="CREATE",
        after_snapshot={
            "title": expense.title,
            "total_amount_paise": total_amount_paise,
            "allocations_count": len(allocations_data),
        }
    )

    db.session.commit()
    return expense


def get_spending_by_category(user_id: int) -> List[Dict[str, Any]]:
    """Aggregate spending by category for donut chart & reports."""
    from app.models.category import Category
    results = (
        db.session.query(
            Category.name,
            func.coalesce(func.sum(Expense.total_amount_paise), 0).label("total_paise")
        )
        .outerjoin(Expense, (Expense.category_id == Category.id) & (Expense.user_id == user_id))
        .filter((Category.user_id == user_id) | (Category.user_id.is_(None)))
        .group_by(Category.name)
        .having(func.sum(Expense.total_amount_paise) > 0)
        .order_by(func.sum(Expense.total_amount_paise).desc())
        .all()
    )

    total_spent = sum(r.total_paise for r in results)
    category_breakdown = []
    for r in results:
        percentage = round((r.total_paise / total_spent * 100), 1) if total_spent > 0 else 0
        category_breakdown.append({
            "name": r.name,
            "total_paise": r.total_paise,
            "percentage": percentage,
        })
    return category_breakdown


def get_recoverable_contributions_total(user_id: int) -> int:
    """Calculate total personal money spent where reimbursement is expected."""
    return (
        db.session.query(func.coalesce(func.sum(ExpenseAllocation.allocated_amount_paise), 0))
        .filter(
            ExpenseAllocation.user_id == user_id,
            ExpenseAllocation.source_type == "POCKET_MONEY",
            ExpenseAllocation.reimbursement_expected.is_(True)
        )
        .scalar()
    )
