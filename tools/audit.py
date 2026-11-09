"""Tamper-evident audit log of everything agents and people do with a recording.

    python tools/audit.py log <action> --actor <who> [--call-id <id>] [--detail key=value ...]
    python tools/audit.py show [--call-id <id>] [--last 20]
    python tools/audit.py verify

Every tool writes here automatically (consent, transcription, redaction, analysis, CRM changes,
approvals, erasure). Each event carries HMAC-SHA256(server secret, previous event), so `verify`
detects any edited, inserted or deleted line, and nobody without the secret can recompute the
chain. A signed anchor (data/audit.anchor) records the event count and head, so cutting events
off the end is detected too. Publish the head shown by `verify` (or /api/trust) somewhere outside
the server (an email, a ticket) to make the log provable to an auditor.

Events written before the HMAC upgrade use plain SHA-256 links; the first keyed event
("chain.rekey") seals them, so editing them is still detected.
"""

from __future__ import annotations

import argparse
import hashlib
import json

from common import AUDIT_ANCHOR, AUDIT_FILE, HMAC_ALG, audit, audit_hmac, utf8_stdout


def read_lines() -> list[bytes]:
    if not AUDIT_FILE.exists():
        return []
    return [ln for ln in AUDIT_FILE.read_bytes().splitlines() if ln.strip()]


def read_events() -> list[dict]:
    """Parsed events; a corrupt line is returned as a placeholder instead of breaking callers."""
    out = []
    for raw in read_lines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            out.append({"action": "corrupt-line", "detail": {}, "actor": "?", "ts": None, "call_id": None})
    return out


def head() -> str | None:
    lines = read_lines()
    return audit_hmac(lines[-1]) if lines else None


def verify() -> tuple[bool, str]:
    lines = read_lines()
    prev: bytes | None = None
    legacy = keyed = 0
    for n, raw in enumerate(lines, 1):
        try:
            event = json.loads(raw)
        except ValueError:
            return False, f"line {n} is not valid JSON (corrupted or edited)"
        if prev is None:
            expected = "0" * 64
        elif event.get("alg") == HMAC_ALG:
            expected = audit_hmac(prev)
        else:
            expected = hashlib.sha256(prev).hexdigest()
        if event.get("prev") != expected:
            return False, (f"chain broken at line {n} ({event.get('ts')} {event.get('action')}): "
                           "an earlier line was edited, inserted or removed")
        if event.get("alg") == HMAC_ALG:
            keyed += 1
        else:
            if keyed:
                return False, f"line {n} is an unkeyed event after the keyed chain started (forged?)"
            legacy += 1
        prev = raw

    if not AUDIT_ANCHOR.exists():
        if keyed:
            return False, "audit.anchor is missing: events may have been removed from the end"
        return True, f"audit log OK: {len(lines)} legacy events, no anchor yet"
    try:
        anchor = json.loads(AUDIT_ANCHOR.read_text())
        count, anchored_head, sig = int(anchor["count"]), anchor["head"], anchor["sig"]
    except (ValueError, KeyError):
        return False, "audit.anchor is unreadable"
    if audit_hmac(f"{count}|{anchored_head}".encode()) != sig:
        return False, "audit.anchor signature is invalid (forged anchor)"
    if count > len(lines):
        return False, f"log truncated: the anchor records {count} events but only {len(lines)} remain"
    if audit_hmac(lines[count - 1]) != anchored_head:
        return False, f"event #{count} does not match the anchored head (log rewritten)"
    note = "" if count == len(lines) else f" ({len(lines) - count} event(s) after the anchor, e.g. after a crash)"
    return True, (f"audit log OK: {len(lines)} events ({legacy} legacy SHA-256 + {keyed} HMAC-keyed), "
                  f"anchored, head {audit_hmac(lines[-1])[:12]}{note}")


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
        events = read_events()
        if args.call_id:
            events = [e for e in events if e.get("call_id") == args.call_id]
        for e in events[-args.last:]:
            detail = ", ".join(f"{k}={v}" for k, v in (e.get("detail") or {}).items())
            print(f"{e.get('ts')}  {e.get('actor'):<12} {e.get('action'):<24} {e.get('call_id') or '':<32} {detail}")
    else:
        ok, msg = verify()
        print(msg)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
