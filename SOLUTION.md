# DevOps Assessment Solution

## Root Cause Analysis
The current design synchronously performs 5 MongoDB writes and 5 reads on every `/api/data` request. At 10,000 VUs, this drives ~100,000 Mongo operations/sec against a single-node database capped at ~100 IOPS. The request path is tightly coupled to MongoDB, causing saturation, connection churn, timeouts, and EOF errors.

## Architecture
The system is re-architected to decouple the request path from MongoDB:

Ingress → App Pods → Redis (buffer + cache) → Worker Pods → MongoDB

Key behaviors:
- App pods never read/write MongoDB synchronously.
- Writes are enqueued to Redis Stream `writes_stream`.
- Reads are served from Redis List `recent_records`.
- `/api/stats` uses Redis counter `record_count`.
- Worker drains stream, batches inserts, rate-limits to ≤100 ops/sec, updates Redis cache/counters.

## Design Decisions
- Redis Stream provides durable in-cluster buffering with backpressure via `MAXLEN`.
- Redis List serves as a rolling read cache to satisfy the 5 logical reads per request.
- `insert_many` with batching reduces Mongo round-trips.
- Rate limiting in worker enforces the single-node IOPS cap.
- App is horizontally scalable; workers remain limited to protect Mongo.

## Tradeoffs
- Reads are eventually consistent (Redis cache reflects persisted data).
- MongoDB is no longer the request path dependency, improving latency at the cost of strict read-after-write guarantees.
- Stream trimming may drop very old events under extreme backlog, but recent data remains available for API semantics.

## k6 Results
Command:
```
k6 run stress-test/stress-test.js
```

Status:
Not executed in this environment. Run the command above to capture the exact threshold results.
