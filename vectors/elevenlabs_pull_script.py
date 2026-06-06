"""
Pull agent configurations and guardrails from ElevenLabs Conversational AI API.

Usage:
    python elevenlabs_pull_script.py              # print summary to terminal
    python elevenlabs_pull_script.py --save       # also save full JSON to elevenlabs_agents.json
    python elevenlabs_pull_script.py --agent <id> # pull one specific agent by ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("elevenlabs_api_key", "").strip().strip("'\"")
BASE_URL = "https://api.elevenlabs.io/v1"

HEADERS = {
    "xi-api-key": API_KEY,
    "Content-Type": "application/json",
}


# ── API helpers ────────────────────────────────────────────────────────────────

def get(path: str) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
    if resp.status_code == 401:
        print("❌ Unauthorised — check your elevenlabs_api_key in .env", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def list_agents() -> list[dict]:
    data = get("/convai/agents")
    return data.get("agents", [])


def get_agent(agent_id: str) -> dict:
    return get(f"/convai/agents/{agent_id}")


# ── Display helpers ────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def print_guardrails(agent: dict) -> None:
    name = agent.get("name", agent.get("agent_id", "unknown"))
    agent_id = agent.get("agent_id", "")
    _section(f"Agent: {name}  ({agent_id})")

    conv = agent.get("conversation_config", {})

    # System prompt / persona
    agent_cfg = conv.get("agent", {})
    prompt = agent_cfg.get("prompt", {})
    system_prompt = prompt.get("prompt", "")
    if system_prompt:
        print(f"\n[System Prompt]\n{system_prompt[:400]}{'...' if len(system_prompt) > 400 else ''}")

    # Safety / guardrails block (varies by ElevenLabs plan/version)
    safety = conv.get("safety", {})
    guardrails = conv.get("guardrails", {})
    moderation = conv.get("moderation", {})

    for label, block in [("safety", safety), ("guardrails", guardrails), ("moderation", moderation)]:
        if block:
            print(f"\n[{label}]")
            print(json.dumps(block, indent=2))

    # Banned topics / words if present
    banned = agent_cfg.get("banned_words") or prompt.get("banned_words")
    if banned:
        print(f"\n[Banned words/topics]\n{banned}")

    # Knowledge base attachments
    kb = prompt.get("knowledge_base") or conv.get("knowledge_base", [])
    if kb:
        print(f"\n[Knowledge Base ({len(kb)} sources)]")
        for k in kb:
            print(f"  • {k.get('name', k.get('id', str(k)))}")

    # First message / greeting
    first_msg = agent_cfg.get("first_message", "")
    if first_msg:
        print(f"\n[First Message]\n{first_msg}")

    # Language / voice
    voice_cfg = conv.get("tts", {})
    if voice_cfg:
        print(f"\n[Voice] voice_id={voice_cfg.get('voice_id')} model={voice_cfg.get('model_id')}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pull ElevenLabs agent guardrails.")
    parser.add_argument("--save", action="store_true", help="Save full JSON to elevenlabs_agents.json")
    parser.add_argument("--agent", metavar="ID", help="Pull a single agent by ID")
    args = parser.parse_args()

    if not API_KEY:
        print("❌ elevenlabs_api_key not set in .env", file=sys.stderr)
        sys.exit(1)

    if args.agent:
        agents = [get_agent(args.agent)]
    else:
        print("⬇️  Fetching agents from ElevenLabs...")
        agents = list_agents()
        # Fetch full config for each (list endpoint returns stubs)
        full_agents = []
        for stub in agents:
            aid = stub.get("agent_id", stub.get("id", ""))
            print(f"   • {stub.get('name', aid)} ({aid})")
            full_agents.append(get_agent(aid))
        agents = full_agents

    print(f"\n✅ Found {len(agents)} agent(s)")

    for agent in agents:
        print_guardrails(agent)

    if args.save:
        out = Path(__file__).parent / "elevenlabs_agents.json"
        out.write_text(json.dumps(agents, indent=2))
        print(f"\n💾 Full JSON saved to {out}")


if __name__ == "__main__":
    main()
