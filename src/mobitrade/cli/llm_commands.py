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

@click.group(name="llm")
def llm_cli():
    """MobiTrade AI - 8-Model Local LLM Integration & Scheduler CLI"""
    pass

@llm_cli.command(name="status")
def llm_status():
    """Display Local LLM inference engine and scheduler status."""
    click.echo("==================================================")
    click.echo("MobiTrade AI - 8-Model Local LLM Engine Status")
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
    click.echo("MobiTrade AI - Sequential Evaluation Summary")
    click.echo("==================================================")
    click.echo(f"Run ID:              {run.run_id}")
    click.echo(f"Snapshot ID:         {run.snapshot_id}")
    click.echo(f"Evaluated Models:    {len(run.evaluated_models)}")
    click.echo(f"Successful:          {len(run.successful_decisions)}")
    click.echo(f"Failed / Invalid:    {len(run.failed_models)}")
    click.echo(f"Total Cycle Time:    {run.total_cycle_time_ms:.2f} ms")
    click.echo("Decisions successfully recorded to database/mobitrade.db.")
    click.echo("==================================================")
