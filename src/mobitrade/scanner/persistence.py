import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from mobitrade.domain.scanner_models import OpportunityCandidate

class ScannerDatabaseRepository:
    """
    SQLite persistence for Opportunity Scanner executions and candidate rankings.
    Database file: D:\\Trading LLM\\MobiTradeAI\\database\\mobitrade.db
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
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    decision_timestamp TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    scanner_version TEXT NOT NULL,
                    configuration_version TEXT NOT NULL,
                    universe_version TEXT NOT NULL,
                    total_universe INTEGER NOT NULL,
                    eligible_count INTEGER NOT NULL,
                    candidate_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    decision_timestamp TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    price REAL NOT NULL,
                    opportunity_score REAL NOT NULL,
                    score_components TEXT NOT NULL,
                    trend TEXT NOT NULL,
                    momentum REAL,
                    relative_volume REAL,
                    volatility REAL,
                    atr REAL,
                    vwap REAL,
                    is_eligible INTEGER NOT NULL,
                    rejection_reason TEXT,
                    scanner_version TEXT NOT NULL,
                    feature_version TEXT NOT NULL,
                    source_dataset_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(scan_id) REFERENCES scans(scan_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_dt ON scans(decision_timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_scan ON scan_candidates(scan_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_sym ON scan_candidates(symbol)")
            conn.commit()

    def save_scan_results(
        self,
        scan_id: str,
        decision_timestamp: datetime,
        timeframe: str,
        scanner_version: str,
        configuration_version: str,
        universe_version: str,
        candidates: List[OpportunityCandidate],
        total_universe: int,
        eligible_count: int
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        dt_str = decision_timestamp.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Upsert scan record
            cursor.execute("""
                INSERT OR REPLACE INTO scans (
                    scan_id, decision_timestamp, timeframe, scanner_version,
                    configuration_version, universe_version, total_universe,
                    eligible_count, candidate_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id, dt_str, timeframe, scanner_version,
                configuration_version, universe_version, total_universe,
                eligible_count, len(candidates), now_str
            ))

            # Insert candidates
            for c in candidates:
                cand_id = f"{scan_id}_{c.symbol}_{c.timeframe.value}"
                cursor.execute("""
                    INSERT OR REPLACE INTO scan_candidates (
                        candidate_id, scan_id, symbol, exchange,
                        decision_timestamp, timeframe, price,
                        opportunity_score, score_components, trend,
                        momentum, relative_volume, volatility, atr, vwap,
                        is_eligible, rejection_reason, scanner_version,
                        feature_version, source_dataset_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cand_id,
                    scan_id,
                    c.symbol,
                    c.exchange,
                    c.decision_timestamp.isoformat(),
                    c.timeframe.value,
                    c.price,
                    c.opportunity_score,
                    json.dumps(c.score_components),
                    c.trend.value,
                    c.momentum,
                    c.relative_volume,
                    c.volatility,
                    c.atr,
                    c.vwap,
                    1 if c.is_eligible else 0,
                    c.rejection_reason.value if c.rejection_reason else None,
                    c.scanner_version,
                    c.feature_version,
                    c.source_dataset_id,
                    now_str
                ))
            conn.commit()

    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_candidates(self, scan_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_candidates WHERE scan_id = ? ORDER BY opportunity_score DESC", (scan_id,))
            return [dict(r) for r in cursor.fetchall()]
