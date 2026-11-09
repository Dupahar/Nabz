"""Data retention and erasure: keep recordings only as long as the purpose needs them.

    python tools/retention.py run [--dry-run]                    # apply config/workspace.yaml privacy.retain_*
    python tools/retention.py erase --account "BrightMart" --by <admin handle>   # a person's/company's data
    python tools/retention.py export --account "BrightMart" --out export.zip     # data access request

DPDP Act 2023 s.8(7): erase personal data once the purpose is served; s.11-12: people can ask
what is held about them, and for erasure. Raw audio goes first (default 30 days); transcripts,
notes and scores stay longer for coaching and the CRM (default 365 days). Every deletion is
written to the audit log, so you can show what was removed and when without keeping the data.
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from common import CALLS, audit, read_json, utf8_stdout, workspace

AUDIO_FILES = ("audio.*", "upload.ogg", "transcript.raw.json", "prisma.json")


def call_date(folder: Path) -> datetime:
    t = folder / "transcript.json"
    if t.exists():
        try:
            return datetime.fromisoformat(read_json(t)["recorded_at"])
        except (KeyError, ValueError):
            pass
    return datetime.fromtimestamp(folder.stat().st_mtime)


def calls_for(account: str) -> list[Path]:
    out = []
    for folder in CALLS.iterdir():
        a = folder / "analysis.json"
        t = folder / "transcript.json"
        name = ""
        if a.exists():
            name = read_json(a).get("account", "")
        elif t.exists():
            name = read_json(t).get("title", "")
        if account.lower() in name.lower():
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
        p = workspace().get("privacy") or {}
        audio_cut = datetime.now() - timedelta(days=p.get("retain_audio_days", 30))
        all_cut = datetime.now() - timedelta(days=p.get("retain_transcripts_days", 365))
        removed = 0
        for folder in sorted(CALLS.iterdir()) if CALLS.exists() else []:
            when = call_date(folder)
            if when < all_cut:
                print(f"{'would delete' if args.dry_run else 'deleted'} call {folder.name} ({when:%Y-%m-%d})")
                if not args.dry_run:
                    shutil.rmtree(folder)
                    audit("retention.call_deleted", call_id=folder.name, recorded=f"{when:%Y-%m-%d}")
                removed += 1
            elif when < audio_cut:
                for pattern in AUDIO_FILES:
                    for f in folder.glob(pattern):
                        print(f"{'would delete' if args.dry_run else 'deleted'} {folder.name}/{f.name}")
                        if not args.dry_run:
                            f.unlink()
                            audit("retention.audio_deleted", call_id=folder.name, file=f.name)
                        removed += 1
        print(f"retention: {removed} item(s) {'to remove' if args.dry_run else 'removed'}")
    elif args.cmd == "erase":
        folders = calls_for(args.account)
        for f in folders:
            shutil.rmtree(f)
            audit("erasure.call_deleted", actor=args.by, call_id=f.name, reason="erasure request")
        print(f"erased {len(folders)} conversation(s) for '{args.account}'. Remove the CRM entry with the deal desk if requested too.")
    else:
        folders = calls_for(args.account)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in folders:
                for item in f.iterdir():
                    if item.name not in ("transcript.raw.json", "prisma.json") and not item.name.startswith(("audio", "upload")):
                        z.write(item, f"{f.name}/{item.name}")
        audit("access.export", call_id=None, account=args.account, conversations=len(folders))
        print(f"exported {len(folders)} conversation(s) to {args.out}")


if __name__ == "__main__":
    main()
