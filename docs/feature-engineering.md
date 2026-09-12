# Quantitative Feature Engineering & Temporal Availability (Hardened Phase 3.1)

## Temporal Availability Semantics
Historical candles in AutoTrade AI are strictly `INTERVAL_BEGINNING`.
- A 1-minute candle with timestamp `09:15:00` covers `09:15:00` to `09:15:59`. Its completed close and OHLCV statistics are only available at `09:16:00`.
- A 5-minute candle with timestamp `09:15:00` covers `09:15:00` to `09:19:59`. Available at `09:20:00`.
- A 15-minute candle with timestamp `09:15:00` covers `09:15:00` to `09:29:59`. Available at `09:30:00`.

## Snapshot API: `calculate_features_as_of()`
- Evaluates eligible historical candles where `candle.available_at <= decision_timestamp`.
- Incomplete/forming candles are strictly excluded.
- At `09:15:30`, the `09:15` candle is still forming and cannot be seen.
- At `09:16:00`, the completed `09:15` candle becomes eligible.

## Timeframe-Aware Volatility Annualization
Realized volatility uses:
$$\text{Annual Factor} = \sqrt{252 \times \text{bars\_per\_session}}$$
- 1m: 375 bars/session $\rightarrow \sqrt{252 \times 375}$
- 5m: 75 bars/session $\rightarrow \sqrt{252 \times 75}$
- 15m: 25 bars/session $\rightarrow \sqrt{252 \times 25}$

## Invariant Provenance
Every `TechnicalFeatures` record tracks:
- `candle_timestamp`: Original bar open timestamp.
- `feature_available_at`: Earliest point in time the feature could be observed.
- `timeframe`: Active resolution.
- `feature_version`: Versioned feature calculation logic (`1.1.0`).
- `source_dataset_id`: Parent dataset provenance reference.
- Model invariant enforcement: Pydantic rejects records where `feature_available_at < candle_timestamp`.

## Storage Idempotence & Query Safety (Phase 3.2)
- **Incremental Merging**: `ParquetFeatureRepository.save_features()` loads any existing partition data, merges incoming batches, sorts strictly by `candle_timestamp`, and deduplicates on `(symbol, exchange, timeframe, candle_timestamp, feature_version)`.
- **Pure Reads**: `load_features(create=False)` performs side-effect-free queries and never creates empty partition folders for missing datasets.
- **Scanner Temporal Gate**: Decision-making at $T$ evaluates only complete historical bars where `feature_available_at <= T`. At $09:17:30$, 1-minute bars through $09:16$ (available at $09:17:00$) are visible, while $09:17$ is still forming. For 5-minute bars, only bars through $09:10$ (available at $09:15:00$) are visible, preventing lookahead leakage.