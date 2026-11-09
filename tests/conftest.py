"""Test setup: an isolated data directory and a fixed secret, set BEFORE any Nabz module is imported.
No test calls a paid API (Gnani, Anthropic): processing is stubbed where needed."""
import json
import os
import sys
import tempfile
from pathlib import Path

DATA_DIR = Path(tempfile.mkdtemp(prefix="nabz-test-data-"))
os.environ["NABZ_DATA_DIR"] = str(DATA_DIR)
os.environ["NABZ_SECRET"] = "test-secret-not-for-production"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import pytest  # noqa: E402
import yaml  # noqa: E402

CSRF = {"X-Nabz": "1"}
DEMO_PIN = "1234"


TEST_CONFIG = DATA_DIR.parent / f"{DATA_DIR.name}-workspace.yaml"
os.environ["NABZ_CONFIG"] = str(TEST_CONFIG)  # must be set before any Nabz module is imported


def _write_test_workspace() -> None:
    """A private copy of config/workspace.yaml in which every user's PIN is DEMO_PIN, so tests never
    depend on (or reveal) the PINs configured for a real deployment."""
    from set_pin import hash_pin  # imports common, which now reads NABZ_CONFIG

    ws = yaml.safe_load((ROOT / "config" / "workspace.yaml").read_text(encoding="utf-8"))
    for member in ws.get("team", []):
        member["pin_hash"] = hash_pin(DEMO_PIN, iterations=1000)
    TEST_CONFIG.write_text(yaml.safe_dump(ws, allow_unicode=True, sort_keys=False), encoding="utf-8")


_write_test_workspace()


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def make_visit(call_id: str, rep: str = "arjun", status: str = "done", method: str = "rep-confirmed",
               segments: list | None = None, recorded_at: str = "2026-11-09T10:00:00", account: str = "Test Store") -> Path:
    from common import CALLS

    folder = CALLS / call_id
    write(folder / "visit.json", {"call_id": call_id, "rep_handle": rep, "rep_name": rep.title(), "account": account,
                                  "contact": "Ramesh ji", "segment": "Kirana", "region": "Delhi NCR", "note": "",
                                  "upload": "upload.ogg", "created": recorded_at})
    write(folder / "status.json", {"status": status, "stage": status, "updated": recorded_at})
    write(folder / "consent.json", {"call_id": call_id, "method": method, "confirmed_by": rep, "subject": "Ramesh ji",
                                    "purpose": "test", "recorded_at": recorded_at, "withdrawn": False,
                                    "verified": None, "verified_segment": None, "review": None})
    if segments is not None:
        write(folder / "transcript.json", {"call_id": call_id, "recorded_at": recorded_at, "duration_sec": 60,
                                           "segments": segments, "diarized": True})
    return folder


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    import app.server as server

    return TestClient(server.app)


def login(c, handle: str, pin: str = DEMO_PIN):
    return c.post("/api/login", json={"handle": handle, "pin": pin}, headers=CSRF)
