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
        Feature Engineering Engine (Phase 3)
                    │
                    ▼
        Opportunity Scanner (Phase 4)
                    │
                    ▼
        Market Snapshot -> 8 Isolated Local LLMs
                    │
                    ▼
            Trade Decision
                    │
                    ▼
       Risk Engine (Deterministic Limits)
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