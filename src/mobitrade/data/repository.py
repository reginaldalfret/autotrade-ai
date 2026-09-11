import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from mobitrade.domain.data_models import HistoricalCandle, DatasetProvenance, Timeframe, DataStatus, CandleTimestampSemantic

class ParquetDataRepository:
    """
    Columnar Parquet repository for processed historical candles on D: drive.
    Structured under:
    data/processed/market=indian_equity/exchange={exchange}/symbol={symbol}/timeframe={timeframe}/
    """
    def __init__(self, base_data_dir: str = "/mnt/d/Trading LLM/MobiTradeAI/data"):
        self.base_dir = Path(base_data_dir)
        self.raw_dir = self.base_dir / "raw"
        self.processed_dir = self.base_dir / "processed" / "market=indian_equity"
        self.metadata_dir = self.base_dir / "metadata"
        
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_partition_path(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        path = (
            self.processed_dir
            / f"exchange={exchange}"
            / f"symbol={symbol}"
            / f"timeframe={timeframe.value}"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_candles(
        self, candles: List[HistoricalCandle], provenance: DatasetProvenance
    ) -> str:
        if not candles:
            return ""

        sample = candles[0]
        partition = self._get_partition_path(sample.exchange, sample.symbol, sample.timeframe)
        
        # Format year/month filename for chunking
        start_str = sample.timestamp.strftime("%Y%m%d")
        file_name = f"candles_{start_str}.parquet"
        file_path = partition / file_name

        data = []
        for c in candles:
            data.append({
                "symbol": c.symbol,
                "exchange": c.exchange,
                "timeframe": c.timeframe.value,
                "timestamp": c.timestamp,
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
        table = pa.Table.from_pandas(df)
        pq.write_table(table, file_path)

        # Save provenance metadata
        meta_file = self.metadata_dir / f"provenance_{provenance.dataset_id}.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(provenance.model_dump_json(indent=2))

        return str(file_path)

    def load_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        exchange: str = "NSE"
    ) -> List[HistoricalCandle]:
        partition = self._get_partition_path(exchange, symbol, timeframe)
        parquet_files = list(partition.glob("*.parquet"))
        if not parquet_files:
            return []

        all_dfs = [pq.read_table(f).to_pandas() for f in parquet_files]
        df = pd.concat(all_dfs, ignore_index=True)
        
        # Ensure timestamp sorting
        df = df.sort_values(by="timestamp")

        if start_time:
            df = df[df["timestamp"] >= start_time]
        if end_time:
            df = df[df["timestamp"] <= end_time]

        result = []
        for _, row in df.iterrows():
            result.append(
                HistoricalCandle(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    timeframe=Timeframe(row["timeframe"]),
                    timestamp=row["timestamp"].to_pydatetime(),
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