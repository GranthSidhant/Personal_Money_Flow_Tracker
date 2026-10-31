import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.services.report_service import (
    get_monthly_cashflow_trend,
    generate_transactions_csv,
    generate_excel_workbook,
    export_user_json_backup,
)
from app.services.balance_service import get_all_people_summaries, get_total_entrusted_balance
from app.services.bank_balance_service import get_all_bank_accounts_summary, get_combined_bank_balances
from app.services.pocket_money_service import get_pocket_money_balance
from app.services.allocation_service import get_spending_by_category
from app.services.settlement_service import get_outstanding_receivable
from app.utils.money import format_inr, paise_to_rupees

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports")
@login_required
def index():
    """Visual analytics & reporting dashboard matching UI.png specs."""
    cashflow_trend = get_monthly_cashflow_trend(current_user.id, months=6)
    category_breakdown = get_spending_by_category(current_user.id)
    people_summaries = get_all_people_summaries(current_user.id)
    bank_summaries = get_all_bank_accounts_summary(current_user.id)

    pocket_info = get_pocket_money_balance(current_user.id)
    entrusted_total = get_total_entrusted_balance(current_user.id)
    combined_bank = get_combined_bank_balances(current_user.id)
    receivables = get_outstanding_receivable(current_user.id)

    # Convert paise to rupees for Chart.js
    trend_labels = [item["month_label"] for item in cashflow_trend]
    trend_income = [paise_to_rupees(item["money_in_paise"]) for item in cashflow_trend]
    trend_expense = [paise_to_rupees(item["money_out_paise"]) for item in cashflow_trend]

    cat_labels = [c["name"] for c in category_breakdown]
    cat_amounts = [paise_to_rupees(c["total_paise"]) for c in category_breakdown]

    return render_template(
        "reports/index.html",
        cashflow_trend=cashflow_trend,
        category_breakdown=category_breakdown,
        people_summaries=people_summaries,
        bank_summaries=bank_summaries,
        pocket_info=pocket_info,
        entrusted_total=entrusted_total,
        combined_bank=combined_bank,
        receivables=receivables,
        trend_labels=trend_labels,
        trend_income=trend_income,
        trend_expense=trend_expense,
        cat_labels=cat_labels,
        cat_amounts=cat_amounts,
    )


@reports_bp.route("/reports/export/csv")
@login_required
def export_csv():
    """Download user-scoped CSV of all money flow transactions."""
    csv_data = generate_transactions_csv(current_user.id)
    filename = f"money_flow_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/reports/export/excel")
@login_required
def export_excel():
    """Download user-scoped multi-sheet Excel report."""
    excel_buf = generate_excel_workbook(current_user.id)
    filename = f"money_flow_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        excel_buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route("/reports/backup")
@login_required
def backup_json():
    """Download complete user data backup as JSON."""
    backup_data = export_user_json_backup(current_user.id)
    filename = f"personal_money_flow_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        json.dumps(backup_data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/reports/restore", methods=["POST"])
@login_required
def restore_json():
    """Restore or inspect uploaded JSON backup."""
    file = request.files.get("backup_file")
    if not file or not file.filename.endswith(".json"):
        flash("Please upload a valid JSON backup file.", "danger")
        return redirect(url_for("reports.index"))

    try:
        content = json.loads(file.read().decode("utf-8"))
        if "version" not in content or "data" not in content:
            flash("Invalid backup file format.", "danger")
            return redirect(url_for("reports.index"))

        item_count = sum(len(items) for items in content["data"].values())
        flash(f"Backup validated successfully ({item_count} items found across {len(content['data'])} entities).", "success")
    except Exception as e:
        flash(f"Error reading backup file: {str(e)}", "danger")

    return redirect(url_for("reports.index"))
