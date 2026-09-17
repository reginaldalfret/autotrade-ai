"""
Domain and Data Models for AutoTrade AI Self-Learning Engine (Phase 11).
Structured schemas for observations, profiles, candidate strategies, and validation reports.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class WeaknessType(str, Enum):
    FALSE_POSITIVE_ENTRY = "FALSE_POSITIVE_ENTRY"
    LOW_CONFIDENCE_LOSS = "LOW_CONFIDENCE_LOSS"
    TIME_OF_DAY_DECAY = "TIME_OF_DAY_DECAY"
    MODEL_SPECIFIC_UNDERPERFORMANCE = "MODEL_SPECIFIC_UNDERPERFORMANCE"
    MARKET_CONDITION_FAILURE = "MARKET_CONDITION_FAILURE"
    EXCESSIVE_CHOP_ENTRY = "EXCESSIVE_CHOP_ENTRY"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"


class LearningObservation(BaseModel):
    observation_id: str
    created_at: str
    weakness_type: WeaknessType
    model_id: Optional[str] = None
    description: str
    sample_size: int = Field(ge=1)
    supporting_trade_ids: List[str] = Field(default_factory=list)
    metrics_impact: Dict[str, Any] = Field(default_factory=dict)
    recommended_remedy: str = ""


class ModelPerformanceProfile(BaseModel):
    model_id: str
    version: str = "1.0.0"
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    net_pnl: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    confidence_calibration: Dict[str, Any] = Field(default_factory=dict)
    time_of_day_performance: Dict[str, Any] = Field(default_factory=dict)
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class StrategyConfig(BaseModel):
    version_id: str
    parent_version_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    min_confidence_threshold: float = 0.50
    allowed_models: List[str] = Field(default_factory=lambda: [
        "nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"
    ])
    model_confidence_thresholds: Dict[str, float] = Field(default_factory=dict)
    allowed_trading_windows: List[Dict[str, str]] = Field(default_factory=lambda: [
        {"start": "09:30", "end": "15:00"}
    ])
    max_trades_per_model: int = 20
    status: CandidateStatus = CandidateStatus.PROPOSED
    reason: str = ""
    supporting_observations: List[str] = Field(default_factory=list)
    sample_size: int = 0


class ValidationReport(BaseModel):
    candidate_version_id: str
    baseline_version_id: str
    sample_size: int
    is_validated: bool
    rejection_reasons: List[str] = Field(default_factory=list)
    baseline_metrics: Dict[str, Any] = Field(default_factory=dict)
    candidate_metrics: Dict[str, Any] = Field(default_factory=dict)
    overfitting_check_passed: bool = False
    hard_safety_check_passed: bool = True
    evaluation_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
