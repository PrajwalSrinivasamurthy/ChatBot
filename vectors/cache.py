from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import redis

from embeddings import embed

REDIS_URL            = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL            = int(os.getenv("CACHE_TTL", 3600))
SIMILARITY_THRESHOLD = 0.92

r = redis.from_url(REDIS_URL, decode_responses=False)


def _cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def get_cached_response(query: str) -> dict | None:
    query_vec = embed(query)
    for key in r.scan_iter("cache:query:*"):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)   # json.loads accepts bytes (Python 3.6+)
            sim = _cosine_similarity(query_vec, data["vector"])
            if sim >= SIMILARITY_THRESHOLD:
                return {
                    "response": data["response"],
                    "cache_hit": True,
                    "similarity": round(sim, 4),
                    "original_query": data["query"],
                }
        except Exception:
            continue
    return None


def store_cached_response(query: str, response: str) -> None:
    query_vec = embed(query)
    key = f"cache:query:{hashlib.md5(query.encode()).hexdigest()}"
    r.setex(key, CACHE_TTL, json.dumps({
        "query": query,
        "vector": query_vec,
        "response": response,
    }))


def clear_cache() -> int:
    keys = list(r.scan_iter("cache:query:*"))
    if keys:
        return r.delete(*keys)
    return 0
