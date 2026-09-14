from pathlib import Path
from typing import List, Dict, Optional
from mobitrade.config.settings import ModelConfig, load_yaml_config

class ModelRegistry:
    """
    Central registry for the 8 local LLMs. Models can be reconfigured
    without modifying application logic.
    """
    def __init__(self, config_path: Optional[str] = None):
        self._models: Dict[str, ModelConfig] = {}
        if config_path is None:
            candidates = [
                Path("configs/models.yaml"),
                Path(__file__).resolve().parent.parent.parent.parent / "configs" / "models.yaml",
                Path("configs/models.yaml"),
                Path("D:/Trading LLM/MobiTradeAI/configs/models.yaml"),
            ]
            for cand in candidates:
                if cand.exists():
                    config_path = str(cand)
                    break
        if config_path and Path(config_path).exists():
            self.load_from_yaml(config_path)

    def load_from_yaml(self, config_path: str):
        data = load_yaml_config(config_path)
        for item in data.get("models", []):
            cfg = ModelConfig(**item)
            self._models[cfg.id] = cfg

    def register_model(self, model: ModelConfig):
        self._models[model.id] = model

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        return self._models.get(model_id)

    def list_all_models(self) -> List[ModelConfig]:
        return list(self._models.values())

    def list_enabled_models(self) -> List[ModelConfig]:
        return [m for m in self._models.values() if m.enabled]
