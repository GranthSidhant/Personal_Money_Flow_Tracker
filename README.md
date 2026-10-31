# Personal Money Flow Tracker

> **Every rupee has a source, every expense has an allocation, and every remaining amount has a clear owner and history.**

Personal Money Flow Tracker is a responsive web application designed for personal finance and money-flow management. Unlike conventional expense trackers, it preserves the relational integrity between **People**, **Funds**, **Receipts**, **Expenses**, **Allocations**, **Bank Accounts**, **Pocket Money**, **Quick Notes**, and **AI Drafts**.

---

## 🎨 UI & Design Baseline

Refer to [`UI.png`](UI.png) for the baseline interface design, featuring:
- Responsive desktop & mobile views
- Curated light & dark themes
- People & Funds management
- Manual Bank Account tracking & reconciliation
- Multi-source expense allocations
- Quick Voice Notes & optional location context
- AI-assisted transaction draft inbox

---

## 📋 Product Specifications & Architecture

Full architectural and product requirements are detailed in [`project_requirements.md`](project_requirements.md):
- **Document Version:** 2.0 (Approved requirements baseline)
- **Tech Stack:** Python 3, Flask, SQLAlchemy, SQLite (Dev) / PostgreSQL (Prod), Vanilla JS / Bootstrap 5, Chart.js, Leaflet, optional Gemini API
- **Financial Integrity:** Integer paise calculations, double-entry tracking for transfers, no silent overdraws, immutable audit trail

---

## 🚀 Getting Started

*(Application foundation and Phase 1 implementation in progress)*

```bash
# Clone the repository
git clone https://github.com/GranthSidhant/Personal_Money_Flow_Tracker.git
cd Personal_Money_Flow_Tracker
```
