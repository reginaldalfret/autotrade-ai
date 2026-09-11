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
    """
    def __init__(self, base_data_dir: str = "/mnt/d/Trading LLM/MobiTradeAI/data"):
        self.base_dir = Path(base_data_dir)
        self.features_dir = self.base_dir / "processed" / "market=indian_equity" / "features"
        self.features_dir.mkdir(parents=True, exist_ok=True)

    def _get_partition_dir(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        path = (
            self.features_dir
            / f"exchange={exchange}"
            / f"symbol={symbol}"
            / f"timeframe={timeframe.value}"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_features(self, features: List[TechnicalFeatures]) -> str:
        if not features:
            return ""

        sample = features[0]
        part_dir = self._get_partition_dir(sample.exchange, sample.symbol, sample.timeframe)
        file_path = part_dir / f"features_{sample.feature_version}.parquet"

        records = []
        for f in features:
            d = f.model_dump()
            d["timeframe"] = f.timeframe.value
            d["data_status"] = f.data_status.value
            d["trend"] = f.trend.value
            # Serialize metadata dict to JSON string to avoid empty struct pyarrow error
            d["metadata"] = json.dumps(d.get("metadata", {}))
            records.append(d)

        df = pd.DataFrame(records)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, file_path)
        return str(file_path)

    def load_features(
        self, symbol: str, timeframe: Timeframe, exchange: str = "NSE"
    ) -> List[TechnicalFeatures]:
        part_dir = self._get_partition_dir(exchange, symbol, timeframe)
        parquet_files = list(part_dir.glob("*.parquet"))
        if not parquet_files:
            return []

        all_dfs = [pq.read_table(f).to_pandas() for f in parquet_files]
        df = pd.concat(all_dfs, ignore_index=True).sort_values(by="timestamp")

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