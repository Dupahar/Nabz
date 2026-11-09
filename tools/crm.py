"""A small file-backed CRM (data/crm.json) that the deal-desk agent keeps up to date.

    python tools/crm.py pipeline                          # every deal, grouped by stage
    python tools/crm.py show "BrightMart"                 # one account with its history
    python tools/crm.py upsert "BrightMart" --contact "Priya Shah" --owner "Arjun" \
        --stage proposal --value 480000 --next-step "Send pricing" --next-date 2026-11-10
    python tools/crm.py log "BrightMart" --type call --call-id <id> --summary "Demo went well"
    python tools/crm.py email "BrightMart" --call-id <id> --status drafted|approved|sent --file <path>

Add --dry-run to upsert to print the change without saving: the deal desk shows that diff in
the room and applies it only after a person approves (agents get multi-step CRM work wrong
often enough: CRMArena-Pro, 2025). Add --by <handle> to record who approved a change; every
write goes to the audit log.

It stands in for Salesforce/HubSpot in the demo. Swap these functions for API calls to
use a real CRM; the agents only ever go through this command line.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from common import CRM_FILE, read_json, utf8_stdout, write_json

STAGES = ["lead", "discovery", "demo", "proposal", "negotiation", "closed-won", "closed-lost"]


def load() -> dict:
    if CRM_FILE.exists():
        return read_json(CRM_FILE)
    return {"accounts": {}}


def find(db: dict, name: str) -> tuple[str, dict] | None:
    for key, acc in db["accounts"].items():
        if key.lower() == name.lower():
            return key, acc
    return None


def now() -> str:
    return datetime.now().isoformat(timespec="minutes")


def money(v: float | None) -> str:
    return f"₹{v:,.0f}" if v else "—"


def cmd_upsert(db: dict, a: argparse.Namespace) -> None:
    hit = find(db, a.account)
    key, acc = hit if hit else (a.account, {"created": now(), "history": [], "emails": []})
    changes = []
    for field in ("contact", "owner", "stage", "value", "next_step", "next_date"):
        val = getattr(a, field)
        if val is None:
            continue
        if field == "stage" and val not in STAGES:
            raise SystemExit(f"error: stage must be one of {STAGES}")
        if acc.get(field) != val:
            changes.append(f"{field}: {acc.get(field, '—')} → {val}")
            acc[field] = val
    acc["updated"] = now()
    if changes:
        acc["history"].append({"at": now(), "type": "update", "summary": "; ".join(changes)})
    db["accounts"][key] = acc
    verb = ("would update" if hit else "would create") if getattr(a, "dry_run", False) else ("updated" if hit else "created")
    print(f"{verb} {key}: " + ("; ".join(changes) or "no changes"))


def cmd_log(db: dict, a: argparse.Namespace) -> None:
    hit = find(db, a.account)
    if not hit:
        raise SystemExit(f"error: no account '{a.account}'. Create it with `upsert` first.")
    key, acc = hit
    acc["history"].append({"at": now(), "type": a.type, "call_id": a.call_id, "summary": a.summary})
    acc["updated"] = now()
    print(f"logged {a.type} on {key}")


def cmd_email(db: dict, a: argparse.Namespace) -> None:
    hit = find(db, a.account)
    if not hit:
        raise SystemExit(f"error: no account '{a.account}'")
    key, acc = hit
    for e in acc["emails"]:
        if e["call_id"] == a.call_id:
            e["status"], e["at"] = a.status, now()
            if a.file:
                e["file"] = a.file
            break
    else:
        acc["emails"].append({"call_id": a.call_id, "status": a.status, "file": a.file, "at": now()})
    acc["history"].append({"at": now(), "type": "email", "call_id": a.call_id, "summary": f"follow-up {a.status}"})
    print(f"follow-up email for {key} ({a.call_id}) is now {a.status}")


def cmd_show(db: dict, a: argparse.Namespace) -> None:
    hit = find(db, a.account)
    if not hit:
        raise SystemExit(f"error: no account '{a.account}'")
    key, acc = hit
    print(f"{key} · stage {acc.get('stage', '—')} · value {money(acc.get('value'))} · owner {acc.get('owner', '—')}")
    print(f"contact: {acc.get('contact', '—')}")
    print(f"next step: {acc.get('next_step', '—')} ({acc.get('next_date', 'no date')})")
    for h in acc["history"][-10:]:
        print(f"  {h['at']}  {h['type']:<6} {h['summary']}")


def cmd_pipeline(db: dict, _: argparse.Namespace) -> None:
    if not db["accounts"]:
        print("pipeline is empty")
        return
    total = 0.0
    for stage in STAGES:
        rows = [(k, v) for k, v in db["accounts"].items() if v.get("stage") == stage]
        if not rows:
            continue
        subtotal = sum(v.get("value") or 0 for _, v in rows)
        if not stage.startswith("closed"):
            total += subtotal
        print(f"{stage} ({len(rows)}, {money(subtotal)})")
        for k, v in rows:
            print(f"  • {k}: {money(v.get('value'))}, owner {v.get('owner', '—')}, next: {v.get('next_step', '—')} ({v.get('next_date', '—')})")
    print(f"open pipeline: {money(total)}")


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pipeline")
    p = sub.add_parser("show")
    p.add_argument("account")
    p = sub.add_parser("upsert")
    p.add_argument("account")
    p.add_argument("--contact")
    p.add_argument("--owner")
    p.add_argument("--stage")
    p.add_argument("--value", type=float)
    p.add_argument("--next-step", dest="next_step")
    p.add_argument("--next-date", dest="next_date")
    p.add_argument("--dry-run", action="store_true", help="show the change, don't save")
    p.add_argument("--by", default="nabz-dealdesk", help="who approved / made this change")
    p = sub.add_parser("log")
    p.add_argument("account")
    p.add_argument("--type", default="call", choices=["call", "meeting", "note", "email"])
    p.add_argument("--call-id")
    p.add_argument("--summary", required=True)
    p = sub.add_parser("email")
    p.add_argument("account")
    p.add_argument("--call-id", required=True)
    p.add_argument("--status", required=True, choices=["drafted", "approved", "sent", "rejected"])
    p.add_argument("--file")
    p.add_argument("--by", default="nabz-dealdesk")
    args = parser.parse_args()

    db = load()
    {"upsert": cmd_upsert, "log": cmd_log, "email": cmd_email, "show": cmd_show, "pipeline": cmd_pipeline}[args.cmd](db, args)
    if args.cmd in ("upsert", "log", "email"):
        if getattr(args, "dry_run", False):
            print("(dry run: nothing saved; post this change for approval)")
            return
        write_json(CRM_FILE, db)
        from common import audit
        detail = {"account": args.account}
        if args.cmd == "email":
            detail["status"] = args.status
        if args.cmd == "upsert":
            detail.update({k: getattr(args, k) for k in ("stage", "value", "next_date") if getattr(args, k) is not None})
        audit(f"crm.{args.cmd}", actor=getattr(args, "by", "nabz-dealdesk"), call_id=getattr(args, "call_id", None), **detail)


if __name__ == "__main__":
    main()
