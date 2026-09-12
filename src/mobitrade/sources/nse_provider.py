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

class NSECorporateAnnouncementsProvider(ExternalInformationProvider):
    """
    Provider for official NSE Corporate Announcements and Exchange Disclosures.
    Authority Level: OFFICIAL_EXCHANGE (Rank 1).
    """
    def __init__(
        self,
        provider_version: str = "1.0.0",
        simulated_delay_minutes: int = 0
    ):
        super().__init__(provider_name="NSE_ANNOUNCEMENTS", provider_version=provider_version)
        self.simulated_delay_minutes = simulated_delay_minutes
        self._store: List[ExternalInformation] = []

    def ingest_document(
        self,
        symbol: str,
        title: str,
        summary: str,
        published_at: datetime,
        available_at: Optional[datetime] = None,
        category: InformationCategory = InformationCategory.OTHER,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExternalInformation:
        """
        Manually or programmically ingest a document into provider storage (fixture/feed).
        """
        pub_ts = published_at.astimezone(IST) if published_at.tzinfo else published_at.replace(tzinfo=IST)
        avail_ts = (available_at.astimezone(IST) if available_at.tzinfo else available_at.replace(tzinfo=IST)) if available_at else pub_ts
        now_ts = datetime.now(timezone.utc)

        content_hash = ExternalInformation.generate_content_hash(title, summary, "NSE")
        doc = ExternalInformation(
            information_id=f"nse_{uuid.uuid4().hex[:8]}",
            source=self.provider_name,
            source_type=SourceType.NSE_ANNOUNCEMENT,
            publisher="NSE",
            title=title,
            url=url or f"https://www.nseindia.com/companies-listing/corporate-filings/announcements/{symbol}",
            symbol=symbol,
            published_at=pub_ts,
            available_at=avail_ts,
            retrieved_at=now_ts,
            summary=summary,
            authority=SourceAuthority.OFFICIAL_EXCHANGE,
            relevance=RelevanceLevel.HIGH,
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
