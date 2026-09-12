import re
from typing import List, Dict
from mobitrade.domain.information_models import ExternalInformation

class InformationDeduplicator:
    """
    Deterministic deduplicator for multi-source financial information.
    Consolidates identical announcements while preserving distinct filings.
    If duplicates exist across different sources, prioritizes the higher authority record.
    """
    @staticmethod
    def normalize_title(title: str) -> str:
        # Strip non-alphanumeric noise and normalize spaces
        cleaned = re.sub(r"[^\w\s]", "", title.lower())
        return " ".join(cleaned.split())

    def deduplicate(
        self, documents: List[ExternalInformation]
    ) -> List[ExternalInformation]:
        if not documents:
            return []

        dedup_map: Dict[str, ExternalInformation] = {}

        for doc in documents:
            norm_title = self.normalize_title(doc.title)
            # Composite identity key
            key = f"{doc.symbol or 'MARKET'}_{norm_title}_{doc.published_at.date().isoformat()}"

            if key not in dedup_map:
                dedup_map[key] = doc
            else:
                existing = dedup_map[key]
                # Compare authority: lower enum value = higher authority (1=OFFICIAL_EXCHANGE)
                if int(doc.authority.value) < int(existing.authority.value):
                    dedup_map[key] = doc
                elif int(doc.authority.value) == int(existing.authority.value):
                    # Earlier availability or longer summary preferred
                    if len(doc.summary) > len(existing.summary):
                        dedup_map[key] = doc

        # Preserve ordering by available_at descending
        return sorted(list(dedup_map.values()), key=lambda d: d.available_at, reverse=True)
