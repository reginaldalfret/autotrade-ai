from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from mobitrade.domain.data_models import Timeframe, DataStatus

class TrendClassification(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class TechnicalFeatures(BaseModel):
    symbol: str
    exchange: str = "NSE"
    candle_timestamp: datetime
    feature_available_at: datetime
    timeframe: Timeframe
    data_status: DataStatus = DataStatus.VALID
    feature_version: str = "1.1.0"
    source_dataset_id: Optional[str] = None

    # Base Bar References (from last completed candle)
    price: float = Field(gt=0)
    volume: float = Field(ge=0)

    # 1. Moving Averages (5, 9, 20, 50)
    sma_5: Optional[float] = None
    sma_9: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None

    ema_5: Optional[float] = None
    ema_9: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None

    # 2. Oscillators & Volatility
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    atr_14: Optional[float] = None
    volatility_20: Optional[float] = None

    # 3. Session & Volume
    vwap: Optional[float] = None
    relative_volume_20: Optional[float] = None

    # 4. Momentum (1, 3, 5, 10, 20 bars)
    momentum_1: Optional[float] = None
    momentum_3: Optional[float] = None
    momentum_5: Optional[float] = None
    momentum_10: Optional[float] = None
    momentum_20: Optional[float] = None

    # 5. Price Structure
    distance_from_session_high: Optional[float] = None
    distance_from_session_low: Optional[float] = None
    distance_from_vwap: Optional[float] = None
    rolling_high_20: Optional[float] = None
    rolling_low_20: Optional[float] = None
    candle_body: float = 0.0
    candle_range: float = 0.0
    upper_wick: float = 0.0
    lower_wick: float = 0.0
    close_position_in_range: float = 0.5

    # 6. Trend
    trend: TrendClassification = TrendClassification.NEUTRAL
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_temporal_ordering(self):
        # Strict temporal invariant: feature_available_at cannot precede candle_timestamp
        if self.feature_available_at < self.candle_timestamp:
            raise ValueError(
                f"Temporal violation: feature_available_at ({self.feature_available_at}) "
                f"cannot be earlier than candle_timestamp ({self.candle_timestamp})"
            )
        return self