from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────

HEALTH_URL   = os.getenv("HEALTH_URL", "http://localhost:8000/health")
TWILIO_SID   = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM", "")
TWILIO_TO_1  = os.getenv("TWILIO_TO_1", "")
TWILIO_TO_2  = os.getenv("TWILIO_TO_2", "")

RECIPIENTS = [n for n in [TWILIO_TO_1, TWILIO_TO_2] if n.strip()]

# Persists last known status across cron invocations (this script is single-shot,
# run on a schedule, rather than a long-running daemon).
STATE_FILE = Path(__file__).parent / ".monitor_state"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def send_sms(body: str) -> None:
    """Send SMS to all configured recipients. Logs per-number failures silently."""
    from twilio.rest import Client
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    for number in RECIPIENTS:
        try:
            client.messages.create(body=body, from_=TWILIO_FROM, to=number)
        except Exception as exc:
            print(f"  [monitor] SMS to {number} failed: {exc}")


def check_health() -> tuple[bool, str]:
    """Returns (is_up, error_message)."""
    try:
        resp = httpx.get(HEALTH_URL, timeout=10)
        if resp.status_code == 200:
            return True, ""
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


# ── Single-shot check (invoked by cron every 30 min) ──────────────────────────

def main() -> None:
    last_status = STATE_FILE.read_text().strip() if STATE_FILE.exists() else None

    is_up, error = check_health()
    ts = _now()
    status = "up" if is_up else "down"
    print(f"[{ts}] Status: {status.upper()}" + (f" ({error})" if error else ""), flush=True)

    if last_status is None:
        # First-ever run: only alert if we start out down; otherwise just record state.
        if not is_up:
            send_sms(f"🔴 TTU Chatbot is DOWN\nFailed at: {ts} UTC\nError: {error}")
    elif status != last_status:
        if is_up:
            send_sms(f"✅ TTU Chatbot is back UP\nRecovered at: {ts} UTC")
        else:
            send_sms(f"🔴 TTU Chatbot is DOWN\nFailed at: {ts} UTC\nError: {error}")

    STATE_FILE.write_text(status)


if __name__ == "__main__":
    main()

# ── Cron setup ──────────────────────────────────────────────────────────────────
# Runs every 30 minutes:
# */30 * * * * cd "/path/to/vectors" && .venv/bin/python3 monitor.py >> logs/monitor.log 2>&1
