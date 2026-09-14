import pytest
from mobitrade.config.settings import load_yaml_config
from mobitrade.config.model_registry import ModelRegistry

def test_configuration_loading():
    models_cfg = load_yaml_config("configs/models.yaml")
    assert "models" in models_cfg
    assert len(models_cfg["models"]) == 8
    
    registry = ModelRegistry("configs/models.yaml")
    assert len(registry.list_all_models()) == 8
    
    nemotron = registry.get_model("nemotron")
    assert nemotron is not None
    assert nemotron.runtime_model_name == "nemotron-3-nano:latest"

def test_performance_profile_loading():
    from mobitrade.config import load_performance_profile, LLMPerformanceProfile
    profile = load_performance_profile("nemotron")
    assert isinstance(profile, LLMPerformanceProfile)
    assert profile.model_id == "nemotron"
    assert profile.runtime == "ollama"

