import uuid
import logging
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

logger = logging.getLogger(__name__)

class FinancialNewsProvider(ExternalInformationProvider):
    """
    Provider for Tier-1 Financial News and media coverage (e.g. Mint, ET, Business Standard).
    Authority Level: REPUTABLE_NEWS (Rank 3).
    """
    def __init__(
        self,
        provider_name: str = "FINANCIAL_NEWS",
        provider_version: str = "1.0.0"
    ):
        super().__init__(provider_name=provider_name, provider_version=provider_version)
        self._store: List[ExternalInformation] = []

    def ingest_article(
        self,
        title: str,
        summary: str,
        publisher: str,
        published_at: datetime,
        available_at: Optional[datetime] = None,
        symbol: Optional[str] = None,
        category: InformationCategory = InformationCategory.OTHER,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExternalInformation:
        pub_ts = published_at.astimezone(IST) if published_at.tzinfo else published_at.replace(tzinfo=IST)
        avail_ts = (available_at.astimezone(IST) if available_at.tzinfo else available_at.replace(tzinfo=IST)) if available_at else pub_ts
        now_ts = datetime.now(timezone.utc)

        content_hash = ExternalInformation.generate_content_hash(title, summary, publisher)
        doc = ExternalInformation(
            information_id=f"news_{uuid.uuid4().hex[:8]}",
            source=self.provider_name,
            source_type=SourceType.FINANCIAL_NEWS,
            publisher=publisher,
            title=title,
            url=url,
            symbol=symbol,
            published_at=pub_ts,
            available_at=avail_ts,
            retrieved_at=now_ts,
            summary=summary,
            authority=SourceAuthority.REPUTABLE_NEWS,
            relevance=RelevanceLevel.MEDIUM if symbol else RelevanceLevel.LOW,
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
        docs = [d for d in self._store if (symbol is None or d.symbol == symbol)]
        return sorted(docs, key=lambda x: x.available_at, reverse=True)[:limit]

    def get_information_as_of(
        self,
        decision_timestamp: datetime,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[ExternalInformation]:
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)
        eligible = [
            d for d in self._store
            if (symbol is None or d.symbol == symbol) and d.available_at <= dec_ts
        ]
        return sorted(eligible, key=lambda x: x.available_at, reverse=True)[:limit]
