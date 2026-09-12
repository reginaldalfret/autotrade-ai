# Data Methodology & Quality Standards (Hardened Phase 3.1)

## Indian Equities Data Pipeline (NSE First)
1. **Timezone Representation**:
   - All internal and stored candle timestamps are timezone-aware `Asia/Kolkata` (IST).
   - Provenance timestamps are recorded in UTC (`datetime.now(timezone.utc)`).
   - Naive datetimes are explicitly rejected or normalized to IST. Queries using equivalent UTC and IST ranges return identical datasets.
2. **Candle Semantics**:
   - Explicitly configured as `INTERVAL_BEGINNING`.
   - `available_at = timestamp + timeframe_duration`.
3. **Partitioning & Memory Efficiency (8 GB RAM Friendly)**:
   - Stored in Apache Parquet partitioned by:
     `data/processed/market=indian_equity/exchange={exchange}/symbol={symbol}/timeframe={timeframe}/year={year}/month={month}/`
   - Repository queries only load Parquet partitions overlapping requested date boundaries.
4. **Strict Incomplete Aggregation**:
   - 5-minute candle requires exactly 5 one-minute candles.
   - 15-minute candle requires exactly 15 one-minute candles.
   - If incomplete, the higher-timeframe candle is explicitly marked `DataStatus.INCOMPLETE` (never silently treated as `VALID`).
5. **Missing Interval & Anomaly Detection**:
   - Calculates expected NSE trading sessions (09:15 to 15:30 IST) across the versioned market calendar.
   - Detects missing candles, duplicate timestamps, and unexpected sessions without silently fabricating data.
6. **Cryptographic Provenance**:
   - Real 64-character SHA-256 computed across all candle attributes.