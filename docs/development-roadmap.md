# AutoTrade AI — Development Roadmap & Milestone Progress

## Progress Tracker

| Phase | Description | Status | Test Coverage | Storage Compliance |
|---|---|---|---|---|
| **Phase 0** | Environment Discovery, Workspace Integrity & Local LLM Registry | **COMPLETE** | Verified | E: for Fedora WSL2, D: for code |
| **Phase 1** | Local-First Architecture, Domain Models, Risk Engine, Paper Broker, Portfolio Manager | **COMPLETE** | 12 tests | D: drive, no C: usage |
| **Phase 2** | Historical Market Data Engine, NSE Indian Equities, Parquet Partitioning | **COMPLETE** | 28 tests | Partitioned on D: |
| **Phase 2.1**| Hardened FYERS HTTP Request, Real SHA-256 Provenance, Missing Interval Calculation | **COMPLETE** | 40 tests | Parquet + SHA-256 on D: |
| **Phase 3** | Quantitative Feature Engineering & Deterministic Trailing Stop Engine | **COMPLETE** | 50 tests | Versioned features on D: |
| **Phase 3.1**| Feature Availability Semantics (`available_at`), `calculate_features_as_of()`, Timeframe Volatility | **COMPLETE** | 54 tests | Point-in-time gated |
| **Phase 3.2**| Feature Storage Idempotence, Pure Non-Mutating Reads, Scanner Temporal Safety Gate | **COMPLETE** | 61 tests | Idempotent Parquet merge |
| **Phase 4** | NSE Opportunity Scanner, Modular Filters, Explainable Scoring, Top-N Ranking, SQLite DB | **COMPLETE** | 73 tests | SQLite database on D: |
| **Phase 5** | External Financial Information, Point-in-Time Context Layer, MarketSnapshot, SQLite DB | **COMPLETE** | 82 tests | Caching + DB on D: |
| **Phase 6** | 8-Model Local LLM Integration & Sequential LLM Scheduler | **COMPLETE** | 90 tests | Local inference on D: |
| **Phase 7** | Paper Trading, Portfolio Manager & Compounding Engine | **COMPLETE** | 101 tests | SQLite database on D: |
| **Phase 8** | Cryptographic Audit Logging, Performance Analytics Engine & Daily PDF Reporting | **COMPLETE** | 113 tests | Reports on D:, C: prohibited |

---

## Market Scope Policy
- **Primary Market**: NSE Indian Equity Cash Market (09:15 to 15:30 IST).
- **Prohibited in Current Implementation**: Cryptocurrency, Bitcoin, BSE, Futures, Options, Margin, Leverage, Live Broker Execution.
