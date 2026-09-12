from pathlib import Path
from typing import List, Optional
import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from mobitrade.domain.data_models import Timeframe, DataStatus
from mobitrade.domain.feature_models import TechnicalFeatures, TrendClassification

class ParquetFeatureRepository:
    """
    Columnar Parquet repository for computed TechnicalFeatures on D: drive.
    Partitioned as:
    data/processed/market=indian_equity/features/exchange={exchange}/symbol={symbol}/timeframe={timeframe}/
    
    Hardening:
    - Pure reads NEVER create directories (no side-effects during query).
    - Writes are idempotent: Incremental batches merge safely without data loss.
    - Deterministic deduplication across identity key:
      (symbol, exchange, timeframe, candle_timestamp, feature_version).
    - Sorts strictly by candle_timestamp.
    """
    def __init__(self, base_data_dir: str = "/mnt/d/Trading LLM/MobiTradeAI/data"):
        self.base_dir = Path(base_data_dir)
        self.features_dir = self.base_dir / "processed" / "market=indian_equity" / "features"

    def _get_partition_dir(self, exchange: str, symbol: str, timeframe: Timeframe, create: bool = False) -> Path:
        path = (
            self.features_dir
            / f"exchange={exchange}"
            / f"symbol={symbol}"
            / f"timeframe={timeframe.value}"
        )
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def save_features(self, features: List[TechnicalFeatures]) -> str:
        if not features:
            return ""

        sample = features[0]
        # Only create directories during explicit save/write
        part_dir = self._get_partition_dir(sample.exchange, sample.symbol, sample.timeframe, create=True)
        file_path = part_dir / f"features_{sample.feature_version}.parquet"

        records = []
        for f in features:
            d = f.model_dump()
            d["timeframe"] = f.timeframe.value
            d["data_status"] = f.data_status.value
            d["trend"] = f.trend.value
            d["metadata"] = json.dumps(d.get("metadata", {}))
            records.append(d)

        new_df = pd.DataFrame(records)

        # Merge with existing data if present (Idempotent incremental batch persistence)
        if file_path.exists():
            existing_df = pq.read_table(file_path).to_pandas()
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # Deduplicate by primary identity key
            dedup_subset = ["symbol", "exchange", "timeframe", "candle_timestamp", "feature_version"]
            combined_df = combined_df.drop_duplicates(subset=dedup_subset, keep="last")
            df = combined_df.sort_values(by="candle_timestamp")
        else:
            df = new_df.sort_values(by="candle_timestamp")

        table = pa.Table.from_pandas(df)
        pq.write_table(table, file_path)
        return str(file_path)

    def load_features(
        self, symbol: str, timeframe: Timeframe, exchange: str = "NSE"
    ) -> List[TechnicalFeatures]:
        """
        Pure read operation: NEVER creates missing partition directories.
        """
        part_dir = self._get_partition_dir(exchange, symbol, timeframe, create=False)
        if not part_dir.exists():
            return []

        parquet_files = list(part_dir.glob("*.parquet"))
        if not parquet_files:
            return []

        all_dfs = [pq.read_table(f).to_pandas() for f in parquet_files]
        df = pd.concat(all_dfs, ignore_index=True).sort_values(by="candle_timestamp")

        results = []
        for _, row in df.iterrows():
            record = row.to_dict()
            record["timeframe"] = Timeframe(record["timeframe"])
            record["data_status"] = DataStatus(record["data_status"])
            record["trend"] = TrendClassification(record["trend"])
            if isinstance(record.get("metadata"), str):
                try:
                    record["metadata"] = json.loads(record["metadata"])
                except Exception:
                    record["metadata"] = {}
            results.append(TechnicalFeatures(**record))
        return results