import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import zoneinfo
from mobitrade.domain.data_models import HistoricalCandle, DatasetProvenance, Timeframe
from mobitrade.data.validator import DataQualityValidator
from mobitrade.data.repository import ParquetDataRepository

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

class DataDownloadManager:
    """
    Manages deterministic chunked historical downloads, validation,
    real SHA-256 computation, overlap deduplication, and failure recovery.
    """
    def __init__(
        self,
        repository: ParquetDataRepository,
        validator: DataQualityValidator
    ):
        self.repository = repository
        self.validator = validator

    def generate_chunks(
        self, start_date: datetime, end_date: datetime, chunk_days: int = 15
    ) -> List[Tuple[datetime, datetime]]:
        """
        Splits a wide date range into deterministic provider-friendly chunks.
        """
        chunks = []
        curr = start_date
        while curr < end_date:
            chunk_end = min(curr + timedelta(days=chunk_days), end_date)
            chunks.append((curr, chunk_end))
            curr = chunk_end + timedelta(days=1)
        return chunks

    def ingest_candles(
        self,
        provider_name: str,
        symbol: str,
        timeframe: Timeframe,
        raw_candles: List[HistoricalCandle],
        start_date: datetime,
        end_date: datetime,
        exchange: str = "NSE",
        endpoint: str = "/history"
    ) -> DatasetProvenance:
        dataset_id = f"ds_{uuid.uuid4().hex[:8]}"

        # 1. Validation, cleaning, and missing intervals calculation
        cleaned_candles, stats = self.validator.validate_and_clean_candles(
            raw_candles,
            expected_range_start=start_date,
            expected_range_end=end_date
        )

        # 2. Cryptographically sound SHA-256 digest
        real_sha256 = self.validator.compute_dataset_sha256(cleaned_candles)

        actual_start = cleaned_candles[0].timestamp if cleaned_candles else None
        actual_end = cleaned_candles[-1].timestamp if cleaned_candles else None

        # 3. Complete dataset provenance with timezone-aware UTC retrieval timestamp
        provenance = DatasetProvenance(
            dataset_id=dataset_id,
            source_provider=provider_name,
            endpoint=endpoint,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            requested_range_start=self.validator.normalize_timestamp(start_date),
            requested_range_end=self.validator.normalize_timestamp(end_date),
            actual_range_start=actual_start,
            actual_range_end=actual_end,
            retrieval_timestamp=datetime.now(UTC),
            source_version="1.0",
            processing_version="1.1.0",
            calendar_version=self.validator.calendar.version,
            total_candles=len(cleaned_candles),
            missing_intervals=stats["missing_intervals"],
            duplicate_count=stats["duplicates"],
            anomalies_count=stats["anomalies"],
            checksum_sha256=real_sha256
        )

        # 4. Save to partition-aware Parquet
        self.repository.save_candles(cleaned_candles, provenance)

        return provenance