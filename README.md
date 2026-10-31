# Personal Money Flow Tracker

> **Every rupee has a source, every expense has an allocation, and every remaining amount has a clear owner and history.**

Personal Money Flow Tracker is a responsive web application designed for personal finance and money-flow management. Unlike conventional expense trackers, it preserves the relational integrity between **People**, **Funds**, **Receipts**, **Expenses**, **Allocations**, **Bank Accounts**, **Pocket Money**, and **Quick Voice Notes**.

---

## 🎨 UI & Design Baseline

Refer to [`UI.png`](UI.png) for the baseline interface design, featuring:
- Responsive desktop & mobile views
- Curated light & dark themes with instant switching
- People & Funds management
- Manual Bank Account tracking & reconciliation
- Multi-source expense allocations
- Quick Voice Notes & optional location context
- Direct Voice-to-Expense Linking
- Progressive Web App (PWA) with offline draft capture & background sync

---

## 📋 Implementation Status & Roadmap

| Phase | Milestone | Status |
| :--- | :--- | :--- |
| **Phase 1** | Foundation & Authentication (App factory, Auth, User isolation, DB migrations, UI baseline) | ✅ **Completed** |
| **Phase 2** | People, Funds, and Receipts (Bank accounts, manual tx, unclassified tx, multi-receipt funds) | ✅ **Completed** |
| **Phase 3** | Expenses and Allocations (Multi-fund split, personal contributions, overdraw prevention, Leaflet map) | ✅ **Completed** |
| **Phase 4** | Pocket Money and Settlements (Ledger transfers, returns, reimbursements, atomic double entry) | ✅ **Completed** |
| **Phase 5** | Dashboard and Reports (Chart.js analytics, cashflow trend, Excel/CSV exports, JSON backup) | ✅ **Completed** |
| **Phase 6** | Quick Voice Notes & Location (MediaRecorder, waveforms, authenticated audio streaming, optional location) | ✅ **Completed** |
| **Phase 7** | Voice Expense Linking (Direct expense association, user-controlled financial ledger linking) | ✅ **Completed** |
| **Phase 8** | PWA & Offline Drafts (Web App Manifest, Service Worker app-shell caching, IndexedDB draft queue, idempotent sync) | ✅ **Completed** |
| **Phase 9** | Production Hardening & Deployment (PostgreSQL, Gunicorn, HTTPS, security audit, access control) | ✅ **Completed** |

---

## 🚀 Local Development Setup

### 1. Prerequisites
- Python 3.10+ (tested with Python 3.14)
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/GranthSidhant/Personal_Money_Flow_Tracker.git
cd Personal_Money_Flow_Tracker

# Create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Database Setup & Migrations
```bash
# Apply all schema migrations
flask db upgrade
```

### 5. Running the Application
```bash
python run.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🧪 Automated Testing

The application includes an exhaustive test suite covering all business rules, strict integer-paise calculations, duplicate approval prevention, cross-user isolation, and security headers:

```bash
python -m pytest -v
```

**Results:**
- **50 passed tests** in ~8.7s
- 100% passing test rate
- Test categories:
  - `test_auth.py` & `test_user_isolation.py`: Authentication, session security, password hashing, and data tenancy isolation.
  - `test_bank_accounts.py` & `test_bank_transactions.py`: Manual bank tracking, balance calculation, and reconciliation.
  - `test_funds.py` & `test_receipts.py`: People, independent funds, and incoming receipts.
  - `test_expenses.py`: Single and multi-source allocations, overdraw prevention, and refund reversals.
  - `test_pocket_money.py` & `test_settlements.py`: Double-entry atomic transfers, returns, and reimbursements.
  - `test_reports.py`: CSV, Excel, and user-scoped JSON backup/restore exports.
  - `test_voice_notes.py`: Audio storage isolation, authenticated playback, and Leaflet location capture.
  - `test_sync.py`: PWA manifest, service worker, offline shell, and idempotent IndexedDB sync.
  - `test_security_production.py`: Security headers, production cookie settings, and postgres URL normalization.

---

## 🌐 Production Deployment

### 1. Environment Variables
In production, set the following environment variables:
```bash
export FLASK_ENV=production
export SECRET_KEY="generate-a-strong-cryptographic-key-here"
export DATABASE_URL="postgresql://user:password@localhost:5432/money_flow_db"
export UPLOAD_FOLDER="/var/lib/moneyflow/uploads"
```

### 2. Running with Gunicorn
Run the production WSGI application with Gunicorn:
```bash
gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app
```

### 3. Nginx Reverse Proxy with HTTPS
```nginx
server {
    listen 443 ssl http2;
    server_name moneyflow.example.com;

    ssl_certificate /etc/letsencrypt/live/moneyflow.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/moneyflow.example.com/privkey.pem;

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## 🔒 Security & Privacy Guarantees

- **Integer Paise Arithmetic:** All monetary math is stored and calculated in integer paise (`₹1.00 = 100 paise`), preventing binary floating-point roundoff errors.
- **Deterministic User Control:** Voice recordings are strictly user-managed audio memos that can be explicitly linked to expenses without automated modifications.
- **Audio & Media Isolation:** Audio recordings are stored in user-isolated directories outside the static tree and served exclusively through authenticated routes checking `voice_note.user_id == current_user.id`.
- **Zero-Paid Requirement:** The application is 100% functional locally with zero paid third-party dependencies.
