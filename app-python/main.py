import os
import random
import string
import json
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
APP_PORT = int(os.getenv("APP_PORT", "8000"))

WRITES_STREAM = "writes_stream"
RECENT_RECORDS = "recent_records"
RECORD_COUNT = "record_count"
RECENT_MAX = int(os.getenv("RECENT_MAX", "1000"))

app = FastAPI(
    title="DevOps Assessment API",
    version="1.0.0",
)

redis_client: Redis | None = None


def get_redis() -> Redis:
    global redis_client
    if redis_client is None:
        redis_client = Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
            health_check_interval=30,
            max_connections=200,
        )
    return redis_client


def random_payload(size: int = 512) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=size))


# Liveness probe
@app.get("/healthz")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# Readiness probe
@app.get("/readyz")
def readiness_check():
    try:
        r = get_redis()
        r.ping()
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# Core endpoint — must perform exactly 5 reads and 5 writes per request
@app.get("/api/data")
def process_data():
    reads = []
    writes = []

    try:
        r = get_redis()
        pipe = r.pipeline()

        # 5 writes (enqueue)
        for i in range(5):
            record_id = str(uuid.uuid4())
            record = {
                "_id": record_id,
                "type": "write",
                "index": i,
                "payload": random_payload(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            record_json = json.dumps(record, separators=(",", ":"))
            pipe.xadd(WRITES_STREAM, {"record": record_json}, maxlen=100000, approximate=True)
            writes.append(record_id)

        # 5 reads from Redis cache
        for _ in range(5):
            pipe.lindex(RECENT_RECORDS, 0)

        results = pipe.execute()

        read_results = results[5:]
        for item in read_results:
            reads.append(item)

        return JSONResponse(
            content={
                "status": "success",
                "reads": reads,
                "writes": writes,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    except RedisError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Collection stats (from Redis counters)
@app.get("/api/stats")
def get_stats():
    try:
        r = get_redis()
        count = r.get(RECORD_COUNT)
        total = int(count) if count is not None else 0
        return {"total_documents": total, "timestamp": datetime.utcnow().isoformat()}
    except RedisError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
