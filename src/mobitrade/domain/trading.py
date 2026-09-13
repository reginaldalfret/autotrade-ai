from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from mobitrade.domain.enums import Action, OrderSide, OrderType, OrderStatus, ExitReason

class TradingSignal(BaseModel):
    timestamp: datetime
    symbol: str
    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_entry: float = Field(gt=0)
    suggested_stop_loss: Optional[float] = None
    suggested_target: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TradeDecision(BaseModel):
    symbol: str
    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    quantity: int = Field(ge=0)
    entry_price: float = Field(gt=0)
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action in (Action.BUY, Action.SELL) and self.quantity <= 0:
            raise ValueError(f"Quantity must be positive for {self.action} action")
        if self.action == Action.BUY:
            if self.stop_loss is not None and self.stop_loss >= self.entry_price:
                raise ValueError("For BUY action, stop_loss must be lower than entry_price")
            if self.target_price is not None and self.target_price <= self.entry_price:
                raise ValueError("For BUY action, target_price must be higher than entry_price")
        return self

class OrderRequest(BaseModel):
    model_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    account_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    decision_id: Optional[str] = None

class Order(BaseModel):
    order_id: str
    model_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime
    updated_at: datetime
    account_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    decision_id: Optional[str] = None

class Execution(BaseModel):
    execution_id: str
    order_id: str
    model_id: str
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    fill_price: float = Field(gt=0)
    fee: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    executed_at: datetime
    account_id: Optional[str] = None

class Trade(BaseModel):
    trade_id: str
    model_id: str
    account_id: Optional[str] = None
    symbol: str
    exchange: str = "NSE"
    entry_execution_id: str
    exit_execution_id: Optional[str] = None
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    exit_price: Optional[float] = None
    entry_time: datetime
    exit_time: Optional[datetime] = None
    initial_stop: Optional[float] = None
    trailing_stop: Optional[float] = None
    gross_pnl: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    net_pnl: float = 0.0
    exit_reason: Optional[ExitReason] = None
    snapshot_id: Optional[str] = None
    decision_id: Optional[str] = None
    is_closed: bool = False
