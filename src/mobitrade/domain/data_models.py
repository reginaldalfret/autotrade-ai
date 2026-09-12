from datetime import datetime, date, time, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
from mobitrade.domain.enums import MarketType

class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    D1 = "1d"

    @property
    def minutes(self) -> int:
        if self == Timeframe.M1:
            return 1
        elif self == Timeframe.M5:
            return 5
        elif self == Timeframe.M15:
            return 15
        elif self == Timeframe.D1:
            return 375
        return 1

    @property
    def intraday_bars_per_session(self) -> int:
        """
        Standard NSE cash market trading hours: 09:15 to 15:30 IST = 375 minutes.
        1m  = 375 bars
        5m  = 75 bars
        15m = 25 bars
        1d  = 1 bar
        """
        if self == Timeframe.M1:
            return 375
        elif self == Timeframe.M5:
            return 75
        elif self == Timeframe.M15:
            return 25
        elif self == Timeframe.D1:
            return 1
        return 375

class CandleTimestampSemantic(str, Enum):
    INTERVAL_BEGINNING = "INTERVAL_BEGINNING"
    INTERVAL_END = "INTERVAL_END"

class DataStatus(str, Enum):
    VALID = "VALID"
    ZERO_VOLUME = "ZERO_VOLUME"
    MISSING = "MISSING"
    HALTED = "HALTED"
    ANOMALY = "ANOMALY"
    INCOMPLETE = "INCOMPLETE"

class Instrument(BaseModel):
    symbol: str
    exchange: str = "NSE"
    segment: str = "EQUITY"
    instrument_id: Optional[str] = None
    isin: Optional[str] = None
    security_name: str
    trading_status: str = "ACTIVE"
    lot_size: int = 1
    tick_size: float = 0.05
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    data_source: str
    ingested_at: datetime
    source_version: str = "1.0"

class CorporateActionType(str, Enum):
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    DIVIDEND = "DIVIDEND"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    MERGER = "MERGER"

class CorporateAction(BaseModel):
    symbol: str
    action_type: CorporateActionType
    ex_date: date
    ratio_from: Optional[float] = None
    ratio_to: Optional[float] = None
    dividend_amount: Optional[float] = None
    old_symbol: Optional[str] = None
    new_symbol: Optional[str] = None
    description: str

class HistoricalCandle(BaseModel):
    symbol: str
    exchange: str = "NSE"
    timeframe: Timeframe
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    status: DataStatus = DataStatus.VALID
    timestamp_semantic: CandleTimestampSemantic = CandleTimestampSemantic.INTERVAL_BEGINNING
    is_adjusted: bool = False

    @property
    def available_at(self) -> datetime:
        """
        Explicit temporal availability:
        Since historical candles use INTERVAL_BEGINNING, the completed candle
        close and final OHLCV values are only available after interval completion.
        e.g. 1m candle at 09:15 is available_at 09:16:00.
             5m candle at 09:15 is available_at 09:20:00.
             15m candle at 09:15 is available_at 09:30:00.
        """
        if self.timestamp_semantic == CandleTimestampSemantic.INTERVAL_BEGINNING:
            return self.timestamp + timedelta(minutes=self.timeframe.minutes)
        return self.timestamp

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < self.open or self.high < self.close or self.high < self.low:
            raise ValueError(f"High ({self.high}) must be >= open, close, and low")
        if self.low > self.open or self.low > self.close:
            raise ValueError(f"Low ({self.low}) must be <= open and close")
        return self

class DatasetProvenance(BaseModel):
    dataset_id: str
    source_provider: str
    endpoint: str = "/history"
    symbol: str
    exchange: str = "NSE"
    timeframe: Timeframe
    requested_range_start: datetime
    requested_range_end: datetime
    actual_range_start: Optional[datetime] = None
    actual_range_end: Optional[datetime] = None
    retrieval_timestamp: datetime
    source_version: str = "1.0"
    processing_version: str = "1.1.0"
    calendar_version: str = "1.0.0"
    total_candles: int
    missing_intervals: int = 0
    duplicate_count: int = 0
    anomalies_count: int = 0
    checksum_sha256: str