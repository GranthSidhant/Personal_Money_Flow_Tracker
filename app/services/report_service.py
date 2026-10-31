import io
import csv
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from app.extensions import db
from app.models.expense import Expense
from app.models.receipt import Receipt
from app.models.fund import Fund
from app.models.person import Person
from app.models.settlement import Settlement
from app.models.pocket_money_entry import PocketMoneyEntry
from app.models.bank_transaction import BankTransaction
from app.models.bank_account import BankAccount
from app.models.category import Category
from app.services.balance_service import get_all_people_summaries, get_total_entrusted_balance
from app.services.bank_balance_service import get_all_bank_accounts_summary, get_combined_bank_balances
from app.services.pocket_money_service import get_pocket_money_balance
from app.services.allocation_service import get_spending_by_category
from app.services.settlement_service import get_outstanding_receivable
from app.utils.money import format_inr, paise_to_rupees


def get_monthly_cashflow_trend(user_id: int, months: int = 6) -> List[Dict[str, Any]]:
    """
    Generate last N months trend for money received vs expenses spent.
    """
    now = datetime.now(timezone.utc)
    monthly_data = []

    for i in range(months - 1, -1, -1):
        # Calculate year and month
        month_target = (now.month - i - 1) % 12 + 1
        year_target = now.year + (now.month - i - 1) // 12
        
        start_of_month = datetime(year_target, month_target, 1, tzinfo=timezone.utc)
        if month_target == 12:
            end_of_month = datetime(year_target + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_of_month = datetime(year_target, month_target + 1, 1, tzinfo=timezone.utc)

        # Money in (Receipts in this month)
        money_in = (
            db.session.query(func.coalesce(func.sum(Receipt.amount_paise), 0))
            .filter(
                Receipt.user_id == user_id,
                Receipt.received_at >= start_of_month,
                Receipt.received_at < end_of_month,
            )
            .scalar()
        )

        # Money out (Expenses in this month)
        money_out = (
            db.session.query(func.coalesce(func.sum(Expense.total_amount_paise), 0))
            .filter(
                Expense.user_id == user_id,
                Expense.expense_at >= start_of_month,
                Expense.expense_at < end_of_month,
            )
            .scalar()
        )

        monthly_data.append({
            "month_label": start_of_month.strftime("%b %Y"),
            "money_in_paise": money_in,
            "money_out_paise": money_out,
            "net_flow_paise": money_in - money_out,
        })

    return monthly_data


def generate_transactions_csv(user_id: int) -> str:
    """
    Generate a complete, user-scoped CSV containing all transactions.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Transaction Type",
        "Date",
        "Title / Description",
        "Entity / Person",
        "Source / Account",
        "Amount (INR)",
        "Notes / Narration",
        "Reference ID",
    ])

    # 1. Receipts (Money In)
    receipts = Receipt.query.filter_by(user_id=user_id).order_by(Receipt.received_at.desc()).all()
    for r in receipts:
        writer.writerow([
            "RECEIPT (MONEY IN)",
            r.received_at.strftime("%Y-%m-%d %H:%M"),
            f"Receipt for {r.fund.title}",
            r.fund.person.name,
            f"Fund: {r.fund.title}",
            f"{paise_to_rupees(r.amount_paise):.2f}",
            r.notes or "",
            r.reference_id or "",
        ])

    # 2. Expenses (Money Out)
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.expense_at.desc()).all()
    for e in expenses:
        alloc_sources = [a.fund.title if a.fund else "Pocket Money" for a in e.allocations]
        writer.writerow([
            "EXPENSE",
            e.expense_at.strftime("%Y-%m-%d %H:%M"),
            e.title,
            e.merchant or "",
            ", ".join(alloc_sources),
            f"-{paise_to_rupees(e.total_amount_paise):.2f}",
            e.description or "",
            e.reference_id or "",
        ])

    # 3. Settlements
    settlements = Settlement.query.filter_by(user_id=user_id).order_by(Settlement.settlement_at.desc()).all()
    for s in settlements:
        writer.writerow([
            f"SETTLEMENT ({s.settlement_type})",
            s.settlement_at.strftime("%Y-%m-%d %H:%M"),
            s.settlement_type,
            s.person.name,
            s.fund.title if s.fund else "Direct Settlement",
            f"{paise_to_rupees(s.amount_paise):.2f}",
            s.notes or "",
            "",
        ])

    # 4. Bank Transactions
    bank_txs = BankTransaction.query.filter_by(user_id=user_id).order_by(BankTransaction.transaction_at.desc()).all()
    for bt in bank_txs:
        writer.writerow([
            f"BANK ({bt.transaction_type})",
            bt.transaction_at.strftime("%Y-%m-%d %H:%M"),
            bt.description,
            bt.person.name if bt.person else "",
            bt.bank_account.account_nickname,
            f"{paise_to_rupees(bt.amount_paise):.2f}" if bt.is_credit else f"-{paise_to_rupees(bt.amount_paise):.2f}",
            bt.notes or "",
            bt.reference_id or "",
        ])

    return output.getvalue()


def generate_excel_workbook(user_id: int) -> io.BytesIO:
    """
    Generate a professional multi-sheet Excel workbook using openpyxl.
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    border_style = Side(border_style="thin", color="E5E7EB")
    cell_border = Border(top=border_style, bottom=border_style, left=border_style, right=border_style)

    # Sheet 1: Financial Summary
    ws_summary = wb.create_sheet(title="Financial Summary")
    ws_summary.append(["Metric", "Value (INR)"])
    for cell in ws_summary[1]:
        cell.font = header_font
        cell.fill = header_fill

    pocket_bal = get_pocket_money_balance(user_id)
    entrusted_bal = get_total_entrusted_balance(user_id)
    bank_bal = get_combined_bank_balances(user_id)
    receivables = get_outstanding_receivable(user_id)

    metrics = [
        ("Current Entrusted Funds Balance", paise_to_rupees(entrusted_bal)),
        ("Pocket Money Balance", paise_to_rupees(pocket_bal["current_balance_paise"])),
        ("Combined Bank Accounts Balance", paise_to_rupees(bank_bal)),
        ("Pending Receivables (Reimbursements Owed)", paise_to_rupees(receivables)),
    ]
    for row in metrics:
        ws_summary.append(row)

    # Sheet 2: Expenses
    ws_exp = wb.create_sheet(title="Expenses")
    ws_exp.append(["ID", "Date", "Title", "Category", "Merchant", "Amount (INR)", "Funding Sources", "Notes"])
    for cell in ws_exp[1]:
        cell.font = header_font
        cell.fill = header_fill

    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.expense_at.desc()).all()
    for e in expenses:
        sources = ", ".join([a.fund.title if a.fund else "Pocket Money" for a in e.allocations])
        ws_exp.append([
            e.id,
            e.expense_at.strftime("%Y-%m-%d %H:%M"),
            e.title,
            e.category.name if e.category else "Uncategorized",
            e.merchant or "",
            paise_to_rupees(e.total_amount_paise),
            sources,
            e.description or "",
        ])

    # Sheet 3: Receipts
    ws_rec = wb.create_sheet(title="Receipts")
    ws_rec.append(["ID", "Date", "Fund", "Person", "Amount (INR)", "Payment Method", "Notes"])
    for cell in ws_rec[1]:
        cell.font = header_font
        cell.fill = header_fill

    receipts = Receipt.query.filter_by(user_id=user_id).order_by(Receipt.received_at.desc()).all()
    for r in receipts:
        ws_rec.append([
            r.id,
            r.received_at.strftime("%Y-%m-%d %H:%M"),
            r.fund.title,
            r.fund.person.name,
            paise_to_rupees(r.amount_paise),
            r.payment_method or "",
            r.notes or "",
        ])

    # Sheet 4: Settlements & Pocket Money
    ws_set = wb.create_sheet(title="Settlements")
    ws_set.append(["ID", "Date", "Type", "Person", "Fund / Related", "Amount (INR)", "Notes"])
    for cell in ws_set[1]:
        cell.font = header_font
        cell.fill = header_fill

    settlements = Settlement.query.filter_by(user_id=user_id).order_by(Settlement.settlement_at.desc()).all()
    for s in settlements:
        ws_set.append([
            s.id,
            s.settlement_at.strftime("%Y-%m-%d %H:%M"),
            s.settlement_type,
            s.person.name,
            s.fund.title if s.fund else "",
            paise_to_rupees(s.amount_paise),
            s.notes or "",
        ])

    # Autofit column widths
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_user_json_backup(user_id: int) -> Dict[str, Any]:
    """
    Generate a complete, isolated JSON backup of all user financial records.
    """
    people = Person.query.filter_by(user_id=user_id).all()
    funds = Fund.query.filter_by(user_id=user_id).all()
    receipts = Receipt.query.filter_by(user_id=user_id).all()
    categories = Category.query.filter_by(user_id=user_id).all()
    expenses = Expense.query.filter_by(user_id=user_id).all()
    settlements = Settlement.query.filter_by(user_id=user_id).all()
    pocket_entries = PocketMoneyEntry.query.filter_by(user_id=user_id).all()
    bank_accounts = BankAccount.query.filter_by(user_id=user_id).all()
    bank_txs = BankTransaction.query.filter_by(user_id=user_id).all()

    return {
        "version": "1.0",
        "app": "Personal Money Flow Tracker",
        "backup_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "data": {
            "people": [
                {
                    "id": p.id,
                    "name": p.name,
                    "relationship": p.relationship,
                    "phone": p.phone,
                    "email": p.email,
                    "notes": p.notes,
                }
                for p in people
            ],
            "funds": [
                {
                    "id": f.id,
                    "person_id": f.person_id,
                    "title": f.title,
                    "purpose": f.purpose,
                    "status": f.status,
                }
                for f in funds
            ],
            "receipts": [
                {
                    "id": r.id,
                    "fund_id": r.fund_id,
                    "amount_paise": r.amount_paise,
                    "received_at": r.received_at.isoformat(),
                    "payment_method": r.payment_method,
                    "notes": r.notes,
                }
                for r in receipts
            ],
            "expenses": [
                {
                    "id": e.id,
                    "category_id": e.category_id,
                    "title": e.title,
                    "total_amount_paise": e.total_amount_paise,
                    "expense_at": e.expense_at.isoformat(),
                    "merchant": e.merchant,
                    "description": e.description,
                    "allocations": [
                        {
                            "source_type": a.source_type,
                            "fund_id": a.fund_id,
                            "person_id": a.person_id,
                            "allocated_amount_paise": a.allocated_amount_paise,
                            "reimbursement_expected": a.reimbursement_expected,
                        }
                        for a in e.allocations
                    ],
                }
                for e in expenses
            ],
            "settlements": [
                {
                    "id": s.id,
                    "person_id": s.person_id,
                    "fund_id": s.fund_id,
                    "settlement_type": s.settlement_type,
                    "amount_paise": s.amount_paise,
                    "settlement_at": s.settlement_at.isoformat(),
                    "notes": s.notes,
                }
                for s in settlements
            ],
            "pocket_money_entries": [
                {
                    "id": pe.id,
                    "entry_type": pe.entry_type,
                    "amount_paise": pe.amount_paise,
                    "description": pe.description,
                    "occurred_at": pe.occurred_at.isoformat(),
                }
                for pe in pocket_entries
            ],
            "bank_accounts": [
                {
                    "id": ba.id,
                    "account_nickname": ba.account_nickname,
                    "bank_name": ba.bank_name,
                    "account_type": ba.account_type,
                    "opening_balance_paise": ba.opening_balance_paise,
                    "opening_balance_date": ba.opening_balance_date.isoformat(),
                }
                for ba in bank_accounts
            ],
        },
    }
