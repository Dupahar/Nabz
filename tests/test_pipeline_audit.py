"""The audit log detects edits, truncation and forged anchors (M3). Runs on a private copy."""
import pytest


@pytest.fixture()
def private_log(tmp_path, monkeypatch):
    import audit
    import common

    log, anchor = tmp_path / "audit.jsonl", tmp_path / "audit.anchor"
    for mod in (common, audit):
        monkeypatch.setattr(mod, "AUDIT_FILE", log)
        monkeypatch.setattr(mod, "AUDIT_ANCHOR", anchor)
    for i in range(5):
        common.audit("test.event", actor="t", n=i)
    return log, anchor


def test_intact_log_verifies(private_log):
    import audit

    ok, msg = audit.verify()
    assert ok, msg


def test_edit_is_detected(private_log):
    import audit

    log, _ = private_log
    lines = log.read_bytes().splitlines()
    lines[2] = lines[2].replace(b'"n": 2', b'"n": 7')
    log.write_bytes(b"\n".join(lines) + b"\n")
    ok, msg = audit.verify()
    assert not ok and "broken" in msg


def test_truncation_is_detected(private_log):
    import audit

    log, _ = private_log
    lines = log.read_bytes().splitlines()
    log.write_bytes(b"\n".join(lines[:-2]) + b"\n")
    ok, msg = audit.verify()
    assert not ok and "truncated" in msg


def test_forged_anchor_is_detected(private_log):
    import json

    import audit

    log, anchor = private_log
    lines = log.read_bytes().splitlines()
    log.write_bytes(b"\n".join(lines[:-1]) + b"\n")
    a = json.loads(anchor.read_text())
    a["count"] -= 1  # pretend the log was always one shorter, without the secret to re-sign
    anchor.write_text(json.dumps(a))
    ok, msg = audit.verify()
    assert not ok and "signature" in msg
