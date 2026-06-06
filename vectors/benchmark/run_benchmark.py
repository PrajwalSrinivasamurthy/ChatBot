from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from vectors/ parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from agents_config import AGENTS
from embeddings import embed, sparse_embed
from qdrant_store import get_client
from qdrant_client.models import FusionQuery, Fusion, Prefetch, SparseVector

# ── Paths ──────────────────────────────────────────────────────────────────────

_BENCHMARK_DIR = Path(__file__).parent
_QA_FILE       = _BENCHMARK_DIR / "qa_pairs.json"
_RESULTS_DIR   = _BENCHMARK_DIR / "results"
_RESULTS_DIR.mkdir(exist_ok=True)

TOP_K = 5


# ── Retrieval ──────────────────────────────────────────────────────────────────

def _retrieve(collection: str, question: str, top_k: int = TOP_K) -> list[dict]:
    """Run hybrid dense+sparse retrieval against a collection. Returns ranked chunks."""
    dense_vector = embed(question)
    sv = sparse_embed(question)
    client = get_client()
    response = client.query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(query=dense_vector, using="dense", limit=top_k * 2),
            Prefetch(
                query=SparseVector(indices=sv[0], values=sv[1]),
                using="sparse",
                limit=top_k * 2,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "rank": i + 1,
            "source": r.payload.get("source", ""),
            "text": r.payload.get("text", ""),
            "chunk_index": r.payload.get("chunk_index", 0),
            "qdrant_score": r.score,
        }
        for i, r in enumerate(response.points)
    ]


# ── Metrics ────────────────────────────────────────────────────────────────────

def _hit_rate(chunks: list[dict], expected_source: str) -> bool:
    return any(expected_source in c["source"] for c in chunks)


def _top1_hit(chunks: list[dict], expected_source: str) -> bool:
    return bool(chunks) and expected_source in chunks[0]["source"]


def _mrr_score(chunks: list[dict], expected_source: str) -> float:
    for c in chunks:
        if expected_source in c["source"]:
            return round(1.0 / c["rank"], 4)
    return 0.0


def _keyword_hit(chunks: list[dict], keywords: list[str]) -> bool:
    combined = " ".join(c["text"] for c in chunks).lower()
    return any(kw.lower() in combined for kw in keywords)


def _avg_score(chunks: list[dict]) -> float:
    if not chunks:
        return 0.0
    return round(sum(c["qdrant_score"] for c in chunks) / len(chunks), 4)


# ── Per-question evaluation ────────────────────────────────────────────────────

def evaluate_question(qa: dict) -> dict:
    agent_id = qa.get("agent", "")
    # Normalise: accept both "ttu_online" and "ttu-online" style keys
    if agent_id not in AGENTS:
        agent_id = agent_id.replace("_", "-")
    if agent_id not in AGENTS:
        return {
            "id": qa["id"],
            "agent": agent_id,
            "question": qa["question"],
            "error": f"Unknown agent: {agent_id}",
            "hit_rate": False,
            "top1_hit": False,
            "mrr_score": 0.0,
            "keyword_hit": False,
            "avg_qdrant_score": 0.0,
            "chunks_retrieved": 0,
            "chunks": [],
        }

    collection = AGENTS[agent_id]["collection"]
    expected_source = qa.get("expected_source", "")
    keywords = qa.get("expected_answer_keywords", [])

    try:
        chunks = _retrieve(collection, qa["question"])
    except Exception as e:
        return {
            "id": qa["id"],
            "agent": agent_id,
            "question": qa["question"],
            "error": str(e),
            "hit_rate": False,
            "top1_hit": False,
            "mrr_score": 0.0,
            "keyword_hit": False,
            "avg_qdrant_score": 0.0,
            "chunks_retrieved": 0,
            "chunks": [],
        }

    return {
        "id": qa["id"],
        "agent": agent_id,
        "question": qa["question"],
        "expected_source": expected_source,
        "expected_keywords": keywords,
        "hit_rate": _hit_rate(chunks, expected_source),
        "top1_hit": _top1_hit(chunks, expected_source),
        "mrr_score": _mrr_score(chunks, expected_source),
        "keyword_hit": _keyword_hit(chunks, keywords),
        "avg_qdrant_score": _avg_score(chunks),
        "chunks_retrieved": len(chunks),
        "chunks": chunks,
        "error": None,
    }


# ── Summary ────────────────────────────────────────────────────────────────────

def build_summary(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {"total_questions": 0}

    hit_count     = sum(1 for r in results if r.get("hit_rate"))
    top1_count    = sum(1 for r in results if r.get("top1_hit"))
    kw_count      = sum(1 for r in results if r.get("keyword_hit"))
    mrr_total     = sum(r.get("mrr_score", 0.0) for r in results)
    score_total   = sum(r.get("avg_qdrant_score", 0.0) for r in results)

    return {
        "total_questions":     total,
        "hit_rate":            round(hit_count / total, 4),
        "top1_accuracy":       round(top1_count / total, 4),
        "mrr":                 round(mrr_total / total, 4),
        "keyword_hit_rate":    round(kw_count / total, 4),
        "avg_retrieval_score": round(score_total / total, 4),
        "per_question_results": results,
    }


# ── Terminal table ─────────────────────────────────────────────────────────────

def _bool_cell(v: bool) -> str:
    return "YES" if v else "NO "


def print_table(results: list[dict]) -> None:
    col_q  = 42
    header = f"{'ID':<8} {'Question':<{col_q}} {'Hit':<5} {'Top1':<5} {'MRR':<6} {'KW':<5} {'Score':<7} {'Error'}"
    sep    = "-" * len(header)
    print()
    print(sep)
    print(header)
    print(sep)
    for r in results:
        q     = r["question"][:col_q].ljust(col_q)
        err   = r.get("error") or ""
        print(
            f"{r['id']:<8} {q} "
            f"{_bool_cell(r.get('hit_rate', False)):<5} "
            f"{_bool_cell(r.get('top1_hit', False)):<5} "
            f"{r.get('mrr_score', 0.0):<6.2f} "
            f"{_bool_cell(r.get('keyword_hit', False)):<5} "
            f"{r.get('avg_qdrant_score', 0.0):<7.4f} "
            f"{err}"
        )
    print(sep)


def print_summary(summary: dict) -> None:
    total = summary.get("total_questions", 0)
    print(f"\n{'='*50}")
    print(f"  BENCHMARK SUMMARY  ({total} questions)")
    print(f"{'='*50}")
    print(f"  Hit Rate (any rank):  {summary.get('hit_rate', 0)*100:.1f}%")
    print(f"  Top-1 Accuracy:       {summary.get('top1_accuracy', 0)*100:.1f}%")
    print(f"  MRR:                  {summary.get('mrr', 0):.4f}")
    print(f"  Keyword Hit Rate:     {summary.get('keyword_hit_rate', 0)*100:.1f}%")
    print(f"  Avg Retrieval Score:  {summary.get('avg_retrieval_score', 0):.4f}")
    print(f"{'='*50}\n")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if not _QA_FILE.exists():
        print(f"ERROR: qa_pairs.json not found at {_QA_FILE}")
        sys.exit(1)

    qa_pairs = json.loads(_QA_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(qa_pairs)} QA pairs from {_QA_FILE.name}")

    results = []
    for i, qa in enumerate(qa_pairs, 1):
        print(f"  [{i}/{len(qa_pairs)}] {qa['id']} — {qa['question'][:60]}...")
        results.append(evaluate_question(qa))

    summary = build_summary(results)

    print_table(results)
    print_summary(summary)

    # Save report — strip chunks from summary-level keys to keep file readable,
    # but keep full chunks in per_question_results
    date_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = _RESULTS_DIR / f"{date_label}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report saved to: {out_path}")


if __name__ == "__main__":
    main()
