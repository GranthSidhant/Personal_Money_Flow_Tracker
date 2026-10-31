import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from app.extensions import db
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.receipt import Receipt
from app.services.audit_service import log_audit_event


def record_internal_transfer(
    user_id: int,
    source_account_id: int,
    dest_account_id: int,
    amount_paise: int,
    transaction_at: datetime,
    description: str = "Internal Transfer",
    reference_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Tuple[BankTransaction, BankTransaction]:
    """
    Atomically execute an internal transfer between two bank accounts owned by the same user.
    Creates paired TRANSFER_OUT and TRANSFER_IN entries sharing a transfer_group_id.
    """
    if source_account_id == dest_account_id:
        raise ValueError("Source and destination accounts must be different.")

    if amount_paise <= 0:
        raise ValueError("Transfer amount must be greater than zero.")

    # Validate ownership of both accounts
    source_acc = BankAccount.query.filter_by(id=source_account_id, user_id=user_id).first()
    dest_acc = BankAccount.query.filter_by(id=dest_account_id, user_id=user_id).first()

    if not source_acc or not dest_acc:
        raise ValueError("One or both accounts do not exist or do not belong to you.")

    transfer_group_id = str(uuid.uuid4())

    debit_tx = BankTransaction(
        user_id=user_id,
        bank_account_id=source_account_id,
        transaction_type="TRANSFER_OUT",
        amount_paise=amount_paise,
        transaction_at=transaction_at,
        description=f"Transfer to {dest_acc.account_nickname}: {description}",
        reference_id=reference_id,
        transfer_group_id=transfer_group_id,
        classification_status="CLASSIFIED",
        notes=notes,
    )

    credit_tx = BankTransaction(
        user_id=user_id,
        bank_account_id=dest_account_id,
        transaction_type="TRANSFER_IN",
        amount_paise=amount_paise,
        transaction_at=transaction_at,
        description=f"Transfer from {source_acc.account_nickname}: {description}",
        reference_id=reference_id,
        transfer_group_id=transfer_group_id,
        classification_status="CLASSIFIED",
        notes=notes,
    )

    db.session.add(debit_tx)
    db.session.add(credit_tx)
    db.session.flush()

    log_audit_event(
        user_id=user_id,
        entity_type="BANK_TRANSACTION",
        entity_id=debit_tx.id,
        action="TRANSFER_OUT",
        after_snapshot={"dest_account_id": dest_account_id, "amount_paise": amount_paise},
    )

    log_audit_event(
        user_id=user_id,
        entity_type="BANK_TRANSACTION",
        entity_id=credit_tx.id,
        action="TRANSFER_IN",
        after_snapshot={"source_account_id": source_account_id, "amount_paise": amount_paise},
    )

    return debit_tx, credit_tx


def link_transaction_to_receipt(
    bank_transaction_id: int,
    receipt_id: int,
    user_id: int,
) -> BankTransaction:
    """
    Link a bank credit transaction to an incoming receipt record.
    Ensures ownership and validates matching amounts/semantics.
    """
    tx = BankTransaction.query.filter_by(id=bank_transaction_id, user_id=user_id).first()
    if not tx:
        raise ValueError("Bank transaction not found.")

    if tx.transaction_type not in ("CREDIT", "REVERSAL_IN"):
        raise ValueError("Only credit transactions can be linked to receipts.")

    receipt = Receipt.query.filter_by(id=receipt_id, user_id=user_id).first()
    if not receipt:
        raise ValueError("Receipt not found.")

    # Check if receipt is already linked to another bank transaction
    existing = BankTransaction.query.filter_by(linked_receipt_id=receipt_id, user_id=user_id).first()
    if existing and existing.id != tx.id:
        raise ValueError("This receipt is already linked to another bank transaction.")

    tx.linked_receipt_id = receipt_id
    tx.classification_status = "CLASSIFIED"
    
    # Also associate person if fund has a person
    if receipt.fund and receipt.fund.person_id:
        tx.person_id = receipt.fund.person_id

    log_audit_event(
        user_id=user_id,
        entity_type="BANK_TRANSACTION",
        entity_id=tx.id,
        action="LINK_RECEIPT",
        after_snapshot={"linked_receipt_id": receipt_id},
    )

    return tx


def unlink_transaction_from_receipt(
    bank_transaction_id: int,
    user_id: int,
) -> BankTransaction:
    """Unlink a bank transaction from its receipt, returning it to unclassified."""
    tx = BankTransaction.query.filter_by(id=bank_transaction_id, user_id=user_id).first()
    if not tx:
        raise ValueError("Bank transaction not found.")

    prev_receipt_id = tx.linked_receipt_id
    tx.linked_receipt_id = None
    tx.classification_status = "UNCLASSIFIED"

    log_audit_event(
        user_id=user_id,
        entity_type="BANK_TRANSACTION",
        entity_id=tx.id,
        action="UNLINK_RECEIPT",
        before_snapshot={"linked_receipt_id": prev_receipt_id},
    )

    return tx
