"""Data retention and erasure: keep recordings only as long as the purpose needs them.

    python tools/retention.py run [--dry-run]                    # apply config/workspace.yaml privacy.retain_*
    python tools/retention.py erase --account "BrightMart" --by <admin handle>   # a person's/company's data
    python tools/retention.py export --account "BrightMart" --out export.zip     # data access request

DPDP Act 2023 s.8(7): erase personal data once the purpose is served; s.11-12: people can ask
what is held about them, and for erasure. Raw audio and the unredacted transcript go first
(default: 1 day after the recording); redacted transcripts, notes and scores stay longer for
coaching and the CRM (default 365 days). The web server runs `apply()` at startup and every few
hours (config: server.retention_interval_hours). Every deletion is written to the audit log.
"""

from __future__ import annotations

import argparse
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from common import CALLS, audit, read_json, utf8_stdout, workspace

RAW_FILES = ("audio.*", "upload.*", "transcript.raw.json", "prisma.json", "job.json")
PROCESSING = {"queued", "transcribing", "analysing", "voicing"}


def call_date(folder: Path) -> datetime:
    for name in ("transcript.json", "visit.json"):
        t = folder / name
        if t.exists():
            try:
                d = read_json(t)
                value = d.get("recorded_at") or d.get("created")
                if value:
                    return datetime.fromisoformat(value).replace(tzinfo=None)
            except (ValueError, KeyError):
                pass
    return datetime.fromtimestamp(folder.stat().st_mtime)


def _busy(folder: Path) -> bool:
    st = folder / "status.json"
    try:
        return st.exists() and read_json(st).get("status") in PROCESSING
    except ValueError:
        return False


def apply(dry_run: bool = False) -> list[str]:
    """Delete raw audio past retain_audio_days and whole visits past retain_transcripts_days.
    Visits still being processed are skipped. Returns a list of what was (or would be) removed."""
    p = workspace().get("privacy") or {}
    audio_cut = datetime.now() - timedelta(days=float(p.get("retain_audio_days", 1)))
    all_cut = datetime.now() - timedelta(days=float(p.get("retain_transcripts_days", 365)))
    removed: list[str] = []
    if not CALLS.exists():
        return removed
    for folder in sorted(CALLS.iterdir()):
        if not folder.is_dir() or _busy(folder):
            continue
        when = call_date(folder)
        if when < all_cut:
            removed.append(f"visit {folder.name}")
            if not dry_run:
                from consent import erase

                erase(folder.name, "retention", reason=f"retention: older than {p.get('retain_transcripts_days', 365)} days")
        elif when < audio_cut:
            for pattern in RAW_FILES:
                for f in folder.glob(pattern):
                    removed.append(f"{folder.name}/{f.name}")
                    if not dry_run:
                        f.unlink(missing_ok=True)
                        audit("retention.raw_deleted", call_id=folder.name, file=f.name)
    return removed


def calls_for(account: str) -> list[Path]:
    out = []
    if not CALLS.exists():
        return out
    for folder in CALLS.iterdir():
        name = ""
        for f in ("analysis.json", "visit.json", "transcript.json"):
            if (folder / f).exists():
                d = read_json(folder / f)
                name = d.get("account") or d.get("title") or ""
                if name:
                    break
        if name and account.lower() in name.lower():
            out.append(folder)
    return out


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    e = sub.add_parser("erase")
    e.add_argument("--account", required=True)
    e.add_argument("--by", required=True)
    x = sub.add_parser("export")
    x.add_argument("--account", required=True)
    x.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.cmd == "run":
        removed = apply(args.dry_run)
        for item in removed:
            print(("would delete " if args.dry_run else "deleted ") + item)
        print(f"retention: {len(removed)} item(s) {'to remove' if args.dry_run else 'removed'}")
    elif args.cmd == "erase":
        from consent import erase

        folders = calls_for(args.account)
        for f in folders:
            erase(f.name, args.by, reason="erasure request")
        print(f"erased {len(folders)} visit(s) for '{args.account}' (call folders, CRM entries, usage rows)")
    else:
        folders = calls_for(args.account)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in folders:
                for item in f.iterdir():
                    if item.name in ("transcript.raw.json", "prisma.json", "job.json") or item.name.startswith(("audio", "upload")):
                        continue
                    z.write(item, f"{f.name}/{item.name}")
        audit("access.export", account=args.account, visits=len(folders))
        print(f"exported {len(folders)} visit(s) to {args.out}")


if __name__ == "__main__":
    main()
