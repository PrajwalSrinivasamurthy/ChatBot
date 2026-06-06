from __future__ import annotations

import hashlib
import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _log_file(date_label: str) -> Path:
    return _LOGS_DIR / f"{date_label}.jsonl"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()


def _append_record(record: dict[str, Any]) -> None:
    with _log_file(_today_label()).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Public API ─────────────────────────────────────────────────────────────────

def log_interaction(
    session_id: str,
    query_text: str,
    agent: str,
    user_ip: str,
    user_agent: str,
    retrieval_result: dict[str, Any],
    response_result: dict[str, Any],
    eval_result: dict[str, Any] | None = None,
) -> str:
    """Write one complete interaction to today's .jsonl file.

    retrieval_result expected keys:
        method              "hybrid" | "qdrant_only" | "bm25_only"
        chunks_retrieved    int
        retrieval_latency_ms  int
        chunks              list of dicts — see schema below

    Each chunk dict:
        chunk_id, source, text, qdrant_score, bm25_score, rank

    response_result expected keys:
        text, model_used, prompt_tokens, completion_tokens,
        tokens_used, llm_latency_ms, total_latency_ms, fallback_triggered

    eval_result: output of evaluator.evaluate_response() — optional, stored as-is.

    Returns the log_id (uuid4 string).
    """
    log_id = str(uuid.uuid4())
    response_text = response_result.get("text", "")

    record: dict[str, Any] = {
        "log_id": log_id,
        "timestamp": _now_iso(),
        "session_id": session_id,
        "query": {
            "text": query_text,
            "length": len(query_text),
            "agent_routed_to": agent,
            "user_ip_hash": _hash_ip(user_ip),
            "user_agent": user_agent,
        },
        "retrieval": {
            "method": retrieval_result.get("method", "hybrid"),
            "chunks_retrieved": retrieval_result.get("chunks_retrieved", 0),
            "retrieval_latency_ms": retrieval_result.get("retrieval_latency_ms", 0),
            "chunks": retrieval_result.get("chunks", []),
        },
        "response": {
            "text": response_text,
            "length": len(response_text),
            "model_used": response_result.get("model_used", "unknown"),
            "prompt_tokens": response_result.get("prompt_tokens", 0),
            "completion_tokens": response_result.get("completion_tokens", 0),
            "tokens_used": response_result.get("tokens_used", 0),
            "llm_latency_ms": response_result.get("llm_latency_ms", 0),
            "total_latency_ms": response_result.get("total_latency_ms", 0),
            "fallback_triggered": response_result.get("fallback_triggered", False),
        },
        "eval_result": eval_result,
        "feedback": None,
        "error": None,
    }

    _append_record(record)
    return log_id


def log_feedback(
    log_id: str,
    feedback_type: str,
    feedback_text: str | None,
    log_date: str,
) -> bool:
    """Find a logged interaction by log_id and update its feedback field in-place.

    log_date must be "YYYY-MM-DD" (UTC) matching the file the interaction was written to.
    feedback_type: "thumbs_up" | "thumbs_down"
    Returns True if the record was found and updated, False otherwise.
    """
    log_file = _log_file(log_date)
    if not log_file.exists():
        return False

    lines = log_file.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue

        if record.get("log_id") == log_id:
            record["feedback"] = {
                "type": feedback_type,
                "text": feedback_text,
                "timestamp": _now_iso(),
            }
            new_lines.append(json.dumps(record, ensure_ascii=False))
            updated = True
        else:
            new_lines.append(line)

    if updated:
        log_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return updated


def log_error(
    session_id: str,
    query_text: str,
    agent: str,
    user_ip: str,
    user_agent: str,
    error: Exception,
    error_type: str = "unknown",
    component: str = "unknown",
    severity: str = "error",
) -> str:
    """Write a failed interaction where retrieval and response are null.

    error_type: "qdrant_timeout" | "llm_api_error" | "bm25_failure" | "rate_limit" | "unknown"
    component:  "retrieval" | "llm" | "api"
    severity:   "warning" | "error" | "critical"

    Returns the log_id (uuid4 string).
    """
    log_id = str(uuid.uuid4())

    record: dict[str, Any] = {
        "log_id": log_id,
        "timestamp": _now_iso(),
        "session_id": session_id,
        "query": {
            "text": query_text,
            "length": len(query_text),
            "agent_routed_to": agent,
            "user_ip_hash": _hash_ip(user_ip),
            "user_agent": user_agent,
        },
        "retrieval": None,
        "response": None,
        "feedback": None,
        "error": {
            "type": error_type,
            "message": str(error),
            "component": component,
            "severity": severity,
            "stack_trace": traceback.format_exc(),
            "timestamp": _now_iso(),
        },
    }

    _append_record(record)
    return log_id
