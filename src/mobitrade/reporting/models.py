"""
Data models for Daily Trading Reports.
Pydantic schemas ensuring deterministic report structuring.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    report_id: str
    session_id: str
    report_date: str
    generated_at: str
    product_name: str = "AutoTrade AI"
    version: str = "0.1.0"
    market: str = "NSE Indian Equity Cash Market (Intraday)"
    pdf_sha256: Optional[str] = None


class ExecutiveSummaryData(BaseModel):
    session_id: str
    session_date: str
    total_models: int
    total_starting_equity: float
    total_ending_equity: float
    total_gross_pnl: float
    total_net_pnl: float
    overall_return_pct: float
    total_trades: int
    total_wins: int
    total_losses: int
    overall_win_rate: float
    total_fees: float
    total_slippage: float
    targets_reached_count: int
    stops_triggered_count: int
    best_performing_model: str
    worst_performing_model: str


class LeaderboardRowData(BaseModel):
    rank: int
    model_id: str
    starting_balance: float
    ending_balance: float
    gross_pnl: float
    net_pnl: float
    return_pct: float
    trades_count: int
    win_rate: float
    profit_factor: Union[float, str]
    max_drawdown: float
    target_status: str
    stop_status: str
    sharpe: Union[float, str]


class ModelReportSectionData(BaseModel):
    model_id: str
    starting_balance: float
    ending_balance: float
    gross_pnl: float
    net_pnl: float
    return_pct: float
    target_status: str
    stop_status: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: Union[float, str]
    max_drawdown_amount: float
    max_drawdown_pct: float
    sharpe: Union[float, str]
    sortino: Union[float, str]
    calmar: Union[float, str]
    volatility: Union[float, str]
    total_fees: float
    total_slippage: float


class TradeDetailData(BaseModel):
    trade_id: str
    model_id: str
    symbol: str
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: str
    exit_time: Optional[str] = None
    gross_pnl: float
    total_fees: float
    total_slippage: float
    net_pnl: float
    exit_reason: Optional[str] = None


class AuditSummaryData(BaseModel):
    total_events: int
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    is_valid: bool
    genesis_previous_hash: str
    latest_event_hash: Optional[str] = None
    verification_errors: List[str] = Field(default_factory=list)


class DailyTradingReport(BaseModel):
    metadata: ReportMetadata
    executive_summary: ExecutiveSummaryData
    leaderboard: List[LeaderboardRowData]
    model_sections: List[ModelReportSectionData]
    trades: List[TradeDetailData]
    audit_summary: AuditSummaryData
