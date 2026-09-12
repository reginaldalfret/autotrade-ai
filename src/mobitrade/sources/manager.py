from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from mobitrade.domain.data_models import HistoricalCandle, Timeframe
from mobitrade.domain.feature_models import TechnicalFeatures
from mobitrade.domain.scanner_models import OpportunityCandidate
from mobitrade.domain.information_models import (
    ExternalInformation,
    InformationContext,
    SourceAuthority,
    RelevanceLevel,
)
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.sources.base import ExternalInformationProvider
from mobitrade.sources.deduplication import InformationDeduplicator
from mobitrade.sources.relevance import RelevanceClassifier
from mobitrade.sources.persistence import InformationRepository
from mobitrade.data.calendar import IST

class ExternalInformationManager:
    """
    Coordinates multi-source external information ingestion, point-in-time filtering,
    deduplication, relevance ranking, and snapshot creation.
    """
    def __init__(
        self,
        providers: Optional[List[ExternalInformationProvider]] = None,
        repository: Optional[InformationRepository] = None,
        deduplicator: Optional[InformationDeduplicator] = None,
        classifier: Optional[RelevanceClassifier] = None,
        context_version: str = "1.0.0"
    ):
        self.providers = providers or []
        self.repository = repository or InformationRepository()
        self.deduplicator = deduplicator or InformationDeduplicator()
        self.classifier = classifier or RelevanceClassifier()
        self.context_version = context_version

    def register_provider(self, provider: ExternalInformationProvider) -> None:
        self.providers.append(provider)

    def get_information_as_of(
        self,
        symbol: str,
        decision_timestamp: datetime,
        limit: int = 20,
        min_relevance: RelevanceLevel = RelevanceLevel.MEDIUM
    ) -> List[ExternalInformation]:
        """
        Point-in-time query for a specific symbol across all registered providers.
        Guarantees: available_at <= decision_timestamp.
        """
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)
        all_docs: List[ExternalInformation] = []

        for p in self.providers:
            # Query provider for company-specific or market-wide documents
            docs = p.get_information_as_of(dec_ts, symbol=symbol, limit=limit)
            all_docs.extend(docs)
            # Also query macro / market-wide documents
            macro_docs = p.get_information_as_of(dec_ts, symbol=None, limit=10)
            all_docs.extend(macro_docs)

        # 1. Deduplication
        deduped = self.deduplicator.deduplicate(all_docs)

        # 2. Relevance Classification & Ranking
        ranked = self.classifier.filter_and_rank_by_relevance(
            deduped, symbol, dec_ts, min_relevance=min_relevance
        )

        return ranked[:limit]

    def get_context_as_of(
        self,
        symbol: str,
        decision_timestamp: datetime,
        limit: int = 10,
        persist: bool = True
    ) -> InformationContext:
        """
        Builds an immutable, auditable InformationContext for a symbol at decision_timestamp.
        """
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)
        relevant_docs = self.get_information_as_of(symbol, dec_ts, limit=limit)

        high_auth = sum(
            1 for d in relevant_docs
            if d.authority in (SourceAuthority.OFFICIAL_EXCHANGE, SourceAuthority.REGULATORY_FILING)
        )
        latest_avail = max((d.available_at for d in relevant_docs), default=None)

        context = InformationContext(
            decision_timestamp=dec_ts,
            symbol=symbol,
            relevant_information=relevant_docs,
            source_count=len(relevant_docs),
            high_authority_count=high_auth,
            latest_available_information_time=latest_avail,
            context_version=self.context_version,
            created_at=datetime.now(timezone.utc)
        )

        if persist:
            self.repository.save_context(context)

        return context

    def build_market_snapshot(
        self,
        symbol: str,
        decision_timestamp: datetime,
        timeframe: Timeframe,
        candle: Optional[HistoricalCandle] = None,
        features: Optional[TechnicalFeatures] = None,
        candidate: Optional[OpportunityCandidate] = None,
        persist_context: bool = True
    ) -> MarketSnapshot:
        """
        Assembles the complete MarketSnapshot integrating market data, features,
        scanner opportunity candidate, and external information context.
        """
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)
        context = self.get_context_as_of(symbol, dec_ts, limit=10, persist=persist_context)

        return MarketSnapshot(
            symbol=symbol,
            exchange="NSE",
            decision_timestamp=dec_ts,
            timeframe=timeframe,
            candle=candle,
            features=features,
            candidate=candidate,
            information_context=context,
            feature_version=features.feature_version if features else "1.1.0",
            scanner_version=candidate.scanner_version if candidate else "1.0.0",
            context_version=self.context_version,
            source_dataset_id=features.source_dataset_id if features else None
        )
