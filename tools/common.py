"""Shared paths and helpers for the Nabz tools."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# NABZ_DATA_DIR lets tests (and multi-tenant deployments) point at a separate data directory.
DATA = Path(os.environ["NABZ_DATA_DIR"]) if os.environ.get("NABZ_DATA_DIR") else ROOT / "data"
CALLS = DATA / "calls"
CRM_FILE = DATA / "crm.json"

# Colours used by every chart, so the rep, customer and team views read as one system.
REP_COLOR = "#2563EB"
CUSTOMER_COLOR = "#F97316"
OTHER_COLORS = ["#10B981", "#A855F7", "#64748B", "#EAB308"]


def call_dir(call_id: str) -> Path:
    path = CALLS / call_id
    if not path.is_dir() or "/" in call_id or "\\" in call_id or ".." in call_id:
        raise ValueError(f"no call folder {path}. Run tools/transcribe.py (or tools/pipeline.py) first.")
    return path


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


class CallErased(ValueError):
    """Raised when something tries to write into a visit that has been erased."""


ERASED_FILE = DATA / "erased.jsonl"
_erased_cache: tuple = (-1.0, set())


def erased_ids() -> set:
    """Call ids with an erasure tombstone (data/erased.jsonl). Cached by file mtime."""
    global _erased_cache
    try:
        mtime = ERASED_FILE.stat().st_mtime
    except FileNotFoundError:
        return set()
    if mtime != _erased_cache[0]:
        ids = set()
        for line in ERASED_FILE.read_text(encoding="utf-8").splitlines():
            try:
                ids.add(json.loads(line)["call_id"])
            except (ValueError, KeyError):
                continue
        _erased_cache = (mtime, ids)
    return _erased_cache[1]


def is_erased(call_id: str) -> bool:
    return call_id in erased_ids()


def guard_not_erased(path: Path) -> None:
    """Refuse to (re)create anything inside an erased visit's folder: a pipeline still running
    when consent was withdrawn must not bring the data back."""
    try:
        rel = Path(path).resolve().relative_to(CALLS.resolve())
    except ValueError:
        return
    if rel.parts and is_erased(rel.parts[0]):
        raise CallErased(f"visit {rel.parts[0]} was erased")


def write_json(path: Path, data: object) -> None:
    import uuid

    guard_not_erased(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")  # unique per writer
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


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

# NABZ_CONFIG lets tests (and deployments) use a different workspace file.
CONFIG_FILE = Path(os.environ["NABZ_CONFIG"]) if os.environ.get("NABZ_CONFIG") else ROOT / "config" / "workspace.yaml"
LENSES_DIR = ROOT / "lenses"
AUDIT_FILE = DATA / "audit.jsonl"


def workspace() -> dict:
    """config/workspace.yaml as a dict (empty dict if missing)."""
    import yaml

    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def secret_key() -> bytes:
    """Server secret: NABZ_SECRET, or data/secret.key (created on first use, never committed).
    Signs sessions, keys the audit-log HMAC chain and salts pseudonyms."""
    env = os.environ.get("NABZ_SECRET", "").strip()
    if env:
        return env.encode()
    path = DATA / "secret.key"
    if not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(os.urandom(32).hex())
        except FileExistsError:
            pass
    return path.read_text().strip().encode()


def pseudonym(text: str | None) -> str | None:
    """Salted, keyed hash of a personal name for logs: records can be matched without storing the name."""
    import hashlib
    import hmac

    if not text:
        return None
    return "h:" + hmac.new(secret_key(), text.strip().lower().encode(), hashlib.sha256).hexdigest()[:16]


def audit(action: str, *, actor: str = "system", call_id: str | None = None, **detail) -> dict:
    """Append one event to the tamper-evident audit log (data/audit.jsonl).

    Each line stores HMAC-SHA256(server secret, previous line), so editing, inserting or deleting a
    past event breaks the chain, and the chain can't be recomputed without the secret. A signed
    anchor (data/audit.anchor: event count + head) detects truncation from the end. Events from
    before the HMAC upgrade use plain SHA-256 and are sealed by a "chain.rekey" event.
    Never log PII values here: log what happened, and use pseudonym() for names."""
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _audit_lock():
        return _append_audit(action, actor, call_id, detail)


AUDIT_ANCHOR = DATA / "audit.anchor"
HMAC_ALG = "hmac-sha256"


def audit_hmac(data: bytes) -> str:
    import hashlib
    import hmac

    return hmac.new(secret_key(), data, hashlib.sha256).hexdigest()


def _audit_lock():
    """Cross-process lock (pipelines run in parallel processes): an exclusive lock file holding
    an owner token. A stale lock (> 30 s) is broken by atomically renaming it away, so only one
    waiter can break it, and a writer only ever removes its own lock."""
    import contextlib
    import time
    import uuid

    @contextlib.contextmanager
    def lock():
        path = AUDIT_FILE.with_suffix(".lock")
        token = f"{os.getpid()}:{uuid.uuid4().hex}"
        deadline = time.time() + 30
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, token.encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - path.stat().st_mtime > 30:
                        os.rename(path, path.with_name(f"{path.name}.stale.{uuid.uuid4().hex[:8]}"))
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise TimeoutError("audit log lock busy")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                if path.read_text() == token:
                    path.unlink()
            except OSError:
                pass
    return lock()


def _last_audit_line() -> bytes | None:
    if not AUDIT_FILE.exists():
        return None
    with AUDIT_FILE.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        block = 65536
        while True:
            start = max(0, size - block)
            fh.seek(start)
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
            if not lines:
                return None
            if start == 0 or len(lines) > 1:  # the last line is complete
                return lines[-1]
            block *= 4


def _write_audit_line(event: dict) -> bytes:
    line = json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")
    with AUDIT_FILE.open("ab") as fh:
        fh.write(line + b"\n")
        fh.flush()
        os.fsync(fh.fileno())
    return line


def _update_anchor(line: bytes) -> None:
    count = None
    if AUDIT_ANCHOR.exists():
        try:
            count = int(json.loads(AUDIT_ANCHOR.read_text())["count"]) + 1
        except (ValueError, KeyError):
            count = None
    if count is None:
        count = sum(1 for ln in AUDIT_FILE.read_bytes().splitlines() if ln.strip())
    head = audit_hmac(line)
    anchor = {"count": count, "head": head, "sig": audit_hmac(f"{count}|{head}".encode())}
    tmp = AUDIT_ANCHOR.with_name(f"audit.anchor.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(anchor))
    os.replace(tmp, AUDIT_ANCHOR)


def _append_audit(action: str, actor: str, call_id: str | None, detail: dict) -> dict:
    import hashlib
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    last = _last_audit_line()
    if last is not None:
        try:
            legacy = json.loads(last).get("alg") != HMAC_ALG
        except ValueError:
            legacy = False
        if legacy:  # seal the old SHA-256 segment before starting the keyed chain
            rekey = {"ts": now, "actor": "system", "action": "chain.rekey", "call_id": None,
                     "detail": {"old_head_sha256": hashlib.sha256(last).hexdigest(), "alg": HMAC_ALG},
                     "prev": audit_hmac(last), "alg": HMAC_ALG}
            last = _write_audit_line(rekey)
            _update_anchor(last)
    event = {"ts": now, "actor": actor, "action": action, "call_id": call_id, "detail": detail,
             "prev": audit_hmac(last) if last is not None else "0" * 64, "alg": HMAC_ALG}
    line = _write_audit_line(event)
    _update_anchor(line)
    return event
