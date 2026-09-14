"""
Unit tests for LLMPerformanceProfile and configuration loader/saver.
"""

from pathlib import Path
import pytest
from mobitrade.config.performance import (
    LLMPerformanceProfile,
    load_performance_profile,
    save_performance_profile,
)


def test_default_profile_attributes():
    """Verify dataclass default values conform to requirements."""
    profile = LLMPerformanceProfile(model_id="nemotron")
    assert profile.model_id == "nemotron"
    assert profile.runtime == "ollama"
    assert profile.context_size == 2048
    assert profile.gpu_layers == -1
    assert profile.flash_attention is True
    assert profile.kv_cache_type == "f16"
    assert profile.threads == 4
    assert profile.batch_size == 512
    assert profile.recommended_configuration == {}
    assert profile.benchmark_result == {}
    assert profile.updated_at is None


def test_to_dict_and_from_dict():
    """Test serialization and deserialization helpers."""
    original = LLMPerformanceProfile(
        model_id="qwen",
        runtime="ollama",
        context_size=4096,
        gpu_layers=32,
        flash_attention=False,
        kv_cache_type="q4_0",
        threads=8,
        batch_size=256,
        recommended_configuration={"temperature": 0.2},
        benchmark_result={"avg_latency_ms": 123.4},
        updated_at="2026-09-14T10:00:00Z",
    )
    d = original.to_dict()
    assert isinstance(d, dict)
    assert d["model_id"] == "qwen"
    assert d["context_size"] == 4096

    restored = LLMPerformanceProfile.from_dict(d)
    assert restored == original

    # Safe handling of sparse dictionary
    sparse = LLMPerformanceProfile.from_dict({"model_id": "sparse_model"})
    assert sparse.model_id == "sparse_model"
    assert sparse.runtime == "ollama"
    assert sparse.context_size == 2048
    assert sparse.recommended_configuration == {}


def test_load_all_eight_models():
    """Verify all 8 predefined model profiles load correctly from configs/llm-performance."""
    model_ids = [
        "nemotron",
        "qwen",
        "gemma",
        "llama",
        "granite",
        "phi",
        "smollm",
        "falcon",
    ]

    for m_id in model_ids:
        profile = load_performance_profile(m_id)
        assert profile.model_id == m_id
        assert profile.runtime == "ollama"
        assert profile.context_size >= 2048
        assert profile.gpu_layers == -1
        assert profile.flash_attention is True
        assert isinstance(profile.recommended_configuration, dict)
        assert len(profile.recommended_configuration) > 0
        assert "temperature" in profile.recommended_configuration
        assert isinstance(profile.benchmark_result, dict)
        assert len(profile.benchmark_result) > 0
        assert "avg_latency_ms" in profile.benchmark_result
        assert "tokens_per_second" in profile.benchmark_result
        assert profile.updated_at is not None


def test_load_nonexistent_model_returns_safe_defaults():
    """Verify loading a nonexistent model YAML returns safe defaults rather than error."""
    profile = load_performance_profile("nonexistent_model_12345")
    assert profile.model_id == "nonexistent_model_12345"
    assert profile.runtime == "ollama"
    assert profile.context_size == 2048
    assert profile.gpu_layers == -1
    assert profile.recommended_configuration == {}
    assert profile.benchmark_result == {}
    assert profile.updated_at is None


def test_save_and_load_roundtrip(tmp_path: Path):
    """Verify saving a profile to YAML and loading it back."""
    profile = LLMPerformanceProfile(
        model_id="custom_model",
        runtime="ollama",
        context_size=1024,
        gpu_layers=16,
        flash_attention=True,
        kv_cache_type="f16",
        threads=2,
        batch_size=128,
        recommended_configuration={"notes": "Custom test model"},
        benchmark_result={"avg_latency_ms": 99.9},
        updated_at="2026-09-14T12:00:00Z",
    )

    saved_path = save_performance_profile(profile, config_dir=str(tmp_path))
    assert Path(saved_path).exists()
    assert Path(saved_path).name == "custom_model.yaml"

    loaded = load_performance_profile("custom_model", config_dir=str(tmp_path))
    assert loaded == profile


def test_load_corrupted_yaml_returns_safe_defaults(tmp_path: Path):
    """Verify corrupted YAML files safely fallback to defaults."""
    corrupt_file = tmp_path / "corrupt.yaml"
    corrupt_file.write_text("::: Invalid YAML [[[[", encoding="utf-8")

    profile = load_performance_profile("corrupt", config_dir=str(tmp_path))
    assert profile.model_id == "corrupt"
    assert profile.context_size == 2048
    assert profile.runtime == "ollama"
