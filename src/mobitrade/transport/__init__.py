"""
Transport & Event Streaming Layer for AutoTrade AI (Phase 13).
Provides Redis Streams, Pub/Sub, and high-speed in-memory caching
with graceful zero-downtime fallback to SQLite and in-process buffers.
"""

from mobitrade.transport.redis_service import (
    RedisPipelineService,
    redis_service,
    RedisStreamName,
    ConsumerGroupName,
)

__all__ = [
    "RedisPipelineService",
    "redis_service",
    "RedisStreamName",
    "ConsumerGroupName",
]
