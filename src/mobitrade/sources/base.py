from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from mobitrade.domain.information_models import ExternalInformation

class ExternalInformationProvider(ABC):
    """
    Abstract interface for external financial information providers.
    Every provider must support point-in-time filtering via get_information_as_of.
    """
    def __init__(self, provider_name: str, provider_version: str = "1.0.0"):
        self.provider_name = provider_name
        self.provider_version = provider_version

    @abstractmethod
    def fetch_information(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> List[ExternalInformation]:
        """
        Retrieves raw documents from source/API and converts them into normalized ExternalInformation.
        """
        pass

    @abstractmethod
    def get_information_as_of(
        self,
        decision_timestamp: datetime,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[ExternalInformation]:
        """
        Strict point-in-time query:
        Returns only documents satisfying: available_at <= decision_timestamp.
        """
        pass
