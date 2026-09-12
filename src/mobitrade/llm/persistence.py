import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from mobitrade.domain.llm_models import LLMDecisionRecord, ModelEvaluationRun

class LLMDatabaseRepository:
    """
    SQLite persistence for LLM model runs, decisions, and hardware inference metrics.
    Database: D:\\Trading LLM\\MobiTradeAI\\database\\mobitrade.db
    """
    def __init__(self, db_path: str = "/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    model_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    runtime_model_name TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_runs (
                    run_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    decision_timestamp TEXT NOT NULL,
                    total_cycle_time_ms REAL NOT NULL,
                    evaluated_count INTEGER NOT NULL,
                    success_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_decisions (
                    decision_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    decision_timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    entry_rationale TEXT NOT NULL,
                    proposed_stop_loss REAL,
                    proposed_target REAL,
                    holding_intent TEXT NOT NULL,
                    reasoning_summary TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    rejection_reason TEXT,
                    inference_latency_ms REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES model_runs(run_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inference_metrics (
                    metric_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    load_time_ms REAL,
                    unload_time_ms REAL,
                    tokens_prompt INTEGER,
                    tokens_generated INTEGER,
                    ram_usage_mb REAL,
                    vram_usage_mb REAL,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(decision_id) REFERENCES llm_decisions(decision_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_run ON llm_decisions(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_model ON llm_decisions(model_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_snap ON llm_decisions(snapshot_id)")
            conn.commit()

    def save_evaluation_run(
        self,
        run: ModelEvaluationRun,
        decisions: List[LLMDecisionRecord]
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO model_runs (
                    run_id, snapshot_id, decision_timestamp, total_cycle_time_ms,
                    evaluated_count, success_count, failed_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.snapshot_id,
                run.decision_timestamp.isoformat(),
                run.total_cycle_time_ms,
                len(run.evaluated_models),
                len(run.successful_decisions),
                len(run.failed_models),
                now_str
            ))

            for d in decisions:
                cursor.execute("""
                    INSERT OR REPLACE INTO llm_decisions (
                        decision_id, run_id, model_id, model_version, prompt_version,
                        snapshot_id, decision_timestamp, symbol, action, confidence,
                        entry_rationale, proposed_stop_loss, proposed_target,
                        holding_intent, reasoning_summary, validation_status,
                        rejection_reason, inference_latency_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d.decision_id,
                    run.run_id,
                    d.model_id,
                    d.model_version,
                    d.prompt_version,
                    d.snapshot_id,
                    d.decision_timestamp.isoformat(),
                    d.symbol,
                    d.action.value,
                    d.confidence,
                    d.entry_rationale,
                    d.proposed_stop_loss,
                    d.proposed_target,
                    d.holding_intent,
                    d.reasoning_summary,
                    d.validation_status.value,
                    d.rejection_reason,
                    d.metrics.inference_latency_ms if d.metrics else 0.0,
                    now_str
                ))

                if d.metrics:
                    m = d.metrics
                    metric_id = f"met_{d.decision_id}"
                    cursor.execute("""
                        INSERT OR REPLACE INTO inference_metrics (
                            metric_id, decision_id, model_id, snapshot_id, latency_ms,
                            load_time_ms, unload_time_ms, tokens_prompt, tokens_generated,
                            ram_usage_mb, vram_usage_mb, success, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric_id,
                        d.decision_id,
                        m.model_id,
                        m.snapshot_id,
                        m.inference_latency_ms,
                        m.model_load_time_ms,
                        m.model_unload_time_ms,
                        m.tokens_prompt,
                        m.tokens_generated,
                        m.ram_usage_mb,
                        m.vram_usage_mb,
                        1 if m.success else 0,
                        now_str
                    ))
            conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            cursor.execute("SELECT * FROM llm_decisions WHERE run_id = ?", (run_id,))
            res["decisions"] = [dict(r) for r in cursor.fetchall()]
            return res
