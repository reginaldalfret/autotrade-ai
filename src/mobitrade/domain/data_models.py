from datetime import datetime, date, time
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
            return 375 # Standard NSE trading day minutes (09:15 to 15:30)
        return 1

class CandleTimestampSemantic(str, Enum):
    INTERVAL_BEGINNING = "INTERVAL_BEGINNING" # e.g. FYERS: 09:15 candle covers 09:15:00 to 09:15:59
    INTERVAL_END = "INTERVAL_END"

class DataStatus(str, Enum):
    VALID = "VALID"
    ZERO_VOLUME = "ZERO_VOLUME"
    MISSING = "MISSING"
    HALTED = "HALTED"
    ANOMALY = "ANOMALY"

class Instrument(BaseModel):
    symbol: str
    exchange: str = "NSE"
    segment: str = "EQUITY" # e.g. CM (Capital Market) / EQ
    instrument_id: Optional[str] = None # e.g. NSE:RELIANCE-EQ
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
    ratio_from: Optional[float] = None # e.g. 1
    ratio_to: Optional[float] = None   # e.g. 2 for 1:2 split
    dividend_amount: Optional[float] = None
    old_symbol: Optional[str] = None
    new_symbol: Optional[str] = None
    description: str

class HistoricalCandle(BaseModel):
    symbol: str
    exchange: str = "NSE"
    timeframe: Timeframe
    timestamp: datetime # Timezone-aware Asia/Kolkata
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    status: DataStatus = DataStatus.VALID
    timestamp_semantic: CandleTimestampSemantic = CandleTimestampSemantic.INTERVAL_BEGINNING
    is_adjusted: bool = False # Raw prices by default

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < self.open or self.high < self.close or self.high < self.low:
            raise ValueError(f"High ({self.high}) must be >= open, close, and low")
        if self.low > self.open or self.low > self.close:
            raise ValueError(f"Low ({self.low}) must be <= open and close")
        return self

class DatasetProvenance(BaseModel):
    dataset_id: str
    symbol: str
    exchange: str = "NSE"
    timeframe: Timeframe
    source_provider: str
    source_version: str
    retrieval_timestamp: datetime
    start_date: datetime
    end_date: datetime
    total_candles: int
    missing_intervals: int = 0
    duplicate_count: int = 0
    anomalies_count: int = 0
    checksum_sha256: Optional[str] = None
    processing_version: str = "1.0.0"