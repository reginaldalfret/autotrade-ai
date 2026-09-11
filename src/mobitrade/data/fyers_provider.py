import os
import requests
from datetime import datetime, timezone
from typing import List, Optional
import zoneinfo
from mobitrade.domain.data_models import HistoricalCandle, Timeframe, DataStatus, CandleTimestampSemantic

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

class FyersDataProvider:
    """
    FYERS API v3 historical market data adapter.
    Documentation specifications:
    - History API endpoint: GET {base_url}/history
    - Parameters: symbol (e.g. NSE:RELIANCE-EQ), resolution (1, 5, 15, D),
                  date_format=1, range_from (YYYY-MM-DD), range_to (YYYY-MM-DD)
    - Response candles schema: [[timestamp, open, high, low, close, volume], ...]
    - Timestamp represents interval beginning in Unix epoch.
    - Handles timeouts, rate-limits (HTTP 429), errors, and malformed structures cleanly.
    """
    def __init__(
        self,
        app_id: Optional[str] = None,
        access_token: Optional[str] = None,
        base_url: str = "https://api-t1.fyers.in/data",
        timeout: int = 10,
        session: Optional[requests.Session] = None
    ):
        self.app_id = app_id or os.getenv("FYERS_APP_ID")
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.access_token)

    def _map_timeframe_to_resolution(self, timeframe: Timeframe) -> str:
        if timeframe == Timeframe.M1:
            return "1"
        elif timeframe == Timeframe.M5:
            return "5"
        elif timeframe == Timeframe.M15:
            return "15"
        elif timeframe == Timeframe.D1:
            return "D"
        return "1"

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
                "FYERS API credentials not configured. Set FYERS_APP_ID and FYERS_ACCESS_TOKEN."
            )

        fyers_symbol = f"{exchange}:{symbol}-EQ" if not symbol.startswith("NSE:") else symbol
        resolution = self._map_timeframe_to_resolution(timeframe)

        # Normalize dates to YYYY-MM-DD
        range_from = start_time.strftime("%Y-%m-%d")
        range_to = end_time.strftime("%Y-%m-%d")

        url = f"{self.base_url}/history"
        headers = {
            "Authorization": f"{self.app_id}:{self.access_token}"
        }
        params = {
            "symbol": fyers_symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1"
        }

        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"FYERS API request timed out after {self.timeout}s: {e}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"FYERS API network failure: {e}")

        if resp.status_code == 429:
            raise RuntimeError("FYERS API rate limit exceeded (HTTP 429).")
        elif resp.status_code != 200:
            raise RuntimeError(f"FYERS API error {resp.status_code}: {resp.text}")

        try:
            payload = resp.json()
        except Exception as e:
            raise ValueError(f"Malformed JSON response from FYERS API: {e}")

        if payload.get("s") != "ok":
            error_msg = payload.get("message", "Unknown error from FYERS API")
            raise ValueError(f"FYERS API responded with error: {error_msg}")

        raw_candles = payload.get("candles", [])
        if not isinstance(raw_candles, list):
            raise ValueError("Malformed response: 'candles' key is not a list")

        candles: List[HistoricalCandle] = []
        for item in raw_candles:
            if not isinstance(item, list) or len(item) < 6:
                raise ValueError(f"Invalid candle record in FYERS payload: {item}")

            epoch_ts, o, h, l, c, v = item[0], item[1], item[2], item[3], item[4], item[5]
            # Convert epoch to timezone-aware Asia/Kolkata
            ts = datetime.fromtimestamp(epoch_ts, tz=IST)

            candles.append(
                HistoricalCandle(
                    symbol=symbol.replace("NSE:", "").replace("-EQ", ""),
                    exchange=exchange,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(v),
                    status=DataStatus.VALID,
                    timestamp_semantic=CandleTimestampSemantic.INTERVAL_BEGINNING,
                    is_adjusted=False
                )
            )

        return candles