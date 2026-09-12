import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from mobitrade.domain.data_models import HistoricalCandle, Timeframe
from mobitrade.domain.feature_models import TechnicalFeatures
from mobitrade.domain.scanner_models import OpportunityCandidate
from mobitrade.domain.information_models import InformationContext

class MarketSnapshot(BaseModel):
    """
    Standardized multi-layer point-in-time snapshot for downstream local LLM consumption.
    Combines:
    A. Historical Market Data (Completed Candle)
    B. Technical Features (Timeframe-aware, normalized)
    C. Opportunity Scanner Output (Score & Rank)
    D. External Financial Information Context (Company & Macro news available at T)
    """
    snapshot_id: str = Field(default_factory=lambda: f"snap_{uuid.uuid4().hex[:10]}")
    symbol: str
    exchange: str = "NSE"
    decision_timestamp: datetime
    timeframe: Timeframe
    candle: Optional[HistoricalCandle] = None
    features: Optional[TechnicalFeatures] = None
    candidate: Optional[OpportunityCandidate] = None
    information_context: Optional[InformationContext] = None

    # Version Tracking & Provenance
    feature_version: str = "1.1.0"
    scanner_version: str = "1.0.0"
    context_version: str = "1.0.0"
    source_dataset_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
