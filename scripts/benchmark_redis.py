import time
import sqlite3
from mobitrade.transport.redis_service import redis_service, RedisStreamName

def run_benchmark():
    N = 1000
    print(f"Running benchmark with N={N} iterations...")

    # 1. Benchmark Redis publish
    t0 = time.perf_counter()
    for i in range(N):
        redis_service.publish(
            RedisStreamName.MARKET,
            {"symbol": "TATAMOTORS", "price": 500.0 + i},
            event_id=f"bench_mkt_{i}"
        )
    t_redis_write = (time.perf_counter() - t0) / N * 1000.0

    # 2. Benchmark SQLite write with disk fsync/commit
    db_path = "database/bench_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS bench (id TEXT PRIMARY KEY, data TEXT)")
    conn.commit()
    t0 = time.perf_counter()
    for i in range(N):
        conn.execute("INSERT OR REPLACE INTO bench VALUES (?, ?)", (f"bench_{i}", '{"symbol": "TATAMOTORS"}'))
        conn.commit()
    t_sqlite_write = (time.perf_counter() - t0) / N * 1000.0
    conn.close()
    import os
    if os.path.exists(db_path):
        os.remove(db_path)

    # 3. Benchmark Redis Cache read vs SQLite read
    redis_service.set_cache("bench_cache", {"test": 123}, ttl_seconds=60)
    t0 = time.perf_counter()
    for i in range(N):
        _ = redis_service.get_cache("bench_cache")
    t_redis_read = (time.perf_counter() - t0) / N * 1000.0

    conn_read = sqlite3.connect("database/mobitrade.db")
    t0 = time.perf_counter()
    for i in range(N):
        _ = conn_read.execute("SELECT state FROM accounts LIMIT 1").fetchone()
    t_sqlite_read = (time.perf_counter() - t0) / N * 1000.0
    conn_read.close()

    print("================ LATENCY BENCHMARK RESULTS ================")
    print(f"Redis Stream Publish Latency: {t_redis_write:.4f} ms per event")
    print(f"SQLite Disk Write Latency:    {t_sqlite_write:.4f} ms per record")
    speedup_write = t_sqlite_write / t_redis_write if t_redis_write > 0 else 1.0
    print(f"Write Throughput Speedup:     {speedup_write:.1f}x FASTER via Redis Streams")
    print("-----------------------------------------------------------")
    print(f"Redis In-Memory Cache Read:   {t_redis_read:.4f} ms per lookup")
    print(f"SQLite Disk Query Read:       {t_sqlite_read:.4f} ms per query")
    speedup_read = t_sqlite_read / t_redis_read if t_redis_read > 0 else 1.0
    print(f"Read Latency Speedup:         {speedup_read:.1f}x FASTER via Redis Cache")
    print("===========================================================")

if __name__ == "__main__":
    run_benchmark()
