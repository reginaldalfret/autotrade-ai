"""
Unit Tests for Phase 13 Redis Fast Event and Execution Pipeline.
Verifies connection, stream creation, consumer groups, idempotency/deduplication,
in-memory fallback degradation, and API endpoints.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient
from mobitrade.transport.redis_service import (
    RedisPipelineService,
    RedisStreamName,
    ConsumerGroupName,
    redis_service,
)
from mobitrade.api.app import create_app


def test_redis_service_initialization():
    """Verify default streams and consumer groups are defined."""
    assert len(RedisStreamName.ALL_STREAMS) == 5
    assert RedisStreamName.MARKET in RedisStreamName.ALL_STREAMS
    assert RedisStreamName.SIGNALS in RedisStreamName.ALL_STREAMS
    assert RedisStreamName.DECISIONS in RedisStreamName.ALL_STREAMS
    assert RedisStreamName.TRADES in RedisStreamName.ALL_STREAMS
    assert RedisStreamName.ACTIVITY in RedisStreamName.ALL_STREAMS

    assert ConsumerGroupName.DASHBOARD in ConsumerGroupName.ALL_GROUPS
    assert ConsumerGroupName.ANALYTICS in ConsumerGroupName.ALL_GROUPS
    assert ConsumerGroupName.LEARNING in ConsumerGroupName.ALL_GROUPS


def test_redis_publish_and_deduplication():
    """Verify event publishing and idempotent deduplication."""
    import uuid
    # Test deduplication with unique event ID
    event_id = f"test_evt_{uuid.uuid4().hex[:8]}"
    # First check: should not be duplicate
    is_dup = redis_service.is_duplicate(event_id)
    assert is_dup is False

    # Second check: should be duplicate
    is_dup_second = redis_service.is_duplicate(event_id)
    assert is_dup_second is True

    # Publish an event
    msg_id = redis_service.publish(
        RedisStreamName.ACTIVITY,
        {"action": "TEST_EVENT", "status": "OK"},
        event_id="test_act_001"
    )
    assert msg_id is not None
    assert len(msg_id) > 0


def test_redis_caching():
    """Verify fast TTL caching functionality."""
    key = "autotrade:test_key"
    data = {"active_model": "nemotron", "phase": "INFERENCE"}
    ok = redis_service.set_cache(key, data, ttl_seconds=60)
    assert ok is True

    val = redis_service.get_cache(key)
    assert val == data


def test_redis_consumer_group_reading():
    """Verify consumer group reading or fallback reading."""
    event_id = "grp_test_999"
    redis_service.publish(
        RedisStreamName.DECISIONS,
        {"model_id": "nemotron", "action": "BUY", "symbol": "TATAMOTORS"},
        event_id=event_id
    )

    events = redis_service.read_stream(
        stream=RedisStreamName.DECISIONS,
        group_name=ConsumerGroupName.DASHBOARD,
        consumer_name="test_worker_1",
        count=5
    )
    assert isinstance(events, list)


def test_redis_fallback_mode():
    """Verify transparent fallback when connected to an invalid/down Redis instance."""
    # Create isolated service pointing to invalid port
    fallback_svc = RedisPipelineService(redis_url="redis://127.0.0.1:59999/0")
    assert fallback_svc.is_connected() is False

    # Publishing must not crash and must store in fallback buffer
    msg_id = fallback_svc.publish(
        RedisStreamName.TRADES,
        {"symbol": "INFY", "pnl": 1500.0},
        event_id="fb_evt_01"
    )
    assert msg_id == "fb_evt_01"

    # Deduplication must function in fallback mode
    assert fallback_svc.is_duplicate("fb_dedup_01") is False
    assert fallback_svc.is_duplicate("fb_dedup_01") is True

    # Cache must function in fallback mode
    assert fallback_svc.set_cache("fb_cache_key", {"status": "ok"}, ttl_seconds=60) is True
    assert fallback_svc.get_cache("fb_cache_key") == {"status": "ok"}

    # Status must report degraded fallback
    status = fallback_svc.get_status()
    assert status["status"] == "degraded_fallback"
    assert status["fallback_mode"] is True
    assert status["connected"] is False


def test_redis_api_endpoints():
    """Verify /redis/status and /runtime/stream-status endpoints."""
    app = create_app()
    client = TestClient(app)

    # 1. /redis/status
    res = client.get("/redis/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "connected" in data
    assert "streams_count" in data
    assert data["streams_count"] == 5

    # 2. /runtime/stream-status
    res2 = client.get("/runtime/stream-status")
    assert res2.status_code == 200
    data2 = res2.json()
    assert "consumer_groups" in data2
    assert "streams" in data2
