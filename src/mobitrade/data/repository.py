import os
import json
from pathlib import Path
from datetime import datetime, date, timezone
from typing import List, Optional
import zoneinfo
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from mobitrade.domain.data_models import HistoricalCandle, DatasetProvenance, Timeframe, DataStatus, CandleTimestampSemantic

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

class ParquetDataRepository:
    """
    Partition-aware columnar Parquet repository for processed historical candles on D: drive.
    Structured by year/month to avoid reading all files into memory on an 8 GB RAM system:
    data/processed/market=indian_equity/exchange={exchange}/symbol={symbol}/timeframe={timeframe}/year={year}/month={month}/
    """
    def __init__(self, base_data_dir: str = "data"):
        self.base_dir = Path(base_data_dir)
        self.raw_dir = self.base_dir / "raw"
        self.processed_dir = self.base_dir / "processed" / "market=indian_equity"
        self.metadata_dir = self.base_dir / "metadata"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_partition_dir(self, exchange: str, symbol: str, timeframe: Timeframe, dt: datetime) -> Path:
        dt_ist = dt.astimezone(IST) if dt.tzinfo else dt.replace(tzinfo=IST)
        path = (
            self.processed_dir
            / f"exchange={exchange}"
            / f"symbol={symbol}"
            / f"timeframe={timeframe.value}"
            / f"year={dt_ist.year}"
            / f"month={dt_ist.month:02d}"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_candles(
        self, candles: List[HistoricalCandle], provenance: DatasetProvenance
    ) -> List[str]:
        if not candles:
            return []

        # Group candles by year/month for efficient partitioning
        grouped = {}
        for c in candles:
            dt = c.timestamp.astimezone(IST) if c.timestamp.tzinfo else c.timestamp.replace(tzinfo=IST)
            key = (dt.year, dt.month)
            grouped.setdefault(key, []).append(c)

        saved_files = []
        for (year, month), chunk in grouped.items():
            sample = chunk[0]
            part_dir = self._get_partition_dir(sample.exchange, sample.symbol, sample.timeframe, sample.timestamp)
            file_name = f"candles_{year}{month:02d}.parquet"
            file_path = part_dir / file_name

            data = []
            for c in chunk:
                data.append({
                    "symbol": c.symbol,
                    "exchange": c.exchange,
                    "timeframe": c.timeframe.value,
                    "timestamp": c.timestamp.astimezone(IST),
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "status": c.status.value,
                    "timestamp_semantic": c.timestamp_semantic.value,
                    "is_adjusted": c.is_adjusted
                })

            df = pd.DataFrame(data)
            # Merge with existing file if it exists to preserve idempotence & chunk resume
            if file_path.exists():
                existing_df = pq.read_table(file_path).to_pandas()
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=["timestamp"]).sort_values(by="timestamp")

            table = pa.Table.from_pandas(df)
            pq.write_table(table, file_path)
            saved_files.append(str(file_path))

        # Save provenance with UTC timestamp
        meta_file = self.metadata_dir / f"provenance_{provenance.dataset_id}.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(provenance.model_dump_json(indent=2))

        return saved_files

    def load_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        exchange: str = "NSE"
    ) -> List[HistoricalCandle]:
        """
        Date-range aware Parquet load: reads only relevant year/month partitions.
        Accepts naive, UTC, or IST timestamps and handles them deterministically.
        """
        base_symbol_dir = (
            self.processed_dir
            / f"exchange={exchange}"
            / f"symbol={symbol}"
            / f"timeframe={timeframe.value}"
        )
        if not base_symbol_dir.exists():
            return []

        # Normalize filter boundaries to IST
        start_ist = start_time.astimezone(IST) if (start_time and start_time.tzinfo) else (
            start_time.replace(tzinfo=IST) if start_time else None
        )
        end_ist = end_time.astimezone(IST) if (end_time and end_time.tzinfo) else (
            end_time.replace(tzinfo=IST) if end_time else None
        )

        all_files = list(base_symbol_dir.glob("**/*.parquet"))
        if not all_files:
            return []

        # Filter files by partition path if start/end are specified
        matched_files = []
        for f in all_files:
            # Parse year and month from path e.g. year=2026/month=09
            try:
                parts = f.parent.parts
                m_part = [p for p in parts if p.startswith("month=")][0]
                y_part = [p for p in parts if p.startswith("year=")][0]
                y = int(y_part.split("=")[1])
                m = int(m_part.split("=")[1])
                
                # Check range overlap
                if start_ist and (y < start_ist.year or (y == start_ist.year and m < start_ist.month)):
                    continue
                if end_ist and (y > end_ist.year or (y == end_ist.year and m > end_ist.month)):
                    continue
                matched_files.append(f)
            except Exception:
                matched_files.append(f)

        if not matched_files:
            return []

        all_dfs = [pq.read_table(f).to_pandas() for f in matched_files]
        df = pd.concat(all_dfs, ignore_index=True)
        df = df.sort_values(by="timestamp").drop_duplicates(subset=["timestamp"])

        if start_ist:
            df = df[df["timestamp"] >= start_ist]
        if end_ist:
            df = df[df["timestamp"] <= end_ist]

        result = []
        for _, row in df.iterrows():
            ts = row["timestamp"].to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=IST)
            result.append(
                HistoricalCandle(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    timeframe=Timeframe(row["timeframe"]),
                    timestamp=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    status=DataStatus(row["status"]),
                    timestamp_semantic=CandleTimestampSemantic(row["timestamp_semantic"]),
                    is_adjusted=bool(row["is_adjusted"])
                )
            )
        return result

    def get_provenance(self, dataset_id: str) -> Optional[DatasetProvenance]:
        meta_file = self.metadata_dir / f"provenance_{dataset_id}.json"
        if not meta_file.exists():
            return None
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return DatasetProvenance(**data)