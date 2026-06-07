from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

_LOGS_DIR = Path(__file__).parent / "logs"

# ── ANSI colours ───────────────────────────────────────────────────────────────
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
R  = "\033[91m"   # red
B  = "\033[94m"   # blue
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _rec_colour(rec: str) -> str:
    return {
        "ok":       f"{G}ok{RESET}",
        "review":   f"{Y}review{RESET}",
        "escalate": f"{R}ESCALATE{RESET}",
    }.get(rec, rec)


def _ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso).astimezone()
        return dt.strftime("%H:%M:%S")
    except Exception:
        return iso[:8]


def print_record(r: dict, idx: int, verbose: bool = False) -> None:
    q   = r.get("query", {})
    res = r.get("response") or {}
    ev  = r.get("eval_result") or {}
    err = r.get("error")
    fb  = r.get("feedback")

    ts      = _ts(r.get("timestamp", ""))
    agent   = q.get("agent_routed_to", "?")
    query   = q.get("text", "")[:80]
    answer  = res.get("text", "")[:120] if res else ""
    latency = res.get("total_latency_ms", 0)
    rec     = ev.get("recommendation", "")
    score   = ev.get("score", "")
    flags   = ev.get("triggered_flags", [])

    sep = f"{DIM}{'─' * 72}{RESET}"
    print(sep)
    print(f"{BOLD}#{idx:>3}{RESET}  {DIM}{ts}{RESET}  [{B}{agent}{RESET}]  "
          f"{_rec_colour(rec)}  score={score}  {latency}ms")
    print(f"  {BOLD}Q:{RESET} {query}{'…' if len(q.get('text','')) > 80 else ''}")

    if err:
        print(f"  {R}ERROR:{RESET} {err.get('type')} — {err.get('message','')[:80]}")
    else:
        print(f"  {BOLD}A:{RESET} {answer}{'…' if len(res.get('text','')) > 120 else ''}")

    if flags:
        print(f"  {Y}Flags:{RESET} {', '.join(flags)}")

    if fb:
        icon = "👍" if fb.get("type") == "thumbs_up" else "👎"
        print(f"  {icon} Feedback: {fb.get('text') or fb.get('type')}")

    if verbose:
        retrieval = r.get("retrieval") or {}
        chunks = retrieval.get("chunks", [])
        print(f"  {DIM}Chunks: {retrieval.get('chunks_retrieved',0)} | "
              f"retrieval={retrieval.get('retrieval_latency_ms',0)}ms | "
              f"llm={res.get('llm_latency_ms',0)}ms{RESET}")
        for c in chunks[:3]:
            print(f"    {DIM}[{c.get('rank')}] score={c.get('qdrant_score',0):.3f} "
                  f"| {c.get('source','')} | {c.get('text','')[:60]}…{RESET}")


def load_logs(date_label: str) -> list[dict]:
    path = _LOGS_DIR / f"{date_label}.jsonl"
    if not path.exists():
        print(f"No log file found: {path}")
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def print_summary(records: list[dict]) -> None:
    total     = len(records)
    errors    = sum(1 for r in records if r.get("error"))
    ok        = sum(1 for r in records if (r.get("eval_result") or {}).get("recommendation") == "ok")
    review    = sum(1 for r in records if (r.get("eval_result") or {}).get("recommendation") == "review")
    escalate  = sum(1 for r in records if (r.get("eval_result") or {}).get("recommendation") == "escalate")
    avg_ms    = (sum((r.get("response") or {}).get("total_latency_ms", 0) for r in records) // total
                 if total else 0)

    print(f"\n{BOLD}{'─'*40}")
    print(f"  SUMMARY — {total} interactions")
    print(f"{'─'*40}{RESET}")
    print(f"  {G}OK{RESET}        {ok}")
    print(f"  {Y}Review{RESET}    {review}")
    print(f"  {R}Escalate{RESET}  {escalate}")
    print(f"  Errors     {errors}")
    print(f"  Avg latency {avg_ms}ms")
    print(f"{BOLD}{'─'*40}{RESET}\n")


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="View chatbot interaction logs")
    parser.add_argument("--date",     default=today,    help="Date to view (YYYY-MM-DD)")
    parser.add_argument("--agent",    default=None,     help="Filter by agent name")
    parser.add_argument("--flag",     default=None,     help="Filter by flag e.g. hallucination_risk")
    parser.add_argument("--bad",      action="store_true", help="Show only review + escalate")
    parser.add_argument("--errors",   action="store_true", help="Show only errors")
    parser.add_argument("--verbose",  action="store_true", help="Show chunks and latency detail")
    parser.add_argument("--tail",     type=int, default=None, help="Show last N records")
    parser.add_argument("--list",     action="store_true", help="List available log dates")
    args = parser.parse_args()

    if args.list:
        files = sorted(_LOGS_DIR.glob("*.jsonl"))
        if not files:
            print("No log files found.")
        for f in files:
            lines = sum(1 for l in f.read_text().splitlines() if l.strip())
            print(f"  {f.stem}  ({lines} records)")
        return

    records = load_logs(args.date)
    if not records:
        return

    # Apply filters
    if args.agent:
        records = [r for r in records if r.get("query", {}).get("agent_routed_to") == args.agent]
    if args.bad:
        records = [r for r in records if (r.get("eval_result") or {}).get("recommendation") in ("review", "escalate")]
    if args.errors:
        records = [r for r in records if r.get("error")]
    if args.flag:
        records = [r for r in records if args.flag in (r.get("eval_result") or {}).get("triggered_flags", [])]
    if args.tail:
        records = records[-args.tail:]

    print(f"\n{BOLD}Logs for {args.date} — {len(records)} records{RESET}")

    for i, r in enumerate(records, 1):
        print_record(r, i, verbose=args.verbose)

    print_summary(records)


if __name__ == "__main__":
    main()
