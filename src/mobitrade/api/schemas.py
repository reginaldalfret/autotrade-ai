"""
Pydantic Schemas for AutoTrade AI Local Operator API.
Deterministic request and response models for Hermes / operator interactions.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    market_session: Dict[str, Any]
    llm_provider: Dict[str, Any]
    database: Dict[str, Any]


class ModelInfo(BaseModel):
    id: str
    display_name: str
    provider: str
    runtime_model_name: str
    context_length: int
    temperature: float
    top_p: float
    system_prompt_version: str
    enabled: bool


class ModelsResponse(BaseModel):
    count: int
    models: List[ModelInfo]


class AccountSummary(BaseModel):
    model_id: str
    account_id: str
    starting_balance: float
    cash_balance: float
    current_equity: float
    realized_pnl: float
    unrealized_pnl: float
    state: str
    trades_count: int
    lock_reason: Optional[str] = None


class PortfolioResponse(BaseModel):
    total_equity: float
    total_cash: float
    total_realized_pnl: float
    active_accounts_count: int
    accounts: List[AccountSummary]


class PositionItem(BaseModel):
    trade_id: str
    model_id: str
    symbol: str
    quantity: int
    entry_price: float
    initial_stop: Optional[float] = None
    trailing_stop: Optional[float] = None
    entry_timestamp: str


class PositionsResponse(BaseModel):
    count: int
    positions: List[PositionItem]


class TradeItem(BaseModel):
    trade_id: str
    model_id: str
    symbol: str
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    entry_timestamp: str
    exit_timestamp: Optional[str] = None
    gross_pnl: float
    net_pnl: float
    fees: float
    slippage: float
    exit_reason: Optional[str] = None
    is_closed: bool


class TradesResponse(BaseModel):
    count: int
    trades: List[TradeItem]


class RiskParametersResponse(BaseModel):
    market_segment: str = "NSE Cash Intraday"
    daily_target_pct: float
    daily_loss_limit_pct: float
    hard_stop_loss_pct: float
    max_trades_per_session: int
    max_concurrent_positions: int
    auto_square_off_time: str = "15:15 IST"
    session_close_time: str = "15:30 IST"
    session_open_time: str = "09:15 IST"
    allow_overnight: bool = False
    allow_leverage: bool = False
    require_stop_loss: bool = True
    min_confidence_score: float = 0.50
    authority: str = "RiskEngine Deterministic Enforcement"


class AnalyticsResponse(BaseModel):
    session_id: Optional[str] = None
    session_date: Optional[str] = None
    gross_pnl: float
    net_pnl: float
    total_trades: int
    win_rate: float
    leaderboard: List[Dict[str, Any]]
    drawdown: Dict[str, Any]
    trade_statistics: Dict[str, Any]
    risk_adjusted: Dict[str, Any]


class ReportItem(BaseModel):
    report_id: str
    session_id: str
    report_date: str
    file_path: str
    file_hash: str
    generated_at: str
    generation_status: str


class ReportsResponse(BaseModel):
    count: int
    reports: List[ReportItem]


class AuditVerificationResponse(BaseModel):
    is_valid: bool
    total_events: int
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    errors: List[str]
    session_id: Optional[str] = None


class SessionRunRequest(BaseModel):
    session_date: Optional[str] = None
    symbol: Optional[str] = "TATAMOTORS"
    symbols: Optional[List[str]] = None
    mock_llm: bool = True


class SessionRunResponse(BaseModel):
    status: str
    session_id: str
    session_date: str
    symbol: str
    total_trades: int
    leaderboard: List[Dict[str, Any]]
    message: str
