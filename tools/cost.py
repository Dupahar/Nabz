"""What each conversation costs to process: speech minutes, voice characters, LLM tokens, rupees.

    python tools/cost.py [--call-id <id>] [--days 30]

Speech-to-text and text-to-speech usage is logged automatically by tools/gnani.py on every API
call (data/usage.jsonl). LLM usage is estimated from the transcript size: the agents read the
transcript about three times (scribe, analyst, deal desk) plus instructions, at about four
characters per token. Rupee rates come from config/workspace.yaml `rates_inr`; leave them at 0
and you still get the units.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from common import CALLS, DATA, read_json, utf8_stdout, workspace

LLM_PASSES = 3
OVERHEAD_TOKENS = 12_000  # playbooks, CLAUDE.md, tool output, replies


def llm_tokens(call_id: str) -> int:
    path = CALLS / call_id / "transcript.json"
    if not path.exists():
        return 0
    chars = sum(len(s["text"]) for s in read_json(path)["segments"])
    return int(chars / 4 * LLM_PASSES + OVERHEAD_TOKENS)


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--call-id")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    rates = workspace().get("rates_inr") or {}
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    rows = []
    usage = DATA / "usage.jsonl"
    if usage.exists():
        for line in usage.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if datetime.fromisoformat(r["ts"]) >= since and (not args.call_id or r.get("call_id") == args.call_id):
                rows.append(r)

    calls = sorted({r["call_id"] for r in rows if r.get("call_id")})
    if args.call_id:
        calls = [args.call_id]
    stt_min = sum(r.get("seconds", 0) for r in rows if r["kind"] == "stt" and r.get("call_id") in calls) / 60
    tts_chars = sum(r.get("chars", 0) for r in rows if r["kind"] == "tts" and r.get("call_id") in calls)
    llm_rows = [r for r in rows if r["kind"] == "llm" and r.get("call_id") in calls]
    tokens = sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) + r.get("cache_read", 0) + r.get("cache_write", 0)
                 for r in llm_rows) or sum(llm_tokens(c) for c in calls)
    llm_inr = sum(r.get("cost_inr", 0) for r in llm_rows)

    inr = (stt_min * rates.get("prisma_per_min", 0) + tts_chars / 1000 * rates.get("timbre_per_1k_chars", 0)
           + (llm_inr or tokens / 1000 * rates.get("llm_per_1k_tokens", 0)))
    scope = f"call {args.call_id}" if args.call_id else f"last {args.days} days, {len(calls)} conversations"
    print(f"Cost report ({scope})")
    print(f"  Prisma speech-to-text   {stt_min:7.1f} min")
    print(f"  Timbre voice debriefs   {tts_chars:7d} chars")
    print(f"  LLM                     {tokens:7d} tokens" + (f"  (Rs {llm_inr:,.2f} at list prices, measured)" if llm_inr else "  (estimated)"))
    if any(rates.values()):
        print(f"  Total                   ₹{inr:,.2f}" + (f"  (₹{inr / len(calls):,.2f} per conversation)" if len(calls) > 1 else ""))
    else:
        print("  (set rates_inr in config/workspace.yaml to see rupees)")


if __name__ == "__main__":
    main()
