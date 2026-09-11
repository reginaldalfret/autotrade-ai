import json
import zoneinfo
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from mobitrade.domain.data_models import HistoricalCandle, Timeframe, DataStatus, CandleTimestampSemantic

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

class LocalFileMarketDataProvider:
    """
    Offline/Fixture data provider for reproducible testing and CI.
    Reads local JSON/CSV fixture files from tests/fixtures/ without network requests.
    """
    def __init__(self, fixtures_dir: str = "tests/fixtures"):
        self.fixtures_dir = Path(fixtures_dir)

    def fetch_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        exchange: str = "NSE"
    ) -> List[HistoricalCandle]:
        fixture_file = self.fixtures_dir / f"{symbol}_{timeframe.value}.json"
        if not fixture_file.exists():
            return []

        with open(fixture_file, "r", encoding="utf-8") as f:
            raw_candles = json.load(f)

        candles: List[HistoricalCandle] = []
        for item in raw_candles:
            # Parse ISO or Unix timestamp
            if isinstance(item["timestamp"], (int, float)):
                ts = datetime.fromtimestamp(item["timestamp"], tz=IST)
            else:
                ts = datetime.fromisoformat(item["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=IST)

            if start_time <= ts <= end_time:
                candles.append(
                    HistoricalCandle(
                        symbol=symbol,
                        exchange=exchange,
                        timeframe=timeframe,
                        timestamp=ts,
                        open=float(item["open"]),
                        high=float(item["high"]),
                        low=float(item["low"]),
                        close=float(item["close"]),
                        volume=float(item["volume"]),
                        status=DataStatus(item.get("status", "VALID")),
                        timestamp_semantic=CandleTimestampSemantic.INTERVAL_BEGINNING,
                        is_adjusted=bool(item.get("is_adjusted", False))
                    )
                )

        return sorted(candles, key=lambda c: c.timestamp)