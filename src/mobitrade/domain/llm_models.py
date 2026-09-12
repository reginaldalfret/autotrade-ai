from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class LLMAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_ACTION = "NO_ACTION"

class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_ACTION = "INVALID_ACTION"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_STOP_LOSS = "INVALID_STOP_LOSS"
    INVALID_CONFIDENCE = "INVALID_CONFIDENCE"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    TIMESTAMP_MISMATCH = "TIMESTAMP_MISMATCH"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"

class InferenceMetrics(BaseModel):
    model_id: str
    snapshot_id: str
    start_time: datetime
    end_time: datetime
    inference_latency_ms: float
    model_load_time_ms: Optional[float] = None
    model_unload_time_ms: Optional[float] = None
    tokens_prompt: Optional[int] = None
    tokens_generated: Optional[int] = None
    ram_usage_mb: Optional[float] = None
    vram_usage_mb: Optional[float] = None
    success: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LLMDecisionRecord(BaseModel):
    decision_id: str
    model_id: str
    model_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    snapshot_id: str
    decision_timestamp: datetime
    symbol: str
    action: LLMAction
    confidence: float = Field(ge=0.0, le=1.0)
    entry_rationale: str
    proposed_stop_loss: Optional[float] = None
    proposed_target: Optional[float] = None
    holding_intent: str = "INTRADAY"
    reasoning_summary: str
    validation_status: ValidationStatus = ValidationStatus.VALID
    rejection_reason: Optional[str] = None
    metrics: Optional[InferenceMetrics] = None
    raw_response: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ModelEvaluationRun(BaseModel):
    run_id: str
    snapshot_id: str
    decision_timestamp: datetime
    evaluated_models: List[str] = Field(default_factory=list)
    successful_decisions: List[str] = Field(default_factory=list)
    failed_models: List[str] = Field(default_factory=list)
    total_cycle_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
