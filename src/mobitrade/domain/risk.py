from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from mobitrade.domain.enums import RiskDecision

class RiskCheckResult(BaseModel):
    decision: RiskDecision
    reason: str
    rule_name: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        return self.decision == RiskDecision.APPROVED

class RiskEvent(BaseModel):
    event_id: str
    model_id: str
    session_id: str
    event_type: str
    description: str
    timestamp: datetime
    triggered_value: float
    threshold_value: float
    action_taken: str
