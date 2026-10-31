from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.people import people_bp
from app.routes.funds import funds_bp
from app.routes.receipts import receipts_bp
from app.routes.bank_accounts import bank_accounts_bp
from app.routes.bank_transactions import bank_transactions_bp
from app.routes.expenses import expenses_bp
from app.routes.pocket_money import pocket_money_bp
from app.routes.settlements import settlements_bp
from app.routes.reports import reports_bp
from app.routes.voice_notes import voice_notes_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "people_bp",
    "funds_bp",
    "receipts_bp",
    "bank_accounts_bp",
    "bank_transactions_bp",
    "expenses_bp",
    "pocket_money_bp",
    "settlements_bp",
    "reports_bp",
    "voice_notes_bp",
]
