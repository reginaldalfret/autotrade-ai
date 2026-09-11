# Data Methodology & Quality Standards

## Indian Equities Data Pipeline
1. **Timezone Representation**: All internal and stored timestamps are strictly normalized to `Asia/Kolkata` (IST).
2. **Candle Semantics**: Candle timestamps represent the beginning of the interval (`INTERVAL_BEGINNING`), preserving FYERS History API semantics.
3. **Partitioning Scheme**: Processed datasets are stored in Apache Parquet format partitioned as:
   `data/processed/market=indian_equity/exchange={exchange}/symbol={symbol}/timeframe={timeframe}/`
4. **Timeframe Aggregation**: 5-minute and 15-minute bars are derived deterministically from validated 1-minute bars without mixing external feeds.
5. **Quality Checks**:
   - Explicit anomaly tagging (`DataStatus.ANOMALY`) rather than silent deletions.
   - Non-negative volumes and positive prices.
   - Explicit zero-volume tracking (`DataStatus.ZERO_VOLUME`) distinguished from market halts or missing data.
   - Strict OHLC inequality verification: `high >= open`, `high >= close`, `low <= open`, `low <= close`.
6. **Corporate Actions & Survivorship Bias**: Raw vs. Adjusted pricing is maintained explicitly via `is_adjusted` flags. The instrument master supports point-in-time validity tracking (`valid_from` to `valid_to`) to eliminate survivorship bias.