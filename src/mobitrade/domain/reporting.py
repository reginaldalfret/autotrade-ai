from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class PerformanceMetrics(BaseModel):
    model_id: str
    starting_balance: float
    ending_equity: float
    gross_pnl: float
    net_pnl: float
    total_return_pct: float
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    target_reached: bool = False
    daily_stop_triggered: bool = False

class TaxRecord(BaseModel):
    record_id: str
    model_id: str
    session_id: str
    asset_type: str
    realized_gain_loss: float
    estimated_tax: float
    tds_deducted: float
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SessionResult(BaseModel):
    session_id: str
    date: str
    market: str
    starting_balance: float
    ending_equity: float
    daily_pnl: float
    daily_return_pct: float
    target_reached: bool
    daily_stop_triggered: bool
    trade_count: int

class ModelExperimentResult(BaseModel):
    experiment_id: str
    model_id: str
    sessions: List[SessionResult] = Field(default_factory=list)
    overall_metrics: Optional[PerformanceMetrics] = None

class DailyReportMetadata(BaseModel):
    report_id: str
    date: str
    market: str
    models_evaluated: List[str]
    generated_at: datetime
    pdf_path: str
