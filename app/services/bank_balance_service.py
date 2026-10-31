from typing import Dict, Any, List
from sqlalchemy import func
from app.extensions import db
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction


def calculate_bank_account_balance(bank_account_id: int, user_id: int) -> Dict[str, Any]:
    """
    Calculate the manually tracked balance for a specific bank account.
    Formula: Opening Balance + Total Credits (including transfer in) - Total Debits (including transfer out)
    """
    account = BankAccount.query.filter_by(id=bank_account_id, user_id=user_id).first()
    if not account:
        return {
            "account_id": bank_account_id,
            "opening_balance_paise": 0,
            "total_credits_paise": 0,
            "total_debits_paise": 0,
            "current_balance_paise": 0,
            "transaction_count": 0,
        }

    # Sum of all credit transactions (CREDIT, TRANSFER_IN, REVERSAL_IN)
    credits_total = (
        db.session.query(func.coalesce(func.sum(BankTransaction.amount_paise), 0))
        .filter(
            BankTransaction.bank_account_id == bank_account_id,
            BankTransaction.user_id == user_id,
            BankTransaction.transaction_type.in_(["CREDIT", "TRANSFER_IN", "REVERSAL_IN"])
        )
        .scalar()
    )

    # Sum of all debit transactions (DEBIT, TRANSFER_OUT, REVERSAL_OUT)
    debits_total = (
        db.session.query(func.coalesce(func.sum(BankTransaction.amount_paise), 0))
        .filter(
            BankTransaction.bank_account_id == bank_account_id,
            BankTransaction.user_id == user_id,
            BankTransaction.transaction_type.in_(["DEBIT", "TRANSFER_OUT", "REVERSAL_OUT"])
        )
        .scalar()
    )

    transaction_count = (
        db.session.query(func.count(BankTransaction.id))
        .filter(BankTransaction.bank_account_id == bank_account_id, BankTransaction.user_id == user_id)
        .scalar()
    )

    current_balance_paise = account.opening_balance_paise + credits_total - debits_total

    return {
        "account": account,
        "account_id": account.id,
        "opening_balance_paise": account.opening_balance_paise,
        "total_credits_paise": credits_total,
        "total_debits_paise": debits_total,
        "current_balance_paise": current_balance_paise,
        "transaction_count": transaction_count,
    }


def get_all_bank_accounts_summary(user_id: int, include_archived: bool = False) -> List[Dict[str, Any]]:
    """Return balance summaries for all bank accounts owned by the user."""
    query = BankAccount.query.filter_by(user_id=user_id)
    if not include_archived:
        query = query.filter(BankAccount.archived_at.is_(None))
    
    accounts = query.order_by(BankAccount.bank_name.asc(), BankAccount.account_nickname.asc()).all()
    return [calculate_bank_account_balance(acc.id, user_id) for acc in accounts]


def get_combined_bank_balances(user_id: int) -> int:
    """Calculate combined manually tracked bank balances across all active accounts."""
    summaries = get_all_bank_accounts_summary(user_id, include_archived=False)
    return sum(s["current_balance_paise"] for s in summaries)
