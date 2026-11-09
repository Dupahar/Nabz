"""Restart recovery (H9), never-stuck processing, spoken-consent review (H5), retention."""
from datetime import datetime, timedelta

from conftest import make_visit, write

CONSENTED = [
    {"i": 0, "start": 0.0, "end": 4.0, "speaker": "S1", "text": "Namaste ji, main ye baat training ke liye record kar raha hoon, theek hai?"},
    {"i": 1, "start": 4.0, "end": 6.0, "speaker": "S2", "text": "Haan haan, kar lo."},
    {"i": 2, "start": 6.0, "end": 9.0, "speaker": "S1", "text": "Maggi ka stock kaisa hai?"},
]
NO_CONSENT = [
    {"i": 0, "start": 0.0, "end": 4.0, "speaker": "S1", "text": "Namaste ji, Maggi ka stock kaisa hai?"},
    {"i": 1, "start": 4.0, "end": 6.0, "speaker": "S2", "text": "Theek hai, do carton bhej do."},
]


def test_interrupted_visits_are_requeued_on_startup(monkeypatch):
    import app.server as server
    import pipeline

    make_visit("rq-1", status="transcribing")
    make_visit("rq-2", status="done")
    seen = []
    monkeypatch.setattr(server, "submit", lambda cid: seen.append(cid) or True)
    monkeypatch.setattr(server, "_retention_loop", lambda stop: None)
    server.on_startup()
    assert "rq-1" in seen and "rq-2" not in seen
    assert "rq-1" in pipeline.pending_visits()  # status reset to queued, still pending until processed


def test_crash_in_a_step_never_leaves_a_visit_stuck(monkeypatch):
    import llm
    import pipeline
    from common import CALLS, read_json

    make_visit("rq-crash", status="queued", method="verbal", segments=CONSENTED)

    def boom(*a, **k):
        raise SystemExit("helper called sys.exit")

    monkeypatch.setattr(llm, "analyse", boom)
    pipeline.run("rq-crash")
    st = read_json(CALLS / "rq-crash" / "status.json")
    assert st["status"] == "error"
    assert read_json(CALLS / "rq-crash" / "consent.json")["verified"] is True


def test_verbal_consent_missing_holds_the_visit(monkeypatch):
    import llm
    import pipeline
    from common import CALLS, read_json

    called = []
    monkeypatch.setattr(llm, "analyse", lambda *a, **k: called.append(1))
    make_visit("rq-noconsent", status="queued", method="verbal", segments=NO_CONSENT)
    pipeline.run("rq-noconsent")
    assert read_json(CALLS / "rq-noconsent" / "status.json")["status"] == "needs_consent_review"
    assert read_json(CALLS / "rq-noconsent" / "consent.json")["verified"] is False
    assert not called  # no AI analysis before a manager reviews


def test_manager_confirmation_resumes_processing(client, monkeypatch):
    import app.server as server
    from conftest import CSRF, login

    make_visit("rq-review", status="needs_consent_review", method="verbal", segments=NO_CONSENT)
    queued = []
    monkeypatch.setattr(server, "submit", lambda cid: queued.append(cid) or True)
    login(client, "arjun")
    assert client.post("/api/visits/rq-review/confirm-consent", headers=CSRF).status_code == 403
    login(client, "kavita")
    assert client.post("/api/visits/rq-review/confirm-consent", headers=CSRF).status_code == 200
    assert queued == ["rq-review"]
    c = client.get("/api/visits/rq-review").json()["consent"]
    assert c["review"]["confirmed_by"] == "kavita"


def test_retention_deletes_old_raw_audio_but_keeps_redacted_transcript():
    import retention
    from common import CALLS

    old = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
    folder = make_visit("ret-1", status="done", segments=CONSENTED, recorded_at=old)
    (folder / "audio.ogg").write_bytes(b"x")
    write(folder / "transcript.raw.json", {"raw": True})
    busy = make_visit("ret-busy", status="transcribing", segments=CONSENTED, recorded_at=old)
    (busy / "audio.ogg").write_bytes(b"x")

    removed = retention.apply()
    assert "ret-1/audio.ogg" in removed and "ret-1/transcript.raw.json" in removed
    assert not (folder / "audio.ogg").exists() and (folder / "transcript.json").exists()
    assert (busy / "audio.ogg").exists()  # never touches a visit still being processed
    assert (CALLS / "ret-1").exists()
