"""Shared paths and helpers for the Nabz tools."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CALLS = DATA / "calls"
CRM_FILE = DATA / "crm.json"

# Colours used by every chart, so the rep, customer and team views read as one system.
REP_COLOR = "#2563EB"
CUSTOMER_COLOR = "#F97316"
OTHER_COLORS = ["#10B981", "#A855F7", "#64748B", "#EAB308"]


def call_dir(call_id: str) -> Path:
    path = CALLS / call_id
    if not path.is_dir():
        sys.exit(f"error: no call folder {path}. Run tools/transcribe.py first, or check `tools/calls.py list`.")
    return path


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "call"


def fmt_ts(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def utf8_stdout() -> None:
    """Windows consoles default to cp1252; agents read our output, so force UTF-8."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- workspace config + audit log

CONFIG_FILE = ROOT / "config" / "workspace.yaml"
LENSES_DIR = ROOT / "lenses"
AUDIT_FILE = DATA / "audit.jsonl"


def workspace() -> dict:
    """config/workspace.yaml as a dict (empty dict if missing)."""
    import yaml

    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def audit(action: str, *, actor: str = "system", call_id: str | None = None, **detail) -> dict:
    """Append one event to the hash-chained audit log (data/audit.jsonl).

    Each line stores the SHA-256 of the previous line, so editing or deleting any past event
    breaks the chain and `tools/audit.py verify` reports where. Never log PII values here:
    log what happened (e.g. "redacted 2 phone numbers"), not the data itself."""
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _audit_lock():
        return _append_audit(action, actor, call_id, detail)


def _audit_lock():
    """Cross-process lock (pipelines run in parallel processes): an exclusive lock file.
    Two writers reading the same 'prev' hash would fork the chain."""
    import contextlib
    import os
    import time

    @contextlib.contextmanager
    def lock():
        path = AUDIT_FILE.with_suffix(".lock")
        deadline = time.time() + 30
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:  # a crashed writer leaves a stale lock; break it after 30 s
                    if time.time() - path.stat().st_mtime > 30:
                        path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.time() > deadline:
                    raise TimeoutError("audit log lock busy")
                time.sleep(0.02)
        try:
            yield
        finally:
            os.close(fd)
            path.unlink(missing_ok=True)
    return lock()


def _append_audit(action: str, actor: str, call_id: str | None, detail: dict) -> dict:
    import hashlib
    from datetime import datetime, timezone

    prev = "0" * 64
    if AUDIT_FILE.exists():
        with AUDIT_FILE.open("rb") as fh:
            try:
                fh.seek(-4096, 2)
            except OSError:
                fh.seek(0)
            tail = [ln for ln in fh.read().splitlines() if ln.strip()]
        if tail:
            prev = hashlib.sha256(tail[-1]).hexdigest()
    event = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "actor": actor, "action": action,
             "call_id": call_id, "detail": detail, "prev": prev}
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with AUDIT_FILE.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    return event
