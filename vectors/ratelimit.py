from __future__ import annotations

import os

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_REQ   = int(os.getenv("RATE_LIMIT_MAX", 20))
WINDOW    = int(os.getenv("RATE_LIMIT_WINDOW", 60))

r = redis.from_url(REDIS_URL, decode_responses=True)


def is_rate_limited(ip_hash: str) -> bool:
    key = f"ratelimit:{ip_hash}"
    count = r.get(key)
    if count is None:
        r.set(key, 1, ex=WINDOW)
        return False
    if int(count) >= MAX_REQ:
        return True
    r.incr(key)
    return False
