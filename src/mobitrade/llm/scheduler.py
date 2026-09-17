import uuid
import time
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.llm_models import (
    LLMAction,
    ValidationStatus,
    LLMDecisionRecord,
    InferenceMetrics,
    ModelEvaluationRun,
)
from mobitrade.config.model_registry import ModelRegistry, ModelConfig
from mobitrade.llm.base import LocalLLMProvider
from mobitrade.llm.validator import DecisionValidator
from mobitrade.llm.persistence import LLMDatabaseRepository
from mobitrade.config.settings import load_yaml_config
from mobitrade.transport.redis_service import redis_service, RedisStreamName

class SequentialLLMScheduler:
    """
    Sequential Local LLM Scheduler designed for 8 GB RAM / RTX 2050 4 GB VRAM.
    Evaluates each model one-at-a-time on the EXACT SAME frozen MarketSnapshot:
    load -> infer -> validate -> record -> unload.
    """
    def __init__(
        self,
        provider: LocalLLMProvider,
        registry: Optional[ModelRegistry] = None,
        validator: Optional[DecisionValidator] = None,
        repository: Optional[LLMDatabaseRepository] = None,
        prompt_config_path: str = "configs/prompts/trading_decision_v1.yaml",
        timeout_seconds: float = 30.0,
        max_retries: int = 1
    ):
        self.provider = provider
        self.registry = registry or ModelRegistry()
        self.validator = validator or DecisionValidator()
        self.repository = repository or LLMDatabaseRepository()
        self.prompt_config = load_yaml_config(prompt_config_path) or {}
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def evaluate_snapshot(
        self,
        snapshot: MarketSnapshot,
        enabled_only: bool = True,
        persist: bool = True
    ) -> ModelEvaluationRun:
        """
        Sequentially evaluates all models on the supplied immutable MarketSnapshot.
        Simulation time remains frozen throughout the decision cycle.
        """
        cycle_start = time.perf_counter()
        run_id = f"run_{uuid.uuid4().hex[:8]}"

        models = self.registry.list_enabled_models() if enabled_only else self.registry.list_all_models()
        evaluated_models = []
        successful_decisions = []
        failed_models = []
        decision_records: List[LLMDecisionRecord] = []

        system_prompt = self.prompt_config.get("system_prompt", "")
        prompt_payload = self._build_prompt_payload(snapshot)

        for model_cfg in models:
            evaluated_models.append(model_cfg.id)
            decision = self._evaluate_single_model(
                model_cfg, snapshot, prompt_payload, system_prompt
            )
            decision_records.append(decision)

            if decision.validation_status == ValidationStatus.VALID:
                successful_decisions.append(model_cfg.id)
            else:
                failed_models.append(model_cfg.id)

        total_cycle_time = (time.perf_counter() - cycle_start) * 1000.0

        run = ModelEvaluationRun(
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            decision_timestamp=snapshot.decision_timestamp,
            evaluated_models=evaluated_models,
            successful_decisions=successful_decisions,
            failed_models=failed_models,
            total_cycle_time_ms=total_cycle_time,
            created_at=datetime.now(timezone.utc)
        )

        if persist:
            self.repository.save_evaluation_run(run, decision_records)

        return run

    def _evaluate_single_model(
        self,
        model_cfg: ModelConfig,
        snapshot: MarketSnapshot,
        prompt_payload: str,
        system_prompt: str
    ) -> LLMDecisionRecord:
        decision_id = f"dec_{model_cfg.id}_{snapshot.snapshot_id}_{uuid.uuid4().hex[:6]}"
        tag = model_cfg.runtime_model_name
        current_price = snapshot.candle.close if snapshot.candle else (
            snapshot.candidate.price if snapshot.candidate else 100.0
        )

        load_time_ms = 0.0
        unload_time_ms = 0.0
        start_ts = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

        try:
            # 1. Load Model (ensures single residency in VRAM)
            load_time_ms = self.provider.load_model(tag)
            redis_service.publish_event(
                RedisStreamName.DECISIONS,
                "MODEL_LOAD",
                {"model_id": model_cfg.id, "tag": tag, "symbol": snapshot.symbol, "load_time_ms": load_time_ms}
            )
            redis_service.set_cache("autotrade:cache:active_model", model_cfg.id, ttl_seconds=30)

            # 2. Generate with retries & timeout
            raw_response = None
            gen_res = None
            last_err = None

            redis_service.publish_event(
                RedisStreamName.DECISIONS,
                "INFERENCE_START",
                {"model_id": model_cfg.id, "symbol": snapshot.symbol}
            )

            for attempt in range(self.max_retries + 1):
                try:
                    gen_res = self.provider.generate(
                        model_tag=tag,
                        prompt=prompt_payload,
                        system_prompt=system_prompt,
                        timeout_seconds=self.timeout_seconds
                    )
                    raw_response = gen_res.get("raw_text", "")
                    break
                except TimeoutError as te:
                    last_err = te
                    if attempt == self.max_retries:
                        return self._create_error_decision(
                            decision_id, model_cfg, snapshot, ValidationStatus.TIMEOUT,
                            str(te), (time.perf_counter() - start_perf) * 1000.0, load_time_ms
                        )
                except Exception as e:
                    last_err = e
                    if attempt == self.max_retries:
                        return self._create_error_decision(
                            decision_id, model_cfg, snapshot, ValidationStatus.PROVIDER_ERROR,
                            str(e), (time.perf_counter() - start_perf) * 1000.0, load_time_ms
                        )

            redis_service.publish_event(
                RedisStreamName.DECISIONS,
                "INFERENCE_COMPLETE",
                {"model_id": model_cfg.id, "symbol": snapshot.symbol}
            )

            # 3. Output Validation
            is_valid, status, reason, parsed_data = self.validator.validate_response(
                raw_response, snapshot.symbol, snapshot.snapshot_id, current_price
            )
            redis_service.publish_event(
                RedisStreamName.DECISIONS,
                "VALIDATION",
                {"model_id": model_cfg.id, "symbol": snapshot.symbol, "is_valid": is_valid, "status": status.value, "reason": reason}
            )

            end_perf = time.perf_counter()
            latency_ms = (end_perf - start_perf) * 1000.0
            end_ts = datetime.now(timezone.utc)

            metrics = InferenceMetrics(
                model_id=model_cfg.id,
                snapshot_id=snapshot.snapshot_id,
                start_time=start_ts,
                end_time=end_ts,
                inference_latency_ms=latency_ms,
                model_load_time_ms=load_time_ms,
                tokens_prompt=gen_res.get("tokens_prompt") if gen_res else None,
                tokens_generated=gen_res.get("tokens_generated") if gen_res else None,
                success=is_valid
            )

            if not is_valid or parsed_data is None:
                return LLMDecisionRecord(
                    decision_id=decision_id,
                    model_id=model_cfg.id,
                    model_version=model_cfg.parameters.get("quantization", "1.0"),
                    prompt_version=self.prompt_config.get("version", "1.0.0"),
                    snapshot_id=snapshot.snapshot_id,
                    decision_timestamp=snapshot.decision_timestamp,
                    symbol=snapshot.symbol,
                    action=LLMAction.NO_ACTION,
                    confidence=0.0,
                    entry_rationale="Rejected by validation gate",
                    holding_intent="INTRADAY",
                    reasoning_summary=f"Validation failed: {reason}",
                    validation_status=status,
                    rejection_reason=reason,
                    metrics=metrics,
                    raw_response=raw_response,
                    created_at=end_ts
                )

            redis_service.publish_event(
                RedisStreamName.DECISIONS,
                "DECISION_RECORDED",
                {
                    "decision_id": decision_id,
                    "model_id": model_cfg.id,
                    "symbol": snapshot.symbol,
                    "action": parsed_data["action"].upper(),
                    "confidence": float(parsed_data["confidence"]),
                },
                event_id=decision_id,
            )

            return LLMDecisionRecord(
                decision_id=decision_id,
                model_id=model_cfg.id,
                model_version=model_cfg.parameters.get("quantization", "1.0"),
                prompt_version=self.prompt_config.get("version", "1.0.0"),
                snapshot_id=snapshot.snapshot_id,
                decision_timestamp=snapshot.decision_timestamp,
                symbol=snapshot.symbol,
                action=LLMAction(parsed_data["action"].upper()),
                confidence=float(parsed_data["confidence"]),
                entry_rationale=parsed_data.get("entry_rationale", ""),
                proposed_stop_loss=parsed_data.get("proposed_stop_loss"),
                proposed_target=parsed_data.get("proposed_target"),
                holding_intent=parsed_data.get("holding_intent", "INTRADAY"),
                reasoning_summary=parsed_data.get("reasoning_summary", ""),
                validation_status=ValidationStatus.VALID,
                metrics=metrics,
                raw_response=raw_response,
                created_at=end_ts
            )

        finally:
            # 4. Explicit Unload (Always executed in finally block)
            try:
                unload_time_ms = self.provider.unload_model(tag)
                redis_service.publish_event(
                    RedisStreamName.DECISIONS,
                    "MODEL_UNLOAD",
                    {"model_id": model_cfg.id, "tag": tag, "unload_time_ms": unload_time_ms}
                )
            except Exception:
                pass

    def _create_error_decision(
        self,
        decision_id: str,
        model_cfg: ModelConfig,
        snapshot: MarketSnapshot,
        status: ValidationStatus,
        reason: str,
        latency_ms: float,
        load_time_ms: float
    ) -> LLMDecisionRecord:
        now = datetime.now(timezone.utc)
        metrics = InferenceMetrics(
            model_id=model_cfg.id,
            snapshot_id=snapshot.snapshot_id,
            start_time=now,
            end_time=now,
            inference_latency_ms=latency_ms,
            model_load_time_ms=load_time_ms,
            success=False
        )
        return LLMDecisionRecord(
            decision_id=decision_id,
            model_id=model_cfg.id,
            model_version=model_cfg.parameters.get("quantization", "1.0"),
            prompt_version=self.prompt_config.get("version", "1.0.0"),
            snapshot_id=snapshot.snapshot_id,
            decision_timestamp=snapshot.decision_timestamp,
            symbol=snapshot.symbol,
            action=LLMAction.NO_ACTION,
            confidence=0.0,
            entry_rationale="Execution failed or timed out",
            holding_intent="INTRADAY",
            reasoning_summary=f"Error: {reason}",
            validation_status=status,
            rejection_reason=reason,
            metrics=metrics,
            created_at=now
        )

    def _build_prompt_payload(self, snapshot: MarketSnapshot) -> str:
        data: Dict[str, Any] = {
            "snapshot_id": snapshot.snapshot_id,
            "decision_timestamp": snapshot.decision_timestamp.isoformat(),
            "symbol": snapshot.symbol,
            "exchange": snapshot.exchange,
            "timeframe": snapshot.timeframe.value,
        }
        if snapshot.candle:
            data["market_data"] = {
                "open": snapshot.candle.open,
                "high": snapshot.candle.high,
                "low": snapshot.candle.low,
                "close": snapshot.candle.close,
                "volume": snapshot.candle.volume,
                "available_at": snapshot.candle.available_at.isoformat()
            }
        if snapshot.features:
            data["features"] = {
                "sma_20": snapshot.features.sma_20,
                "sma_50": snapshot.features.sma_50,
                "rsi_14": snapshot.features.rsi_14,
                "vwap": snapshot.features.vwap,
                "relative_volume_20": snapshot.features.relative_volume_20,
                "trend": snapshot.features.trend.value,
                "volatility_20": snapshot.features.volatility_20,
                "distance_from_session_high": snapshot.features.distance_from_session_high
            }
        if snapshot.candidate:
            data["opportunity_scanner"] = {
                "opportunity_score": snapshot.candidate.opportunity_score,
                "score_components": snapshot.candidate.score_components,
            }
        if snapshot.information_context:
            data["external_information"] = [
                {
                    "title": d.title,
                    "summary": d.summary,
                    "publisher": d.publisher,
                    "published_at": d.published_at.isoformat(),
                    "available_at": d.available_at.isoformat(),
                    "authority": d.authority.name,
                    "relevance": d.relevance.value,
                }
                for d in snapshot.information_context.relevant_information
            ]
        return json.dumps(data, indent=2)
