"""
Unit tests for GPU environment detection and LLM benchmark runner.
Tests hardware discovery, single-model sequential VRAM residency,
metric capture (tok/s, latency, VRAM, RAM), experiment JSON persistence,
and tabular report generation.
"""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from mobitrade.llm.hardware import (
    detect_gpu_environment,
    get_gpu_vram_mb,
    get_system_ram_mb,
    check_ollama_runtime,
    find_llamacpp_binaries,
    is_wsl2,
    check_wsl2_gpu_passthrough,
)
from mobitrade.llm.benchmark import (
    LLMBenchmarkRunner,
    ModelBenchmarkResult,
    BenchmarkSuiteResult,
)
from mobitrade.llm.mock_provider import MockLLMProvider
from mobitrade.config.model_registry import ModelRegistry


# ============================================================
# 1. HARDWARE ENVIRONMENT DETECTION TESTS
# ============================================================

def test_detect_gpu_environment_mock_mode():
    """Verify detect_gpu_environment in mock mode returns target hardware specs."""
    env = detect_gpu_environment(mock=True)

    # Check GPU specs: RTX 2050 4GB GA107 Ampere CC 8.6
    gpu = env["gpu"]
    assert gpu["available"] is True
    assert gpu["device_name"] == "NVIDIA GeForce RTX 2050"
    assert gpu["total_vram_mb"] == 4096.0
    assert gpu["free_vram_mb"] == 3200.0
    assert gpu["used_vram_mb"] == 896.0
    assert gpu["driver_version"] == "551.76"
    assert gpu["cuda_compute_capability"] == "8.6"
    assert gpu["cuda_available"] is True

    # Check WSL2 structure
    wsl = env["wsl2"]
    assert "is_wsl2" in wsl
    assert "passthrough_detected" in wsl
    assert "libcuda_path" in wsl

    # Check Ollama structure
    ollama = env["ollama"]
    assert ollama["connected"] is True
    assert ollama["gpu_support"] is True
    assert len(ollama["available_models"]) == 8

    # Check llama.cpp structure
    llama = env["llamacpp"]
    assert llama["detected"] is True
    assert "llama-cli.exe" in llama["primary_binary"]

    # Check system memory
    mem = env["system_memory"]
    assert mem["total_ram_mb"] == 8192.0
    assert mem["available_ram_mb"] == 5120.0
    assert mem["percent_used"] > 0

    # Check recommendations
    rec = env["recommendations"]
    assert "Ollama" in rec["recommended_runtime"]
    assert rec["recommended_backend"] == "cuda"
    assert "Sequential" in rec["concurrency_policy"]
    assert "3.5 GB" in rec["max_recommended_model_size"]


def test_detect_gpu_environment_real_mode_structure():
    """Verify detect_gpu_environment in real mode returns compliant dictionary structure."""
    env = detect_gpu_environment(mock=False)

    required_top_keys = {
        "gpu",
        "wsl2",
        "ollama",
        "llamacpp",
        "system_memory",
        "os_environment",
        "recommendations",
    }
    assert required_top_keys.issubset(set(env.keys()))

    assert isinstance(env["gpu"]["available"], bool)
    assert isinstance(env["gpu"]["total_vram_mb"], float)
    assert isinstance(env["wsl2"]["is_wsl2"], bool)
    assert isinstance(env["ollama"]["connected"], bool)
    assert isinstance(env["llamacpp"]["detected"], bool)
    assert env["system_memory"]["total_ram_mb"] > 0
    assert "recommended_runtime" in env["recommendations"]
    assert "recommended_backend" in env["recommendations"]


def test_get_gpu_vram_and_system_ram_mb():
    """Verify helper memory interrogation routines return valid floats."""
    vram = get_gpu_vram_mb()
    assert isinstance(vram, dict)
    assert "total" in vram and "free" in vram and "used" in vram
    assert vram["total"] >= 0.0

    ram = get_system_ram_mb()
    assert isinstance(ram, dict)
    assert "total" in ram and "available" in ram and "used" in ram and "percent" in ram
    assert ram["total"] > 0.0
    assert 0.0 <= ram["percent"] <= 100.0


def test_wsl2_passthrough_detection():
    """Verify WSL2 helper returns dictionary with required fields."""
    info = check_wsl2_gpu_passthrough()
    assert "is_wsl2" in info
    assert "passthrough_detected" in info
    assert "libcuda_path" in info


def test_find_llamacpp_binaries():
    """Verify llama.cpp search returns search paths and binary dict."""
    llama_info = find_llamacpp_binaries()
    assert "detected" in llama_info
    assert "primary_binary" in llama_info
    assert "binaries" in llama_info
    assert "search_paths_checked" in llama_info
    assert len(llama_info["search_paths_checked"]) > 0


# ============================================================
# 2. LLM BENCHMARK RUNNER TESTS
# ============================================================

def test_benchmark_runner_single_model(tmp_path):
    """Test running a standardized benchmark on a single model."""
    provider = MockLLMProvider()
    runner = LLMBenchmarkRunner(
        provider=provider,
        output_dir=str(tmp_path / "experiments"),
        mock_hardware=True,
    )

    registry = ModelRegistry()
    qwen_cfg = registry.get_model("qwen")
    assert qwen_cfg is not None

    result = runner.benchmark_model(qwen_cfg, iterations=1)

    assert result.model_id == "qwen"
    assert result.runtime_model_name == "qwen2.5-coder:1.5b"
    assert result.json_valid is True
    assert result.action in ("BUY", "SELL", "HOLD", "NO_ACTION")
    assert result.confidence is not None
    assert result.latency_ms > 0.0
    assert result.load_time_ms > 0.0
    assert result.unload_time_ms > 0.0
    assert result.tokens_prompt > 0
    assert result.tokens_generated > 0
    assert result.prompt_eval_tok_s > 0.0
    assert result.eval_tok_s > 0.0
    assert result.vram_usage_mb > 0.0
    assert result.ram_usage_mb > 0.0
    assert result.error is None

    # Verify provider VRAM is cleared after test
    assert provider.currently_loaded_model is None


def test_benchmark_runner_all_models_sequential_residency(tmp_path):
    """
    Test running the full benchmark suite across all 8 configured models.
    Enforces strict sequential single-model residency in VRAM.
    """
    provider = MockLLMProvider()
    runner = LLMBenchmarkRunner(
        provider=provider,
        output_dir=str(tmp_path / "experiments"),
        mock_hardware=True,
    )

    suite = runner.run_all_benchmarks(iterations=1)

    assert suite.models_benchmarked == 8
    assert suite.successful_models == 8
    assert suite.failed_models == 0
    assert len(suite.results) == 8

    # Verify all 8 registered models were benchmarked
    expected_ids = {"nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"}
    benchmarked_ids = {r.model_id for r in suite.results}
    assert benchmarked_ids == expected_ids

    # Verify provider load/unload counts: exactly 8 loads and 8 unloads
    assert len(provider.load_history) == 8
    assert len(provider.unload_history) == 8
    # Currently loaded model must be None after suite completion
    assert provider.currently_loaded_model is None

    # Verify summary metrics
    summary = suite.summary
    assert summary["total_models"] == 8
    assert summary["successful_inferences"] == 8
    assert summary["json_compliant_models"] == 8
    assert summary["json_compliance_rate_pct"] == 100.0
    assert summary["fastest_eval_model"] is not None
    assert summary["recommended_production_model"] is not None


def test_benchmark_runner_save_experiment(tmp_path):
    """Test saving experiment JSON and latest.json pointer."""
    exp_dir = tmp_path / "experiments" / "llm_baseline"
    provider = MockLLMProvider()
    runner = LLMBenchmarkRunner(
        provider=provider,
        output_dir=str(exp_dir),
        mock_hardware=True,
    )

    suite = runner.run_all_benchmarks(model_ids=["qwen", "nemotron"])
    out_file = runner.save_experiment(suite)

    assert out_file.exists()
    assert (exp_dir / "latest.json").exists()

    with open(out_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert saved_data["experiment_id"] == suite.experiment_id
    assert saved_data["models_benchmarked"] == 2
    assert len(saved_data["results"]) == 2
    assert "hardware" in saved_data
    assert "summary" in saved_data


def test_benchmark_runner_error_isolation_and_guaranteed_eviction(tmp_path):
    """
    Verify that if a model fails or times out during inference,
    it is cleanly evicted from VRAM and subsequent models continue unaffected.
    """
    provider = MockLLMProvider()
    provider.set_model_timeout("nemotron-3-nano:latest")

    runner = LLMBenchmarkRunner(
        provider=provider,
        output_dir=str(tmp_path / "experiments"),
        mock_hardware=True,
    )

    suite = runner.run_all_benchmarks(model_ids=["nemotron", "qwen"])

    assert suite.models_benchmarked == 2
    nemotron_res = next(r for r in suite.results if r.model_id == "nemotron")
    qwen_res = next(r for r in suite.results if r.model_id == "qwen")

    # Nemotron failed gracefully
    assert nemotron_res.error is not None
    assert "timeout" in nemotron_res.error.lower()
    assert nemotron_res.json_valid is False

    # Qwen succeeded
    assert qwen_res.error is None
    assert qwen_res.json_valid is True

    # Critical: VRAM residency is clean (guaranteed eviction in finally block)
    assert provider.currently_loaded_model is None


def test_benchmark_tabular_report_generation(tmp_path):
    """Test generating tabular benchmark report string."""
    provider = MockLLMProvider()
    runner = LLMBenchmarkRunner(
        provider=provider,
        output_dir=str(tmp_path / "experiments"),
        mock_hardware=True,
    )

    suite = runner.run_all_benchmarks(model_ids=["qwen", "gemma"])
    report_text = runner.generate_tabular_report(suite)

    assert "AutoTrade AI - LLM Baseline Benchmark Report" in report_text
    assert "qwen" in report_text
    assert "gemma" in report_text
    assert "Eval tok/s" in report_text
    assert "Prompt tok/s" in report_text
    assert "VRAM (MB)" in report_text
    assert "RAM (MB)" in report_text
    assert "Summary:" in report_text
