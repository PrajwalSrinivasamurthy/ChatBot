from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────

HEALTH_URL     = os.getenv("HEALTH_URL", "http://localhost:8000/health")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
TWILIO_SID     = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN   = os.getenv("TWILIO_TOKEN", "")
TWILIO_FROM    = os.getenv("TWILIO_FROM", "")
TWILIO_TO_1    = os.getenv("TWILIO_TO_1", "")
TWILIO_TO_2    = os.getenv("TWILIO_TO_2", "")

RECIPIENTS = [n for n in [TWILIO_TO_1, TWILIO_TO_2] if n.strip()]


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


# ── Main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[{_now()}] Monitor starting — checking {HEALTH_URL} every {CHECK_INTERVAL}s")
    print(f"[{_now()}] Alerting {len(RECIPIENTS)} recipient(s): {', '.join(RECIPIENTS)}")

    # Startup notification
    try:
        send_sms(f"✅ TTU Chatbot Monitor started at {_now()} UTC")
    except Exception as exc:
        print(f"[{_now()}] Startup SMS failed: {exc}")

    last_status = "up"

    while True:
        try:
            is_up, error = check_health()
            ts = _now()
            print(f"[{ts}] Status: {'UP' if is_up else 'DOWN'}", flush=True)

            if is_up and last_status == "down":
                try:
                    send_sms(
                        f"✅ TTU Chatbot is back UP\n"
                        f"Recovered at: {ts} UTC"
                    )
                except Exception as exc:
                    print(f"[{ts}] Recovery SMS failed: {exc}")
                last_status = "up"

            elif not is_up and last_status == "up":
                try:
                    send_sms(
                        f"🔴 TTU Chatbot is DOWN\n"
                        f"Failed at: {ts} UTC\n"
                        f"Error: {error}"
                    )
                except Exception as exc:
                    print(f"[{ts}] Alert SMS failed: {exc}")
                last_status = "down"

        except Exception as exc:
            print(f"[{_now()}] Monitor loop error: {exc}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

# ── How to run in background ───────────────────────────────────────────────────
# nohup python monitor.py > logs/monitor.log 2>&1 &
