from __future__ import annotations

import json
import os

import redis

REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_TTL = int(os.getenv("SESSION_TTL", 86400))
MAX_TURNS   = 15

r = redis.from_url(REDIS_URL, decode_responses=True)


def get_history(session_id: str) -> list:
    key = f"session:{session_id}"
    items = r.lrange(key, -MAX_TURNS, -1)
    result = []
    for item in items:
        try:
            result.append(json.loads(item))
        except json.JSONDecodeError:
            pass
    return result


def add_turn(session_id: str, query: str, response: str) -> None:
    key = f"session:{session_id}"
    r.rpush(key, json.dumps({"query": query, "response": response}))
    r.expire(key, SESSION_TTL)
    r.ltrim(key, -MAX_TURNS, -1)


def clear_session(session_id: str) -> None:
    r.delete(f"session:{session_id}")
