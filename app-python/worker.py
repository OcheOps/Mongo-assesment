import os
import time
import json
from datetime import datetime

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from redis import Redis
from redis.exceptions import RedisError

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/assessmentdb")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

WRITES_STREAM = "writes_stream"
RECENT_RECORDS = "recent_records"
RECORD_COUNT = "record_count"

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
FLUSH_INTERVAL_MS = int(os.getenv("FLUSH_INTERVAL_MS", "100"))
MAX_OPS_PER_SEC = int(os.getenv("MAX_OPS_PER_SEC", "100"))
RECENT_MAX = int(os.getenv("RECENT_MAX", "1000"))


def get_redis() -> Redis:
    return Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
        max_connections=200,
    )


def get_mongo():
    while True:
        try:
            client = MongoClient(
                MONGO_URI,
                maxPoolSize=50,
                minPoolSize=5,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
            )
            client.admin.command("ping")
            db = client["assessmentdb"]
            col = db["records"]
            return client, col
        except PyMongoError:
            time.sleep(2)


def rate_limit(last_ts: float, ops: int) -> float:
    if ops <= 0:
        return last_ts
    min_interval = ops / float(MAX_OPS_PER_SEC)
    now = time.monotonic()
    elapsed = now - last_ts
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
        return time.monotonic()
    return now


def main():
    redis_client = get_redis()
    mongo_client, col = get_mongo()

    last_write_ts = time.monotonic()
    last_id = "0-0"

    while True:
        try:
            response = redis_client.xread({WRITES_STREAM: last_id}, count=BATCH_SIZE, block=FLUSH_INTERVAL_MS)
            if not response:
                continue

            stream, messages = response[0]
            docs = []
            ids = []
            for msg_id, fields in messages:
                record_raw = fields.get("record")
                if not record_raw:
                    last_id = msg_id
                    continue
                record = json.loads(record_raw)
                record["timestamp"] = record.get("timestamp") or datetime.utcnow().isoformat()
                docs.append(record)
                ids.append(msg_id)
                last_id = msg_id

            if not docs:
                continue

            try:
                col.insert_many(docs, ordered=False)
            except PyMongoError:
                time.sleep(1)
                continue

            try:
                pipe = redis_client.pipeline()
                for record in docs:
                    record_id = record.get("_id")
                    if record_id:
                        pipe.lpush(RECENT_RECORDS, record_id)
                pipe.ltrim(RECENT_RECORDS, 0, RECENT_MAX - 1)
                pipe.incrby(RECORD_COUNT, len(docs))
                pipe.execute()
            except RedisError:
                pass

            last_write_ts = rate_limit(last_write_ts, len(docs))

        except RedisError:
            time.sleep(1)
        except PyMongoError:
            time.sleep(1)


if __name__ == "__main__":
    main()
