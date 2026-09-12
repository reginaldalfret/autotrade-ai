from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class LocalLLMProvider(ABC):
    """
    Abstract interface for local LLM inference providers.
    Enforces a strict lifecycle: load -> generate -> unload.
    """
    def __init__(self, provider_name: str, provider_version: str = "1.0.0"):
        self.provider_name = provider_name
        self.provider_version = provider_version
        self.currently_loaded_model: Optional[str] = None

    @abstractmethod
    def list_models(self) -> List[str]:
        """Returns list of accessible model tags."""
        pass

    @abstractmethod
    def load_model(self, model_tag: str) -> float:
        """
        Loads the model into memory/VRAM.
        Returns load time in milliseconds.
        """
        pass

    @abstractmethod
    def unload_model(self, model_tag: str) -> float:
        """
        Unloads model from memory/VRAM.
        Returns unload time in milliseconds.
        """
        pass

    @abstractmethod
    def generate(
        self,
        model_tag: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """
        Executes inference against model_tag.
        Returns dictionary containing:
        - raw_text: str
        - latency_ms: float
        - tokens_prompt: Optional[int]
        - tokens_generated: Optional[int]
        - metadata: Dict[str, Any]
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verifies runtime availability."""
        pass
