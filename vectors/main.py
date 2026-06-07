from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid as _uuid
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from qdrant_client.models import FusionQuery, Fusion, Prefetch, SparseVector

from agents_config import AGENTS
from embeddings import embed, sparse_embed
from qdrant_store import get_client
from ingest import download_sharepoint, run_ingestion_from_bytes, ingest_to_collection  # noqa: F401
from pathlib import Path as _Path
from llm import stream_answer
from logger import log_interaction, log_error
from evaluator import evaluate_response, is_crisis_query

logger = logging.getLogger("kb_watcher")

# ── KB auto-sync (per-agent) ───────────────────────────────────────────────────

KB_POLL_MINUTES = int(os.getenv("KB_POLL_MINUTES", "30"))

# hash state per agent_id
_kb_hashes: dict[str, str] = {}


async def _check_agent(agent_id: str, cfg: dict) -> None:
    url = cfg.get("kb_url", "")
    if not url:
        return
    try:
        logger.info(f"KB watcher [{agent_id}]: checking...")
        data, filename = download_sharepoint(url)
        current_hash = hashlib.md5(data).hexdigest()
        if _kb_hashes.get(agent_id) == current_hash:
            logger.info(f"KB watcher [{agent_id}]: no change.")
            return
        logger.info(f"KB watcher [{agent_id}]: change detected in {filename}, re-ingesting...")
        count = run_ingestion_from_bytes(data, filename, cfg["collection"], full=True)
        _kb_hashes[agent_id] = current_hash
        logger.info(f"KB watcher [{agent_id}]: indexed {count} chunks into '{cfg['collection']}'")
    except Exception as e:
        logger.error(f"KB watcher [{agent_id}] error: {e}")


async def _check_all_agents() -> None:
    for agent_id, cfg in AGENTS.items():
        await _check_agent(agent_id, cfg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _check_all_agents()
    active = [k for k, v in AGENTS.items() if v.get("kb_url")]
    if active:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(_check_all_agents, "interval", minutes=KB_POLL_MINUTES)
        scheduler.start()
        logger.info(f"KB watcher: polling every {KB_POLL_MINUTES} min for agents: {active}")
    yield


app = FastAPI(title="TTU KB API", lifespan=lifespan)

# Serve extracted images at /static/images/{id}
_static_dir = _Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
(_static_dir / "images").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

_CORS_ORIGINS = [
    "http://localhost:3000",
    "https://tosmonline0002.ttu.edu",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Models ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""  # frontend passes this; generated server-side if absent


class IngestRequest(BaseModel):
    agent: str
    url: str


class FeedbackRequest(BaseModel):
    log_id: str
    log_date: str           # "YYYY-MM-DD" UTC
    feedback_type: str      # "thumbs_up" | "thumbs_down"
    feedback_text: str = ""


_ingest_status: dict = {"state": "idle", "detail": ""}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _search_collection(collection: str, message: str, top_k: int = 5) -> list[dict]:
    """Hybrid dense+sparse search against a named collection."""
    dense_vector = embed(message)
    sv = sparse_embed(message)
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
            "text": r.payload.get("text", ""),
            "source": r.payload.get("source", ""),
            "chunk_index": r.payload.get("chunk_index", 0),
            "score": r.score,
            "image_ids": r.payload.get("image_ids", []),
        }
        for r in response.points
    ]


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "kb_poll_minutes": KB_POLL_MINUTES,
        "agents": {
            k: {"url_configured": bool(v.get("kb_url")), "collection": v["collection"]}
            for k, v in AGENTS.items()
        },
    }


# ── Agents ─────────────────────────────────────────────────────────────────────

@app.get("/agents")
def list_agents():
    return [
        {"id": k, "display_name": v["display_name"], "description": v["description"]}
        for k, v in AGENTS.items()
    ]


# ── Ingest (URL trigger) ───────────────────────────────────────────────────────

def _run_ingest_job(agent_id: str, url: str) -> None:
    global _ingest_status
    if agent_id not in AGENTS:
        _ingest_status = {"state": "error", "detail": f"Unknown agent: {agent_id}"}
        return
    collection = AGENTS[agent_id]["collection"]
    try:
        _ingest_status = {"state": "running", "detail": f"[{agent_id}] Downloading..."}
        data, filename = download_sharepoint(url)
        _ingest_status = {"state": "running", "detail": f"[{agent_id}] Embedding {filename}..."}
        count = run_ingestion_from_bytes(data, filename, collection, full=True)
        _ingest_status = {"state": "done", "detail": f"[{agent_id}] Indexed {count} chunks from {filename}"}
    except Exception as e:
        _ingest_status = {"state": "error", "detail": str(e)}


@app.post("/ingest")
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    if _ingest_status.get("state") == "running":
        raise HTTPException(status_code=409, detail="Ingestion already in progress")
    background_tasks.add_task(_run_ingest_job, req.agent, req.url)
    return {"status": "started"}


@app.get("/ingest/status")
def ingest_status():
    return _ingest_status


# ── Feedback ───────────────────────────────────────────────────────────────────

@app.post("/feedback")
def feedback(req: FeedbackRequest):
    from logger import log_feedback
    ok = log_feedback(req.log_id, req.feedback_type, req.feedback_text or None, req.log_date)
    if not ok:
        raise HTTPException(status_code=404, detail="log_id not found for that date")
    return {"status": "updated"}


# ── Chat ───────────────────────────────────────────────────────────────────────

_NO_INFO_PHRASES = [
    "does not contain",
    "don't have that information",
    "do not have that information",
    "context does not",
    "not in the context",
    "no information",
    "cannot find",
    "not found in",
]


_CRISIS_RESPONSE = (
    "If you or someone you know is in crisis, please reach out for help immediately:\n\n"
    "• 911 — Emergency services\n"
    "• 988 Suicide & Crisis Lifeline — Call or text 988 (available 24/7)\n"
    "• Crisis Text Line — Text HOME to 741741\n"
    "• TTU Counseling Center — 806.742.3674\n\n"
    "You are not alone. Help is available right now.\n\n"
    "For questions about TTU programs, I'm here to assist."
)

_CRISIS_KEYWORDS_MAIN = [
    "killing myself", "kill myself", "suicide", "overdose", "panic attack",
    "self harm", "harm myself", "hurt myself", "end my life", "want to die",
    "emergency", "severe panic",
]


def get_crisis_response(query: str) -> str | None:
    lower = query.lower()
    if any(kw in lower for kw in _CRISIS_KEYWORDS_MAIN):
        return _CRISIS_RESPONSE
    return None


@app.post("/chat/{agent_name}")
async def chat(agent_name: str, req: ChatRequest, request: Request):
    if agent_name not in AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Available: {list(AGENTS.keys())}",
        )

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    crisis_msg = get_crisis_response(req.message)
    if crisis_msg:
        async def crisis_stream():
            yield crisis_msg
        return StreamingResponse(crisis_stream(), media_type="text/plain; charset=utf-8")

    collection = AGENTS[agent_name]["collection"]
    user_ip    = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    session_id = req.session_id or str(_uuid.uuid4())
    t_request  = time.monotonic()

    try:
        t0 = time.monotonic()
        results = _search_collection(collection, req.message, top_k=5)
        retrieval_latency_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        log_error(
            session_id, req.message, agent_name, user_ip, user_agent, e,
            error_type="qdrant_timeout", component="retrieval", severity="error",
        )
        raise HTTPException(status_code=503, detail=f"Retrieval error: {e}")

    print(f"\n--- [{agent_name}] QUERY: {req.message}")
    print(f"--- CHUNKS RETRIEVED: {len(results)} ({retrieval_latency_ms}ms)")
    for i, r in enumerate(results):
        print(f"  [{i+1}] score={r['score']:.3f} | {r['text'][:80]}...")

    retrieval_result = {
        "method": "hybrid",
        "chunks_retrieved": len(results),
        "retrieval_latency_ms": retrieval_latency_ms,
        "chunks": [
            {
                "chunk_id": f"{r['source']}_{r['chunk_index']}",
                "source": r["source"],
                "text": r["text"],
                "qdrant_score": r["score"],
                "bm25_score": None,  # RRF fuses scores; individual BM25 not exposed by Qdrant
                "rank": i + 1,
            }
            for i, r in enumerate(results)
        ],
    }

    if not results:
        async def no_results():
            yield "I don't have that information in the current knowledge base. Try rephrasing your question."
        return StreamingResponse(no_results(), media_type="text/plain; charset=utf-8")

    # Collect unique image IDs from all retrieved chunks (preserve order)
    seen: set[str] = set()
    image_ids: list[str] = []
    for r in results:
        for img_id in r.get("image_ids", []):
            if img_id and img_id not in seen:
                image_ids.append(img_id)
                seen.add(img_id)

    if image_ids:
        print(f"--- IMAGES: {image_ids}")

    guardrails = AGENTS[agent_name].get("guardrails", "")

    async def streamer():
        full = ""
        t_llm = time.monotonic()
        async for chunk in stream_answer(req.message, results, guardrails=guardrails):
            full += chunk
            yield chunk
        llm_latency_ms   = int((time.monotonic() - t_llm) * 1000)
        total_latency_ms = int((time.monotonic() - t_request) * 1000)

        answered = not any(p in full.lower() for p in _NO_INFO_PHRASES)
        if image_ids and answered:
            yield f"\n__IMAGES__:{','.join(image_ids)}"

        eval_result = evaluate_response(
            query=req.message,
            response_text=full,
            chunks=retrieval_result["chunks"],
            fallback_triggered=not answered,
        )
        if eval_result["recommendation"] != "ok":
            print(f"  [EVAL] {eval_result['recommendation'].upper()} | score={eval_result['score']} | flags={eval_result['triggered_flags']}")

        log_interaction(
            session_id=session_id,
            query_text=req.message,
            agent=agent_name,
            user_ip=user_ip,
            user_agent=user_agent,
            retrieval_result=retrieval_result,
            response_result={
                "text": full,
                "model_used": "gemini-2.5-flash",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "tokens_used": 0,
                "llm_latency_ms": llm_latency_ms,
                "total_latency_ms": total_latency_ms,
                "fallback_triggered": not answered,
            },
            eval_result=eval_result,
        )

    return StreamingResponse(streamer(), media_type="text/plain; charset=utf-8")
