# System Architecture

## Overview
MobiTrade AI is built as a strictly decoupled, layered research platform:

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
         Standardized MarketSnapshot -> 8 Isolated Local LLMs (Phase 6)
                    │
                    ▼
            Trade Decision
                    │
                    ▼
       Risk Engine (Deterministic Limits + Trailing Stop)
                    │
                    ▼
       Paper Broker (Slippage + Costs)
                    │
                    ▼
      Portfolio Manager (Compounding)
                    │
                    ▼
        Audit Logger & PDF Reports
```