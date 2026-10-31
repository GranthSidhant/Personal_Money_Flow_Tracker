# Personal Money Flow Tracker

> **Every rupee has a source, every expense has an allocation, and every remaining amount has a clear owner and history.**

Personal Money Flow Tracker is a responsive web application designed for personal finance and money-flow management. Unlike conventional expense trackers, it preserves the relational integrity between **People**, **Funds**, **Receipts**, **Expenses**, **Allocations**, **Bank Accounts**, **Pocket Money**, **Quick Notes**, and **AI Drafts**.

---

## 🎨 UI & Design Baseline

Refer to [`UI.png`](UI.png) for the baseline interface design, featuring:
- Responsive desktop & mobile views
- Curated light & dark themes with instant switching
- People & Funds management
- Manual Bank Account tracking & reconciliation
- Multi-source expense allocations
- Quick Voice Notes & optional location context
- AI-assisted transaction draft inbox

---

## 📋 Implementation Status

| Phase | Milestone | Status |
| :--- | :--- | :--- |
| **Phase 1** | Foundation & Authentication (App factory, Auth, User isolation, DB migrations, UI baseline) | ✅ **Completed** |
| **Phase 2** | People, Funds, and Receipts (Bank accounts, manual tx, unclassified tx, multi-receipt funds) | ✅ **Completed** |
| **Phase 3** | Expenses and Allocations (Multi-fund split, personal contributions, overdraw prevention, Leaflet map) | ✅ **Completed** |
| **Phase 4** | Pocket Money and Settlements (Ledger transfers, returns, reimbursements, atomic double entry) | ✅ **Completed** |
| **Phase 5** | Dashboard and Reports (Chart.js analytics, cashflow trend, Excel/CSV exports, JSON backup) | ✅ **Completed** |
| **Phase 6** | Quick Voice Notes & Location (MediaRecorder, waveforms, optional geolocation) | ⏳ Up Next |
| **Phase 7** | AI Transactions Inbox (Gemini extraction, provenance, manual approval) | ⏳ Pending |
| **Phase 8** | PWA & Offline Drafts (Service Worker, IndexedDB sync queue, conflict resolution) | ⏳ Pending |
| **Phase 9** | Production Hardening & Deployment (PostgreSQL, Gunicorn, HTTPS, audit) | ⏳ Pending |

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
# Run database migrations to apply latest schema
flask --app run.py db upgrade
```

### 5. Running the Application
```bash
python run.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🧪 Running Automated Tests

Run the full automated test suite with pytest:
```bash
python -m pytest -v
```
All tests verify:
- Secure password hashing and credential validation
- Session-based authentication (login/logout/profile/password update)
- Route protection and multi-user data isolation
