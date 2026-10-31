# Personal Money Flow Tracker

## Complete Product Requirements & Antigravity Development Specification

**Document version:** 2.0\
**Status:** Approved requirements baseline\
**Project type:** Personal finance and money-flow management web
application\
**Primary deployment:** Hosted, multi-user web application\
**Development approach:** Local-first development, phased
implementation, free/open-source-first stack

> **Product promise:** Every rupee has a source, every expense has an
> allocation, and every remaining amount has a clear owner and history.

------------------------------------------------------------------------

# 1. Product overview

Personal Money Flow Tracker is a responsive web application for tracking
money received from other people, purchases made on their behalf,
personal expenses, personal contributions, remaining entrusted funds,
reimbursements, returns, and transfers into personal Pocket Money.

It is not a conventional income-and-expense tracker. Its central purpose
is to preserve the relationship between:

1.  **People** --- who provided or received money.
2.  **Funds** --- the purpose-based pools created from money received.
3.  **Receipts** --- each individual incoming payment.
4.  **Expenses** --- purchases and payments.
5.  **Allocations** --- exactly which sources funded each expense.
6.  **Settlements and transfers** --- money returned, reimbursed,
    recovered, or moved into Pocket Money.
7.  **Quick Notes** --- voice recordings and optional location context
    captured at the time.
8.  **AI drafts** --- suggestions extracted from voice notes that
    require the user's review before becoming actual financial records.

The app must support one individual using it privately, while its
architecture must allow multiple registered users on a hosted instance.
Every user's data must remain isolated.

## 1.1 Main user problems to solve

-   Money from different people gets mixed together.
-   A person may send money multiple times for different purposes.
-   Some transfers are additions to an existing purpose/fund, while
    others should remain separate.
-   Expenses may use more than one person's fund and/or the user's own
    money.
-   The user may spend more than a fund contains.
-   The user may be owed reimbursement, or may have voluntarily
    contributed.
-   Unspent money may be returned or transferred to Pocket Money with
    permission.
-   The user may forget an expense if they cannot enter it immediately.
-   Voice notes and the time/location of capture can help reconstruct
    what happened.
-   AI may help turn voice notes into draft receipts and expenses, but
    must never silently alter the ledger.

## 1.2 Product principles

-   Financial correctness before visual polish.
-   Manual entry must always work without AI.
-   Voice recording must work without AI.
-   AI suggestions must remain drafts until explicitly approved.
-   Location capture must be optional and user-initiated.
-   No continuous/background location tracking.
-   No automatic merging of funds.
-   No automatic spending of one person's remaining fund to cover
    another fund's shortfall.
-   No hidden financial changes: every material change must be
    traceable.
-   Free/open-source-first technologies; paid services must never be
    mandatory for core operation.
-   Easy local installation and portable deployment.
-   Privacy, backup, and export are first-class requirements.

------------------------------------------------------------------------

# 2. Confirmed product decisions

The following decisions are approved and must be reflected in
implementation.

  ---------------------------------------------------------------------
  Area                               Confirmed decision
  ---------------------------------- ----------------------------------
  Fund handling                      Both: create a new fund or add a
                                     receipt to an existing fund,
                                     chosen by the user

  Overspending                       Both: reimbursement expected or
                                     voluntary/non-recoverable personal
                                     contribution, chosen per
                                     allocation

  Bank tracking                      Logical money tracking only in the
                                     initial version; no claim to know
                                     actual bank balances

  Personal expenses                  Both: separate personal expense
                                     entry and personal allocations
                                     alongside other funds

  Deployment                         Hosted web application accessible
                                     from different devices

  Local use                          Must remain straightforward to run
                                     locally

  Pocket Money                       Explicit full or partial transfers
                                     from entrusted funds, with
                                     complete history

  Voice notes                        Quick recording and playback with
                                     automatic timestamp

  Location                           Optional, permission-based capture
                                     at recording/expense time only

  AI                                 Optional Gemini integration;
                                     drafts require manual review and
                                     approval

  Offline                            PWA support and offline draft
                                     capture, with synchronization when
                                     connected

  Technology                         Free/open-source-first; paid
                                     APIs/services must not be required
                                     for core functionality
  ---------------------------------------------------------------------

------------------------------------------------------------------------

# 3. Scope and release strategy

## 3.1 Core release (MVP)

The first usable release must include:

-   Registration, login, logout, and user data isolation.
-   People management.
-   Multiple bank accounts and manual bank transaction tracking.
-   Funds and incoming receipts.
-   Add money to an existing fund or create a new fund.
-   Expense recording and multi-source allocations.
-   Personal money allocations and personal expenses.
-   Reimbursement expected vs not expected.
-   Pocket Money ledger and transfers from funds.
-   Settlements and returns.
-   Dashboard and basic reports.
-   Search, filters, edit/correction history.
-   Bank transaction reconciliation and unclassified transaction review.
-   CSV export and database backup.
-   Responsive interface.

## 3.2 Follow-on release: Quick Capture

-   Voice recording in the browser.
-   Audio playback, deletion, and optional text note.
-   Automatic recording timestamp and duration.
-   Optional location capture.
-   Unreviewed recording list and reminders.
-   Attach a recording to an existing transaction.
-   Offline voice/text draft capture where browser support permits.

## 3.3 Follow-on release: AI assistance

-   Optional Gemini provider integration.
-   Audio transcription or transcription from a locally/user-provided
    transcript.
-   Structured extraction of incoming receipts, expenses, people,
    purposes, dates, amounts, categories, and possible fund
    relationships.
-   AI Transactions Inbox.
-   Manual editing, matching, splitting, approving, or rejecting
    suggestions.
-   AI provenance and confidence display.
-   No direct writes from AI to the financial ledger.

## 3.4 Follow-on release: PWA and synchronization hardening

-   Installable PWA.
-   Service worker and application-shell caching.
-   IndexedDB for offline drafts.
-   Pending-sync queue.
-   Retry and conflict handling.
-   Clear sync status and user-controlled retry.
-   Never silently treat an unsynchronized draft as a saved ledger
    transaction.

Features may be developed in stages, but the architecture and PRD must
account for all of them.

------------------------------------------------------------------------

# 4. User accounts, authentication, and privacy boundaries

## 4.1 Authentication

Implement:

-   User registration: name, email, password, password confirmation.
-   Login and logout.
-   Secure password hashing using a maintained password-hashing library
    supported by the framework.
-   Session-based authentication.
-   Password change.
-   Password reset only if a reliable email delivery method is
    configured; otherwise provide a documented administrator/manual
    recovery approach for local development.
-   Account profile and account deletion/export flows.

Do not store plain-text passwords. Do not commit secrets or production
data to source control.

## 4.2 Multi-user isolation

Every business record must be associated with the authenticated user,
directly or through a parent record.

Enforce ownership checks on the server for every read, create, update,
delete, upload, export, and download operation. Never rely only on
hiding data in the frontend.

A user must not be able to access another user's people, funds,
receipts, expenses, allocations, settlements, notes, audio files,
locations, AI drafts, exports, or backups by changing an ID or URL.

Use database constraints and indexes where appropriate. Add automated
cross-user access tests.

## 4.3 Sensitive data controls

-   Voice recordings, location data, receipts, and financial records are
    private.
-   Ask for browser location permission only when the user initiates a
    location-enabled capture.
-   Do not request location permission at sign-up or on every page load.
-   Do not continuously track location or collect it in the background.
-   Make location capture visibly optional.
-   Allow users to remove location metadata from a note or transaction.
-   Provide deletion controls for audio recordings, subject to any
    retention policy the user chooses.
-   Explain what data is sent to Gemini before an AI request is made.
-   Do not send audio, financial data, or location to an AI provider
    unless the user has enabled the feature and initiated processing.
-   Never place secrets or API keys in frontend JavaScript.
-   Provide export and backup capabilities.
-   Document that hosted free tiers may have provider-specific
    retention, storage, and availability limitations.

------------------------------------------------------------------------

# 5. Core financial concepts and rules

## 5.1 People

A person is an individual or organization from whom the user receives
money or for whom the user records money-related activity.

Examples: Mother, Father, friend, roommate, colleague.

A person can have multiple funds and multiple receipts.

## 5.2 Funds

A fund is a purpose-based pool associated with a person. Examples:

-   Mother --- October groceries
-   Father --- College supplies
-   Friend --- Shared travel booking

Each fund must be independently traceable.

When money arrives, the user chooses:

1.  Create a new fund; or
2.  Add a new receipt to an existing fund.

Adding money to an existing fund must create a separate receipt record.
Never overwrite or erase the original receipt.

Do not automatically merge funds merely because the person or purpose is
the same.

## 5.3 Receipts (money received)

Every incoming transfer must be recorded as a receipt with:

-   Person.
-   Fund.
-   Amount.
-   Date/time received.
-   Purpose or description.
-   Payment method (optional).
-   UPI/bank reference (optional).
-   Notes.
-   Creation timestamp.

A receipt may create a new fund or be linked to an existing fund.

## 5.4 Expenses

An expense represents one purchase/payment. It may be funded by one or
more sources.

Fields:

-   Title.
-   Total amount.
-   Date/time of expense.
-   Category.
-   Merchant/payee (optional).
-   Description.
-   Payment method (optional).
-   Reference ID (optional).
-   Receipt image/file (optional).
-   Notes.
-   Optional linked voice note.
-   Optional location metadata.

## 5.5 Expense allocations

A separate allocation record identifies the source of each portion of an
expense.

Supported sources:

-   A specific entrusted fund.
-   The user's Pocket Money/personal source.

Example: ₹3,000 purchase: - Mother's fund: ₹1,500. - Father's fund:
₹1,000. - Pocket Money: ₹500.

The sum of allocations must equal the expense total before an expense
can be finalized.

For personal allocations, the user must choose: - Reimbursement
expected; or - No reimbursement expected.

A shortfall in a fund must not silently draw from another fund. The user
must explicitly allocate the shortfall to Pocket Money or another
selected source.

## 5.6 Pocket Money

Pocket Money is the logical personal-money ledger. It is not a live bank
balance and must never be described as the user's actual bank/UPI
balance.

Pocket Money records:

-   Money the user adds as personal opening money or personal income, if
    enabled.
-   Personal contributions to other people's expenses.
-   Personal expenses.
-   Reimbursements received.
-   Authorized transfers from entrusted funds.
-   Corrections/reversals.

Personal expenses should be recorded as expenses funded by Pocket Money,
with a category and optional merchant/notes.

## 5.7 Fund balance

For a fund:

**Available entrusted balance = total receipts − expense allocations
from that fund − money returned to the provider − authorized transfers
to Pocket Money.**

Refunds against an expense must reverse the appropriate original
allocation and restore the relevant source.

Do not count an internal transfer to Pocket Money as new external
income.

## 5.8 Personal contribution and receivables

Track personal contributions separately from fund balances.

-   Recoverable contribution: amount the user expects the relevant
    person to reimburse.
-   Non-recoverable contribution: voluntary amount the user does not
    expect back.

Outstanding receivable:

**Recoverable personal contributions − reimbursements allocated to those
contributions.**

Support partial reimbursements. Each reimbursement must be linked to the
relevant person and, where possible, the original contribution/expense.

## 5.9 Returns and settlements

Support:

-   Return unused money to the person who provided it.
-   Receive reimbursement for a personal contribution.
-   Transfer unused entrusted money to Pocket Money with permission.
-   Record additional money received.
-   Record recovery of personal contributions.
-   Partial settlements.

Every settlement must include amount, date, person, related fund and/or
expense where applicable, settlement type, notes, and audit information.

A settlement cannot exceed the applicable outstanding amount unless a
separately described adjustment is explicitly recorded.

## 5.10 Fund closure

A fund is not automatically closed when its balance becomes zero.

Allow statuses such as: - Active - Partially used - Fully allocated -
Settled - Archived

Require explicit user action to settle/close/archive a fund. Warn if
unresolved balance or receivable remains.

------------------------------------------------------------------------

# 6. Pocket Money transfers and complete history

This feature is mandatory.

## 6.1 Transfer action

On a fund detail page, provide an action such as **Transfer to Pocket
Money**.

Allow: - Full remaining balance transfer. - Partial transfer. -
User-entered amount. - Date/time. - Notes. - Confirmation before saving.

Only permit transfers up to the fund's available entrusted balance.

## 6.2 Ledger behavior

A transfer must create linked ledger entries:

1.  A debit/reduction against the entrusted fund.
2.  A credit/addition to Pocket Money.

Both entries must be created atomically in one database transaction.

Example:

Mother's fund has ₹1,500 remaining. User transfers ₹500.

History: - Mother's fund: transfer to Pocket Money, −₹500. - Pocket
Money: received from Mother's fund, +₹500. - Mother's fund remaining
balance: ₹1,000. - Pocket Money increases by ₹500.

Do not create external income or a new receipt for this operation.

## 6.3 Transfer history

Provide a dedicated history showing:

-   Date/time.
-   From fund/person.
-   To Pocket Money.
-   Amount.
-   Notes.
-   Related transaction ID.
-   Status.

Support filters by date and person. Transfers must be editable only
through a controlled correction/reversal flow, not by silently changing
one side of the ledger.

------------------------------------------------------------------------

# 7. People management

Fields: - ID. - User ID. - Name. - Relationship (optional). - Phone
(optional). - Email (optional). - Notes. - Created/updated timestamps.

Features: - Add, edit, archive. - Search. - Person detail page. - Total
received. - Total spent from their funds. - Current entrusted balance. -
Personal contributions made on their behalf. - Outstanding
reimbursement. - Returns and settlements. - Fund list and complete
transaction timeline.

Deleting a person with financial history should be blocked or replaced
with archive functionality.

------------------------------------------------------------------------

# 8. Bank Accounts and Manual Bank Transaction Tracking

This is a dedicated module for manually recording activity from the
user's own banking applications. It does not connect to banks, UPI apps,
payment providers, or open-banking APIs.

## 8.1 Bank accounts

Allow each user to create and manage multiple bank accounts, for example
Kotak Savings and another bank account.

Fields: - Account nickname. - Bank name. - Account type (savings,
current, other). - Optional masked identifier or last four digits. -
Opening balance in paise. - Opening balance date. - Currency (INR
initially). - Optional notes. - Active/archived status.

Allow users to add, edit, view, and archive accounts. Accounts with
transaction history should be archived rather than destructively
deleted.

Never request or store internet banking passwords, UPI PINs, OTPs, CVVs,
card numbers, or full account numbers.

## 8.2 Manually entered bank transactions

The user manually enters credits and debits seen in their banking app.

Transaction types: - Credit: money received into the account. - Debit:
money spent or transferred out. - Own-account transfer: money moved
between two accounts owned by the same user. - Reversal/refund: a
correction linked to an original transaction where applicable.

Fields: - Bank account. - Transaction type. - Amount in paise. -
Transaction date/time. - Description or bank narration. - Optional
UPI/bank reference ID. - Optional person/counterparty. - Optional
category. - Optional linked receipt, expense, or settlement. - Notes. -
Entry source (manual in the initial release). - Created timestamp.

There must be no bank connection or automatic fetching in the initial
project. This module is a manual ledger.

## 8.3 Connect bank activity to people, funds, receipts, and expenses

A bank transaction may be linked to a corresponding record in the
money-flow system.

Example: - Father sends ₹2,000 to Kotak. - Record a ₹2,000 credit in
Kotak. - Select Father as sender. - Create or select Father's fund and
record the corresponding ₹2,000 receipt. - Later record a ₹500 Kotak
debit for an item purchased for Father. - Link that debit to the expense
and allocate ₹500 from Father's fund.

The bank record and the linked receipt/expense are two views of the same
real-world event. Linking them must never create a duplicate receipt,
expense, income, or expenditure.

When recording a credit, offer: 1. Record bank credit only and classify
it later; or 2. Record bank credit and create/link the receipt and fund
in one guided workflow; or 3. Link the credit to an existing receipt.

When recording a debit, offer: 1. Record bank debit only and classify it
later; or 2. Record bank debit and create/link the expense with its
allocations; or 3. Link the debit to an existing expense.

A user must be able to leave a transaction unclassified and return to it
later.

## 8.4 Person-wise bank activity

Use the existing People records. Do not create a duplicate person for
every bank transaction.

For a bank credit, the user can select who sent the money, enter the
amount/date, and optionally create or link a receipt and fund.

For a bank debit, the user can select who the spending was for, describe
the purchase, and optionally create or link an expense allocated to one
or more funds and/or Pocket Money.

Person selection is optional because not every bank transaction relates
to another person.

## 8.5 Calculated bank account balance

Calculate a bank account's manually tracked balance as:

**Opening balance + credits − debits**, with refunds/reversals and
own-account transfers represented by their appropriate signed entries.

Display this as **Manually tracked balance**. It is only as accurate as
the transactions the user has entered; it is not fetched, verified, or
synchronized with the bank.

Allow an opening balance and date. If the user needs to correct a
balance, record an auditable adjustment transaction with a reason
instead of silently overwriting the calculated balance.

## 8.6 Transfers between the user's own bank accounts

Support transfers between two bank accounts owned by the same user.

Create two linked entries atomically: - Debit from the source account. -
Credit to the destination account.

This is an internal movement, not income or expenditure. Do not create a
person receipt, expense, or Pocket Money income for this transfer.

## 8.7 Unclassified transactions and reconciliation

Provide an unclassified transaction inbox and filters for: -
Unclassified credits. - Unclassified debits. - Transactions linked to
receipts. - Transactions linked to expenses. - Own-account transfers. -
Date range. - Bank account. - Person. - Amount range.

Users can classify an unclassified bank entry later by linking it to an
existing record or creating the relevant receipt/expense.

## 8.8 Bank account history and summaries

Each account page should show: - Opening balance. - Manually tracked
current balance. - Total credits. - Total debits. - Recent transaction
history. - Unclassified transaction count. - Person-wise credits and
spending where linked. - Search and date filters.

Provide an all-accounts view and individual account views. If showing
combined balances, label them **Combined manually tracked bank
balances**.

## 8.9 Separate bank balances from logical money ownership

A bank balance represents money recorded in a physical bank account.
Fund balances and Pocket Money represent the user's logical
classification of money.

These totals can differ because transactions may be unclassified, cash
may be used, a receipt may be entered before its bank entry, or money
may move between accounts.

Never automatically equate a bank balance with Pocket Money or entrusted
fund balances. Do not add bank credits to income totals again when they
are already linked to receipts. Do not add bank debits to expenditure
totals again when they are already linked to expenses.

------------------------------------------------------------------------

# 9. Expense management and categories

Provide standard categories such as: - Groceries - Food - Household -
Shopping - Travel - Education - Bills - Medical - Entertainment -
Subscriptions - Personal - Other

Allow user-created categories.

Features: - Add expense. - Add personal-only expense. - Allocate across
multiple funds and Pocket Money. - Edit with recalculation. - Attach
bill/receipt. - Link a voice note. - Add optional location. - Search and
filter. - Record refund/return against the original expense.

Use an explicit refund/reversal record rather than treating refunds as
new income.

------------------------------------------------------------------------

# 10. Quick Voice Notes

This feature allows the user to record what happened when they do not
have time to enter a formal transaction.

## 10.1 Recording experience

Provide a prominent **Quick Voice Note** action.

The user can: - Start recording. - Pause/resume if supported. - Stop and
save. - Listen to playback. - Rename or add a text note. - Delete the
recording. - Attach it to an existing transaction later. - Request
optional AI processing.

Use the browser MediaRecorder API where supported. Show a clear
unsupported-browser message and provide manual text-note fallback.

## 10.2 Automatic metadata

At capture time, save: - Recording timestamp (server timestamp when
uploaded; client capture time also retained). - Duration. - Audio MIME
type/format. - Optional user-entered title. - Upload/sync status. -
Optional location, only if separately enabled and permission granted.

Do not infer an expense date from the upload date when the original
capture timestamp is available.

## 10.3 Recording statuses

-   Unreviewed
-   Transcription pending
-   Transcribed
-   AI processing pending
-   AI draft created
-   Linked to transaction
-   Archived
-   Rejected
-   Sync pending
-   Sync failed

A recording must remain available for review until the user deletes or
archives it.

## 10.4 Unreviewed-note reminders

Show a count of unreviewed recordings on the dashboard/navigation.

Provide an optional reminder setting. Do not send push notifications or
email unless the user explicitly enables and configures them.

The reminder should be helpful, not intrusive. Provide a quick link to
the unreviewed notes list.

------------------------------------------------------------------------

# 11. Optional location capture

Location is an optional contextual aid, not a requirement for recording
an expense.

## 11.1 User interaction

When starting a voice note or adding an expense, provide an optional
**Attach current location** control.

-   Ask for permission only after the user selects the control.
-   Capture a one-time location fix.
-   Do not continuously track.
-   Do not capture location silently.
-   If permission is denied or unavailable, continue without location.

## 11.2 Stored location data

When consented and available: - Latitude. - Longitude. - Accuracy in
meters. - Capture timestamp. - Optional place label entered by user or
resolved later.

Do not require a paid maps/geocoding API. A map view may use
OpenStreetMap-compatible tools and comply with the provider's usage and
attribution policies.

Location should be visible on the note/transaction detail page and
removable by the user.

Do not send location to Gemini by default. Include it in AI processing
only if the user explicitly chooses to include it.

------------------------------------------------------------------------

# 12. Optional AI transaction assistant

AI is an optional convenience layer. The application must remain fully
functional without it.

## 12.1 Provider integration

-   Initial optional provider: Gemini API.
-   Store the API key only in server-side environment variables.
-   Never expose the key in browser JavaScript or repository files.
-   Provide an AI-enabled/disabled setting.
-   If no API key is configured, hide/disable AI processing while
    keeping recording and manual entry available.
-   Handle quotas, timeouts, unavailable models, and provider errors
    gracefully.
-   Do not assume the free tier is permanent or unlimited.
-   Make it possible to replace the provider later through a provider
    abstraction.

Use a supported Gemini model and current API documentation at
implementation time. Do not hard-code a model name without checking its
availability and pricing/quotas.

## 12.2 AI input and consent

Before sending audio or transcript content to an external AI provider: -
Explain what will be sent. - Obtain an explicit user action. - Allow
transcript-only processing where possible. - Do not send location unless
separately and explicitly selected. - Do not send unrelated account
history.

## 12.3 Structured extraction

The AI may suggest: - Incoming money received. - Sender/person name. -
Amount and currency. - Purpose. - Expense amount. - Expense
description. - Category. - Date/time if clearly stated. - Possible fund
association. - Whether an amount may be a personal contribution. -
Whether reimbursement may be expected.

The AI must distinguish stated facts from guesses. Unknown values must
remain null/unknown, not invented.

If a note says "Mother sent me 2,000 and I spent 1,000 on groceries", AI
may suggest: - Receipt: ₹2,000, person suggestion: Mother. - Expense:
₹1,000, category suggestion: Groceries. - Fund relationship: suggested,
not confirmed.

Do not assume that the expense was paid from that new receipt unless the
statement clearly supports that interpretation. Show ambiguity to the
user.

## 12.4 AI Transactions Inbox

Create a dedicated page named **AI Notes** or **AI Transactions Inbox**.

Each draft should show: - Source voice note. - Transcript. - Extracted
suggestions. - Confidence/uncertainty indicators where supported. -
Suggested person. - Suggested fund. - Suggested category. - Suggested
amount/date. - Warnings or missing information. - Created timestamp. -
AI provider/model metadata where useful.

Actions: - Edit. - Match to an existing person. - Create a new person. -
Select an existing fund. - Create a new fund. - Split an expense across
sources. - Approve selected draft items. - Approve all only after
reviewing all items. - Reject. - Retry processing. - Return to original
recording.

## 12.5 Approval boundary

AI-generated drafts must never automatically become actual receipts,
expenses, allocations, or settlements.

Only an explicit user approval action may create financial ledger
entries.

Approval must run the same validation and business rules as manual
entry. If validation fails, show the error and do not partially create
records.

Maintain provenance indicating that a transaction originated from an
AI-assisted draft, while preserving the fact that the user reviewed and
approved it.

## 12.6 AI error handling

-   AI output must be parsed and validated against a strict schema.
-   Never execute code or SQL returned by AI.
-   Never trust extracted amounts without user review.
-   Prevent duplicate approval.
-   Preserve the original audio and transcript until the user deletes
    them.
-   Record processing failures and allow manual entry.

------------------------------------------------------------------------

# 13. AI and manual transaction provenance

Actual transactions should optionally identify their origin: - Manual
entry. - Approved voice-note draft. - CSV import (future). - Other
explicitly supported source.

Display a small source label in transaction details. AI origin is
informational and must not imply that the AI verified the transaction.

------------------------------------------------------------------------

# 14. Dashboard and navigation

## 14.1 Navigation

-   Dashboard
-   Bank Accounts
-   Bank Transactions
-   People
-   Funds
-   Expenses
-   Pocket Money
-   Settlements
-   Quick Notes
-   AI Transactions Inbox (when enabled)
-   Reports
-   Settings

## 14.2 Dashboard summary cards

-   Total money received.
-   Total expenses.
-   Combined manually tracked bank balances (clearly distinguished from
    logical money balances).
-   Remaining entrusted funds.
-   Pocket Money logical balance.
-   Recoverable personal contributions.
-   Outstanding amount to return.
-   Personal expenses.
-   Unreviewed voice notes.

Clearly distinguish: - Entrusted money still held. - Personal Pocket
Money. - Amounts receivable. - Amounts to return.

Do not combine these into a misleading single "available balance".

## 14.3 Dashboard sections

-   Recent transactions.
-   Person-wise summary.
-   Active funds.
-   Fund utilization.
-   Monthly expense chart.
-   Category-wise chart.
-   Pending settlements.
-   Unreviewed quick notes.
-   Quick action buttons.

------------------------------------------------------------------------

# 15. Reports, search, and exports

Reports: - Bank-account-wise balance and transaction history. - Bank
credits and debits by date range. - Unclassified bank transactions. -
Person-wise bank credits and spending where linked. - Person-wise. -
Fund-wise. - Receipt history. - Expense history. - Category-wise. -
Monthly/yearly. - Personal expenses. - Personal contributions. -
Reimbursements outstanding. - Entrusted funds remaining. - Returns. -
Pocket Money movements. - Transfers to Pocket Money. - Voice notes
converted to transactions.

Filters: - Date range. - Person. - Fund. - Category. - Amount range. -
Payment method. - Transaction source. - Settlement status. - AI/manual
origin.

Exports: - CSV for core tables and reports. - Excel workbook if
practical using a free library. - User data export. - Backup/restore
process.

Exports must be user-scoped and must not expose another user's records.

------------------------------------------------------------------------

# 16. PWA and offline draft capture

The application should be installable as a Progressive Web App.

## 16.1 PWA requirements

-   Web app manifest.
-   App icons.
-   Service worker.
-   Installable experience on supported browsers.
-   Cache static application assets and safe read-only shell content.
-   Display online/offline state.

Do not cache sensitive financial pages or API responses
indiscriminately. Use an explicit private-data caching policy.

## 16.2 Offline drafts

When offline, allow the user to create basic pending drafts such as: -
Text expense note. - Amount and description if entered. - Quick voice
note, where browser recording support and available device storage
permit. - Capture timestamp. - Optional location only when permission
and platform support allow it.

Use IndexedDB for local pending drafts. Do not use localStorage for
audio blobs or sensitive financial records.

Show clear states: - Saved on this device. - Waiting to sync. -
Syncing. - Synced. - Sync failed. - Needs attention.

## 16.3 Synchronization

When connectivity returns: - Automatically attempt to upload pending
drafts. - Use unique client-generated IDs/idempotency keys to prevent
duplicates. - Retry transient failures with bounded backoff. - Preserve
the local draft until the server confirms successful storage. - Do not
silently overwrite server records. - If there is a conflict, show the
user a resolution screen. - Never convert a pending offline draft into a
confirmed financial transaction without the usual validation and
approval steps.

The app must remain usable if offline synchronization is unavailable in
a particular browser.

------------------------------------------------------------------------

# 17. UI/UX design system

Design style: - Modern, minimal, trustworthy financial dashboard. -
Light theme initially, with optional dark theme later. -
White/light-grey surfaces. - Dark navy/charcoal typography. - Green for
received money and positive balances. - Red for expenses/negative
balances. - Amber for pending review/settlements. - Subtle borders and
shadows. - Rounded cards. - Clear spacing and readable typography.

Responsive behavior: - Desktop sidebar. - Collapsible mobile navigation
or bottom navigation. - Touch-friendly controls. - Large quick-record
button on mobile. - Forms usable on small screens.

Reusable components: - StatCard - PersonCard - FundCard -
TransactionTable - AddPersonForm - ReceiveMoneyForm - AddExpenseForm -
ExpenseAllocationForm - PocketMoneyTransferForm - SettlementForm -
QuickVoiceRecorder - AudioPlaybackCard - LocationConsentControl -
AIDraftCard - AIReviewPanel - SyncStatusIndicator - FilterBar -
BalanceProgressBar - ExpenseChart - MonthlyChart - EmptyState -
ConfirmationDialog - ToastNotification

Accessibility: - Keyboard-accessible controls. - Labels for inputs. -
Visible focus states. - Adequate contrast. - Clear validation errors. -
Do not communicate transaction state through color alone.

------------------------------------------------------------------------

# 18. Recommended technology stack

Use a free/open-source-first stack and avoid mandatory paid
dependencies.

## Backend

-   Python 3.
-   Flask.
-   Flask-SQLAlchemy.
-   SQLAlchemy.
-   Flask-Migrate.
-   Flask-Login.
-   Flask-WTF or equivalent CSRF protection.
-   Werkzeug security utilities or another maintained password-hashing
    implementation.

## Frontend

-   HTML5.
-   CSS3.
-   Vanilla JavaScript.
-   Bootstrap 5.
-   Jinja2 templates.
-   Bootstrap Icons or Lucide icons.

Avoid React, Next.js, Node.js, and complex frontend build tooling unless
a demonstrated requirement emerges.

## Bank tracking

-   Manual bank transaction entry only; no bank connectivity, account
    aggregation, or paid financial API.

## Database

-   SQLite for local development and simple single-instance use.
-   PostgreSQL for hosted multi-user production.
-   SQLAlchemy ORM and migrations.

## Voice and offline

-   Browser MediaRecorder API.
-   IndexedDB for offline drafts.
-   Service Worker.
-   Web App Manifest.
-   Browser Geolocation API.

## Charts

-   Chart.js.

## Maps

-   OpenStreetMap-compatible map library such as Leaflet, subject to
    tile-provider terms and attribution.
-   Do not assume unlimited free tile usage; configure a compliant
    provider and graceful fallback.

## Optional AI

-   Gemini API through server-side integration only.
-   AI provider abstraction so another provider or local transcription
    option can be added later.
-   AI disabled by default until configured by the user.

## Deployment

-   Gunicorn for production WSGI serving.
-   PostgreSQL.
-   Environment-based configuration.
-   A hosting provider with a suitable free tier if available.
-   Persistent storage for database backups and audio/receipt files.

**Cost policy:** Core financial tracking, voice recording/playback,
location capture, reports, and local development must not require a paid
API. Gemini is optional and subject to provider quotas/pricing. Hosting
free tiers can change, sleep, or impose storage/bandwidth limits. Never
promise permanent free hosting.

------------------------------------------------------------------------

# 19. Suggested database model

Use normalized SQLAlchemy models with foreign keys, constraints,
indexes, and timestamps. Use integer paise for monetary values; never
use binary floating-point for money.

Suggested entities:

## User

-   id
-   name
-   email
-   password_hash
-   created_at
-   updated_at

## BankAccount

-   id
-   user_id
-   account_nickname
-   bank_name
-   account_type
-   masked_identifier
-   opening_balance_paise
-   opening_balance_date
-   currency
-   notes
-   archived_at
-   created_at
-   updated_at

## BankTransaction

-   id
-   user_id
-   bank_account_id
-   transaction_type
-   amount_paise
-   transaction_at
-   description
-   reference_id
-   person_id (nullable)
-   category_id (nullable)
-   linked_receipt_id (nullable)
-   linked_expense_id (nullable)
-   linked_settlement_id (nullable)
-   transfer_group_id (nullable)
-   classification_status
-   notes
-   created_at
-   updated_at

Use linked paired entries for transfers between the user's own accounts.
Validate that links belong to the same user and that a bank transaction
is not linked to incompatible financial records. A linked bank entry is
not a second receipt or expense.

## Person

-   id
-   user_id
-   name
-   relationship
-   phone
-   email
-   notes
-   archived_at
-   created_at
-   updated_at

## Fund

-   id
-   user_id
-   person_id
-   title
-   purpose
-   status
-   created_at
-   updated_at

## Receipt

-   id
-   user_id
-   fund_id
-   amount_paise
-   received_at
-   payment_method
-   reference_id
-   notes
-   created_at

## Category

-   id
-   user_id
-   name
-   category_type
-   created_at

## Expense

-   id
-   user_id
-   category_id
-   title
-   total_amount_paise
-   expense_at
-   merchant
-   payment_method
-   reference_id
-   description
-   receipt_file_id (nullable)
-   created_at
-   updated_at
-   origin_type

## ExpenseAllocation

-   id
-   user_id
-   expense_id
-   source_type (FUND or POCKET_MONEY)
-   fund_id (nullable)
-   allocated_amount_paise
-   reimbursement_expected
-   created_at

For FUND source, fund_id is required and must belong to the same user.
For POCKET_MONEY source, fund_id must be null.

## Settlement

-   id
-   user_id
-   person_id
-   fund_id (nullable)
-   related_expense_id (nullable)
-   settlement_type
-   amount_paise
-   settlement_at
-   notes
-   created_at

## PocketMoneyEntry

-   id
-   user_id
-   entry_type
-   amount_paise
-   related_fund_id (nullable)
-   related_expense_id (nullable)
-   related_settlement_id (nullable)
-   transfer_group_id (nullable)
-   description
-   occurred_at
-   created_at

Use paired, linked entries for internal transfers and ensure both sides
are committed atomically.

## VoiceNote

-   id
-   user_id
-   audio_storage_key/path
-   title
-   text_note
-   transcript
-   captured_at
-   uploaded_at
-   duration_seconds
-   mime_type
-   status
-   location_id (nullable)
-   created_at
-   updated_at

## Location

-   id
-   user_id
-   latitude
-   longitude
-   accuracy_meters
-   captured_at
-   user_label
-   created_at

## AIDraft

-   id
-   user_id
-   voice_note_id
-   provider
-   model
-   status
-   extracted_payload_json
-   confidence_metadata_json (nullable)
-   processing_error (nullable)
-   created_at
-   reviewed_at
-   approved_at

## FileAsset

-   id
-   user_id
-   storage_key/path
-   file_type
-   mime_type
-   size_bytes
-   created_at

## AuditEvent

-   id
-   user_id
-   entity_type
-   entity_id
-   action
-   before_snapshot_json (where appropriate)
-   after_snapshot_json (where appropriate)
-   created_at

Use a database design that supports controlled corrections and audit
history. Avoid storing derived balances as manually editable fields.

The implementation may introduce additional join tables or contribution
records where necessary to ensure that partial reimbursements can be
allocated to specific recoverable contributions without ambiguity.

------------------------------------------------------------------------

# 20. Financial integrity, validation, and audit rules

Mandatory rules:

1.  Use integer paise for all amounts.
2.  Validate positive amounts and sensible date values.
3.  Allocation totals must equal the expense total before finalization.
4.  A fund cannot be over-allocated unless the shortfall is explicitly
    funded by Pocket Money or another selected source.
5.  A fund must belong to the current user.
6.  A person and fund relationship must be validated server-side.
7.  A settlement cannot exceed the related outstanding amount without an
    explicit adjustment workflow.
8.  A Pocket Money transfer must debit the fund and credit Pocket Money
    atomically.
9.  Refunds must reverse the original source allocations proportionally
    or through explicit user-directed allocation.
10. Reimbursements must reduce the relevant outstanding receivable.
11. AI drafts must not create ledger records before approval.
12. Offline drafts must be idempotent on synchronization.
13. Repeated approval requests must not duplicate records.
14. Editing a financial record must recalculate all affected summaries.
15. Deletion of financial records must use a controlled reversal/void
    approach where required to preserve history.
16. Use database transactions for multi-record financial operations.
17. Centralize calculations in tested service functions.
18. Dashboard and reports must use the same calculation logic.
19. No automatic cross-fund balancing.
20. No automatic assumption that unspent entrusted money belongs to the
    user.

------------------------------------------------------------------------

# 21. Project folder structure

Use a modular Flask application:

``` text
personal-money-flow-tracker/
│
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models/
│   │   ├── user.py
│   │   ├── bank_account.py
│   │   ├── bank_transaction.py
│   │   ├── person.py
│   │   ├── fund.py
│   │   ├── receipt.py
│   │   ├── expense.py
│   │   ├── allocation.py
│   │   ├── settlement.py
│   │   ├── pocket_money.py
│   │   ├── voice_note.py
│   │   ├── location.py
│   │   ├── ai_draft.py
│   │   └── audit_event.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── bank_accounts.py
│   │   ├── bank_transactions.py
│   │   ├── dashboard.py
│   │   ├── people.py
│   │   ├── funds.py
│   │   ├── receipts.py
│   │   ├── expenses.py
│   │   ├── pocket_money.py
│   │   ├── settlements.py
│   │   ├── voice_notes.py
│   │   ├── ai_drafts.py
│   │   ├── reports.py
│   │   └── settings.py
│   │
│   ├── services/
│   │   ├── bank_balance_service.py
│   │   ├── bank_reconciliation_service.py
│   │   ├── balance_service.py
│   │   ├── allocation_service.py
│   │   ├── settlement_service.py
│   │   ├── pocket_money_service.py
│   │   ├── voice_note_service.py
│   │   ├── ai_extraction_service.py
│   │   ├── sync_service.py
│   │   ├── report_service.py
│   │   └── audit_service.py
│   │
│   ├── templates/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   ├── icons/
│   │   ├── manifest.webmanifest
│   │   └── service-worker.js
│   │
│   └── utils/
│       ├── money.py
│       ├── validation.py
│       └── security.py
│
├── migrations/
├── tests/
│   ├── test_auth.py
│   ├── test_bank_accounts.py
│   ├── test_bank_transactions.py
│   ├── test_user_isolation.py
│   ├── test_funds.py
│   ├── test_receipts.py
│   ├── test_expenses.py
│   ├── test_allocations.py
│   ├── test_pocket_money.py
│   ├── test_settlements.py
│   ├── test_voice_notes.py
│   ├── test_ai_drafts.py
│   └── test_sync.py
│
├── instance/
├── uploads/
├── backups/
├── config.py
├── run.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

Keep audio and uploaded files outside public static directories. Use
authenticated download routes that verify ownership.

------------------------------------------------------------------------

# 22. Development phases and acceptance criteria

## Phase 1 --- Foundation and authentication

Build: - Flask app factory. - Configuration. - SQLAlchemy. - SQLite
local configuration and PostgreSQL production configuration. -
Migrations. - Registration/login/logout. - User isolation. - Responsive
base layout.

Acceptance: - Users can register and log in. - Passwords are hashed. -
Protected pages require authentication. - Cross-user access tests
pass. - Application runs locally using documented instructions.

## Phase 2 --- People, funds, and receipts

Build: - People CRUD/archive. - Create and archive multiple bank
accounts. - Set opening balances. - Manually record bank credits and
debits. - Link bank transactions to receipts and expenses. - Review
unclassified transactions. - Transfer between own accounts. - Create
fund. - Add receipt to new fund. - Add receipt to existing fund. - Fund
detail and history. - Centralized fund balance calculations.

Acceptance: - Multiple bank accounts can be created and archived. -
Opening balances and manual credits/debits calculate correctly. - Bank
transactions can be linked to existing receipts/expenses without
duplication. - Own-account transfers create paired entries and do not
count as income or expenditure. - Unclassified transactions remain
available for later review. - Bank balances are distinct from fund and
Pocket Money balances. - Each receipt is retained separately. - Funds
remain independent. - Balances are correct after multiple receipts. -
User ownership is enforced.

## Phase 3 --- Expenses and allocations

Build: - Expense creation/editing. - Categories. - Multiple
allocations. - Pocket Money allocation. - Recoverable/non-recoverable
personal contribution. - Personal-only expenses. - Refund/reversal
handling.

Acceptance: - Allocation sum equals expense total. - No silent
overdraw. - Multiple funding sources work. - Personal expenses remain
separately reportable. - Corrections recalculate balances.

## Phase 4 --- Pocket Money and settlements

Build: - Pocket Money ledger. - Full/partial transfer from a fund. -
Linked debit/credit entries. - Return unused money. - Reimbursement. -
Permission-to-keep transfer. - Settlement history.

Acceptance: - Partial transfer reduces the fund and increases Pocket
Money by the same amount. - Internal transfer is not counted as new
income. - Both ledger sides are atomic. - Partial reimbursements work. -
No invalid duplicate settlements.

## Phase 5 --- Dashboard and reports

Build: - Financial summary cards. - People/fund summaries. - Charts. -
Search and filters. - CSV/Excel exports. - Backup and restore.

Acceptance: - Dashboard and reports use shared calculation services. -
Values reconcile with underlying transactions. - Export is user-scoped.

## Phase 6 --- Quick Voice Notes and location

Build: - Browser audio recording. - Playback. - Timestamp and
duration. - Text notes. - Unreviewed list. - Optional one-time location
capture. - Attach note to an expense. - Delete/archive controls.

Acceptance: - Recording works in supported browsers over HTTPS. -
Unsupported browsers have a fallback. - Location is requested only after
user action. - No background tracking. - Audio downloads/playback
require authentication. - Unreviewed notes are visible.

## Phase 7 --- AI Transactions Inbox

Build: - Optional Gemini configuration. - Server-side provider
adapter. - Explicit processing consent. - Transcription/extraction. -
Structured AI drafts. - Review/edit/match/approve/reject workflow. -
Provenance and error handling.

Acceptance: - App works when AI is disabled or unconfigured. - AI never
writes directly to the ledger. - Approval is explicit and validated. -
Duplicate approval is prevented. - Ambiguous data is flagged, not
invented. - API key is never exposed to the browser.

## Phase 8 --- PWA and offline drafts

Build: - Manifest and service worker. - Installability. - Safe
application-shell caching. - IndexedDB draft queue. - Offline text/voice
draft capture where supported. - Automatic sync and status display. -
Idempotency and conflict handling.

Acceptance: - User can identify unsynced drafts. - A draft remains
on-device until server confirmation. - Retried synchronization does not
create duplicates. - Conflicts require user attention. - Offline drafts
are never represented as confirmed ledger transactions.

## Phase 9 --- Security, deployment, and release

Build: - Production PostgreSQL. - Gunicorn. - HTTPS configuration. -
Environment variables. - Persistent file storage strategy. -
Backup/restore. - Security review. - Deployment documentation.

Acceptance: - Production secrets are not in source control. - Cross-user
isolation tests pass. - Backups can be restored. - Audio and receipts
are access-controlled. - Free-tier limitations are documented. - Local
installation remains supported.

------------------------------------------------------------------------

# 23. Testing strategy

Use pytest and a dedicated test database.

Mandatory scenarios:

1.  Register two users and verify isolation.
2.  Create two bank accounts and verify user isolation.
3.  Set an opening bank balance and verify the manually tracked balance.
4.  Enter credits of ₹10,000 and ₹2,000, then debits of ₹2,000, ₹3,000,
    and ₹500; verify the calculated balance.
5.  Create a ₹2,000 Kotak credit linked to an existing ₹2,000 receipt
    from Father; verify no duplicate receipt or fund credit.
6.  Create a ₹500 Kotak debit linked to an existing expense allocated to
    Father's fund; verify no duplicate expense or allocation.
7.  Create a bank credit with Father selected and create/link the
    receipt and fund in one workflow.
8.  Create a bank debit with a person selected and create/link an
    expense and allocation.
9.  Record unclassified credits/debits and classify them later.
10. Transfer between two of the user's bank accounts; verify paired
    entries and no income/expense impact.
11. Verify bank account balances are not automatically treated as Pocket
    Money or entrusted fund balances.
12. Receive ₹5,000 from Mother.
13. Spend ₹2,000 from Mother's fund; remaining is ₹3,000.
14. Add ₹2,000 to the existing fund; preserve both receipt records.
15. Create a second independent fund for Mother.
16. Receive ₹3,000 from Father.
17. Record a ₹3,500 expense using ₹3,000 from Father's fund and ₹500
    from Pocket Money.
18. Mark the ₹500 as recoverable and verify the receivable.
19. Repeat with non-recoverable personal contribution.
20. Receive partial reimbursement and verify outstanding amount.
21. Return unused money and verify fund balance.
22. Transfer ₹500 partially from a fund to Pocket Money.
23. Verify paired ledger entries and no new-income classification.
24. Transfer the full remaining fund amount.
25. Refund part of an expense and restore the correct source.
26. Record personal-only expense.
27. Verify a closed/archived fund cannot be used without reopening.
28. Reject an invalid allocation total.
29. Reject cross-user fund and expense references.
30. Ensure AI draft approval creates records once only.
31. Ensure rejected AI drafts do not alter the ledger.
32. Ensure AI-disabled mode supports manual workflows.
33. Verify voice-note timestamp and authenticated playback.
34. Verify location is absent when permission is not granted.
35. Verify offline draft idempotency and synchronization retry.
36. Verify exports include only the current user's data.
37. Verify backup and restore preserve financial relationships.

Include edge cases for zero values, decimal rupees/paise, partial
refunds, concurrent updates, deleted/archived people, network failure,
and timezone handling.

  ---------------------------------------------------------------------
  \# 24. Free/open-source and operating-cost policy

  The project must be designed to minimize ongoing cost.

  \- Prefer open-source libraries and browser-native capabilities. - Do
  not require paid financial APIs. - Do not require Google Maps API. -
  Do not require paid transcription for manual voice notes. - Do not
  require Gemini for any core financial workflow. - Keep the app useful
  if every optional external API is disabled. - Use a free hosting tier
  only if it meets the app's storage, persistence, and privacy needs. -
  Document hosting limits and possible future charges. - Provide a
  local deployment path if free hosting becomes unavailable. - Keep the
  database portable. - Avoid proprietary dependencies where a suitable
  open-source alternative exists.

  Do not claim that any third-party free tier is unlimited or
  guaranteed to remain free.
  ---------------------------------------------------------------------

# 25. GitHub, documentation, and repository hygiene

Provide: - README with setup and usage instructions. - requirements.txt
with pinned or bounded compatible dependencies. - .env.example with
placeholder variable names only. - .gitignore. - Database migration
instructions. - Local SQLite setup. - PostgreSQL setup. - Deployment
instructions. - Backup and restore instructions. - AI setup
instructions, clearly marked optional. - PWA/browser support notes. -
Privacy and location behavior documentation.

Never commit: - `.env` - Real API keys. - Production database. - User
audio. - Receipts. - Personal backups. - User exports. - Private logs.

------------------------------------------------------------------------

# 26. Antigravity implementation instructions

Treat this document as the source of truth.

1.  Read this entire specification before coding.
2.  First inspect the repository and report the proposed implementation
    plan.
3.  Implement one development phase at a time.
4.  Do not skip financial validation or tests.
5.  Do not invent requirements that change financial semantics.
6.  If a requirement is ambiguous, explain the ambiguity and propose a
    safe default before implementing it.
7.  Keep business logic in service modules, not scattered across routes
    or templates.
8.  Use database migrations for schema changes.
9.  Use integer paise for monetary calculations.
10. Use database transactions for multi-record financial operations.
11. Add tests alongside each feature.
12. Run the relevant tests after each phase and report actual results.
13. Do not claim a test, backup, migration, or deployment succeeded
    unless it was actually executed and verified.
14. Keep the application runnable locally throughout development.
15. Keep optional AI, location, and PWA functionality isolated so they
    cannot break core money tracking.
16. Do not expose secrets in source code or client-side assets.
17. Do not use mock data as if it were real user financial data.
18. Use realistic sample data only in development/demo fixtures.
19. Update README and requirements as implementation evolves.
20. Before moving to the next phase, summarize files changed, tests run,
    results, known limitations, and the next step.

## Initial instruction to Antigravity

Start with Phase 1 only. Before writing code, inspect the environment
and present a concise implementation plan based on this specification.
Then implement the foundation and authentication, create migrations and
tests, and verify that the application runs locally. Do not implement
all modules in one attempt.

------------------------------------------------------------------------

# 27. Final product definition

The finished Personal Money Flow Tracker must allow a user to:

-   Record money received from any person.
-   Maintain multiple bank accounts and manually enter credits/debits
    without connecting to banking apps.
-   Link bank credits/debits to people, receipts, expenses, and funds
    without double-counting.
-   Keep transfers separate or add a receipt to an existing fund.
-   Track every expense and its funding source.
-   Split expenses across funds and Pocket Money.
-   Track recoverable and voluntary personal contributions.
-   Return unused funds.
-   Transfer all or part of unused funds to Pocket Money with a complete
    linked history.
-   Record and replay voice notes when formal entry is inconvenient.
-   Optionally capture the time and location associated with a note or
    expense.
-   Optionally use AI to create editable transaction drafts.
-   Review and explicitly approve every AI-generated financial entry.
-   Capture drafts offline and synchronize them safely later.
-   View accurate person-wise, fund-wise, and personal financial
    summaries.
-   Access the application securely from different devices.
-   Export and back up personal data.

The application must remain useful without AI, without location
permission, and without paid services.

**Success criterion:** At any time, the user can select a person, fund,
expense, voice note, or Pocket Money transfer and understand where the
money came from, where it went, what remains, and why the current
balance is what it is.
