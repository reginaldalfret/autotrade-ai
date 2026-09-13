# System Architecture

## Overview
AutoTrade AI is built as a strictly decoupled, layered research platform:

```
External Data / FYERS API v3 / Local Fixtures
                    │
                    ▼
           MarketDataProvider
                    │
                    ▼
           Raw Data (data/raw/)
                    │
                    ▼
 Data Quality Validation (Missing intervals, Duplicates, Anomalies, Strict Incomplete Aggregation)
                    │
                    ▼
   Cryptographic SHA-256 Checksum Computation & Provenance Generation (data/metadata/)
                    │
                    ▼
 Partition-Aware Columnar Storage (Parquet on D: by Year & Month)
                    │
                    ▼
 Feature Engineering Engine (Phase 3 & 3.1)
  - Explicit available_at temporal availability
  - Point-in-time snapshot API: calculate_features_as_of()
  - Timeframe-aware volatility annualization (1m: 375, 5m: 75, 15m: 25)
                    │
                    ▼
         Opportunity Scanner (Phase 4 - Implemented & Verified)
          - Point-in-time scanning: available_at <= decision_timestamp
          - Modular filters: Eligibility, Liquidity, Price, Data Quality
          - Deterministic multi-factor scoring (Momentum, RelVol, Trend, Breakout, Volatility, Liquidity)
          - Top-N ranking & tie-breaking
          - SQLite persistence: database/mobitrade.db
                    │
                    ▼
         External Financial Information & Context Layer (Phase 5 - Implemented & Verified)
          - Multi-provider ingestion: NSE Announcements, Financial News, Macro/RBI
          - Publication vs Availability semantics (available_at <= decision_timestamp)
          - Authority-aware deduplication & deterministic relevance ranking
          - Cryptographic SHA-256 content hashing & provenance
          - SQLite persistence & local filesystem caching
                    │
                    ▼
          Standardized MarketSnapshot -> 8 Isolated Local LLMs (Phase 6 - Implemented & Verified)
           - Sequential LLMScheduler: One model in VRAM at a time (Load -> Infer -> Validate -> Record -> Unload)
           - Frozen MarketSnapshot across all 8 models with frozen simulation time
           - Strict JSON schema validation & fallback to HOLD
           - Account isolation (₹1,000 per model) & comprehensive SQLite persistence
                    │
                    ▼
       Deterministic Risk Engine (Phase 7 - Subordination Authority)
        - Pre-trade validation & position sizing based on available cash
        - Session thresholds: +10% Daily Target / -5% Hard Stop
        - 15:15 IST entry cutoff & mandatory auto square-off
        - Max 20 completed trades limit
                    │
                    ▼
       Paper Broker & Execution Simulation (Phase 7)
        - Authentic Indian equity cash cost schedule (Brokerage, STT, Turn, GST, SEBI, Stamp)
        - 0.05% slippage model
        - Dynamic trailing-stop ratchet & execution
        - 8 isolated sub-account trade execution slots
                    │
                    ▼
       Portfolio Manager & Compounding Engine (Phase 7)
        - 8 independent model ledgers (₹1,000 initial capital per model)
        - Real-time mark-to-market and Gross vs Net P&L attribution
        - Daily realized equity compounding: starting_balance(D+1) = ending_equity(D)
        - SQLite trade journal, snapshots, performance leaderboard & audit events
                    │
                    ▼
        Audit Logger & PDF Reports (Phase 8)
```