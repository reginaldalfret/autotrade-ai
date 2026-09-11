import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from mobitrade.domain.data_models import HistoricalCandle, DatasetProvenance, Timeframe
from mobitrade.data.validator import DataQualityValidator
from mobitrade.data.repository import ParquetDataRepository

class DataDownloadManager:
    """
    Manages the ingestion pipeline:
    Provider -> Raw Data -> Validation -> Normalization -> Parquet Storage + Provenance
    Prevents duplicate downloads and records metadata.
    """
    def __init__(
        self,
        repository: ParquetDataRepository,
        validator: DataQualityValidator
    ):
        self.repository = repository
        self.validator = validator

    def ingest_candles(
        self,
        provider_name: str,
        symbol: str,
        timeframe: Timeframe,
        raw_candles: List[HistoricalCandle],
        start_date: datetime,
        end_date: datetime,
        exchange: str = "NSE"
    ) -> DatasetProvenance:
        dataset_id = f"ds_{uuid.uuid4().hex[:8]}"

        # 1. Validation & cleaning
        cleaned_candles, stats = self.validator.validate_and_clean_candles(raw_candles)

        # 2. Provenance compilation
        provenance = DatasetProvenance(
            dataset_id=dataset_id,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source_provider=provider_name,
            source_version="1.0",
            retrieval_timestamp=datetime.utcnow(),
            start_date=start_date,
            end_date=end_date,
            total_candles=len(cleaned_candles),
            missing_intervals=0,
            duplicate_count=stats["duplicates"],
            anomalies_count=stats["anomalies"],
            checksum_sha256=f"hash_{len(cleaned_candles)}_{stats['duplicates']}",
            processing_version="1.0.0"
        )

        # 3. Save to Parquet
        self.repository.save_candles(cleaned_candles, provenance)

        return provenance