"""Authentication, sessions, CSRF and role checks (audit findings C1, M7, IDOR)."""
from conftest import CSRF, login, make_visit


def test_unauthenticated_config_is_hidden(client):
    assert client.get("/api/config").status_code == 401
    opts = client.get("/api/login-options").json()
    assert opts["demo_mode"] is True
    assert {"handle", "name", "role"} == set(opts["people"][0])  # no PIN hashes, regions or languages


def test_forged_and_tampered_cookies_are_rejected(client):
    client.cookies.set("nabz_session", "arjun")  # the old, unsigned format
    assert client.get("/api/me").status_code == 401
    client.cookies.clear()
    assert login(client, "arjun").status_code == 200
    good = client.cookies.get("nabz_session")
    body, sig = good.rsplit(".", 1)
    client.cookies.clear()
    client.cookies.set("nabz_session", body + "." + ("A" if sig[0] != "A" else "B") + sig[1:])
    assert client.get("/api/me").status_code == 401
    import base64
    import json
    forged = base64.urlsafe_b64encode(json.dumps({"h": "meera", "exp": 9999999999}).encode()).decode().rstrip("=")
    client.cookies.clear()
    client.cookies.set("nabz_session", forged + "." + sig)  # reuse a real signature on an admin body
    assert client.get("/api/me").status_code == 401


def test_wrong_pin_and_rate_limit(client):
    assert login(client, "sneha", "0000").status_code == 401
    assert login(client, "sneha").status_code == 200
    for _ in range(5):
        login(client, "ravi", "9999")
    assert login(client, "ravi").status_code == 429  # even the right PIN is blocked for 15 minutes


def test_csrf_header_required(client):
    assert client.post("/api/login", json={"handle": "arjun", "pin": "1234"}).status_code == 403
    assert login(client, "arjun").status_code == 200
    assert client.post("/api/logout").status_code == 403
    assert client.post("/api/logout", headers=CSRF).status_code == 200


def test_roles_enforced(client):
    login(client, "arjun")
    assert client.get("/api/intel").status_code == 403
    assert client.get("/api/audit").status_code == 403
    assert "audit_head" not in client.get("/api/trust").json()  # reps get only non-sensitive trust fields
    login(client, "kavita")
    assert client.get("/api/intel").status_code == 200
    assert client.get("/api/audit").status_code == 403  # managers: not the full audit log
    login(client, "meera")
    assert client.get("/api/audit").status_code == 200


def test_reps_cannot_read_other_reps_visits(client):
    make_visit("auth-idor-1", rep="arjun")
    login(client, "sneha")
    assert client.get("/api/visits/auth-idor-1").status_code == 403
    assert client.post("/api/visits/auth-idor-1/erase", headers=CSRF).status_code == 403
    assert all(v["call_id"] != "auth-idor-1" for v in client.get("/api/visits?scope=all").json())
    login(client, "kavita")
    assert client.get("/api/visits/auth-idor-1").status_code == 200
    assert client.get("/api/visits/..%5C..%5Cconfig").status_code in (404, 405)


def test_security_headers(client):
    r = client.get("/login")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
