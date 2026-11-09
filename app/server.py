"""Nabz web app: one-tap visit recording for reps, market intelligence for leaders.

    .venv/Scripts/python -m uvicorn app.server:app --port 8000      (from the project root)

Contract: docs/API.md. Security model:
  * Sessions: a signed, expiring cookie (HMAC with the server secret, data/secret.key or
    NABZ_SECRET); login needs the person's PIN (PBKDF2 hash in config/workspace.yaml), with
    rate limiting. In production put SSO/OIDC in front; demo mode only lists who can log in.
  * Roles from config/workspace.yaml are enforced on every endpoint:
    rep = own visits; manager = team + intelligence; admin = also the audit log and erasure of
    flagged visits.
  * CSRF: every state-changing /api call must carry the header `X-Nabz: 1` (a cross-site form
    can't set it). Strict CSP and security headers on every response.
  * Uploads: size cap, type allowlist, ffprobe validation (one audio stream, duration bounds,
    file-only protocols) before anything is processed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import shutil
import sys
import tempfile
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import consent  # noqa: E402
import intel  # noqa: E402
import pipeline  # noqa: E402
from analysis import all_lens_ids, load_lens  # noqa: E402
from common import AUDIT_FILE, CALLS, DATA, audit, is_erased, read_json, secret_key, workspace, write_json  # noqa: E402
from set_pin import check_pin  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
COOKIE = "nabz_session"
CALL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
CHARTJS = "https://cdn.jsdelivr.net"

DATA.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("nabz")
if not log.handlers:
    _h = RotatingFileHandler(DATA / "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


def server_cfg() -> dict:
    return workspace().get("server") or {}


def auth_cfg() -> dict:
    return workspace().get("auth") or {}


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(_app):
    on_startup()
    yield
    on_shutdown()


app = FastAPI(title="Nabz", docs_url="/api/docs", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
workers = ThreadPoolExecutor(max_workers=int(server_cfg().get("workers", 3)))
_inflight: set[str] = set()
_inflight_lock = threading.Lock()


def submit(call_id: str) -> bool:
    """Queue a visit for processing unless it is already running in this server."""
    with _inflight_lock:
        if call_id in _inflight:
            return False
        _inflight.add(call_id)

    def job():
        try:
            pipeline.run(call_id)
        finally:
            with _inflight_lock:
                _inflight.discard(call_id)

    workers.submit(job)
    return True


# ---------------------------------------------------------------- security middleware

@app.middleware("http")
async def security(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("x-nabz") != "1":
            return JSONResponse({"detail": "missing X-Nabz header (CSRF protection)"}, status_code=403)
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' {CHARTJS}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
        "font-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------- sessions

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_session(handle: str) -> str:
    days = float(auth_cfg().get("session_days", 7))
    body = _b64(json.dumps({"h": handle, "exp": int(time.time() + days * 86400)}).encode())
    sig = _b64(hmac.new(secret_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_session(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    good = _b64(hmac.new(secret_key(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, good):
        return None
    try:
        data = json.loads(_unb64(body))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data.get("h")


def team() -> list[dict]:
    return workspace().get("team", [])


def current_user(request: Request) -> dict:
    handle = read_session(request.cookies.get(COOKIE))
    for m in team():
        if handle and m.get("handle") == handle:
            return m
    raise HTTPException(401, "login")


def require(user: dict, *roles: str) -> None:
    if user.get("role") not in roles:
        raise HTTPException(403, f"needs role {' or '.join(roles)}")


def can_see(user: dict, visit: dict) -> bool:
    return user["role"] in ("manager", "admin") or visit.get("rep_handle") == user["handle"]


_failures: dict[tuple, deque] = defaultdict(deque)


def _rate_limited(key: tuple) -> bool:
    window = 15 * 60
    q = _failures[key]
    while q and q[0] < time.time() - window:
        q.popleft()
    return len(q) >= int(auth_cfg().get("max_failed_logins", 5))


# ---------------------------------------------------------------- pages

def page(name: str) -> FileResponse:
    return FileResponse(STATIC / name, headers={"Cache-Control": "no-store"})


def _logged_in(request: Request) -> bool:
    return read_session(request.cookies.get(COOKIE)) is not None


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#4F46E5"/>'
           '<path d="M5 17h6l3-8 4 14 3-6h6" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')


@app.get("/favicon.ico")
def favicon():
    return Response(FAVICON, media_type="image/svg+xml")


@app.get("/")
def rep_page(request: Request):
    return page("rep.html") if _logged_in(request) else RedirectResponse("/login")


@app.get("/login")
def login_page():
    return page("login.html")


@app.get("/dashboard")
def dashboard_page(request: Request):
    return page("dashboard.html") if _logged_in(request) else RedirectResponse("/login")


@app.get("/visit/{call_id}")
def visit_page(call_id: str, request: Request):
    return page("visit.html") if _logged_in(request) else RedirectResponse("/login")


# ---------------------------------------------------------------- session API

@app.get("/api/health")
def health():
    return {"ok": True, "inflight": len(_inflight), "time": datetime.now().isoformat(timespec="seconds")}


@app.get("/api/login-options")
def login_options():
    """Before login, only demo mode reveals who can log in (names and roles; never handles' PINs)."""
    if not auth_cfg().get("demo_mode", False):
        return {"demo_mode": False, "people": []}
    return {"demo_mode": True, "people": [{"handle": m["handle"], "name": m["name"], "role": m["role"]} for m in team()]}


@app.post("/api/login")
async def login(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "bad request")
    handle, pin = str(body.get("handle", ""))[:40], str(body.get("pin", ""))[:12]
    ip = request.client.host if request.client else "?"
    key = (ip, handle)
    if _rate_limited(key):
        audit("session.login_blocked", actor=handle or "?", reason="rate limit")
        raise HTTPException(429, "Too many failed attempts. Wait 15 minutes.")
    user = next((m for m in team() if m.get("handle") == handle), None)
    if not user or not check_pin(pin, user.get("pin_hash")):
        _failures[key].append(time.time())
        audit("session.login_failed", actor=handle or "?")
        raise HTTPException(401, "Wrong name or PIN.")
    _failures.pop(key, None)
    resp = JSONResponse(public_user(user))
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(COOKIE, make_session(handle), httponly=True, samesite="lax", secure=secure,
                    max_age=int(float(auth_cfg().get("session_days", 7)) * 86400))
    audit("session.login", actor=handle)
    return resp


@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


def public_user(m: dict) -> dict:
    return {k: m.get(k) for k in ("name", "handle", "role", "language", "region")}


@app.get("/api/me")
def me(request: Request):
    return public_user(current_user(request))


@app.get("/api/config")
def config(request: Request):
    current_user(request)
    ws = workspace()
    lenses = []
    for lid in all_lens_ids():
        lens = load_lens(lid)
        lenses.append({"id": lid, "name": lens["name"], "score_label": lens["score_label"]})
    vocab = ws.get("vocabulary") or {}
    return {"company": ws.get("company"), "about": (ws.get("about") or "").strip(), "team": [public_user(m) for m in team()],
            "segments": ws.get("segments", []), "lenses": lenses, "products": vocab.get("products", []),
            "competitors": vocab.get("competitors", []),
            "limits": {k: server_cfg().get(k) for k in ("max_upload_mb", "max_minutes", "min_seconds")}}


# ---------------------------------------------------------------- visits

def _safe_json(path: Path):
    try:
        return read_json(path) if path.exists() else None
    except ValueError:
        return None


def visit_summary(folder: Path) -> dict | None:
    v = _safe_json(folder / "visit.json")
    if not v or is_erased(folder.name):
        return None
    st = _safe_json(folder / "status.json") or {"status": "queued", "stage": ""}
    a = _safe_json(folder / "analysis.json")
    t = _safe_json(folder / "transcript.json")
    c = _safe_json(folder / "consent.json") or {}
    lens = None
    if a and a.get("lens"):
        try:
            lens = load_lens(a["lens"])
        except (ValueError, SystemExit):
            lens = None
    stalled = False
    if st.get("status") in pipeline.PROCESSING and st.get("updated"):
        try:
            age = datetime.now() - datetime.fromisoformat(st["updated"])
            stalled = age > timedelta(minutes=float(server_cfg().get("stalled_after_minutes", 20)))
        except ValueError:
            pass
    note = (v.get("note") or "").lower()
    return {
        "call_id": folder.name, "account": v.get("account"), "contact": v.get("contact"), "segment": v.get("segment"),
        "region": v.get("region"), "rep": v.get("rep_name"), "rep_handle": v.get("rep_handle"),
        "recorded_at": (t or {}).get("recorded_at") or v.get("recorded_at") or v.get("created"),
        "duration_sec": (t or {}).get("duration_sec"),
        "status": st.get("status"), "stage": st.get("stage"), "error": st.get("error"), "updated": st.get("updated"),
        "stalled": stalled,
        "synthetic": bool(v.get("synthetic")) or folder.name.startswith("demo-") or "synthetic" in note,
        "note": v.get("note") or "",
        "consent_verified": c.get("verified"), "consent_reviewed": bool(c.get("review")),
        "lens": a.get("lens") if a else None, "lens_name": lens["name"] if lens else None,
        "score_label": lens["score_label"] if lens else None, "score": a.get("score") if a else None,
        "sentiment": a.get("sentiment") if a else None, "summary": a.get("summary") if a else None,
        "flags": len(a.get("compliance_flags", [])) if a else 0, "debrief": (folder / "debrief.ogg").exists(),
    }


def _all_visits(user: dict) -> list[dict]:
    out = []
    if CALLS.exists():
        for folder in CALLS.iterdir():
            if not folder.is_dir():
                continue
            s = visit_summary(folder)
            if s and can_see(user, s):
                out.append(s)
    return out


@app.post("/api/visits")
def create_visit(request: Request, audio: UploadFile = File(...), account: str = Form(...), contact: str = Form(""),
                 segment: str = Form("Other"), region: str = Form(""), consent_method: str = Form(...),
                 consent_confirmed: str = Form(""), note: str = Form(""), recorded_at: str = Form("")):
    """Sync endpoint (runs in the threadpool): validates and stores the upload, then queues it."""
    user = current_user(request)
    lim = pipeline.limits()
    max_bytes = int(lim["max_upload_mb"] * 1024 * 1024)
    if consent_confirmed.lower() not in ("true", "1", "yes", "on"):
        audit("visit.blocked_no_consent", actor=user["handle"])
        raise HTTPException(400, "Consent is required before a visit can be processed (DPDP Act 2023).")
    if consent_method not in ("verbal", "rep-confirmed", "written"):
        raise HTTPException(400, "consent_method must be verbal, rep-confirmed or written")
    account = account.strip()[:120]
    if not account:
        raise HTTPException(400, "Account (shop or organisation) is required.")
    if segment not in (workspace().get("segments") or [segment]):
        raise HTTPException(400, "Unknown segment.")
    suffix = Path(audio.filename or "visit.webm").suffix.lower() or ".webm"
    ctype = (audio.content_type or "").split(";")[0].strip().lower()
    if suffix not in pipeline.ALLOWED_EXTENSIONS or (ctype and not (ctype.startswith("audio/") or ctype in (
            "video/webm", "video/mp4", "application/ogg", "application/octet-stream"))):
        raise HTTPException(415, "Unsupported file type. Use m4a, mp3, ogg, opus, webm or wav.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="nabz-upload-"))
    tmp_path = tmp_dir / f"upload{suffix}"
    try:
        size = 0
        with tmp_path.open("wb") as out:
            while True:
                chunk = audio.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"The file is larger than {lim['max_upload_mb']:.0f} MB.")
                out.write(chunk)
        problem, _ = pipeline.probe_audio(tmp_path)
        if problem:
            raise HTTPException(400, problem)
        call_id = pipeline.create_visit(tmp_path, {
            "rep_handle": user["handle"], "account": account, "contact": contact.strip()[:120], "segment": segment,
            "region": region.strip()[:60], "consent_method": consent_method, "note": note.strip()[:500],
            "recorded_at": recorded_at.strip()[:40] or None})
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    submit(call_id)
    log.info("visit %s created by %s (%d bytes)", call_id, user["handle"], size)
    return {"call_id": call_id, "status": "queued"}


@app.get("/api/visits")
def list_visits(request: Request, scope: str = "mine", limit: int = 50):
    user = current_user(request)
    limit = max(1, min(int(limit), 200))
    out = [s for s in _all_visits(user) if scope != "mine" or s["rep_handle"] == user["handle"]]
    out.sort(key=lambda s: s.get("recorded_at") or "", reverse=True)
    return out[:limit]


def load_visit(request: Request, call_id: str) -> tuple[dict, Path, dict]:
    user = current_user(request)
    if not CALL_ID_RE.match(call_id) or ".." in call_id:
        raise HTTPException(404, "no such visit")
    folder = CALLS / call_id
    s = visit_summary(folder) if folder.is_dir() else None
    if not s:
        raise HTTPException(404, "no such visit")
    if not can_see(user, s):
        raise HTTPException(403, "reps can only see their own visits")
    return user, folder, s


def _events_for(call_id: str) -> list[dict]:
    events = []
    if AUDIT_FILE.exists():
        for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue  # a corrupt line must not break the visit page
            if e.get("call_id") == call_id:
                events.append({k: e.get(k) for k in ("ts", "actor", "action", "detail")})
    return events


@app.get("/api/visits/{call_id}")
def get_visit(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    t = _safe_json(folder / "transcript.json")
    spk = _safe_json(folder / "speakers.json") or {}
    names, sides = spk.get("names", {}), spk.get("sides", {})
    labels = spk.get("labels") or []
    segs = []
    for i, seg in enumerate((t or {}).get("segments", [])):
        lab = labels[i] if i < len(labels) else seg.get("speaker")
        segs.append({"i": seg["i"], "start": seg["start"], "end": seg["end"], "speaker_label": lab,
                     "speaker_name": (names.get(lab) or lab or "").split(" (")[0],
                     "side": sides.get(lab, "us" if lab == spk.get("rep") else "them"), "text": seg["text"]})
    a = _safe_json(folder / "analysis.json")
    lens = None
    if a and a.get("lens"):
        try:
            lens = load_lens(a["lens"])
        except (ValueError, SystemExit):
            lens = None
    c = _safe_json(folder / "consent.json")
    if c:
        c = {k: c.get(k) for k in ("method", "confirmed_by", "subject", "recorded_at", "purpose", "verified",
                                   "verified_segment", "spoken_refusal", "review")}
    return {
        "visit": s, "consent": c,
        "transcript": ({k: t.get(k) for k in ("language", "languages", "engine", "model", "diarized", "recorded_at")}
                       | {"segments": segs}) if t else None,
        "redactions": {"counts": (_safe_json(folder / "redactions.json") or {}).get("counts", {})},
        "analysis": a, "metrics": _safe_json(folder / "metrics.json"),
        "notes_md": (folder / "notes.md").read_text(encoding="utf-8") if (folder / "notes.md").exists() else None,
        "followup": _safe_json(folder / "followup.json"), "crm_proposal": _safe_json(folder / "crm_proposal.json"),
        "lens": {"id": lens["id"], "name": lens["name"], "score_label": lens["score_label"], "checklist": lens.get("checklist", {})} if lens else None,
        "audit": _events_for(call_id),
        "permissions": permissions(user, s, a),
        "assets": {"debrief": f"/api/visits/{call_id}/debrief.ogg" if (folder / "debrief.ogg").exists() else None,
                   "scorecard": f"/api/visits/{call_id}/scorecard.png" if (folder / "scorecard.png").exists() else None},
    }


def permissions(user: dict, s: dict, a: dict | None) -> dict:
    manager = user["role"] in ("manager", "admin")
    own = s.get("rep_handle") == user["handle"]
    flagged = bool(a and a.get("compliance_flags"))
    low = bool(a and (a.get("score") or 0) < 40)
    return {
        "approve": manager or (own and not flagged and not low),
        "approve_reason": None if manager or (own and not flagged and not low) else
        "A manager must approve visits with compliance flags or a score below 40.",
        "erase": user["role"] == "admin" or ((manager or own) and not flagged),
        "erase_reason": None if user["role"] == "admin" or ((manager or own) and not flagged) else
        "Visits with compliance flags can only be erased by an admin (they are evidence).",
        "retry": manager or own,
        "confirm_consent": manager,
    }


@app.get("/api/visits/{call_id}/debrief.ogg")
def debrief_file(call_id: str, request: Request):
    _, folder, _ = load_visit(request, call_id)
    p = folder / "debrief.ogg"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/ogg")


@app.get("/api/visits/{call_id}/scorecard.png")
def scorecard_file(call_id: str, request: Request):
    _, folder, _ = load_visit(request, call_id)
    p = folder / "scorecard.png"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.post("/api/visits/{call_id}/approve")
async def approve(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    a = _safe_json(folder / "analysis.json")
    perm = permissions(user, s, a)
    if not perm["approve"]:
        raise HTTPException(403, perm["approve_reason"] or "not allowed")
    try:
        body = await request.json()
    except ValueError:
        body = {}
    self_approved = s.get("rep_handle") == user["handle"]
    applied = []
    now = datetime.now().isoformat(timespec="seconds")
    prop_path = folder / "crm_proposal.json"
    if body.get("crm", True) and prop_path.exists():
        prop = read_json(prop_path)
        if prop.get("status") == "proposed":
            import argparse as _ap

            import crm
            db = crm.load()
            ns = _ap.Namespace(account=prop.get("account") or s["account"], contact=prop.get("contact"), owner=prop.get("owner"),
                               stage=prop.get("stage") if prop.get("stage") in crm.STAGES else None, value=prop.get("value_inr"),
                               next_step=prop.get("next_step"), next_date=prop.get("next_date"), dry_run=False, by=user["handle"],
                               call_id=call_id)
            crm.cmd_upsert(db, ns)
            crm.cmd_log(db, _ap.Namespace(account=ns.account, type="meeting", call_id=call_id,
                                          summary=((a or {}).get("summary") or "")[:200]))
            write_json(crm.CRM_FILE, db)
            prop.update({"status": "approved", "approved_by": user["name"], "approved_at": now, "self_approved": self_approved})
            write_json(prop_path, prop)
            audit("crm.upsert", actor=user["handle"], call_id=call_id, account=ns.account, stage=ns.stage,
                  next_date=ns.next_date, self_approved=self_approved)
            applied.append("crm")
    fu_path = folder / "followup.json"
    if body.get("followup", True) and fu_path.exists():
        fu = read_json(fu_path)
        if fu.get("status") == "drafted":
            fu.update({"status": "sent", "approved_by": user["name"], "approved_at": now, "self_approved": self_approved})
            write_json(fu_path, fu)
            audit("followup.approved", actor=user["handle"], call_id=call_id, self_approved=self_approved,
                  note="marked sent (no mail server in demo)")
            applied.append("followup")
    return {"ok": True, "applied": applied, "self_approved": self_approved}


@app.post("/api/visits/{call_id}/reject")
def reject(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    if not (user["role"] in ("manager", "admin") or s.get("rep_handle") == user["handle"]):
        raise HTTPException(403)
    for name, key in (("crm_proposal.json", "proposed"), ("followup.json", "drafted")):
        p = folder / name
        if p.exists():
            d = read_json(p)
            if d.get("status") == key:
                d.update({"status": "rejected", "rejected_by": user["name"], "rejected_at": datetime.now().isoformat(timespec="seconds")})
                write_json(p, d)
    audit("proposal.rejected", actor=user["handle"], call_id=call_id)
    return {"ok": True}


@app.post("/api/visits/{call_id}/erase")
def erase(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    perm = permissions(user, s, _safe_json(folder / "analysis.json"))
    if not perm["erase"]:
        raise HTTPException(403, perm["erase_reason"] or "not allowed")
    summary = consent.erase(call_id, user["handle"], "consent withdrawn")
    log.info("visit %s erased by %s: %s", call_id, user["handle"], summary)
    return {"ok": True, "summary": summary}


@app.post("/api/visits/{call_id}/retry")
def retry(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    if not permissions(user, s, None)["retry"]:
        raise HTTPException(403)
    if s["status"] == "needs_consent_review":
        raise HTTPException(409, "This visit is waiting for a manager to review consent.")
    if s["status"] not in ("error",) and not s["stalled"]:
        raise HTTPException(409, "This visit is not stuck.")
    pipeline.set_status(call_id, "queued")
    audit("visit.retry", actor=user["handle"], call_id=call_id)
    submit(call_id)
    return {"ok": True}


@app.post("/api/visits/{call_id}/confirm-consent")
def confirm_consent(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    require(user, "manager", "admin")
    if s["status"] != "needs_consent_review":
        raise HTTPException(409, "This visit is not waiting for a consent review.")
    consent.confirm(call_id, user["handle"])
    pipeline.set_status(call_id, "queued")
    submit(call_id)
    return {"ok": True}


# ---------------------------------------------------------------- intelligence, trust, cost, audit

@app.get("/api/intel")
def get_intel(request: Request, days: int = 30, region: str = "All", segment: str = "All"):
    user = current_user(request)
    require(user, "manager", "admin")
    return JSONResponse(json.loads(json.dumps(intel.build(max(1, min(days, 3650)), region, segment), default=str)))


@app.get("/api/trust")
def trust(request: Request):
    user = current_user(request)
    from audit import verify

    ok, msg = verify()
    p = workspace().get("privacy") or {}
    base = {"audit_ok": ok,
            "data_region": "Speech: Gnani batch results served from AWS ap-south-1 (Mumbai). "
                           "Analysis: Anthropic API (outside India, on redacted text).",
            "retention": {"audio_days": p.get("retain_audio_days"), "transcripts_days": p.get("retain_transcripts_days")}}
    if user["role"] == "rep":
        return base
    anchor = _safe_json(DATA / "audit.anchor") or {}
    k = intel.build(None)["kpis"]
    return base | {"audit_message": msg, "audit_events": anchor.get("count"), "audit_head": (anchor.get("head") or "")[:16],
                   "consent_rate": k.get("consent_rate"), "pii_redacted": k.get("pii_redacted"),
                   "quotes_verified": k.get("quotes_verified")}


@app.get("/api/cost")
def cost(request: Request, days: int = 30):
    user = current_user(request)
    require(user, "manager", "admin")
    from datetime import timezone
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 3650)))
    rows = []
    usage = DATA / "usage.jsonl"
    if usage.exists():
        for line in usage.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if datetime.fromisoformat(r["ts"]) >= since:
                    rows.append(r)
            except (ValueError, KeyError):
                continue
    stt = sum(r.get("seconds", 0) for r in rows if r["kind"] == "stt") / 60
    tts = sum(r.get("chars", 0) for r in rows if r["kind"] == "tts")
    tok = sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) + r.get("cache_write", 0) + r.get("cache_read", 0)
              for r in rows if r["kind"] == "llm")
    visits = len({r.get("call_id") for r in rows if r.get("call_id")}) or 1
    rates = workspace().get("rates_inr") or {}
    inr = None
    # LLM: the exact per-call cost logged by tools/llm.py at list prices; token-rate estimate only for older rows.
    llm_rows = [r for r in rows if r["kind"] == "llm"]
    llm_inr = sum(r["cost_inr"] if "cost_inr" in r else
                  (r.get("input_tokens", 0) + r.get("output_tokens", 0)) / 1000 * rates.get("llm_per_1k_tokens", 0)
                  for r in llm_rows)
    if any(rates.values()):
        inr = round(stt * rates.get("prisma_per_min", 0) + tts / 1000 * rates.get("timbre_per_1k_chars", 0) + llm_inr, 2)
    return {"stt_minutes": round(stt, 1), "tts_chars": tts, "llm_tokens": tok, "inr": inr, "llm_inr": round(llm_inr, 2),
            "basis": "estimates: Prisma Rs 27/hr reseller price, Timbre proxied by Sarvam TTS, LLM at Anthropic list prices",
            "per_visit": {"stt_minutes": round(stt / visits, 2), "tts_chars": round(tts / visits), "llm_tokens": round(tok / visits),
                          "inr": round(inr / visits, 2) if inr is not None else None}, "visits": visits}


@app.get("/api/audit")
def audit_log(request: Request, limit: int = 100):
    user = current_user(request)
    require(user, "admin")
    from audit import read_events

    events = read_events()[-max(1, min(limit, 1000)):]
    return list(reversed(events))


# ---------------------------------------------------------------- startup: requeue + retention

def _retention_loop(stop: threading.Event) -> None:
    import retention

    hours = float(server_cfg().get("retention_interval_hours", 6))
    while not stop.is_set():
        try:
            removed = retention.apply()
            if removed:
                log.info("retention removed %d item(s)", len(removed))
        except Exception:  # noqa: BLE001
            log.exception("retention failed")
        stop.wait(hours * 3600)


_stop = threading.Event()


def on_startup() -> None:
    secret_key()  # make sure the secret exists before the first request
    pending = pipeline.pending_visits()
    for call_id in pending:
        pipeline.safe_status(call_id, "queued")
        submit(call_id)
    if pending:
        log.info("requeued %d interrupted visit(s): %s", len(pending), ", ".join(pending))
        audit("server.requeued", count=len(pending))
    threading.Thread(target=_retention_loop, args=(_stop,), daemon=True, name="retention").start()


def on_shutdown() -> None:
    _stop.set()
