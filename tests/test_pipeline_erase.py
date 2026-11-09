"""Erasure (H4), pseudonymised audit names, and the M6 rule on flagged visits."""
import json

import pytest

from conftest import CSRF, login, make_visit, write


def test_erase_purges_everything_and_leaves_a_tombstone():
    import consent
    from common import CALLS, CRM_FILE, DATA, ERASED_FILE, CallErased, write_json

    cid = "erase-1"
    folder = make_visit(cid, segments=[{"i": 0, "start": 0, "end": 3, "speaker": "S1", "text": "namaste"}])
    write(CRM_FILE, {"accounts": {
        "Only This Visit": {"created_by_call": cid, "history": [{"call_id": cid, "type": "meeting"}], "emails": []},
        "Shared Account": {"history": [{"call_id": cid, "type": "meeting"}, {"call_id": "other", "type": "meeting"}],
                           "emails": [{"call_id": cid, "status": "sent"}]}}})
    usage = DATA / "usage.jsonl"
    usage.write_text(json.dumps({"kind": "stt", "call_id": cid}) + "\n" + json.dumps({"kind": "stt", "call_id": "other"}) + "\n")

    summary = consent.erase(cid, "kavita")
    assert summary["folder_deleted"] and not folder.exists()
    crm = json.loads(CRM_FILE.read_text())["accounts"]
    assert "Only This Visit" not in crm
    assert crm["Shared Account"]["history"] == [{"call_id": "other", "type": "meeting"}]
    assert crm["Shared Account"]["emails"] == []
    assert [json.loads(x)["call_id"] for x in usage.read_text().splitlines()] == ["other"]
    tomb = [json.loads(x) for x in ERASED_FILE.read_text().splitlines()]
    assert any(t["call_id"] == cid and t["subject"].startswith("h:") for t in tomb)

    # A pipeline still running must not be able to bring the folder back.
    with pytest.raises(CallErased):
        write_json(CALLS / cid / "analysis.json", {"x": 1})
    assert not (CALLS / cid).exists()


def test_audit_never_stores_customer_names():
    import consent
    from common import AUDIT_FILE

    make_visit("erase-2")
    consent.record("erase-2", "verbal", "arjun", "Priya Shah")
    consent.erase("erase-2", "arjun")
    assert "Priya" not in AUDIT_FILE.read_text(encoding="utf-8")


def test_rep_cannot_erase_or_self_approve_flagged_visit(client):
    folder = make_visit("erase-flagged", rep="arjun")
    write(folder / "analysis.json", {"score": 25, "compliance_flags": [{"rule": "inducement", "severity": "high"}]})
    write(folder / "crm_proposal.json", {"status": "proposed", "account": "Test Store"})
    login(client, "arjun")
    assert client.post("/api/visits/erase-flagged/erase", headers=CSRF).status_code == 403
    assert client.post("/api/visits/erase-flagged/approve", json={}, headers=CSRF).status_code == 403
    login(client, "kavita")
    assert client.post("/api/visits/erase-flagged/erase", headers=CSRF).status_code == 403  # managers neither
    login(client, "meera")
    assert client.post("/api/visits/erase-flagged/erase", headers=CSRF).status_code == 200
