# System Architecture

## Overview
MobiTrade AI is built as a strictly decoupled, layered research platform:

```
External Data / FYERS / Local Fixtures
                    │
                    ▼
           MarketDataProvider
                    │
                    ▼
           Raw Data (data/raw/)
                    │
                    ▼
       Data Quality Validation & Cleaning
                    │
                    ▼
    Timestamp Normalization (Asia/Kolkata)
                    │
                    ▼
   Processed Columnar Storage (Parquet on D:)
                    │
                    ▼
        Feature Engineering (Phase 3)
                    │
                    ▼
        Opportunity Scanner (Phase 4)
                    │
                    ▼
        Market Snapshot -> 8 Local LLMs
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