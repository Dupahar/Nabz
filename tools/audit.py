"""Tamper-evident audit log of everything agents and people do with a recording.

    python tools/audit.py log <action> --actor <who> [--call-id <id>] [--detail key=value ...]
    python tools/audit.py show [--call-id <id>] [--last 20]
    python tools/audit.py verify

Every tool writes here automatically (transcribe, redact, consent, CRM changes, approvals,
erasure). Each event carries the SHA-256 of the previous one, so `verify` detects any edited,
inserted or deleted line. That is the evidence an auditor (RBI/IRDAI vendor audits, CERT-In
log retention, DPDP processing records) asks for: who touched which conversation, when, and why.
"""

from __future__ import annotations

import argparse
import hashlib
import json

from common import AUDIT_FILE, audit, utf8_stdout


def read_lines() -> list[bytes]:
    if not AUDIT_FILE.exists():
        return []
    return [ln for ln in AUDIT_FILE.read_bytes().splitlines() if ln.strip()]


def verify() -> tuple[bool, str]:
    lines = read_lines()
    prev = "0" * 64
    for n, raw in enumerate(lines, 1):
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return False, f"line {n} is not valid JSON"
        if event.get("prev") != prev:
            return False, f"chain broken at line {n} ({event.get('ts')} {event.get('action')}): an earlier line was edited or removed"
        prev = hashlib.sha256(raw).hexdigest()
    return True, f"audit log OK: {len(lines)} events, chain intact (head {prev[:12]})"


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("log")
    p.add_argument("action")
    p.add_argument("--actor", required=True)
    p.add_argument("--call-id")
    p.add_argument("--detail", action="append", default=[], help="key=value, repeatable")
    s = sub.add_parser("show")
    s.add_argument("--call-id")
    s.add_argument("--last", type=int, default=20)
    sub.add_parser("verify")
    args = parser.parse_args()

    if args.cmd == "log":
        detail = dict(d.split("=", 1) for d in args.detail if "=" in d)
        event = audit(args.action, actor=args.actor, call_id=args.call_id, **detail)
        print(f"logged: {event['ts']} {event['actor']} {event['action']}")
    elif args.cmd == "show":
        events = [json.loads(x) for x in read_lines()]
        if args.call_id:
            events = [e for e in events if e.get("call_id") == args.call_id]
        for e in events[-args.last:]:
            detail = ", ".join(f"{k}={v}" for k, v in (e.get("detail") or {}).items())
            print(f"{e['ts']}  {e['actor']:<12} {e['action']:<22} {e.get('call_id') or '':<32} {detail}")
    else:
        ok, msg = verify()
        print(msg)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
