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

CSRF = {"X-Nabz": "1"}
DEMO_PIN = "1234"


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
