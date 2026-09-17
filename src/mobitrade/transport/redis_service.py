"""
Redis Fast Event & Execution Pipeline Service (Phase 13).
High-speed in-memory transport and event bus between market data, opportunity scanner,
sequential LLM scheduler, RiskEngine, paper broker, and the monitoring dashboard.
SQLite remains the permanent authoritative storage layer.
"""

import os
import json
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from collections import deque

logger = logging.getLogger("mobitrade.transport.redis")


class RedisStreamName:
    MARKET = "autotrade:market"
    SIGNALS = "autotrade:signals"
    DECISIONS = "autotrade:decisions"
    TRADES = "autotrade:trades"
    ACTIVITY = "autotrade:activity"

    ALL_STREAMS = [MARKET, SIGNALS, DECISIONS, TRADES, ACTIVITY]


class ConsumerGroupName:
    DASHBOARD = "dashboard"
    ANALYTICS = "analytics"
    LEARNING = "learning"

    ALL_GROUPS = [DASHBOARD, ANALYTICS, LEARNING]


class RedisPipelineService:
    """
    High-performance Redis Streams transport, Pub/Sub, and caching service.
    Designed with strict zero-downtime degradation: if Redis is unavailable,
    execution transparently continues using bounded in-process queues.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self._client: Optional[Any] = None
        self._connected: bool = False
        self._fallback_events: deque = deque(maxlen=200)
        self._in_memory_dedup: set = set()
        self._in_memory_cache: Dict[str, Tuple[Any, float]] = {}
        self._init_connection()

    def _init_connection(self) -> bool:
        """Initialize Redis connection client with short timeouts."""
        try:
            import redis
            self._client = redis.Redis.from_url(
                self.redis_url,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                decode_responses=True,
            )
            # Test ping
            self._client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
            self._ensure_streams_and_groups()
            return True
        except Exception as e:
            self._connected = False
            logger.warning(
                f"[RedisPipelineService] Redis connection to {self.redis_url} failed: {e}. "
                "Operating in in-process degraded fallback mode."
            )
            return False

    def is_connected(self) -> bool:
        """Check if Redis connection is live."""
        if not self._client:
            return self._init_connection()
        try:
            self._client.ping()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def _ensure_streams_and_groups(self) -> None:
        """Ensure default streams and consumer groups exist."""
        if not self._connected or not self._client:
            return
        for stream in RedisStreamName.ALL_STREAMS:
            for group in ConsumerGroupName.ALL_GROUPS:
                try:
                    self._client.xgroup_create(stream, group, id="0", mkstream=True)
                except Exception:
                    # BusyGroupError: Group already exists
                    pass

    # ==========================================
    # STREAM PUBLISHING & EVENTS
    # ==========================================

    def publish_event(
        self,
        stream: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> str:
        """
        Publish a structured, idempotent event into a Redis stream.
        Also broadcasts to Pub/Sub for immediate live dashboard notifications.
        """
        evt_id = event_id or f"evt_{uuid.uuid4().hex[:12]}"
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        record = {
            "event_id": evt_id,
            "event_type": event_type,
            "timestamp": now_iso,
            "data": json.dumps(payload),
        }

        # Fallback in-process storage
        self._fallback_events.append({
            "stream": stream,
            "event_id": evt_id,
            "event_type": event_type,
            "timestamp": now_dt.strftime("%H:%M:%S"),
            "payload": payload,
        })

        if not self.is_connected() or not self._client:
            return evt_id

        try:
            # XADD to stream
            stream_msg_id = self._client.xadd(stream, record, maxlen=1000, approximate=True)

            # Broadcast to transient dashboard Pub/Sub channel
            pubsub_channel = f"autotrade:pubsub:{stream.split(':')[-1]}"
            self._client.publish(
                pubsub_channel,
                json.dumps({
                    "stream": stream,
                    "event_id": evt_id,
                    "event_type": event_type,
                    "timestamp": now_iso,
                    "payload": payload,
                }),
            )
            return evt_id
        except Exception as e:
            logger.warning(f"Error publishing event {evt_id} to stream {stream}: {e}")
            return evt_id

    def publish(
        self,
        stream: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> str:
        """
        Convenience wrapper to publish a dictionary payload to a Redis stream.
        Extracts event_type from payload if not explicitly provided.
        """
        evt_type = event_type or payload.get("event_type") or payload.get("action") or "EVENT"
        return self.publish_event(stream=stream, event_type=evt_type, payload=payload, event_id=event_id)

    # ==========================================
    # IDEMPOTENCY & DEDUPLICATION
    # ==========================================

    def is_duplicate(self, event_id: str, ttl_seconds: int = 86400) -> bool:
        """
        Safely check if an order/trade event was already processed.
        Returns True if duplicate, False if unique and marks it processed.
        """
        if not event_id:
            return False

        if self.is_connected() and self._client:
            try:
                key = f"autotrade:dedup:{event_id}"
                # SET key 1 NX EX ttl
                is_new = self._client.set(key, "1", nx=True, ex=ttl_seconds)
                return not is_new
            except Exception as e:
                logger.warning(f"Redis dedup error for {event_id}: {e}")

        # Fallback: in-memory deduplication set
        if event_id in self._in_memory_dedup:
            return True
        self._in_memory_dedup.add(event_id)
        if len(self._in_memory_dedup) > 10000:
            self._in_memory_dedup.clear()
        return False

    # ==========================================
    # CONSUMER GROUPS & READING
    # ==========================================

    def read_stream(
        self,
        stream: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 0,
    ) -> List[Dict[str, Any]]:
        """Read pending or new messages using consumer groups."""
        if not self.is_connected() or not self._client:
            # Return from in-process fallback
            return [e for e in list(self._fallback_events) if e.get("stream") == stream][:count]

        try:
            # XREADGROUP
            res = self._client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream: ">"},
                count=count,
                block=block_ms,
            )
            parsed_messages = []
            for stream_entry, messages in res:
                for msg_id, data in messages:
                    payload = json.loads(data.get("data", "{}")) if "data" in data else {}
                    parsed_messages.append({
                        "msg_id": msg_id,
                        "event_id": data.get("event_id"),
                        "event_type": data.get("event_type"),
                        "timestamp": data.get("timestamp"),
                        "payload": payload,
                    })
            return parsed_messages
        except Exception as e:
            logger.warning(f"Error reading stream {stream} group {group_name}: {e}")
            return []

    def ack_event(self, stream: str, group_name: str, msg_id: str) -> bool:
        """Acknowledge processed message in consumer group."""
        if not self.is_connected() or not self._client:
            return True
        try:
            return bool(self._client.xack(stream, group_name, msg_id))
        except Exception:
            return False

    def get_recent_events(self, stream: str = RedisStreamName.ACTIVITY, count: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent events directly from stream for dashboard."""
        if not self.is_connected() or not self._client:
            return [
                {
                    "timestamp": e["timestamp"],
                    "event_id": e["event_id"],
                    "event_type": e["event_type"],
                    "payload": e["payload"],
                }
                for e in reversed(list(self._fallback_events))
                if e.get("stream") == stream or stream == RedisStreamName.ACTIVITY
            ][:count]

        try:
            # XREVRANGE
            records = self._client.xrevrange(stream, max="+", min="-", count=count)
            items = []
            for msg_id, fields in records:
                payload = json.loads(fields.get("data", "{}")) if "data" in fields else {}
                items.append({
                    "msg_id": msg_id,
                    "event_id": fields.get("event_id"),
                    "event_type": fields.get("event_type"),
                    "timestamp": fields.get("timestamp"),
                    "payload": payload,
                })
            return items
        except Exception as e:
            logger.warning(f"Error fetching recent events from {stream}: {e}")
            return []

    # ==========================================
    # HIGH-SPEED IN-MEMORY CACHING
    # ==========================================

    def set_cache(self, key: str, value: Any, ttl_seconds: int = 10) -> bool:
        """Set short-lived cache entry with TTL."""
        val_str = json.dumps(value)
        if self.is_connected() and self._client:
            try:
                self._client.set(key, val_str, ex=ttl_seconds)
                return True
            except Exception as e:
                logger.warning(f"Cache set error for {key}: {e}")

        # In-memory fallback
        self._in_memory_cache[key] = (value, time.time() + ttl_seconds)
        return True

    def get_cache(self, key: str) -> Optional[Any]:
        """Get short-lived cache entry."""
        if self.is_connected() and self._client:
            try:
                raw = self._client.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"Cache get error for {key}: {e}")

        # In-memory fallback
        if key in self._in_memory_cache:
            val, expire_at = self._in_memory_cache[key]
            if time.time() < expire_at:
                return val
            else:
                del self._in_memory_cache[key]
        return None

    # ==========================================
    # OBSERVABILITY & STATUS
    # ==========================================

    def get_status(self) -> Dict[str, Any]:
        """Return overall health, connection state, and stream telemetry."""
        connected = self.is_connected()
        streams_info: Dict[str, Any] = {}

        if connected and self._client:
            for s in RedisStreamName.ALL_STREAMS:
                try:
                    info = self._client.xinfo_stream(s)
                    groups = self._client.xinfo_groups(s)
                    streams_info[s] = {
                        "length": info.get("length", 0),
                        "last_generated_id": info.get("last-generated-id", ""),
                        "groups_count": len(groups),
                        "groups": [g.get("name") for g in groups],
                    }
                except Exception:
                    streams_info[s] = {"length": 0, "status": "empty_or_uninitialized"}

        return {
            "status": "connected" if connected else "degraded_fallback",
            "connected": connected,
            "redis_url": self.redis_url.split("@")[-1],  # mask password if any
            "fallback_mode": not connected,
            "streams_count": len(RedisStreamName.ALL_STREAMS),
            "consumer_groups": ConsumerGroupName.ALL_GROUPS,
            "streams": streams_info,
            "fallback_buffered_events": len(self._fallback_events),
        }

    def get_stream_status(self) -> Dict[str, Any]:
        """Detailed status of all event streams and consumer groups."""
        return self.get_status()


# Global Singleton
redis_service = RedisPipelineService()
