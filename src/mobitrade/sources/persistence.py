import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from mobitrade.domain.information_models import (
    ExternalInformation,
    InformationContext,
    SourceType,
    SourceAuthority,
    InformationCategory,
    RelevanceLevel,
)

class InformationRepository:
    """
    SQLite persistence and local filesystem caching for external financial documents and contexts.
    Database: D:\\Trading LLM\\MobiTradeAI\\database\\mobitrade.db
    Cache:    D:\\Trading LLM\\MobiTradeAI\\data\\raw\\external\\
              D:\\Trading LLM\\MobiTradeAI\\data\\processed\\external\\
              D:\\Trading LLM\\MobiTradeAI\\data\\metadata\\external\\
    """
    def __init__(
        self,
        db_path: str = "database/mobitrade.db",
        base_cache_dir: str = "data"
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.cache_raw = Path(base_cache_dir) / "raw" / "external"
        self.cache_processed = Path(base_cache_dir) / "processed" / "external"
        self.cache_metadata = Path(base_cache_dir) / "metadata" / "external"

        self.cache_raw.mkdir(parents=True, exist_ok=True)
        self.cache_processed.mkdir(parents=True, exist_ok=True)
        self.cache_metadata.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS external_information (
                    information_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    symbol TEXT,
                    published_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    authority INTEGER NOT NULL,
                    relevance TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    provider_version TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS information_contexts (
                    context_id TEXT PRIMARY KEY,
                    decision_timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source_count INTEGER NOT NULL,
                    high_authority_count INTEGER NOT NULL,
                    latest_available_time TEXT,
                    context_version TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_items (
                    context_id TEXT NOT NULL,
                    information_id TEXT NOT NULL,
                    relevance TEXT NOT NULL,
                    PRIMARY KEY (context_id, information_id),
                    FOREIGN KEY (context_id) REFERENCES information_contexts(context_id),
                    FOREIGN KEY (information_id) REFERENCES external_information(information_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_info_avail ON external_information(available_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_info_sym ON external_information(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_info_hash ON external_information(content_hash)")
            conn.commit()

    def save_documents(self, documents: List[ExternalInformation]) -> None:
        if not documents:
            return
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for d in documents:
                cursor.execute("""
                    INSERT OR REPLACE INTO external_information (
                        information_id, source, source_type, publisher,
                        title, url, symbol, published_at, available_at,
                        retrieved_at, summary, authority, relevance,
                        category, content_hash, provider_version,
                        metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d.information_id, d.source, d.source_type.value, d.publisher,
                    d.title, d.url, d.symbol, d.published_at.isoformat(),
                    d.available_at.isoformat(), d.retrieved_at.isoformat(),
                    d.summary, int(d.authority.value), d.relevance.value,
                    d.category.value, d.content_hash, d.provider_version,
                    json.dumps(d.metadata), now_str
                ))

                # Local file cache
                cache_file = self.cache_processed / f"{d.information_id}.json"
                if not cache_file.exists():
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(d.model_dump_json(indent=2))
            conn.commit()

    def save_context(self, context: InformationContext) -> str:
        context_id = f"ctx_{context.symbol}_{context.decision_timestamp.strftime('%Y%m%d_%H%M%S')}_{context.context_version}"
        now_str = datetime.now(timezone.utc).isoformat()
        dt_str = context.decision_timestamp.isoformat()
        latest_avail = context.latest_available_information_time.isoformat() if context.latest_available_information_time else None

        # Ensure all constituent documents are saved first
        self.save_documents(context.relevant_information)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO information_contexts (
                    context_id, decision_timestamp, symbol, source_count,
                    high_authority_count, latest_available_time,
                    context_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                context_id, dt_str, context.symbol, context.source_count,
                context.high_authority_count, latest_avail,
                context.context_version, now_str
            ))

            for d in context.relevant_information:
                cursor.execute("""
                    INSERT OR REPLACE INTO context_items (
                        context_id, information_id, relevance
                    ) VALUES (?, ?, ?)
                """, (context_id, d.information_id, d.relevance.value))
            conn.commit()

        # Cache context JSON
        meta_file = self.cache_metadata / f"{context_id}.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(context.model_dump_json(indent=2))

        return context_id

    def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM information_contexts WHERE context_id = ?", (context_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            cursor.execute("""
                SELECT ei.* FROM external_information ei
                JOIN context_items ci ON ei.information_id = ci.information_id
                WHERE ci.context_id = ?
            """, (context_id,))
            res["items"] = [dict(r) for r in cursor.fetchall()]
            return res
