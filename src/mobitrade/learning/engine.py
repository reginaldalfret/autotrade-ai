"""
AutoTrade AI Self-Learning & Continuous Improvement Engine (Phase 11).
Orchestrates trade error analysis, profile generation, candidate improvements,
deterministic backtest evaluation, versioned strategies, and cryptographic audit tracking.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from mobitrade.learning.models import (
    StrategyConfig,
    CandidateStatus,
    LearningObservation,
    ModelPerformanceProfile,
    ValidationReport,
)
from mobitrade.learning.persistence import LearningDatabaseRepository
from mobitrade.learning.analysis import TradeAnalysisEngine
from mobitrade.learning.generator import CandidateGenerator
from mobitrade.learning.evaluator import CandidateEvaluator
from mobitrade.logging.audit import AuditLogger, AuditEventType
from mobitrade.transport.redis_service import redis_service, RedisStreamName


class SelfLearningEngine:
    """
    Central self-learning controller.
    Analyzes historical paper sessions, discovers patterns, generates candidate improvements,
    deterministically validates them, and maintains versioned strategy configurations.
    Never violates hard RiskEngine constraints.
    """

    def __init__(self, db_path: str = "database/mobitrade.db"):
        self.db_path = db_path
        self.repo = LearningDatabaseRepository(db_path=db_path)
        self.analysis_engine = TradeAnalysisEngine(db_path=db_path)
        self.candidate_generator = CandidateGenerator()
        self.evaluator = CandidateEvaluator(db_path=db_path)
        self.audit_logger = AuditLogger(db_path=db_path)

    def run_learning_cycle(
        self,
        auto_activate_best: bool = False,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute one single, controlled learning cycle.
        Autonomous background execution is strictly prohibited.
        """
        now_str = datetime.now().isoformat()
        sess_id = session_id or f"learn_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_strat = self.repo.get_active_strategy()
        if not active_strat:
            self.repo._ensure_baseline_strategy()
            active_strat = self.repo.get_active_strategy()

        redis_service.publish(
            RedisStreamName.ACTIVITY,
            {
                "event_type": "LEARNING_STARTED",
                "session_id": sess_id,
                "active_strategy": active_strat.version_id,
                "timestamp": now_str,
            },
            event_id=f"learn_start_{sess_id}",
        )

        # Step 1: Update model performance profiles
        profiles = self.analysis_engine.build_model_profiles()
        for p in profiles:
            self.repo.save_model_profile(p)

        # Step 2: Trade Error Analysis & Pattern Discovery
        observations = self.analysis_engine.analyze_session_weaknesses(session_id=session_id)
        for obs in observations:
            self.repo.save_observation(obs)
            self.audit_logger.record_event(
                session_id=sess_id,
                event_type=AuditEventType.LEARNING_OBSERVATION_CREATED,
                payload={
                    "observation_id": obs.observation_id,
                    "weakness_type": obs.weakness_type.value,
                    "sample_size": obs.sample_size,
                    "model_id": obs.model_id,
                },
            )
            redis_service.publish(
                RedisStreamName.ACTIVITY,
                {
                    "event_type": "OBSERVATION_CREATED",
                    "observation_id": obs.observation_id,
                    "weakness_type": obs.weakness_type.value,
                    "sample_size": obs.sample_size,
                    "model_id": obs.model_id,
                    "session_id": sess_id,
                },
                event_id=f"obs_{obs.observation_id}",
            )

        # Step 3: Candidate Improvement Generation
        candidates = self.candidate_generator.generate_candidates(active_strat, observations)
        for cand in candidates:
            self.repo.save_strategy(cand)
            self.audit_logger.record_event(
                session_id=sess_id,
                event_type=AuditEventType.STRATEGY_CANDIDATE_CREATED,
                payload={
                    "candidate_version_id": cand.version_id,
                    "parent_version_id": cand.parent_version_id,
                    "reason": cand.reason,
                    "sample_size": cand.sample_size,
                },
            )
            redis_service.publish(
                RedisStreamName.ACTIVITY,
                {
                    "event_type": "CANDIDATE_CREATED",
                    "candidate_version_id": cand.version_id,
                    "parent_version_id": cand.parent_version_id,
                    "reason": cand.reason,
                    "session_id": sess_id,
                },
                event_id=f"cand_create_{cand.version_id}",
            )

        # Step 4: Replay Evaluation & Overfitting Validation
        validated_candidates: List[StrategyConfig] = []
        rejected_candidates: List[StrategyConfig] = []
        reports: List[ValidationReport] = []

        for cand in candidates:
            cand.status = CandidateStatus.TESTING
            self.repo.save_strategy(cand)
            redis_service.publish(
                RedisStreamName.ACTIVITY,
                {
                    "event_type": "CANDIDATE_TESTED",
                    "candidate_version_id": cand.version_id,
                    "status": "TESTING",
                    "session_id": sess_id,
                },
                event_id=f"cand_test_{cand.version_id}",
            )

            report = self.evaluator.evaluate(cand, active_strat)
            self.repo.save_validation_report(report)
            reports.append(report)

            if report.is_validated:
                cand.status = CandidateStatus.VALIDATED
                validated_candidates.append(cand)
                self.audit_logger.record_event(
                    session_id=sess_id,
                    event_type=AuditEventType.STRATEGY_CANDIDATE_VALIDATED,
                    payload={
                        "candidate_version_id": cand.version_id,
                        "candidate_net_pnl": report.candidate_metrics.get("net_pnl"),
                        "baseline_net_pnl": report.baseline_metrics.get("net_pnl"),
                    },
                )
                redis_service.publish(
                    RedisStreamName.ACTIVITY,
                    {
                        "event_type": "CANDIDATE_VALIDATED",
                        "candidate_version_id": cand.version_id,
                        "candidate_net_pnl": report.candidate_metrics.get("net_pnl"),
                        "baseline_net_pnl": report.baseline_metrics.get("net_pnl"),
                        "session_id": sess_id,
                    },
                    event_id=f"cand_val_{cand.version_id}",
                )
            else:
                cand.status = CandidateStatus.REJECTED
                rejected_candidates.append(cand)
                self.audit_logger.record_event(
                    session_id=sess_id,
                    event_type=AuditEventType.STRATEGY_CANDIDATE_REJECTED,
                    payload={
                        "candidate_version_id": cand.version_id,
                        "rejection_reasons": report.rejection_reasons,
                    },
                )
                redis_service.publish(
                    RedisStreamName.ACTIVITY,
                    {
                        "event_type": "CANDIDATE_REJECTED",
                        "candidate_version_id": cand.version_id,
                        "rejection_reasons": str(report.rejection_reasons),
                        "session_id": sess_id,
                    },
                    event_id=f"cand_rej_{cand.version_id}",
                )
            self.repo.save_strategy(cand)

        # Step 5: Optional promotion of best validated candidate
        promoted_version = None
        if auto_activate_best and validated_candidates:
            best_cand = max(
                validated_candidates,
                key=lambda c: next(
                    (r.candidate_metrics.get("net_pnl", 0.0) for r in reports if r.candidate_version_id == c.version_id),
                    0.0
                )
            )
            self.repo.set_active_strategy(best_cand.version_id)
            promoted_version = best_cand.version_id
            self.audit_logger.record_event(
                session_id=sess_id,
                event_type=AuditEventType.STRATEGY_ACTIVATED,
                payload={
                    "activated_version_id": best_cand.version_id,
                    "previous_active_version": active_strat.version_id,
                },
            )
            redis_service.publish(
                RedisStreamName.ACTIVITY,
                {
                    "event_type": "STRATEGY_ACTIVATED",
                    "activated_version_id": best_cand.version_id,
                    "previous_active_version": active_strat.version_id,
                    "session_id": sess_id,
                },
                event_id=f"strat_act_{best_cand.version_id}",
            )

        current_active = self.repo.get_active_strategy()

        return {
            "status": "completed",
            "timestamp": now_str,
            "observations_count": len(observations),
            "candidates_generated": len(candidates),
            "candidates_validated": len(validated_candidates),
            "candidates_rejected": len(rejected_candidates),
            "current_active_strategy": current_active.version_id if current_active else "strategy_v1",
            "promoted_strategy": promoted_version,
            "validation_reports": [r.model_dump() for r in reports],
        }

    def get_status(self) -> Dict[str, Any]:
        """Get summary status of self-learning engine."""
        active = self.repo.get_active_strategy()
        obs = self.repo.list_observations(limit=5)
        strats = self.repo.list_strategies()
        profiles = self.repo.list_model_profiles()

        return {
            "active_strategy_version": active.version_id if active else "strategy_v1",
            "total_strategy_versions": len(strats),
            "total_observations_recorded": len(self.repo.list_observations(limit=500)),
            "model_profiles_calibrated": len(profiles),
            "recent_observations": [o.model_dump() for o in obs],
        }
