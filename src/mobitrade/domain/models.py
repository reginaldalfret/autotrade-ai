from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class MarketTick(BaseModel):
    symbol: str
    timestamp: datetime
    price: float = Field(gt=0)
    volume: float = Field(ge=0)

class OHLCVCandle(BaseModel):
    symbol: str
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

class TechnicalFeatures(BaseModel):
    timestamp: datetime
    symbol: str
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    vwap: Optional[float] = None
    atr_14: Optional[float] = None
    sma_20: Optional[float] = None
    ema_20: Optional[float] = None
    relative_volume: Optional[float] = None
    custom_metrics: Dict[str, float] = Field(default_factory=dict)

class MarketSnapshot(BaseModel):
    snapshot_id: str
    timestamp: datetime
    market: str
    symbol: str
    current_price: float = Field(gt=0)
    candle: OHLCVCandle
    features: TechnicalFeatures
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Position(BaseModel):
    symbol: str
    quantity: int = Field(ge=0)
    average_entry_price: float = Field(ge=0)
    current_price: float = Field(ge=0)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

class PortfolioSnapshot(BaseModel):
    model_id: str
    session_id: str
    timestamp: datetime
    starting_balance: float = Field(gt=0)
    cash: float = Field(ge=0)
    market_value: float = Field(ge=0)
    total_equity: float = Field(ge=0)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    daily_pnl: float = 0.0
    completed_trades_count: int = Field(default=0, ge=0)
