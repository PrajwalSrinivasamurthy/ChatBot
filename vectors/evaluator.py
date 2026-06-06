from __future__ import annotations

import hashlib
import re
from collections import deque
from typing import Any

# ── Thresholds ─────────────────────────────────────────────────────────────────

_SHORT_THRESHOLD      = 80
_LONG_THRESHOLD       = 1500
_CONFIDENCE_THRESHOLD = 0.60
_SCORE_DEDUCTION      = 0.15

_FALLBACK_PHRASES = [
    "i don't know",
    "i'm not sure",
    "i cannot find",
    "not in my knowledge",
    "i don't have information",
    "please contact",
    "i'm unable to",
]

# Capitalized words that aren't proper nouns — excluded from hallucination check
_COMMON_CAPS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "the", "this", "that", "these", "those", "there", "their",
    "what", "when", "where", "which", "who", "why", "how",
    "also", "however", "therefore", "furthermore", "additionally",
    "please", "note", "important", "available", "here", "below",
    "above", "sure", "sorry", "based", "according", "yes", "no",
}

# ── Response cache (last 50 hashes) ───────────────────────────────────────────

_response_cache: deque[str] = deque(maxlen=50)


# ── Term extraction ────────────────────────────────────────────────────────────

def _extract_specific_terms(text: str) -> set[str]:
    """Extract numbers, URLs, emails, and mid-sentence proper nouns."""
    terms: set[str] = set()

    # URLs
    for m in re.finditer(r'https?://\S+', text):
        terms.add(m.group().lower())

    # Email addresses
    for m in re.finditer(r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b', text, re.IGNORECASE):
        terms.add(m.group().lower())

    # Standalone numbers (2+ digits, optional decimal/percent)
    for m in re.finditer(r'\b\d{2,}(?:[.,]\d+)*%?\b', text):
        terms.add(m.group())

    # Proper nouns: capitalized words that are NOT the first word of a sentence
    sentences = re.split(r'(?<=[.!?\n])\s*', text.strip())
    for sentence in sentences:
        words = sentence.split()
        for word in words[1:]:
            clean = re.sub(r"[^a-zA-Z'-]", "", word)
            if (
                len(clean) >= 3
                and clean[0].isupper()
                and clean.lower() not in _COMMON_CAPS
            ):
                terms.add(clean.lower())

    return terms


# ── Individual flag checks ─────────────────────────────────────────────────────

def _flag_response_too_short(response_text: str) -> bool:
    return len(response_text.strip()) < _SHORT_THRESHOLD


def _flag_fallback_triggered(response_text: str, fallback_triggered: bool) -> bool:
    if fallback_triggered:
        return True
    lower = response_text.lower()
    return any(phrase in lower for phrase in _FALLBACK_PHRASES)


def _flag_hallucination_risk(response_text: str, chunks: list[dict]) -> bool:
    if not chunks:
        return False  # no_chunks_retrieved covers this
    combined = " ".join(c.get("text", "") for c in chunks).lower()
    terms = _extract_specific_terms(response_text)
    return any(term and term not in combined for term in terms)


def _flag_low_retrieval_confidence(chunks: list[dict]) -> bool:
    if not chunks:
        return False
    top_score = float(chunks[0].get("qdrant_score") or 0.0)
    return top_score < _CONFIDENCE_THRESHOLD


def _flag_no_chunks_retrieved(chunks: list[dict] | None) -> bool:
    return not chunks


def _flag_response_too_long(response_text: str) -> bool:
    return len(response_text.strip()) > _LONG_THRESHOLD


def _flag_repeated_response(response_text: str) -> bool:
    h = hashlib.sha256(response_text.strip().encode()).hexdigest()
    found = h in _response_cache
    _response_cache.append(h)
    return found


# ── Main evaluation function ───────────────────────────────────────────────────

def evaluate_response(
    query: str,
    response_text: str,
    chunks: list[dict] | None,
    fallback_triggered: bool,
) -> dict[str, Any]:
    """Run all deterministic checks on a bot response.

    chunks items must have at least: text (str), qdrant_score (float).
    Returns a structured eval dict — no external calls, no I/O.
    """
    safe_chunks = chunks or []

    flags: dict[str, bool] = {
        "response_too_short":       _flag_response_too_short(response_text),
        "fallback_triggered":       _flag_fallback_triggered(response_text, fallback_triggered),
        "hallucination_risk":       _flag_hallucination_risk(response_text, safe_chunks),
        "low_retrieval_confidence": _flag_low_retrieval_confidence(safe_chunks),
        "no_chunks_retrieved":      _flag_no_chunks_retrieved(chunks),
        "response_too_long":        _flag_response_too_long(response_text),
        "repeated_response":        _flag_repeated_response(response_text),
    }

    triggered = [name for name, hit in flags.items() if hit]
    score = max(0.0, round(1.0 - len(triggered) * _SCORE_DEDUCTION, 4))

    if score >= 0.8:
        recommendation = "ok"
    elif score >= 0.5:
        recommendation = "review"
    else:
        recommendation = "escalate"

    return {
        "passed": len(triggered) == 0,
        "flags": flags,
        "score": score,
        "triggered_flags": triggered,
        "recommendation": recommendation,
    }


# ── Batch summary ──────────────────────────────────────────────────────────────

_ALL_FLAGS = [
    "response_too_short",
    "fallback_triggered",
    "hallucination_risk",
    "low_retrieval_confidence",
    "no_chunks_retrieved",
    "response_too_long",
    "repeated_response",
]


def get_eval_summary(eval_results: list[dict]) -> dict[str, Any]:
    """Aggregate a list of evaluate_response() dicts into a summary report."""
    total = len(eval_results)
    if total == 0:
        return {
            "total_evaluated": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "flag_counts": {f: 0 for f in _ALL_FLAGS},
            "avg_score": 0.0,
            "escalations": 0,
        }

    passed      = sum(1 for r in eval_results if r.get("passed"))
    escalations = sum(1 for r in eval_results if r.get("recommendation") == "escalate")
    avg_score   = round(sum(r.get("score", 0.0) for r in eval_results) / total, 4)

    flag_counts: dict[str, int] = {f: 0 for f in _ALL_FLAGS}
    for r in eval_results:
        for flag, hit in r.get("flags", {}).items():
            if flag in flag_counts and hit:
                flag_counts[flag] += 1

    return {
        "total_evaluated": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4),
        "flag_counts": flag_counts,
        "avg_score": avg_score,
        "escalations": escalations,
    }
