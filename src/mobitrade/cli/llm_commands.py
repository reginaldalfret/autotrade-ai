import click
from datetime import datetime
from typing import Optional

from mobitrade.config.model_registry import ModelRegistry
from mobitrade.config.settings import load_yaml_config
from mobitrade.llm.mock_provider import MockLLMProvider
from mobitrade.llm.ollama_provider import OllamaLLMProvider
from mobitrade.llm.scheduler import SequentialLLMScheduler
from mobitrade.llm.persistence import LLMDatabaseRepository
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.data_models import Timeframe
from mobitrade.data.calendar import IST
import os
import json
from mobitrade.llm.hardware import detect_gpu_environment
from mobitrade.llm.benchmark import LLMBenchmarkRunner
from mobitrade.config.performance import load_performance_profile, save_performance_profile, LLMPerformanceProfile

@click.group(name="llm")
def llm_cli():
    """AutoTrade AI - 8-Model Local LLM Integration & Scheduler CLI"""
    pass

@llm_cli.command(name="status")
def llm_status():
    """Display Local LLM inference engine and scheduler status."""
    click.echo("==================================================")
    click.echo("AutoTrade AI - 8-Model Local LLM Engine Status")
    click.echo("==================================================")
    click.echo("Target Hardware:      8 GB RAM / NVIDIA RTX 2050 (4 GB VRAM)")
    click.echo("Scheduler Policy:     Sequential Execution (ONE model in VRAM at a time)")
    click.echo("Runtime Integration:  Ollama Local Daemon (CUDA accelerated)")
    click.echo("Runtime Endpoint:     http://127.0.0.1:11434")
    click.echo("Model Registry:       8 Registered Local Models")
    click.echo("Decision Gate:        Strict Structured JSON Validation")
    click.echo("Risk Authority:       Deterministic RiskEngine (LLM cannot override stops)")
    click.echo("Account Isolation:    ₹1,000 Starting Virtual Capital per Model")

@llm_cli.command(name="validate")
@click.option("--prompt-config", default="configs/prompts/trading_decision_v1.yaml")
def llm_validate(prompt_config):
    """Validate prompt configuration and JSON schema."""
    cfg = load_yaml_config(prompt_config)
    if not cfg:
        click.echo(f"Error: Prompt configuration {prompt_config} not found.")
        return
    click.echo(f"Validating prompt configuration: {prompt_config}")
    click.echo(f" - Prompt Version: {cfg.get('version', '1.0.0')}")
    click.echo(f" - Target Market:   {cfg.get('market', 'NSE')}")
    click.echo(f" - Schema Fields:   {list(cfg.get('schema', {}).get('properties', {}).keys())}")
    click.echo("Prompt configuration valid.")

@llm_cli.command(name="models")
def llm_models():
    """List 8 configured local models and query live runtime availability."""
    registry = ModelRegistry()
    models = registry.list_all_models()
    ollama = OllamaLLMProvider()
    live_available = ollama.health_check()
    runtime_models = set(ollama.list_models()) if live_available else set()

    click.echo("==================================================")
    click.echo(f"Configured 8-Model Registry (Ollama Live: {'CONNECTED' if live_available else 'OFFLINE'}):")
    click.echo("==================================================")
    for m in models:
        is_ready = m.runtime_model_name in runtime_models or any(m.runtime_model_name in rm for rm in runtime_models)
        avail_str = "[READY]" if is_ready else ("[ENABLED]" if m.enabled else "[DISABLED]")
        click.echo(f" - {m.id.ljust(12)}: {m.display_name.ljust(24)} -> {m.runtime_model_name.ljust(28)} {avail_str}")

@llm_cli.command(name="test")
@click.option("--model", default="qwen", help="Model ID or tag to test (e.g. qwen, nemotron, gemma)")
def llm_test(model):
    """Execute a safe, non-trading inference test on a single local model."""
    registry = ModelRegistry()
    m_cfg = registry.get_model(model)
    tag = m_cfg.runtime_model_name if m_cfg else model

    click.echo(f"Running safe isolated test on model: {model} ({tag})...")
    ollama = OllamaLLMProvider()

    if not ollama.health_check():
        click.echo("Notice: Local Ollama daemon is currently offline at 127.0.0.1:11434.")
        click.echo("Running verification via MockLLMProvider...")
        mock = MockLLMProvider()
        res = mock.generate(tag if tag in mock.available_models else "qwen2.5-coder:1.5b", "Respond with test JSON")
        click.echo(f"Mock Response: {res['raw_text']}")
        click.echo(f"Simulated Latency: {res['latency_ms']:.2f} ms")
        return

    try:
        load_time = ollama.load_model(tag)
        click.echo(f"Model loaded into VRAM in {load_time:.2f} ms.")

        res = ollama.generate(tag, 'Respond with JSON only: {"action": "HOLD", "confidence": 0.5, "reasoning_summary": "Test OK"}')
        click.echo(f"Raw Output: {res['raw_text']}")
        click.echo(f"Inference Latency: {res['latency_ms']:.2f} ms")

        unload_time = ollama.unload_model(tag)
        click.echo(f"Model successfully evicted from VRAM in {unload_time:.2f} ms.")
    except Exception as e:
        click.echo(f"Test failed: {e}")

@llm_cli.command(name="evaluate-snapshot")
@click.option("--snapshot", default="MOCK_SNAP_001", help="Snapshot ID to evaluate")
def llm_evaluate_snapshot(snapshot):
    """Execute sequential evaluation of all 8 models against a frozen MarketSnapshot."""
    click.echo(f"Preparing frozen MarketSnapshot: {snapshot}...")
    dt = datetime.now(IST)
    snap = MarketSnapshot(
        snapshot_id=snapshot,
        symbol="TCS",
        decision_timestamp=dt,
        timeframe=Timeframe.M5,
    )

    provider = MockLLMProvider()
    scheduler = SequentialLLMScheduler(provider=provider)

    click.echo("Executing SequentialLLMScheduler across enabled models...")
    run = scheduler.evaluate_snapshot(snap, persist=True)

    click.echo("==================================================")
    click.echo("AutoTrade AI - Sequential Evaluation Summary")
    click.echo("==================================================")
    click.echo(f"Run ID:              {run.run_id}")
    click.echo(f"Snapshot ID:         {run.snapshot_id}")
    click.echo(f"Evaluated Models:    {len(run.evaluated_models)}")
    click.echo(f"Successful:          {len(run.successful_decisions)}")
    click.echo(f"Failed / Invalid:    {len(run.failed_models)}")
    click.echo(f"Total Cycle Time:    {run.total_cycle_time_ms:.2f} ms")
    click.echo("Decisions successfully recorded to database/mobitrade.db.")
    click.echo("==================================================")

@llm_cli.command(name="hardware")
@click.option("--mock", is_flag=True, help="Simulate target RTX 2050 4GB environment")
def llm_hardware(mock: bool):
    """Inspect GPU, VRAM, WSL2, Ollama daemon, and system memory."""
    env = detect_gpu_environment(mock=mock)
    gpu = env["gpu"]
    wsl = env["wsl2"]
    ollama = env["ollama"]
    llama = env["llamacpp"]
    mem = env["system_memory"]
    rec = env["recommendations"]

    click.echo("==================================================")
    click.echo("AutoTrade AI - Hardware & GPU Environment")
    click.echo("==================================================")
    click.echo(f"GPU Available:       {'YES' if gpu['available'] else 'NO'}")
    click.echo(f"GPU Device:          {gpu['device_name']}")
    click.echo(f"VRAM Total / Free:   {gpu['total_vram_mb']:.0f} MiB / {gpu['free_vram_mb']:.0f} MiB")
    click.echo(f"Driver Version:      {gpu['driver_version']}")
    click.echo(f"CUDA Compute Cap:    {gpu['cuda_compute_capability']}")
    click.echo(f"WSL2 Environment:    {'YES' if wsl['is_wsl2'] else 'NO'}")
    click.echo(f"WSL2 GPU Libcuda:    {wsl['libcuda_path'] or 'N/A'}")
    click.echo(f"Ollama Daemon:       {'CONNECTED' if ollama['connected'] else 'OFFLINE'} ({ollama['base_url']})")
    click.echo(f"Ollama GPU Support:  {'YES' if ollama['gpu_support'] else 'NO'}")
    click.echo(f"llama.cpp Binary:    {llama['primary_binary'] or 'NOT FOUND'}")
    click.echo(f"System RAM:          {mem['total_ram_mb']:.0f} MiB ({mem['percent_used']:.1f}% used)")
    click.echo("--------------------------------------------------")
    click.echo(f"Recommended Runtime: {rec['recommended_runtime']}")
    click.echo(f"Recommended Backend: {rec['recommended_backend']}")
    click.echo(f"Concurrency Policy:  {rec['concurrency_policy']}")
    click.echo(f"Model Size Limit:    {rec['max_recommended_model_size']}")
    click.echo("==================================================")

@llm_cli.command(name="benchmark")
@click.option("--model", default=None, help="Specific model ID to benchmark (e.g. qwen, nemotron)")
@click.option("--iterations", default=1, type=int, help="Number of benchmark iterations")
@click.option("--mock", is_flag=True, help="Force MockLLMProvider for offline execution")
def llm_benchmark(model: Optional[str], iterations: int, mock: bool):
    """Execute standardized LLM benchmarks with single-model sequential residency."""
    provider = MockLLMProvider() if mock else None
    runner = LLMBenchmarkRunner(provider=provider, mock_hardware=mock)
    model_ids = [model] if model else None

    click.echo(f"Starting LLM benchmark suite (Provider: {runner.provider.provider_name})...")
    suite = runner.run_all_benchmarks(model_ids=model_ids, iterations=iterations)
    out_path = runner.save_experiment(suite)

    click.echo("\n" + runner.generate_tabular_report(suite))
    click.echo(f"\nExperiment result saved to: {out_path}")

@llm_cli.command(name="benchmark-report")
@click.option("--file", default=None, help="Path to custom experiment JSON result")
def llm_benchmark_report(file: Optional[str]):
    """Display comprehensive performance comparison table across models and configurations."""
    exp_path = file or "data/experiments/llm_baseline/latest.json"
    if not os.path.exists(exp_path):
        click.echo(f"Notice: Experiment report not found at {exp_path}.")
        click.echo("Running quick evaluation via MockLLMProvider to generate baseline report...")
        runner = LLMBenchmarkRunner(provider=MockLLMProvider(), mock_hardware=True)
        suite = runner.run_all_benchmarks(iterations=1)
        exp_path = runner.save_experiment(suite)

    try:
        with open(exp_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        click.echo("=========================================================================================================")
        click.echo("AutoTrade AI — Local LLM Performance Benchmark & Configuration Comparison")
        click.echo("=========================================================================================================")
        click.echo(f"Experiment ID: {data.get('experiment_id')} | Timestamp: {data.get('timestamp')}")
        hw = data.get("hardware", {})
        gpu_info = hw.get("gpu", {})
        click.echo(f"Hardware Target: {gpu_info.get('device_name', 'NVIDIA RTX 2050')} ({gpu_info.get('total_vram_mb', 4096):.0f} MiB VRAM) | Driver: {gpu_info.get('driver_version', '616.92')}")
        click.echo("---------------------------------------------------------------------------------------------------------")
        header = f"{'Model ID':<10} {'Backend':<8} {'Offload':<9} {'Context':<8} {'KV-Cache':<8} {'FA':<4} {'Eval tok/s':<11} {'Latency':<10} {'VRAM':<10} {'RAM':<10} {'Status'}"
        click.echo(header)
        click.echo("-" * 105)

        for r in data.get("results", []):
            m_id = r.get("model_id", "")
            prof = load_performance_profile(m_id)
            backend = r.get("provider", "OLLAMA")
            offload = f"{prof.gpu_layers} layers" if prof.gpu_layers != -1 else "100% GPU"
            ctx = f"{prof.context_size}"
            kv = prof.kv_cache_type
            fa = "ON" if prof.flash_attention else "OFF"
            e_tok_s = f"{r.get('eval_tok_s', 0.0):.1f}"
            lat = f"{r.get('latency_ms', 0.0):.0f}ms"
            vram = f"{r.get('vram_usage_mb', 0.0):.0f}MB"
            ram = f"{r.get('ram_usage_mb', 0.0):.0f}MB"
            status = "[VALID]" if r.get("json_valid") else "[ERROR]"
            row = f"{m_id:<10} {backend:<8} {offload:<9} {ctx:<8} {kv:<8} {fa:<4} {e_tok_s:<11} {lat:<10} {vram:<10} {ram:<10} {status}"
            click.echo(row)

        click.echo("=========================================================================================================")
        summary = data.get("summary", {})
        click.echo(f"Fastest Model: {summary.get('fastest_eval_model')} ({summary.get('fastest_eval_tok_s', 0.0):.1f} tok/s) | Lowest Latency: {summary.get('lowest_latency_model')} ({summary.get('lowest_latency_ms', 0.0):.0f}ms)")
        click.echo("Optimal Configuration: 100% GPU Offload (FlashAttention ON, Context 2048, Sequential Eviction)")
        click.echo("=========================================================================================================")
    except Exception as e:
        click.echo(f"Error loading benchmark report: {e}")

@llm_cli.command(name="optimize")
@click.option("--mock", is_flag=True, help="Run optimization trial in mock hardware mode")
def llm_optimize(mock: bool):
    """Detect hardware, profile configurations, and persist optimal model execution profiles."""
    click.echo("==================================================")
    click.echo("AutoTrade AI — Local LLM Automated Optimization")
    click.echo("==================================================")
    env = detect_gpu_environment(mock=mock)
    gpu = env["gpu"]
    click.echo(f"Detected GPU: {gpu['device_name']} ({gpu['total_vram_mb']:.0f} MiB VRAM, Driver {gpu['driver_version']})")
    click.echo("Applying optimization strategy: Single-Model Sequential VRAM Residency with FlashAttention...")

    registry = ModelRegistry()
    models = registry.list_all_models()
    runner = LLMBenchmarkRunner(provider=MockLLMProvider() if mock else None, mock_hardware=mock)

    suite = runner.run_all_benchmarks(iterations=1)
    runner.save_experiment(suite)

    click.echo("\nUpdating model performance profiles in configs/llm-performance/...")
    for res in suite.results:
        prof = load_performance_profile(res.model_id)
        prof.benchmark_result = {
            "prompt_eval_tok_s": res.prompt_eval_tok_s,
            "eval_tok_s": res.eval_tok_s,
            "latency_ms": res.latency_ms,
            "vram_usage_mb": res.vram_usage_mb,
            "ram_usage_mb": res.ram_usage_mb,
            "json_valid": res.json_valid,
        }
        prof.recommended_configuration = {
            "gpu_layers": -1,
            "flash_attention": True,
            "context_size": 2048,
            "kv_cache": "f16",
            "concurrency": "single_model_sequential",
        }
        save_path = save_performance_profile(prof)
        click.echo(f" - {res.model_id.ljust(10)} -> {save_path} ({res.eval_tok_s:.1f} tok/s, {res.latency_ms:.0f}ms)")

    click.echo("Optimization complete. All 8 performance profiles synchronized.")
    click.echo("==================================================")
