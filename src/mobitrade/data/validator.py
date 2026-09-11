import hashlib
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Tuple, Set
import zoneinfo
from mobitrade.domain.data_models import HistoricalCandle, DataStatus, Timeframe, CandleTimestampSemantic
from mobitrade.data.calendar import IndianMarketCalendar

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = zoneinfo.ZoneInfo("UTC")

class DataQualityValidator:
    """
    Hardened validation, missing-data calculation, strict incomplete aggregation,
    and deterministic SHA-256 computation for Indian Equity candles.
    """
    def __init__(self, calendar: IndianMarketCalendar):
        self.calendar = calendar

    def normalize_timestamp(self, dt: datetime) -> datetime:
        """
        Converts any naive or timezone-aware datetime to timezone-aware Asia/Kolkata.
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)

    def compute_dataset_sha256(self, candles: List[HistoricalCandle]) -> str:
        """
        Calculates a cryptographically sound SHA-256 digest across all candle attributes.
        Guarantees:
        - Identical dataset -> Identical SHA-256.
        - Changed price/volume/timestamp/status -> Different SHA-256.
        """
        hasher = hashlib.sha256()
        sorted_candles = sorted(candles, key=lambda c: (c.symbol, c.timeframe.value, c.timestamp))
        for c in sorted_candles:
            # Deterministic serialization string
            row_str = (
                f"{c.symbol}|{c.exchange}|{c.timeframe.value}|"
                f"{c.timestamp.isoformat()}|{c.open:.4f}|{c.high:.4f}|"
                f"{c.low:.4f}|{c.close:.4f}|{c.volume:.4f}|{c.status.value}|"
                f"{c.timestamp_semantic.value}|{int(c.is_adjusted)}"
            )
            hasher.update(row_str.encode("utf-8"))
        return hasher.hexdigest()

    def get_expected_session_timestamps(
        self, start_dt: datetime, end_dt: datetime, timeframe: Timeframe
    ) -> List[datetime]:
        """
        Generates the exact list of expected NSE interval timestamps between start_dt and end_dt.
        """
        start_ist = self.normalize_timestamp(start_dt)
        end_ist = self.normalize_timestamp(end_dt)
        expected: List[datetime] = []

        curr_date = start_ist.date()
        end_date = end_ist.date()

        interval_delta = timedelta(minutes=timeframe.minutes)

        while curr_date <= end_date:
            if self.calendar.is_trading_day(curr_date):
                # Normal NSE session: 09:15 to 15:30
                session_start = datetime.combine(curr_date, time(9, 15), tzinfo=IST)
                session_end = datetime.combine(curr_date, time(15, 30), tzinfo=IST)
                
                curr_ts = session_start
                while curr_ts < session_end:
                    if start_ist <= curr_ts <= end_ist:
                        expected.append(curr_ts)
                    curr_ts += interval_delta

            curr_date += timedelta(days=1)

        return expected

    def validate_and_clean_candles(
        self,
        candles: List[HistoricalCandle],
        expected_range_start: Optional[datetime] = None,
        expected_range_end: Optional[datetime] = None
    ) -> Tuple[List[HistoricalCandle], Dict[str, Any]]:
        if not candles:
            return [], {
                "total": 0, "valid": 0, "duplicates": 0,
                "anomalies": 0, "missing_intervals": 0, "unexpected": 0
            }

        cleaned: List[HistoricalCandle] = []
        seen_timestamps: Set[datetime] = set()
        duplicates_count = 0
        anomalies_count = 0
        unexpected_count = 0

        sorted_candles = sorted(candles, key=lambda c: c.timestamp)

        for c in sorted_candles:
            ts = self.normalize_timestamp(c.timestamp)

            # Duplicate check
            if ts in seen_timestamps:
                duplicates_count += 1
                continue
            seen_timestamps.add(ts)

            # Unexpected / Session boundary check
            if not self.calendar.is_trading_session(ts):
                unexpected_count += 1
                anomalies_count += 1
                c.status = DataStatus.ANOMALY

            if c.volume == 0 and c.status == DataStatus.VALID:
                c.status = DataStatus.ZERO_VOLUME

            c.timestamp = ts
            cleaned.append(c)

        # Missing interval detection
        missing_count = 0
        sample_tf = candles[0].timeframe
        if expected_range_start and expected_range_end:
            expected_ts_list = self.get_expected_session_timestamps(
                expected_range_start, expected_range_end, sample_tf
            )
            for exp_ts in expected_ts_list:
                if exp_ts not in seen_timestamps:
                    missing_count += 1

        stats = {
            "total": len(candles),
            "valid": len(cleaned),
            "duplicates": duplicates_count,
            "anomalies": anomalies_count,
            "unexpected": unexpected_count,
            "missing_intervals": missing_count
        }
        return cleaned, stats

    def aggregate_candles(
        self, one_min_candles: List[HistoricalCandle], target_timeframe: Timeframe
    ) -> List[HistoricalCandle]:
        """
        Derives 5m and 15m candles from 1m candles.
        CRITICAL REQUIREMENT:
        - 5m candle requires EXACTLY 5 one-minute candles.
        - 15m candle requires EXACTLY 15 one-minute candles.
        If incomplete, flagged as DataStatus.INCOMPLETE (never silently passed as VALID).
        """
        if target_timeframe == Timeframe.M1:
            return one_min_candles
        if not one_min_candles:
            return []

        required_count = target_timeframe.minutes
        aggregated: List[HistoricalCandle] = []

        current_bucket: List[HistoricalCandle] = []
        current_boundary: Optional[datetime] = None

        for c in one_min_candles:
            ts = self.normalize_timestamp(c.timestamp)
            floored_minute = (ts.minute // required_count) * required_count
            bucket_start = ts.replace(minute=floored_minute, second=0, microsecond=0)

            if current_boundary is None:
                current_boundary = bucket_start

            if bucket_start != current_boundary:
                agg = self._build_aggregated_candle(current_bucket, current_boundary, target_timeframe, required_count)
                if agg:
                    aggregated.append(agg)
                current_bucket = [c]
                current_boundary = bucket_start
            else:
                current_bucket.append(c)

        if current_bucket and current_boundary:
            agg = self._build_aggregated_candle(current_bucket, current_boundary, target_timeframe, required_count)
            if agg:
                aggregated.append(agg)

        return aggregated

    def _build_aggregated_candle(
        self, bucket: List[HistoricalCandle], boundary: datetime, timeframe: Timeframe, required_count: int
    ) -> HistoricalCandle:
        first = bucket[0]
        last = bucket[-1]
        highest = max(b.high for b in bucket)
        lowest = min(b.low for b in bucket)
        total_vol = sum(b.volume for b in bucket)

        # Flag incomplete intervals explicitly
        status = DataStatus.VALID if len(bucket) == required_count else DataStatus.INCOMPLETE

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
            status=status,
            timestamp_semantic=first.timestamp_semantic,
            is_adjusted=first.is_adjusted
        )