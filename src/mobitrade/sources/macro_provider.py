import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from mobitrade.domain.information_models import (
    ExternalInformation,
    SourceType,
    SourceAuthority,
    InformationCategory,
    RelevanceLevel,
)
from mobitrade.sources.base import ExternalInformationProvider
from mobitrade.data.calendar import IST

class MacroEconomicProvider(ExternalInformationProvider):
    """
    Provider for Indian Macroeconomic and Regulatory Disclosures (RBI, SEBI, MoF).
    Authority Level: REGULATORY_FILING (Rank 2).
    Scope: MARKET_WIDE (applicable across all symbols).
    """
    def __init__(
        self,
        provider_name: str = "MACRO_REGULATORY",
        provider_version: str = "1.0.0"
    ):
        super().__init__(provider_name=provider_name, provider_version=provider_version)
        self._store: List[ExternalInformation] = []

    def ingest_event(
        self,
        title: str,
        summary: str,
        publisher: str,
        published_at: datetime,
        available_at: Optional[datetime] = None,
        category: InformationCategory = InformationCategory.MACRO,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExternalInformation:
        pub_ts = published_at.astimezone(IST) if published_at.tzinfo else published_at.replace(tzinfo=IST)
        avail_ts = (available_at.astimezone(IST) if available_at.tzinfo else available_at.replace(tzinfo=IST)) if available_at else pub_ts
        now_ts = datetime.now(timezone.utc)

        content_hash = ExternalInformation.generate_content_hash(title, summary, publisher)
        doc = ExternalInformation(
            information_id=f"macro_{uuid.uuid4().hex[:8]}",
            source=self.provider_name,
            source_type=SourceType.MACRO_ECONOMIC,
            publisher=publisher,
            title=title,
            url=url,
            symbol=None, # Market-wide scope
            published_at=pub_ts,
            available_at=avail_ts,
            retrieved_at=now_ts,
            summary=summary,
            authority=SourceAuthority.REGULATORY_FILING,
            relevance=RelevanceLevel.MEDIUM,
            category=category,
            content_hash=content_hash,
            provider_version=self.provider_version,
            metadata=metadata or {}
        )
        self._store.append(doc)
        return doc

    def fetch_information(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> List[ExternalInformation]:
        return sorted(self._store, key=lambda x: x.available_at, reverse=True)[:limit]

    def get_information_as_of(
        self,
        decision_timestamp: datetime,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[ExternalInformation]:
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)
        eligible = [d for d in self._store if d.available_at <= dec_ts]
        return sorted(eligible, key=lambda x: x.available_at, reverse=True)[:limit]
