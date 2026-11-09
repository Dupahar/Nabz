"""Upload validation (H7) and the consent requirement (H5). Processing is stubbed: no API calls."""
import subprocess
from pathlib import Path

import pytest

from conftest import CSRF, ROOT, login

SAMPLE = ROOT / "demo" / "kirana_snippet.ogg"


@pytest.fixture(autouse=True)
def no_processing(monkeypatch):
    import app.server as server

    monkeypatch.setattr(server, "submit", lambda call_id: True)


def form(**over):
    data = {"account": "Upload Store", "contact": "", "segment": "Kirana", "consent_method": "rep-confirmed",
            "consent_confirmed": "true", "recorded_at": ""}
    data.update(over)
    return data


def test_valid_upload_is_accepted(client):
    login(client, "arjun")
    with SAMPLE.open("rb") as fh:
        r = client.post("/api/visits", data=form(), files={"audio": ("v.ogg", fh, "audio/ogg")}, headers=CSRF)
    assert r.status_code == 200, r.text
    v = client.get(f"/api/visits/{r.json()['call_id']}").json()
    assert v["visit"]["status"] == "queued"
    assert v["consent"]["method"] == "rep-confirmed" and v["consent"]["verified"] is None


def test_consent_is_required(client):
    login(client, "arjun")
    with SAMPLE.open("rb") as fh:
        r = client.post("/api/visits", data=form(consent_confirmed=""), files={"audio": ("v.ogg", fh, "audio/ogg")}, headers=CSRF)
    assert r.status_code == 400


def test_csrf_header_required_for_upload(client):
    login(client, "arjun")
    with SAMPLE.open("rb") as fh:
        r = client.post("/api/visits", data=form(), files={"audio": ("v.ogg", fh, "audio/ogg")})
    assert r.status_code == 403


def test_wrong_type_rejected(client):
    login(client, "arjun")
    r = client.post("/api/visits", data=form(), files={"audio": ("notes.txt", b"hello", "text/plain")}, headers=CSRF)
    assert r.status_code == 415


def test_fake_audio_rejected(client):
    login(client, "arjun")
    r = client.post("/api/visits", data=form(), files={"audio": ("fake.ogg", b"not really audio" * 100, "audio/ogg")}, headers=CSRF)
    assert r.status_code == 400


def test_size_cap(client, monkeypatch):
    import pipeline

    real = pipeline.limits
    monkeypatch.setattr(pipeline, "limits", lambda: {**real(), "max_upload_mb": 0.01})
    login(client, "arjun")
    with SAMPLE.open("rb") as fh:
        r = client.post("/api/visits", data=form(), files={"audio": ("v.ogg", fh, "audio/ogg")}, headers=CSRF)
    assert r.status_code == 413


def test_too_short_rejected(client, tmp_path: Path):
    short = tmp_path / "short.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                    str(short)], check=True, timeout=60)
    login(client, "arjun")
    with short.open("rb") as fh:
        r = client.post("/api/visits", data=form(), files={"audio": ("short.wav", fh, "audio/wav")}, headers=CSRF)
    assert r.status_code == 400 and "seconds" in r.json()["detail"]
