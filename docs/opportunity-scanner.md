# MobiTrade AI — Opportunity Scanner & Candidate Ranking (Phase 4)

## Overview
The **Opportunity Scanner** is a deterministic, point-in-time candidate generation engine designed exclusively for the **NSE Indian Equity Cash Market**.
It filters and scores an equity universe as of an explicit `decision_timestamp`, outputting ranked `OpportunityCandidate[]` for future local LLM evaluation.

### Core Architecture Principles
1. **Candidate Generation Only**: The scanner NEVER places trades, generates BUY/SELL orders, or accesses the broker.
2. **Point-in-Time Temporal Gating**: Every scan evaluates information strictly satisfying:
   $$\text{available\_at} \le \text{decision\_timestamp}$$
   Forming bars, future price spikes, future volume, future session highs/lows, and future VWAP are strictly excluded.
3. **Multi-Factor Explainable Scoring**: Opportunity scores are linear combinations of normalized technical factors (0.0 - 100.0) with full component explainability.
4. **Machine-Readable Auditability**: Symbols not meeting filtering criteria are never silently discarded; every rejection carries an explicit `RejectionReason`.
5. **Decoupled Architecture**: Independent of specific broker feeds or hard-coded symbol lists.

---

## Filter Pipeline

```
NSE Instrument Universe
        ↓
EligibilityFilter (Exchange, Segment, Active Status, Trading Session)
        ↓
DataQualityFilter (History Sufficiency, Status != ANOMALY, Temporal Ordering)
        ↓
PriceFilter (min_price <= price <= max_price, positive non-zero)
        ↓
LiquidityFilter (min_volume, relative_volume threshold)
        ↓
Point-in-Time Feature Calculation (calculate_features_as_of)
        ↓
OpportunityScorer (Momentum, RelVol, Trend, Breakout, Volatility, Liquidity)
        ↓
Deterministic Ranking & Top-N Selection (Tie-breaking by symbol)
        ↓
SQLite Persistence (mobitrade.db) & Output Candidate Snapshot
```

### Rejection Reasons
| Reason | Description |
|---|---|
| `NOT_ELIGIBLE` | Instrument is not an NSE equity cash market security. |
| `INVALID_INSTRUMENT` | Inactive status or outside instrument validity bounds (`valid_from` / `valid_to`). |
| `OUTSIDE_SESSION` | Scan requested outside active NSE trading hours (09:15–15:30 IST). |
| `INSUFFICIENT_HISTORY` | Fewer historical completed bars than `min_history_bars` (default: 20). |
| `MISSING_FEATURE` | Critical feature set could not be derived. |
| `DATA_ANOMALY` | Data flagged with anomalous price or corrupted timestamp. |
| `INVALID_PRICE` | Price is non-positive, NaN, or outside `[min_price, max_price]`. |
| `ILLIQUID` | Volume or relative volume below configured thresholds. |

---

## Opportunity Scoring Methodology

The score is an explainable weighted linear combination normalized to 0–100:
$$\text{Total Score} = \frac{\sum w_i \times S_i}{\sum w_i}$$

| Component | Default Weight | Key Inputs |
|---|---|---|
| **Momentum** | 20.0 | Short-term momentum ($M_3, M_5$), price vs SMA-20 / SMA-50 |
| **Relative Volume** | 20.0 | $RV_{20}$ scaled from 0.0 to 3.0+ |
| **Trend Alignment** | 20.0 | Bullish (100), Neutral (50), Bearish (20) |
| **Breakout / Structure**| 15.0 | Proximity to session high, close position in range, price > VWAP |
| **Volatility** | 15.0 | Annualized realized volatility in optimal intraday zone (15% - 60%) |
| **Liquidity Quality** | 10.0 | Raw volume depth |

*Note: The score is a ranking mechanism for candidate prioritization, not a predictive probability of profit.*

---

## Database Persistence (`mobitrade.db`)

Scan runs and evaluated candidates are persisted in SQLite at:
`D:\Trading LLM\MobiTradeAI\database\mobitrade.db`

- `scans`: Tracks `scan_id`, `decision_timestamp`, `timeframe`, `scanner_version`, `configuration_version`, `universe_version`, total universe count, eligible count, and candidate count.
- `scan_candidates`: Detailed records including `opportunity_score`, component breakdown JSON, feature versions, liquidity metrics, and rejection reasons.

---

## CLI Usage

```bash
# Check scanner engine status
mobitrade scanner status

# Validate configuration file
mobitrade scanner validate --config configs/scanner.yaml

# Inspect historical scan runs
mobitrade scanner inspect

# Execute a point-in-time scan
mobitrade scanner scan --timeframe 5m --top-n 10 --timestamp "2026-09-11T10:30:00+05:30"
```
