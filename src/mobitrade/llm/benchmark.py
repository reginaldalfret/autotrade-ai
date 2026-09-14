"""
AutoTrade AI - Local LLM Benchmark Runner.

Executes standardized performance and conformance benchmarks across configured
local language models under strict single-model VRAM residency constraints.
Measures:
- prompt_eval_tok_s: Prompt evaluation speed (tok/s)
- eval_tok_s: Token generation speed (tok/s)
- latency_ms: End-to-end inference latency (ms)
- load_time_ms: VRAM model load time (ms)
- unload_time_ms: VRAM eviction time (ms)
- vram_usage_mb: Resident VRAM footprint (MB)
- ram_usage_mb: Resident system RAM footprint (MB)
- json_valid: Strict schema validation adherence

Saves experiment records to data/experiments/llm_baseline/ and generates
tabular reports and summary scorecards.
"""

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from mobitrade.config.model_registry import ModelRegistry
from mobitrade.config.settings import ModelConfig
from mobitrade.llm.base import LocalLLMProvider
from mobitrade.llm.ollama_provider import OllamaLLMProvider
from mobitrade.llm.mock_provider import MockLLMProvider
from mobitrade.llm.validator import DecisionValidator
from mobitrade.llm.hardware import (
    detect_gpu_environment,
    get_gpu_vram_mb,
    get_system_ram_mb,
)
from mobitrade.data.calendar import IST

# Standard benchmark evaluation prompt adhering to trading_decision_v1 schema
STANDARD_BENCHMARK_SYSTEM_PROMPT = """You are an expert quantitative and fundamental trading analyst evaluating NSE (National Stock Exchange of India) cash market equity opportunities.
You are provided with an explicit, frozen, point-in-time MarketSnapshot containing market data, technical features, scanner scores, and external company news.

CRITICAL CONSTRAINTS:
1. Reason ONLY from the supplied point-in-time snapshot. Do not assume or invent future price action, news, or subsequent market sessions.
2. All trading decisions are strictly intraday (09:15 - 15:30 IST).
3. You have NO ability to bypass hard risk management, daily target/loss stops, or trailing stops.
4. Never claim guaranteed profits. Self-reported confidence reflects signal strength, not empirical win probability.
5. You MUST return ONLY a valid JSON object strictly matching the required schema. Do not output markdown code blocks or conversational text."""

STANDARD_BENCHMARK_PAYLOAD = {
    "symbol": "RELIANCE",
    "exchange": "NSE",
    "timeframe": "5m",
    "timestamp": "2026-09-14T10:15:00+05:30",
    "current_price": 2980.50,
    "candle": {
        "open": 2965.00,
        "high": 2985.00,
        "low": 2962.00,
        "close": 2980.50,
        "volume": 125000,
    },
    "technical_features": {
        "ema_9": 2975.20,
        "ema_21": 2968.40,
        "rsi_14": 63.8,
        "atr_14": 18.50,
        "vwap": 2972.10,
        "volume_ratio": 2.15,
        "trend": "BULLISH",
    },
    "scanner_score": 84.5,
    "external_context": [
        {
            "source": "NEWS_FEED",
            "headline": "Reliance Industries expands retail footprint; Q2 margins beat consensus.",
            "sentiment": "POSITIVE",
        }
    ],
}

STANDARD_BENCHMARK_PROMPT = f"""Evaluate this frozen point-in-time MarketSnapshot for an intraday NSE trading decision:
{json.dumps(STANDARD_BENCHMARK_PAYLOAD, indent=2)}

Required output format:
{{
  "action": "BUY" | "SELL" | "HOLD" | "NO_ACTION",
  "confidence": 0.0 to 1.0,
  "entry_rationale": "Clear string",
  "proposed_stop_loss": 2960.00,
  "proposed_target": 3015.00,
  "holding_intent": "INTRADAY",
  "reasoning_summary": "Concise summary string"
}}
Respond ONLY with the JSON object:"""


@dataclass
class ModelBenchmarkResult:
    """Standardized metric record for a single model benchmark."""
    model_id: str
    display_name: str
    runtime_model_name: str
    provider: str
    prompt_eval_tok_s: float
    eval_tok_s: float
    latency_ms: float
    load_time_ms: float
    unload_time_ms: float
    vram_usage_mb: float
    ram_usage_mb: float
    tokens_prompt: int
    tokens_generated: int
    json_valid: bool
    validation_status: str
    action: Optional[str] = None
    confidence: Optional[float] = None
    reasoning_summary: Optional[str] = None
    error: Optional[str] = None
    raw_text: Optional[str] = None
    iterations: int = 1


@dataclass
class BenchmarkSuiteResult:
    """Complete benchmark experiment results across models with hardware snapshot."""
    experiment_id: str
    timestamp: str
    hardware: Dict[str, Any]
    models_benchmarked: int
    successful_models: int
    failed_models: int
    results: List[ModelBenchmarkResult]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "hardware": self.hardware,
            "models_benchmarked": self.models_benchmarked,
            "successful_models": self.successful_models,
            "failed_models": self.failed_models,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


class LLMBenchmarkRunner:
    """
    Standardized benchmark execution engine for AutoTrade AI local LLMs.
    Enforces sequential execution policy: strictly ONE model in VRAM at any time.
    """

    def __init__(
        self,
        provider: Optional[LocalLLMProvider] = None,
        config_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        mock_hardware: bool = False,
    ):
        self.registry = ModelRegistry(config_path=config_path)
        self.validator = DecisionValidator()
        self.mock_hardware = mock_hardware

        # Resolve provider
        if provider is not None:
            self.provider = provider
        else:
            # Auto-detect Ollama vs Mock fallback
            ollama = OllamaLLMProvider()
            if ollama.health_check():
                self.provider = ollama
            else:
                self.provider = MockLLMProvider()

        # Resolve output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            project_root = Path(__file__).resolve().parents[3]
            self.output_dir = project_root / "data" / "experiments" / "llm_baseline"

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def benchmark_model(
        self,
        model_cfg: ModelConfig,
        iterations: int = 1,
        timeout_seconds: float = 45.0,
    ) -> ModelBenchmarkResult:
        """
        Run standardized benchmark on a single model with explicit load, inference, and eviction.
        Guarantees VRAM cleanup even upon inference failure.
        """
        tag = model_cfg.runtime_model_name
        model_id = model_cfg.id
        display_name = model_cfg.display_name

        # Enforce pre-execution clean slate in VRAM
        if self.provider.currently_loaded_model:
            try:
                self.provider.unload_model(self.provider.currently_loaded_model)
            except Exception:
                pass

        # Initial memory measurement
        vram_before = get_gpu_vram_mb()
        ram_before = get_system_ram_mb()

        load_time_ms = 0.0
        unload_time_ms = 0.0
        latency_samples: List[float] = []
        prompt_tokens_samples: List[int] = []
        gen_tokens_samples: List[int] = []
        prompt_eval_speeds: List[float] = []
        eval_speeds: List[float] = []

        last_raw_text = ""
        last_action = None
        last_confidence = None
        last_reasoning = None
        is_json_valid = False
        val_status_str = "NOT_EVALUATED"
        error_msg: Optional[str] = None
        vram_delta = 0.0
        ram_delta = 0.0

        try:
            # 1. Timed Model Load into VRAM
            load_time_ms = self.provider.load_model(tag)
            vram_loaded = get_gpu_vram_mb()
            ram_loaded = get_system_ram_mb()

            # 2. Timed Inference Iterations
            for it in range(iterations):
                gen_res = self.provider.generate(
                    model_tag=tag,
                    prompt=STANDARD_BENCHMARK_PROMPT,
                    system_prompt=STANDARD_BENCHMARK_SYSTEM_PROMPT,
                    timeout_seconds=timeout_seconds,
                )

                lat = float(gen_res.get("latency_ms", 0.0))
                latency_samples.append(lat)

                raw = str(gen_res.get("raw_text", ""))
                last_raw_text = raw

                tok_prompt = int(gen_res.get("tokens_prompt") or 0)
                tok_gen = int(gen_res.get("tokens_generated") or 0)
                prompt_tokens_samples.append(tok_prompt)
                gen_tokens_samples.append(tok_gen)

                # Tok/s extraction from Ollama metadata if available
                meta = gen_res.get("metadata", {})
                p_dur_ns = meta.get("prompt_eval_duration_ns") or meta.get("prompt_eval_duration")
                g_dur_ns = meta.get("eval_duration_ns") or meta.get("eval_duration")

                if p_dur_ns and p_dur_ns > 0 and tok_prompt > 0:
                    p_speed = tok_prompt / (p_dur_ns / 1e9)
                elif lat > 0 and tok_prompt > 0:
                    p_speed = tok_prompt / (lat / 1000.0)
                else:
                    p_speed = 0.0
                prompt_eval_speeds.append(p_speed)

                if g_dur_ns and g_dur_ns > 0 and tok_gen > 0:
                    e_speed = tok_gen / (g_dur_ns / 1e9)
                elif lat > 0 and tok_gen > 0:
                    e_speed = tok_gen / (lat / 1000.0)
                else:
                    e_speed = 0.0
                eval_speeds.append(e_speed)

                # Validate structured output
                ok, status, reason, parsed = self.validator.validate_response(
                    raw_text=raw,
                    expected_symbol="RELIANCE",
                    expected_snapshot_id="BENCHMARK_SNAP_001",
                    current_price=2980.50,
                )
                is_json_valid = ok
                val_status_str = status.value if hasattr(status, "value") else str(status)
                if ok and parsed:
                    last_action = parsed.get("action")
                    last_confidence = parsed.get("confidence")
                    last_reasoning = parsed.get("reasoning_summary")

            # Measure peak / resident VRAM & RAM
            vram_peak = get_gpu_vram_mb()
            ram_peak = get_system_ram_mb()

            vram_delta = max(0.0, vram_peak["used"] - vram_before["used"])
            # Fallback estimation if zero delta measured (e.g. mock provider or shared driver)
            if vram_delta == 0.0 and vram_loaded["used"] > 0:
                vram_delta = vram_loaded["used"]
            elif vram_delta == 0.0 and isinstance(self.provider, MockLLMProvider):
                # Estimated footprint based on parameter count
                vram_delta = 1200.0 if "1b" in tag or "1.5b" in tag or "1.7b" in tag else 2400.0

            ram_delta = max(0.0, ram_peak["used"] - ram_before["used"])
            if ram_delta == 0.0 and isinstance(self.provider, MockLLMProvider):
                ram_delta = 450.0

        except Exception as e:
            error_msg = str(e)
            is_json_valid = False
            val_status_str = "EXECUTION_ERROR"
        finally:
            # 3. Explicit VRAM Eviction Guaranteed in Finally Block
            try:
                unload_time_ms = self.provider.unload_model(tag)
            except Exception as ue:
                if not error_msg:
                    error_msg = f"Eviction warning: {ue}"

        # Aggregate averages
        avg_latency = sum(latency_samples) / len(latency_samples) if latency_samples else 0.0
        avg_prompt_tokens = int(sum(prompt_tokens_samples) / len(prompt_tokens_samples)) if prompt_tokens_samples else 0
        avg_gen_tokens = int(sum(gen_tokens_samples) / len(gen_tokens_samples)) if gen_tokens_samples else 0
        avg_p_speed = round(sum(prompt_eval_speeds) / len(prompt_eval_speeds), 2) if prompt_eval_speeds else 0.0
        avg_e_speed = round(sum(eval_speeds) / len(eval_speeds), 2) if eval_speeds else 0.0

        return ModelBenchmarkResult(
            model_id=model_id,
            display_name=display_name,
            runtime_model_name=tag,
            provider=self.provider.provider_name,
            prompt_eval_tok_s=avg_p_speed,
            eval_tok_s=avg_e_speed,
            latency_ms=round(avg_latency, 2),
            load_time_ms=round(load_time_ms, 2),
            unload_time_ms=round(unload_time_ms, 2),
            vram_usage_mb=round(vram_delta, 2),
            ram_usage_mb=round(ram_delta, 2),
            tokens_prompt=avg_prompt_tokens,
            tokens_generated=avg_gen_tokens,
            json_valid=is_json_valid,
            validation_status=val_status_str,
            action=last_action,
            confidence=last_confidence,
            reasoning_summary=last_reasoning,
            error=error_msg,
            raw_text=last_raw_text,
            iterations=iterations,
        )

    def run_all_benchmarks(
        self,
        model_ids: Optional[List[str]] = None,
        iterations: int = 1,
    ) -> BenchmarkSuiteResult:
        """
        Execute sequential benchmarks across all requested models.
        Ensures each model is loaded, evaluated, and unloaded sequentially.
        """
        all_models = self.registry.list_enabled_models()
        if model_ids:
            target_models = [m for m in all_models if m.id in model_ids]
        else:
            target_models = all_models

        # Detect hardware environment snapshot
        hw_info = detect_gpu_environment(mock=self.mock_hardware)

        dt_now = datetime.now(timezone.utc)
        exp_id = f"baseline_{dt_now.strftime('%Y%m%d_%H%M%S')}"
        results: List[ModelBenchmarkResult] = []

        for m_cfg in target_models:
            res = self.benchmark_model(m_cfg, iterations=iterations)
            results.append(res)

        successful = sum(1 for r in results if r.error is None and r.json_valid)
        failed = len(results) - successful

        # Compute summary metrics
        summary = self._compute_summary(results, hw_info)

        suite = BenchmarkSuiteResult(
            experiment_id=exp_id,
            timestamp=dt_now.isoformat(),
            hardware=hw_info,
            models_benchmarked=len(results),
            successful_models=successful,
            failed_models=failed,
            results=results,
            summary=summary,
        )

        return suite

    def _compute_summary(
        self,
        results: List[ModelBenchmarkResult],
        hw_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute scorecard summary across benchmark results."""
        if not results:
            return {}

        valid_results = [r for r in results if r.error is None]
        json_valid_results = [r for r in valid_results if r.json_valid]

        fastest_eval = max(valid_results, key=lambda x: x.eval_tok_s) if valid_results else None
        lowest_lat = min(valid_results, key=lambda x: x.latency_ms) if valid_results else None
        lowest_vram = min(valid_results, key=lambda x: x.vram_usage_mb) if valid_results else None

        avg_eval_tok_s = (
            sum(r.eval_tok_s for r in valid_results) / len(valid_results)
            if valid_results
            else 0.0
        )
        avg_latency = (
            sum(r.latency_ms for r in valid_results) / len(valid_results)
            if valid_results
            else 0.0
        )

        compliance_rate = (
            (len(json_valid_results) / len(results) * 100.0)
            if results
            else 0.0
        )

        # Recommendation for trading production
        optimal_model = None
        if json_valid_results:
            # Score combining eval_tok_s (higher better) and latency (lower better)
            scored = sorted(
                json_valid_results,
                key=lambda x: (x.eval_tok_s / max(1.0, x.latency_ms)),
                reverse=True,
            )
            optimal_model = scored[0].model_id

        return {
            "total_models": len(results),
            "successful_inferences": len(valid_results),
            "json_compliant_models": len(json_valid_results),
            "json_compliance_rate_pct": round(compliance_rate, 1),
            "avg_eval_tok_s": round(avg_eval_tok_s, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "fastest_eval_model": fastest_eval.model_id if fastest_eval else None,
            "fastest_eval_tok_s": fastest_eval.eval_tok_s if fastest_eval else 0.0,
            "lowest_latency_model": lowest_lat.model_id if lowest_lat else None,
            "lowest_latency_ms": lowest_lat.latency_ms if lowest_lat else 0.0,
            "lowest_vram_model": lowest_vram.model_id if lowest_vram else None,
            "lowest_vram_mb": lowest_vram.vram_usage_mb if lowest_vram else 0.0,
            "recommended_production_model": optimal_model,
        }

    def save_experiment(self, suite: BenchmarkSuiteResult) -> Path:
        """
        Save experiment result JSON to data/experiments/llm_baseline/
        and write a latest.json pointer.
        """
        out_file = self.output_dir / f"{suite.experiment_id}.json"
        latest_file = self.output_dir / "latest.json"

        data = suite.to_dict()
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return out_file

    def generate_tabular_report(self, suite: BenchmarkSuiteResult) -> str:
        """
        Render a clean tabular report summarizing benchmark outcomes across all models.
        Uses tabulate if installed, otherwise clean aligned text.
        """
        headers = [
            "Model ID",
            "Display Name",
            "Load (ms)",
            "Latency (ms)",
            "Eval tok/s",
            "Prompt tok/s",
            "VRAM (MB)",
            "RAM (MB)",
            "JSON Valid",
            "Action",
        ]

        rows = []
        for r in suite.results:
            rows.append([
                r.model_id,
                r.display_name,
                f"{r.load_time_ms:.1f}",
                f"{r.latency_ms:.1f}",
                f"{r.eval_tok_s:.2f}",
                f"{r.prompt_eval_tok_s:.2f}",
                f"{r.vram_usage_mb:.1f}",
                f"{r.ram_usage_mb:.1f}",
                "YES" if r.json_valid else "NO",
                r.action or "N/A",
            ])

        lines = [
            "==========================================================================================",
            f"AutoTrade AI - LLM Baseline Benchmark Report ({suite.experiment_id})",
            "==========================================================================================",
            f"Hardware: {suite.hardware.get('gpu', {}).get('device_name', 'N/A')} "
            f"({suite.hardware.get('gpu', {}).get('total_vram_mb', 0):.0f} MiB VRAM) | "
            f"RAM: {suite.hardware.get('system_memory', {}).get('total_ram_mb', 0):.0f} MiB",
            f"Policy:   Strict Single-Model Sequential Residency (Load -> Infer -> Evict)",
            "------------------------------------------------------------------------------------------",
        ]

        if HAS_TABULATE:
            lines.append(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            # Fallback simple table formatter
            col_widths = [max(len(str(item)) for item in [h] + [r[i] for r in rows]) for i, h in enumerate(headers)]
            header_row = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
            sep_row = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
            lines.append(header_row)
            lines.append(sep_row)
            for r in rows:
                lines.append(" | ".join(str(r[i]).ljust(col_widths[i]) for i in range(len(headers))))

        lines.append("------------------------------------------------------------------------------------------")
        lines.append(f"Summary: Compliant: {suite.summary.get('json_compliant_models', 0)}/{suite.models_benchmarked} "
                     f"({suite.summary.get('json_compliance_rate_pct', 0)}%) | "
                     f"Avg Latency: {suite.summary.get('avg_latency_ms', 0):.1f} ms | "
                     f"Fastest: {suite.summary.get('fastest_eval_model', 'N/A')} "
                     f"({suite.summary.get('fastest_eval_tok_s', 0):.1f} tok/s) | "
                     f"Recommended: {suite.summary.get('recommended_production_model', 'N/A')}")
        lines.append("==========================================================================================")

        return "\n".join(lines)
