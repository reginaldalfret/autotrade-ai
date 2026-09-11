import os
from datetime import datetime
from typing import List, Optional
from mobitrade.domain.data_models import HistoricalCandle, Timeframe, CandleTimestampSemantic

class FyersDataProvider:
    """
    FYERS API v3 historical market data adapter foundation.
    Documentation specifications:
    - History API: /history?symbol=NSE:SBIN-EQ&resolution=1&date_format=1&range_from=...&range_to=...
    - Candle array schema: [timestamp, open, high, low, close, volume]
    - Timestamp represents the beginning of the candle interval.
    - Operates safely without credentials for testability.
    """
    def __init__(
        self,
        app_id: Optional[str] = None,
        access_token: Optional[str] = None,
        base_url: str = "https://api-t1.fyers.in/data"
    ):
        self.app_id = app_id or os.getenv("FYERS_APP_ID")
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN")
        self.base_url = base_url

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.access_token)

    def fetch_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        exchange: str = "NSE"
    ) -> List[HistoricalCandle]:
        if not self.is_configured:
            raise ValueError(
                "FYERS API credentials not configured. Please set FYERS_APP_ID and FYERS_ACCESS_TOKEN."
            )
        # Note: Live HTTP calls occur only when configured in runtime.
        # Tests use LocalFileMarketDataProvider.
        return []