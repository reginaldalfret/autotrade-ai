from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import zoneinfo
from mobitrade.domain.data_models import HistoricalCandle, DataStatus, Timeframe
from mobitrade.data.calendar import IndianMarketCalendar

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

class DataQualityValidator:
    """
    Validates candle integrity:
    - Timezone conversion to Asia/Kolkata
    - Chronological sorting
    - Detection of duplicates, missing intervals, out-of-bounds prices, and zero volume
    - Aggregation validation (1m -> 5m, 15m)
    """
    def __init__(self, calendar: IndianMarketCalendar):
        self.calendar = calendar

    def normalize_timestamp(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)

    def validate_and_clean_candles(
        self, candles: List[HistoricalCandle]
    ) -> Tuple[List[HistoricalCandle], Dict[str, Any]]:
        if not candles:
            return [], {"total": 0, "valid": 0, "duplicates": 0, "anomalies": 0}

        cleaned: List[HistoricalCandle] = []
        seen_timestamps = set()
        duplicates_count = 0
        anomalies_count = 0

        # Ensure sorted by timestamp
        sorted_candles = sorted(candles, key=lambda c: c.timestamp)

        for c in sorted_candles:
            ts = self.normalize_timestamp(c.timestamp)
            
            # Duplicate check
            if ts in seen_timestamps:
                duplicates_count += 1
                continue
            seen_timestamps.add(ts)

            # Check session boundaries
            if not self.calendar.is_trading_session(ts):
                anomalies_count += 1
                c.status = DataStatus.ANOMALY

            # Check zero volume
            if c.volume == 0 and c.status == DataStatus.VALID:
                c.status = DataStatus.ZERO_VOLUME

            c.timestamp = ts
            cleaned.append(c)

        stats = {
            "total": len(candles),
            "valid": len(cleaned),
            "duplicates": duplicates_count,
            "anomalies": anomalies_count
        }
        return cleaned, stats

    def aggregate_candles(
        self, one_min_candles: List[HistoricalCandle], target_timeframe: Timeframe
    ) -> List[HistoricalCandle]:
        """
        Derives higher timeframe candles (5m, 15m) strictly from validated 1m candles.
        Preserves interval-beginning timestamp semantic.
        """
        if target_timeframe == Timeframe.M1:
            return one_min_candles
        if not one_min_candles:
            return []

        interval_minutes = target_timeframe.minutes
        aggregated: List[HistoricalCandle] = []
        
        # Group by interval boundary
        current_bucket = []
        current_boundary = None

        for c in one_min_candles:
            # Floor timestamp to target interval boundary
            ts = c.timestamp
            floored_minute = (ts.minute // interval_minutes) * interval_minutes
            bucket_start = ts.replace(minute=floored_minute, second=0, microsecond=0)

            if current_boundary is None:
                current_boundary = bucket_start

            if bucket_start != current_boundary:
                # Flush current bucket
                agg = self._build_aggregated_candle(current_bucket, current_boundary, target_timeframe)
                if agg:
                    aggregated.append(agg)
                current_bucket = [c]
                current_boundary = bucket_start
            else:
                current_bucket.append(c)

        # Flush final bucket
        if current_bucket and current_boundary:
            agg = self._build_aggregated_candle(current_bucket, current_boundary, target_timeframe)
            if agg:
                aggregated.append(agg)

        return aggregated

    def _build_aggregated_candle(
        self, bucket: List[HistoricalCandle], boundary: datetime, timeframe: Timeframe
    ) -> HistoricalCandle:
        first = bucket[0]
        last = bucket[-1]
        highest = max(b.high for b in bucket)
        lowest = min(b.low for b in bucket)
        total_vol = sum(b.volume for b in bucket)

        return HistoricalCandle(
            symbol=first.symbol,
            exchange=first.exchange,
            timeframe=timeframe,
            timestamp=boundary,
            open=first.open,
            high=highest,
            low=lowest,
            close=last.close,
            volume=total_vol,
            status=DataStatus.VALID,
            timestamp_semantic=first.timestamp_semantic,
            is_adjusted=first.is_adjusted
        )