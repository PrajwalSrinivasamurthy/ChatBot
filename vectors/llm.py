from __future__ import annotations

import asyncio
import os
import re
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
_DEBUG = os.getenv("DEBUG", "false").lower() == "true"

FALLBACK_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
]

SYSTEM_PROMPT = """You are the TTU Online+ assistant for Texas Tech University.
You help students and staff with questions about TTU Online+ programs, admissions,
registration, financial aid, and Industry Career Certificates.

Answer ONLY using the provided context. If the context does not contain the answer,
say so honestly and direct the user to the TTU Online team.

RESPONSE FORMAT RULES:
1. Organize answers into clear sections with bold headers when the answer covers
   multiple topics or categories.

2. Use bullet points for any list of items (programs, steps, requirements, options).
   Never write a long paragraph when a bulleted list works better.

3. Always include relevant contact information when it appears in the context —
   phone numbers, email addresses, and links must be included in your response,
   not omitted.

4. End every response with a helpful next step — a relevant link, a contact,
   or an offer to help further.

5. Never repeat the same information twice in one response.

6. Be concise and well-organized. Prefer structured, scannable answers over
   dense walls of text.

7. When listing programs or degrees, group them by category (e.g. Business,
   Social Sciences, Computing) rather than one long flat list.

STANDARD CONTACT INFO (include when relevant):
- TTU Online+ phone: 1-844-691-0494
- TTU Online+ email: online@ttu.edu
- Programs page: https://www.depts.ttu.edu/online/programs/
- General info: GoOnline.ttu.edu

SAFETY RULES:
- If a user expresses thoughts of self-harm, suicide, or crisis, do not answer
  normally. Direct them to 988, 911, and the TTU counseling center immediately.
- Never provide medical, legal, or financial advice — route to the appropriate
  TTU office.
- Stay strictly within your scope as a TTU Online assistant."""


# ── Markdown safety net ───────────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)           # bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)                # italic
    text = re.sub(r'^\s*[\*\-]\s+', '', text, flags=re.MULTILINE)  # bullets
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE) # headers
    return text.strip()


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_prompt(question: str, chunks: list[dict]) -> str:
    retrieved_context = "\n\n".join(c["text"] for c in chunks)
    return f"Context:\n{retrieved_context}\n\nQuestion: {question}"


def _debug_footer(chunks: list[dict]) -> str:
    lines = ["\n\n---\nDebug sources:"]
    for i, c in enumerate(chunks):
        lines.append(f"  Chunk {i + 1} | score={c['score']:.2f} | {c['source']}")
    return "\n".join(lines)


def _is_quota_error(e: Exception) -> bool:
    err = str(e)
    return "insufficient_quota" in err or "rate_limit" in err.lower() or "429" in err


# ── Streaming ─────────────────────────────────────────────────────────────────

async def stream_answer(
    question: str,
    chunks: list[dict],
    guardrails: str = "",
    history: list[dict] | None = None,
):
    prompt = build_prompt(question, chunks)

    # System instruction = base prompt + per-agent guardrails (applied on every request)
    system_instr = SYSTEM_PROMPT
    if guardrails:
        system_instr += f"\n\nAgent scope rules:\n{guardrails}"

    # Build multi-turn messages — system, then history turns, then current prompt
    messages: list[dict] = [{"role": "system", "content": system_instr}]
    for turn in (history or [])[-8:]:   # last 4 exchanges max
        role = "user" if turn.get("role") == "user" else "assistant"
        content = turn.get("content", "").strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    for model_name in FALLBACK_MODELS:
        print(f"Trying model: {model_name} | max_tokens=2048 | history={len(messages)-2} turns")
        try:
            full = ""
            stream = await _client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,
                max_tokens=2048,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full += delta

            print(f"  [{model_name}] {full[:120]}...")

            # Stream word-by-word for natural UI feel
            words = full.split(" ")
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
