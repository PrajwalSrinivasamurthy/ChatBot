from __future__ import annotations

import asyncio
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_client = genai.Client(api_key=os.getenv("LLM_API_KEY", ""))
_DEBUG = os.getenv("DEBUG", "false").lower() == "true"

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
    "gemini-flash-lite-latest",
]

SYSTEM_PROMPT = """You must answer using ONLY the context provided. If the answer exists anywhere \
in the context even partially use it to answer. Do NOT say you don't have information unless \
the context is completely empty or entirely unrelated.

If the context contains numbered steps (lines starting with "Step N:"), present each step on \
its own line in the same order. Otherwise answer concisely in plain sentences. \
Do not use markdown asterisks, headers, or bullet symbols."""

_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0,
    max_output_tokens=1024,
    thinking_config=types.ThinkingConfig(thinking_budget=0),
)


# ── Markdown safety net ───────────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)           # bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)                # italic
    text = re.sub(r'^\s*[\*\-]\s+', '', text, flags=re.MULTILINE)  # bullets
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE) # headers
    return text.strip()


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_prompt(question: str, chunks: list[dict], guardrails: str = "") -> str:
    retrieved_context = "\n\n".join(c["text"] for c in chunks)
    agent_rules = f"\n\nAgent scope rules:\n{guardrails}" if guardrails else ""
    return (
        f"{SYSTEM_PROMPT}{agent_rules}\n\n"
        f"Context:\n{retrieved_context}\n\n"
        f"Question: {question}"
    )


def _debug_footer(chunks: list[dict]) -> str:
    lines = ["\n\n---\nDebug sources:"]
    for i, c in enumerate(chunks):
        lines.append(f"  Chunk {i + 1} | score={c['score']:.2f} | {c['source']}")
    return "\n".join(lines)


def _is_quota_error(e: Exception) -> bool:
    err = str(e)
    return "RESOURCE_EXHAUSTED" in err or "429" in err or "quota" in err.lower()


# ── Streaming ─────────────────────────────────────────────────────────────────

async def stream_answer(
    question: str,
    chunks: list[dict],
    guardrails: str = "",
    history: list[dict] | None = None,
):
    prompt = build_prompt(question, chunks, guardrails)

    # Build multi-turn contents — inject history then current prompt
    contents: list = []
    for turn in (history or [])[-8:]:   # last 4 exchanges max
        role = "user" if turn.get("role") == "user" else "model"
        content = turn.get("content", "").strip()
        if content:
            contents.append(types.Content(role=role, parts=[types.Part(text=content)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

    for model_name in FALLBACK_MODELS:
        print(f"Trying model: {model_name} | max_tokens=1024 | history={len(contents)-1} turns")
        try:
            # Buffer the full response so strip_markdown sees complete patterns
            full = ""
            async for chunk in await _client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=_GEN_CONFIG,
            ):
                if chunk.text:
                    full += chunk.text

            clean = strip_markdown(full)
            print(f"  [{model_name}] {clean[:120]}...")

            # Stream the cleaned text word-by-word for natural UI feel
            words = clean.split(" ")
            for i, word in enumerate(words):
                yield ("" if i == 0 else " ") + word
                await asyncio.sleep(0.02)

            if _DEBUG:
                yield _debug_footer(chunks)
            return

        except Exception as e:
            if _is_quota_error(e):
                print(f"  {model_name} quota exceeded, trying next...")
                continue
            else:
                yield f"Error generating response: {e}"
                return

    yield "All available models are rate-limited. Please try again in a few minutes."
