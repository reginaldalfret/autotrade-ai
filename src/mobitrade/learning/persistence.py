"""
SQLite Persistence Layer for AutoTrade AI Self-Learning Engine.
Manages observations, model performance profiles, versioned strategy configurations, and validation records.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any

from mobitrade.learning.models import (
    LearningObservation,
    ModelPerformanceProfile,
    StrategyConfig,
    CandidateStatus,
    WeaknessType,
    ValidationReport,
)


class LearningDatabaseRepository:
    """
    Persistence manager for self-learning memory, candidate strategies, and validation history.
    """

    def __init__(self, db_path: str = "database/mobitrade.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_learning_tables()
        self._ensure_baseline_strategy()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_learning_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_observations (
                    observation_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    weakness_type TEXT NOT NULL,
                    model_id TEXT,
                    description TEXT NOT NULL,
                    sample_size INTEGER NOT NULL,
                    supporting_trades TEXT NOT NULL,
                    metrics_impact TEXT NOT NULL,
                    remedy TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_versions (
                    version_id TEXT PRIMARY KEY,
                    parent_version_id TEXT,
                    created_at TEXT NOT NULL,
                    min_confidence_threshold REAL NOT NULL,
                    allowed_models TEXT NOT NULL,
                    model_confidence_thresholds TEXT NOT NULL,
                    allowed_windows TEXT NOT NULL,
                    max_trades INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    supporting_observations TEXT,
                    sample_size INTEGER NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_performance_profiles (
                    model_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    total_trades INTEGER NOT NULL,
                    winning_trades INTEGER NOT NULL,
                    losing_trades INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    average_win REAL NOT NULL,
                    average_loss REAL NOT NULL,
                    profit_factor REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    confidence_calibration TEXT NOT NULL,
                    time_of_day_performance TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validation_reports (
                    candidate_version_id TEXT NOT NULL,
                    baseline_version_id TEXT NOT NULL,
                    sample_size INTEGER NOT NULL,
                    is_validated INTEGER NOT NULL,
                    rejection_reasons TEXT NOT NULL,
                    baseline_metrics TEXT NOT NULL,
                    candidate_metrics TEXT NOT NULL,
                    overfitting_passed INTEGER NOT NULL,
                    evaluation_timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def _ensure_baseline_strategy(self) -> None:
        """Ensure baseline strategy_v1 exists and is ACTIVE if no active version exists."""
        active = self.get_active_strategy()
        if not active:
            baseline = StrategyConfig(
                version_id="strategy_v1",
                parent_version_id=None,
                status=CandidateStatus.ACTIVE,
                reason="Default baseline trading configuration",
                min_confidence_threshold=0.50,
                allowed_models=[
                    "nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"
                ],
                sample_size=0,
            )
            self.save_strategy(baseline)

    def save_observation(self, obs: LearningObservation) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO learning_observations (
                    observation_id, created_at, weakness_type, model_id,
                    description, sample_size, supporting_trades, metrics_impact, remedy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                obs.observation_id,
                obs.created_at,
                obs.weakness_type.value,
                obs.model_id,
                obs.description,
                obs.sample_size,
                json.dumps(obs.supporting_trade_ids),
                json.dumps(obs.metrics_impact),
                obs.recommended_remedy,
            ))
            conn.commit()

    def list_observations(self, limit: int = 50) -> List[LearningObservation]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM learning_observations ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                LearningObservation(
                    observation_id=r["observation_id"],
                    created_at=r["created_at"],
                    weakness_type=WeaknessType(r["weakness_type"]),
                    model_id=r["model_id"],
                    description=r["description"],
                    sample_size=r["sample_size"],
                    supporting_trade_ids=json.loads(r["supporting_trades"]),
                    metrics_impact=json.loads(r["metrics_impact"]),
                    recommended_remedy=r["remedy"],
                )
                for r in rows
            ]

    def save_strategy(self, config: StrategyConfig) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO strategy_versions (
                    version_id, parent_version_id, created_at, min_confidence_threshold,
                    allowed_models, model_confidence_thresholds, allowed_windows,
                    max_trades, status, reason, supporting_observations, sample_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config.version_id,
                config.parent_version_id,
                config.created_at,
                config.min_confidence_threshold,
                json.dumps(config.allowed_models),
                json.dumps(config.model_confidence_thresholds),
                json.dumps(config.allowed_trading_windows),
                config.max_trades_per_model,
                config.status.value,
                config.reason,
                json.dumps(config.supporting_observations),
                config.sample_size,
            ))
            conn.commit()

    def get_strategy(self, version_id: str) -> Optional[StrategyConfig]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM strategy_versions WHERE version_id = ?", (version_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return StrategyConfig(
                version_id=r["version_id"],
                parent_version_id=r["parent_version_id"],
                created_at=r["created_at"],
                min_confidence_threshold=r["min_confidence_threshold"],
                allowed_models=json.loads(r["allowed_models"]),
                model_confidence_thresholds=json.loads(r["model_confidence_thresholds"]),
                allowed_trading_windows=json.loads(r["allowed_windows"]),
                max_trades_per_model=r["max_trades"],
                status=CandidateStatus(r["status"]),
                reason=r["reason"] or "",
                supporting_observations=json.loads(r["supporting_observations"] or "[]"),
                sample_size=r["sample_size"],
            )

    def get_active_strategy(self) -> Optional[StrategyConfig]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM strategy_versions WHERE status = 'ACTIVE' LIMIT 1")
            r = cursor.fetchone()
            if not r:
                return None
            return StrategyConfig(
                version_id=r["version_id"],
                parent_version_id=r["parent_version_id"],
                created_at=r["created_at"],
                min_confidence_threshold=r["min_confidence_threshold"],
                allowed_models=json.loads(r["allowed_models"]),
                model_confidence_thresholds=json.loads(r["model_confidence_thresholds"]),
                allowed_trading_windows=json.loads(r["allowed_windows"]),
                max_trades_per_model=r["max_trades"],
                status=CandidateStatus.ACTIVE,
                reason=r["reason"] or "",
                supporting_observations=json.loads(r["supporting_observations"] or "[]"),
                sample_size=r["sample_size"],
            )

    def set_active_strategy(self, version_id: str) -> StrategyConfig:
        """
        Promote a VALIDATED strategy to ACTIVE. Ensures exactly one ACTIVE version.
        Rejects activating non-validated or rejected strategies.
        """
        strat = self.get_strategy(version_id)
        if not strat:
            raise ValueError(f"Strategy version {version_id} does not exist.")
        if strat.status not in (CandidateStatus.VALIDATED, CandidateStatus.ACTIVE):
            raise ValueError(f"Cannot activate strategy {version_id} with status {strat.status.value}. Must be VALIDATED.")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Demote any currently ACTIVE version to VALIDATED
            cursor.execute("UPDATE strategy_versions SET status = 'VALIDATED' WHERE status = 'ACTIVE'")
            cursor.execute("UPDATE strategy_versions SET status = 'ACTIVE' WHERE version_id = ?", (version_id,))
            conn.commit()

        strat.status = CandidateStatus.ACTIVE
        return strat

    def list_strategies(self) -> List[StrategyConfig]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM strategy_versions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [
                StrategyConfig(
                    version_id=r["version_id"],
                    parent_version_id=r["parent_version_id"],
                    created_at=r["created_at"],
                    min_confidence_threshold=r["min_confidence_threshold"],
                    allowed_models=json.loads(r["allowed_models"]),
                    model_confidence_thresholds=json.loads(r["model_confidence_thresholds"]),
                    allowed_trading_windows=json.loads(r["allowed_windows"]),
                    max_trades_per_model=r["max_trades"],
                    status=CandidateStatus(r["status"]),
                    reason=r["reason"] or "",
                    supporting_observations=json.loads(r["supporting_observations"] or "[]"),
                    sample_size=r["sample_size"],
                )
                for r in rows
            ]

    def save_model_profile(self, profile: ModelPerformanceProfile) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO model_performance_profiles (
                    model_id, version, total_trades, winning_trades, losing_trades,
                    win_rate, net_pnl, average_win, average_loss, profit_factor,
                    max_drawdown, confidence_calibration, time_of_day_performance, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.model_id,
                profile.version,
                profile.total_trades,
                profile.winning_trades,
                profile.losing_trades,
                profile.win_rate,
                profile.net_pnl,
                profile.average_win,
                profile.average_loss,
                profile.profit_factor,
                profile.max_drawdown,
                json.dumps(profile.confidence_calibration),
                json.dumps(profile.time_of_day_performance),
                profile.last_updated,
            ))
            conn.commit()

    def get_model_profile(self, model_id: str) -> Optional[ModelPerformanceProfile]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_performance_profiles WHERE model_id = ?", (model_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return ModelPerformanceProfile(
                model_id=r["model_id"],
                version=r["version"],
                total_trades=r["total_trades"],
                winning_trades=r["winning_trades"],
                losing_trades=r["losing_trades"],
                win_rate=r["win_rate"],
                net_pnl=r["net_pnl"],
                average_win=r["average_win"],
                average_loss=r["average_loss"],
                profit_factor=r["profit_factor"],
                max_drawdown=r["max_drawdown"],
                confidence_calibration=json.loads(r["confidence_calibration"]),
                time_of_day_performance=json.loads(r["time_of_day_performance"]),
                last_updated=r["last_updated"],
            )

    def list_model_profiles(self) -> List[ModelPerformanceProfile]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_performance_profiles ORDER BY net_pnl DESC")
            rows = cursor.fetchall()
            return [
                ModelPerformanceProfile(
                    model_id=r["model_id"],
                    version=r["version"],
                    total_trades=r["total_trades"],
                    winning_trades=r["winning_trades"],
                    losing_trades=r["losing_trades"],
                    win_rate=r["win_rate"],
                    net_pnl=r["net_pnl"],
                    average_win=r["average_win"],
                    average_loss=r["average_loss"],
                    profit_factor=r["profit_factor"],
                    max_drawdown=r["max_drawdown"],
                    confidence_calibration=json.loads(r["confidence_calibration"]),
                    time_of_day_performance=json.loads(r["time_of_day_performance"]),
                    last_updated=r["last_updated"],
                )
                for r in rows
            ]

    def save_validation_report(self, report: ValidationReport) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO validation_reports (
                    candidate_version_id, baseline_version_id, sample_size,
                    is_validated, rejection_reasons, baseline_metrics, candidate_metrics,
                    overfitting_passed, evaluation_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.candidate_version_id,
                report.baseline_version_id,
                report.sample_size,
                1 if report.is_validated else 0,
                json.dumps(report.rejection_reasons),
                json.dumps(report.baseline_metrics),
                json.dumps(report.candidate_metrics),
                1 if report.overfitting_check_passed else 0,
                report.evaluation_timestamp,
            ))
            conn.commit()

    def list_validation_reports(self, limit: int = 50) -> List[ValidationReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM validation_reports ORDER BY evaluation_timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [
                ValidationReport(
                    candidate_version_id=r["candidate_version_id"],
                    baseline_version_id=r["baseline_version_id"],
                    sample_size=r["sample_size"],
                    is_validated=bool(r["is_validated"]),
                    rejection_reasons=json.loads(r["rejection_reasons"]),
                    baseline_metrics=json.loads(r["baseline_metrics"]),
                    candidate_metrics=json.loads(r["candidate_metrics"]),
                    overfitting_check_passed=bool(r["overfitting_passed"]),
                    evaluation_timestamp=r["evaluation_timestamp"],
                )
                for r in rows
            ]
