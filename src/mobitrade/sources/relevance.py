from datetime import datetime, timedelta
from typing import Optional, Dict
from mobitrade.domain.information_models import ExternalInformation, RelevanceLevel, InformationCategory

class RelevanceClassifier:
    """
    Deterministic relevance classification for financial information relative to a symbol
    and decision timestamp.
    """
    def __init__(self, sector_mapping: Optional[Dict[str, str]] = None):
        # Default NSE Sector Mapping for smoke-test and popular symbols
        self.sector_mapping = sector_mapping or {
            "RELIANCE": "ENERGY_CONGLOMERATE",
            "TCS": "INFORMATION_TECHNOLOGY",
            "INFY": "INFORMATION_TECHNOLOGY",
            "HDFCBANK": "BANKING_FINANCIAL",
            "ICICIBANK": "BANKING_FINANCIAL",
        }

    def classify_relevance(
        self,
        doc: ExternalInformation,
        target_symbol: str,
        decision_timestamp: datetime
    ) -> RelevanceLevel:
        # 1. Exact Symbol Match
        if doc.symbol and doc.symbol.upper() == target_symbol.upper():
            return RelevanceLevel.HIGH

        # 2. Company Name Mention in Title
        if doc.company_name and doc.company_name.lower() in doc.title.lower():
            return RelevanceLevel.HIGH

        # 3. Sector Relevance
        target_sector = self.sector_mapping.get(target_symbol.upper())
        if target_sector and doc.sector and doc.sector.upper() == target_sector:
            return RelevanceLevel.MEDIUM

        # 4. Market-Wide & Macro (e.g. RBI rates, GDP, broad market events)
        if doc.symbol is None or doc.category in (InformationCategory.MACRO, InformationCategory.MARKET_WIDE):
            # If within last 48 hours of decision, MEDIUM; otherwise LOW
            if decision_timestamp - doc.available_at <= timedelta(days=2):
                return RelevanceLevel.MEDIUM
            return RelevanceLevel.LOW

        # 5. Other unrelated specific symbols
        return RelevanceLevel.LOW

    def filter_and_rank_by_relevance(
        self,
        documents: list[ExternalInformation],
        target_symbol: str,
        decision_timestamp: datetime,
        min_relevance: RelevanceLevel = RelevanceLevel.MEDIUM
    ) -> list[ExternalInformation]:
        results = []
        for doc in documents:
            rel = self.classify_relevance(doc, target_symbol, decision_timestamp)
            doc.relevance = rel
            if min_relevance == RelevanceLevel.LOW:
                results.append(doc)
            elif min_relevance == RelevanceLevel.MEDIUM and rel in (RelevanceLevel.HIGH, RelevanceLevel.MEDIUM):
                results.append(doc)
            elif min_relevance == RelevanceLevel.HIGH and rel == RelevanceLevel.HIGH:
                results.append(doc)

        # Sort: HIGH before MEDIUM before LOW, then available_at descending
        rank_val = {RelevanceLevel.HIGH: 0, RelevanceLevel.MEDIUM: 1, RelevanceLevel.LOW: 2}
        return sorted(results, key=lambda d: (rank_val[d.relevance], -d.available_at.timestamp()))
