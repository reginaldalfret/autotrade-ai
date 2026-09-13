# Automated Daily PDF Trading Report Generator

## Overview
AutoTrade AI automatically generates an institutional multi-page PDF trading report upon finalizing each daily session. Built using ReportLab and Matplotlib with a headless `Agg` backend, the report provides a permanent, auditable, human-readable record of model performance, portfolio equity curves, complete trade executions, and cryptographic audit verification.

---

## Report Structure (8 Pages)

| Page | Title | Content |
| :---: | :--- | :--- |
| **1** | **Executive Summary & Overview** | Institutional Title Header, Mandatory Research Disclaimer, Session Metadata Grid, Executive Totals Table, Statutory Fee & Cost Distribution Chart. |
| **2** | **8-Model Tournament Leaderboard** | Deterministic Leaderboard Table (Ranks 1–8), Comparative Net P&L Horizontal Bar Chart, Multi-Model Intraday Equity Curves Chart. |
| **3** | **Model Deep Dives: Models 1 & 2** | Detailed Metrics Grid, Trade Statistics, Statutory Fee Breakdowns, Target/Stop Status for Ranks 1 and 2. |
| **4** | **Model Deep Dives: Models 3 & 4** | Detailed Metrics Grid, Trade Statistics, Statutory Fee Breakdowns, Target/Stop Status for Ranks 3 and 4. |
| **5** | **Model Deep Dives: Models 5 & 6** | Detailed Metrics Grid, Trade Statistics, Statutory Fee Breakdowns, Target/Stop Status for Ranks 5 and 6. |
| **6** | **Model Deep Dives: Models 7 & 8** | Detailed Metrics Grid, Trade Statistics, Statutory Fee Breakdowns, Target/Stop Status for Ranks 7 and 8. |
| **7** | **Trade Execution Ledger** | Complete chronological table of all closed intraday round-trip trades (Trade ID, Model, Symbol, Quantity, Entry/Exit Prices, Gross/Net P&L, Exit Reason). |
| **8** | **Cryptographic Audit Trail** | Cryptographic Chain Verification Badge, Genesis Hash, Latest Hash, Sequence Range, Sample Event Audit Trail, PDF Document SHA-256 Fingerprint. |

---

## Automatic Hook & Error Isolation

In `PaperTradingEngine.finalize_daily_session()`:
1. All 8 accounts close session and record end-of-day compounding.
2. Daily performance records are persisted to SQLite.
3. `DailyReportGenerator.generate(session_id)` is automatically invoked.
4. **Resilience Guarantee**: If report compilation encounters an error (e.g. missing fonts, rendering timeout), the error is caught, logged as a `REPORT_FAILED` audit event, and stored in the `reports` table. **Trading session finalization and compounding are NEVER rolled back or interrupted**.

---

## File Storage & Cryptographic Hashing

- **File Location**: `reports/daily/AutoTradeAI_Daily_{YYYY-MM-DD}.pdf`
- **Temporary Assets**: Chart images are rendered to `reports/temp/` on drive `D:` and removed immediately after PDF assembly.
- **SHA-256 Hashing**:
  Upon document assembly, a full SHA-256 cryptographic digest is computed across the file bytes and stored in the SQLite `reports` table.
- **Verification**:
  Any PDF report can be validated against the database using `mobitrade report validate <path_or_date>`.

---

## CLI Usage

```bash
# Generate report for today or specific session/date
mobitrade report generate
mobitrade report generate --date 2026-09-11

# Force re-generation of report
mobitrade report regenerate --date 2026-09-11

# Cryptographically validate PDF fingerprint against SQLite record
mobitrade report validate 2026-09-11
mobitrade report validate reports/daily/AutoTradeAI_Daily_2026-09-11.pdf
```
