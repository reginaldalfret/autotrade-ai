from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from mobitrade.domain.data_models import Timeframe
from mobitrade.domain.feature_models import TrendClassification

class RejectionReason(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    ILLIQUID = "ILLIQUID"
    INVALID_PRICE = "INVALID_PRICE"
    DATA_ANOMALY = "DATA_ANOMALY"
    MISSING_FEATURE = "MISSING_FEATURE"
    INVALID_INSTRUMENT = "INVALID_INSTRUMENT"
    OUTSIDE_SESSION = "OUTSIDE_SESSION"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"

class OpportunityScore(BaseModel):
    total_score: float = Field(ge=0.0, le=100.0)
    momentum: float = Field(ge=0.0, le=100.0)
    relative_volume: float = Field(ge=0.0, le=100.0)
    trend: float = Field(ge=0.0, le=100.0)
    breakout: float = Field(ge=0.0, le=100.0)
    volatility: float = Field(ge=0.0, le=100.0)
    liquidity: float = Field(ge=0.0, le=100.0)
    price_structure: float = Field(default=0.0, ge=0.0, le=100.0)
    data_quality: float = Field(default=100.0, ge=0.0, le=100.0)
    weights: Dict[str, float] = Field(default_factory=dict)

class OpportunityCandidate(BaseModel):
    symbol: str
    exchange: str = "NSE"
    instrument_id: Optional[str] = None
    decision_timestamp: datetime
    timeframe: Timeframe
    price: float = Field(gt=0.0)
    opportunity_score: float = Field(ge=0.0, le=100.0)
    score_components: Dict[str, Any] = Field(default_factory=dict)
    candle_timestamp: datetime
    feature_available_at: datetime
    trend: TrendClassification = TrendClassification.NEUTRAL
    momentum: Optional[float] = None
    relative_volume: Optional[float] = None
    volatility: Optional[float] = None
    atr: Optional[float] = None
    vwap: Optional[float] = None
    vwap_distance: Optional[float] = None
    breakout_state: Optional[str] = None
    rolling_high: Optional[float] = None
    rolling_low: Optional[float] = None
    liquidity_metrics: Dict[str, Any] = Field(default_factory=dict)
    data_quality: Dict[str, Any] = Field(default_factory=dict)
    is_eligible: bool = True
    rejection_reason: Optional[RejectionReason] = None
    scanner_version: str = "1.0.0"
    feature_version: str = "1.1.0"
    configuration_version: str = "1.0.0"
    universe_version: str = "1.0.0"
    source_dataset_id: Optional[str] = None

class ScannerConfig(BaseModel):
    scanner_version: str = "1.0.0"
    configuration_version: str = "1.0.0"
    feature_version: str = "1.1.0"
    universe_version: str = "1.0.0"
    top_n: int = 10
    min_price: float = 10.0
    max_price: float = 50000.0
    min_volume: float = 1000.0
    min_average_volume: float = 5000.0
    relative_volume_threshold: float = 1.0
    allowed_trends: List[TrendClassification] = Field(
        default_factory=lambda: [
            TrendClassification.BULLISH,
            TrendClassification.BEARISH,
            TrendClassification.NEUTRAL,
        ]
    )
    min_history_bars: int = 20
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "momentum": 20.0,
            "relative_volume": 20.0,
            "trend": 20.0,
            "breakout": 15.0,
            "volatility": 15.0,
            "liquidity": 10.0,
        }
    )
