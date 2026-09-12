import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator

class SourceType(str, Enum):
    NSE_ANNOUNCEMENT = "NSE_ANNOUNCEMENT"
    COMPANY_DISCLOSURE = "COMPANY_DISCLOSURE"
    REGULATORY_FILING = "REGULATORY_FILING"
    FINANCIAL_NEWS = "FINANCIAL_NEWS"
    MACRO_ECONOMIC = "MACRO_ECONOMIC"
    SECTOR_UPDATE = "SECTOR_UPDATE"
    OTHER = "OTHER"

class InformationCategory(str, Enum):
    EARNINGS = "EARNINGS"
    RESULTS = "RESULTS"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    MANAGEMENT = "MANAGEMENT"
    REGULATORY = "REGULATORY"
    ORDER_WIN = "ORDER_WIN"
    MERGER_ACQUISITION = "MERGER_ACQUISITION"
    FUND_RAISE = "FUND_RAISE"
    DIVIDEND = "DIVIDEND"
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    RATING = "RATING"
    MACRO = "MACRO"
    SECTOR = "SECTOR"
    MARKET_WIDE = "MARKET_WIDE"
    OTHER = "OTHER"

class RelevanceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class SourceAuthority(int, Enum):
    OFFICIAL_EXCHANGE = 1     # NSE Official Disclosures / BSE filings
    REGULATORY_FILING = 2     # SEBI, RBI, MCA
    REPUTABLE_NEWS = 3        # Tier-1 Financial Media (e.g. Mint, ET, BS)
    PUBLIC_MEDIA = 4          # General public / web sources

class ExternalInformation(BaseModel):
    information_id: str
    source: str
    source_type: SourceType
    publisher: str
    title: str
    url: Optional[str] = None
    symbol: Optional[str] = None
    company_name: Optional[str] = None
    sector: Optional[str] = None
    published_at: datetime
    available_at: datetime
    retrieved_at: datetime
    effective_at: Optional[datetime] = None
    summary: str = Field(min_length=1)
    language: str = "en"
    relevance: RelevanceLevel = RelevanceLevel.MEDIUM
    authority: SourceAuthority = SourceAuthority.REPUTABLE_NEWS
    category: InformationCategory = InformationCategory.OTHER
    content_hash: str
    provider_version: str = "1.0.0"
    parser_version: str = "1.0.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_temporal_provenance(self):
        # available_at cannot precede published_at unless explicit embargo/pre-release applies
        # and timestamps must have timezone info
        if self.available_at < self.published_at:
            raise ValueError(
                f"available_at ({self.available_at}) cannot precede published_at ({self.published_at})"
            )
        return self

    @classmethod
    def generate_content_hash(cls, title: str, summary: str, publisher: str) -> str:
        payload = f"{publisher}|{title.strip()}|{summary.strip()}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

class InformationContext(BaseModel):
    decision_timestamp: datetime
    symbol: str
    relevant_information: List[ExternalInformation] = Field(default_factory=list)
    source_count: int = 0
    high_authority_count: int = 0
    latest_available_information_time: Optional[datetime] = None
    context_version: str = "1.0.0"
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
