"""Nabz web app: one-tap visit recording for reps, market intelligence for leaders.

    .venv/Scripts/python -m uvicorn app.server:app --port 8000      (from the project root)

Contract: docs/API.md. Roles from config/workspace.yaml are enforced on every endpoint:
rep = own visits; manager = team + intelligence; admin = also audit log and erasure.
Login is a demo picker (cookie); swap for SSO/OIDC in production.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import intel  # noqa: E402
import pipeline  # noqa: E402
from analysis import all_lens_ids, load_lens  # noqa: E402
from common import AUDIT_FILE, CALLS, DATA, audit, read_json, workspace, write_json  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="Nabz", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
workers = ThreadPoolExecutor(max_workers=3)


# ---------------------------------------------------------------- auth

def team() -> list[dict]:
    return workspace().get("team", [])


def current_user(request: Request) -> dict:
    handle = request.cookies.get("nabz_user")
    for m in team():
        if m.get("handle") == handle:
            return m
    raise HTTPException(401, "login")


def require(user: dict, *roles: str) -> None:
    if user.get("role") not in roles:
        raise HTTPException(403, f"needs role {' or '.join(roles)}")


def can_see(user: dict, visit: dict) -> bool:
    return user["role"] in ("manager", "admin") or visit.get("rep_handle") == user["handle"]


# ---------------------------------------------------------------- pages

def page(name: str) -> FileResponse:
    return FileResponse(STATIC / name, headers={"Cache-Control": "no-store"})


@app.get("/")
def rep_page(request: Request):
    if not request.cookies.get("nabz_user"):
        return RedirectResponse("/login")
    return page("rep.html")


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#4F46E5"/>'
           '<path d="M5 17h6l3-8 4 14 3-6h6" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')


@app.get("/favicon.ico")
def favicon():
    from fastapi.responses import Response
    return Response(FAVICON, media_type="image/svg+xml")


@app.get("/login")
def login_page():
    return page("login.html")


@app.get("/dashboard")
def dashboard_page(request: Request):
    if not request.cookies.get("nabz_user"):
        return RedirectResponse("/login")
    return page("dashboard.html")


@app.get("/visit/{call_id}")
def visit_page(call_id: str, request: Request):
    if not request.cookies.get("nabz_user"):
        return RedirectResponse("/login")
    return page("visit.html")


# ---------------------------------------------------------------- session

@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    for m in team():
        if m.get("handle") == body.get("handle"):
            resp = JSONResponse(public_user(m))
            resp.set_cookie("nabz_user", m["handle"], httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
            audit("session.login", actor=m["handle"])
            return resp
    raise HTTPException(404, "no such user")


@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("nabz_user")
    return resp


def public_user(m: dict) -> dict:
    return {k: m.get(k) for k in ("name", "handle", "role", "language", "region")}


@app.get("/api/me")
def me(request: Request):
    return public_user(current_user(request))


@app.get("/api/config")
def config():
    ws = workspace()
    lenses = []
    for lid in all_lens_ids():
        lens = load_lens(lid)
        lenses.append({"id": lid, "name": lens["name"], "score_label": lens["score_label"]})
    vocab = ws.get("vocabulary") or {}
    return {"company": ws.get("company"), "about": (ws.get("about") or "").strip(), "team": [public_user(m) for m in team()],
            "segments": ws.get("segments", []), "lenses": lenses, "products": vocab.get("products", []),
            "competitors": vocab.get("competitors", [])}


# ---------------------------------------------------------------- visits

def visit_summary(folder: Path) -> dict | None:
    vpath = folder / "visit.json"
    if not vpath.exists():
        return None
    v = read_json(vpath)
    st = read_json(folder / "status.json") if (folder / "status.json").exists() else {"status": "queued", "stage": ""}
    a = read_json(folder / "analysis.json") if (folder / "analysis.json").exists() else None
    t = read_json(folder / "transcript.json") if (folder / "transcript.json").exists() else None
    lens = load_lens(a["lens"]) if a and a.get("lens") else None
    return {
        "call_id": folder.name, "account": v.get("account"), "contact": v.get("contact"), "segment": v.get("segment"),
        "region": v.get("region"), "rep": v.get("rep_name"), "rep_handle": v.get("rep_handle"),
        "recorded_at": (t or {}).get("recorded_at") or v.get("created"), "duration_sec": (t or {}).get("duration_sec"),
        "status": st.get("status"), "stage": st.get("stage"), "error": st.get("error"),
        "lens": a.get("lens") if a else None, "lens_name": lens["name"] if lens else None,
        "score_label": lens["score_label"] if lens else None, "score": a.get("score") if a else None,
        "sentiment": a.get("sentiment") if a else None, "summary": a.get("summary") if a else None,
        "flags": len(a.get("compliance_flags", [])) if a else 0, "debrief": (folder / "debrief.ogg").exists(),
    }


@app.post("/api/visits")
async def create_visit(request: Request, audio: UploadFile = File(...), account: str = Form(...), contact: str = Form(""),
                       segment: str = Form("Other"), region: str = Form(""), consent_method: str = Form(...),
                       consent_confirmed: str = Form(""), note: str = Form("")):
    user = current_user(request)
    if consent_confirmed.lower() not in ("true", "1", "yes", "on"):
        audit("visit.blocked_no_consent", actor=user["handle"], account=account)
        raise HTTPException(400, "Consent is required before a visit can be processed (DPDP Act 2023).")
    if consent_method not in ("verbal", "rep-confirmed", "written"):
        raise HTTPException(400, "consent_method must be verbal, rep-confirmed or written")
    suffix = Path(audio.filename or "visit.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        call_id = pipeline.create_visit(tmp_path, {"rep_handle": user["handle"], "account": account.strip(), "contact": contact.strip(),
                                                   "segment": segment, "region": region.strip(), "consent_method": consent_method,
                                                   "note": note.strip()})
    finally:
        tmp_path.unlink(missing_ok=True)
    workers.submit(pipeline.run, call_id)
    return {"call_id": call_id, "status": "queued"}


@app.get("/api/visits")
def list_visits(request: Request, scope: str = "mine", limit: int = 50):
    user = current_user(request)
    out = []
    if CALLS.exists():
        for folder in CALLS.iterdir():
            s = visit_summary(folder)
            if not s or not can_see(user, s):
                continue
            if scope == "mine" and s["rep_handle"] != user["handle"]:
                continue
            out.append(s)
    out.sort(key=lambda s: s.get("recorded_at") or "", reverse=True)
    return out[:limit]


def load_visit(request: Request, call_id: str) -> tuple[dict, Path, dict]:
    user = current_user(request)
    folder = CALLS / call_id
    s = visit_summary(folder) if folder.is_dir() else None
    if not s:
        raise HTTPException(404, "no such visit")
    if not can_see(user, s):
        raise HTTPException(403, "reps can only see their own visits")
    return user, folder, s


@app.get("/api/visits/{call_id}")
def get_visit(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)

    def j(name: str):
        p = folder / name
        return read_json(p) if p.exists() else None

    t = j("transcript.json")
    spk = j("speakers.json") or {}
    names, sides = spk.get("names", {}), spk.get("sides", {})
    labels = spk.get("labels") or []
    segs = []
    for i, seg in enumerate((t or {}).get("segments", [])):
        lab = labels[i] if i < len(labels) else seg.get("speaker")
        segs.append({"i": seg["i"], "start": seg["start"], "end": seg["end"], "speaker_label": lab,
                     "speaker_name": (names.get(lab) or lab or "").split(" (")[0], "side": sides.get(lab, "us" if lab == spk.get("rep") else "them"),
                     "text": seg["text"]})
    a = j("analysis.json")
    lens = load_lens(a["lens"]) if a and a.get("lens") else None
    events = []
    if AUDIT_FILE.exists():
        for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if e.get("call_id") == call_id:
                events.append({k: e.get(k) for k in ("ts", "actor", "action", "detail")})
    fu = j("followup.json")
    return {
        "visit": s, "consent": j("consent.json"),
        "transcript": {k: (t or {}).get(k) for k in ("language", "languages", "engine", "model", "diarized")} | {"segments": segs} if t else None,
        "redactions": {"counts": (j("redactions.json") or {}).get("counts", {})},
        "analysis": a, "metrics": j("metrics.json"),
        "notes_md": (folder / "notes.md").read_text(encoding="utf-8") if (folder / "notes.md").exists() else None,
        "followup": fu, "crm_proposal": j("crm_proposal.json"),
        "lens": {"id": lens["id"], "name": lens["name"], "score_label": lens["score_label"], "checklist": lens.get("checklist", {})} if lens else None,
        "audit": events,
        "assets": {"debrief": f"/api/visits/{call_id}/debrief.ogg" if (folder / "debrief.ogg").exists() else None,
                   "scorecard": f"/api/visits/{call_id}/scorecard.png" if (folder / "scorecard.png").exists() else None},
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
    if user["role"] not in ("manager", "admin") and s["rep_handle"] != user["handle"]:
        raise HTTPException(403, "only the rep or a manager can approve")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    applied = []
    prop_path = folder / "crm_proposal.json"
    if body.get("crm", True) and prop_path.exists():
        prop = read_json(prop_path)
        if prop.get("status") == "proposed":
            import crm
            db = crm.load()
            import argparse as _ap
            ns = _ap.Namespace(account=prop.get("account") or s["account"], contact=prop.get("contact"), owner=prop.get("owner"),
                               stage=prop.get("stage") if prop.get("stage") in crm.STAGES else None, value=prop.get("value_inr"),
                               next_step=prop.get("next_step"), next_date=prop.get("next_date"), dry_run=False, by=user["handle"])
            crm.cmd_upsert(db, ns)
            crm.cmd_log(db, _ap.Namespace(account=ns.account, type="meeting", call_id=call_id, summary=(read_json(folder / "analysis.json").get("summary") or "")[:200]))
            write_json(crm.CRM_FILE, db)
            prop.update({"status": "approved", "approved_by": user["name"], "approved_at": datetime.now().isoformat(timespec="seconds")})
            write_json(prop_path, prop)
            audit("crm.upsert", actor=user["handle"], call_id=call_id, account=ns.account, stage=ns.stage, next_date=ns.next_date)
            applied.append("crm")
    fu_path = folder / "followup.json"
    if body.get("followup", True) and fu_path.exists():
        fu = read_json(fu_path)
        if fu.get("status") == "drafted":
            fu.update({"status": "sent", "approved_by": user["name"], "approved_at": datetime.now().isoformat(timespec="seconds")})
            write_json(fu_path, fu)
            audit("followup.approved", actor=user["handle"], call_id=call_id, note="marked sent (no mail server in demo)")
            applied.append("followup")
    return {"ok": True, "applied": applied}


@app.post("/api/visits/{call_id}/reject")
def reject(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    for name, key in (("crm_proposal.json", "proposed"), ("followup.json", "drafted")):
        p = folder / name
        if p.exists():
            d = read_json(p)
            if d.get("status") == key:
                d.update({"status": "rejected", "rejected_by": user["name"]})
                write_json(p, d)
    audit("proposal.rejected", actor=user["handle"], call_id=call_id)
    return {"ok": True}


@app.post("/api/visits/{call_id}/erase")
def erase(call_id: str, request: Request):
    user, folder, s = load_visit(request, call_id)
    if user["role"] not in ("manager", "admin") and s["rep_handle"] != user["handle"]:
        raise HTTPException(403)
    from consent import withdraw
    withdraw(call_id, user["handle"])
    shutil.rmtree(folder, ignore_errors=True)  # web app: no tombstone folder; the audit log keeps the record
    return {"ok": True}


# ---------------------------------------------------------------- intelligence, trust, cost, audit

@app.get("/api/intel")
def get_intel(request: Request, days: int = 30, region: str = "All", segment: str = "All"):
    user = current_user(request)
    require(user, "manager", "admin")
    return JSONResponse(json.loads(json.dumps(intel.build(days, region, segment), default=str)))


@app.get("/api/trust")
def trust(request: Request):
    current_user(request)
    from audit import verify
    ok, msg = verify()
    k = intel.build(None)["kpis"]
    lines = AUDIT_FILE.read_bytes().splitlines() if AUDIT_FILE.exists() else []
    import hashlib
    head = hashlib.sha256(lines[-1]).hexdigest()[:16] if lines else None
    p = workspace().get("privacy") or {}
    return {"audit_ok": ok, "audit_message": msg, "audit_events": len(lines), "audit_head": head,
            "consent_rate": k["consent_rate"], "pii_redacted": k["pii_redacted"], "quotes_verified": k["quotes_verified"],
            "data_region": "Gnani batch results: AWS ap-south-1 (Mumbai)",
            "retention": {"audio_days": p.get("retain_audio_days"), "transcripts_days": p.get("retain_transcripts_days")}}


@app.get("/api/cost")
def cost(request: Request, days: int = 30):
    user = current_user(request)
    require(user, "manager", "admin")
    from datetime import timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    usage = DATA / "usage.jsonl"
    if usage.exists():
        for line in usage.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if datetime.fromisoformat(r["ts"]) >= since:
                rows.append(r)
    stt = sum(r.get("seconds", 0) for r in rows if r["kind"] == "stt") / 60
    tts = sum(r.get("chars", 0) for r in rows if r["kind"] == "tts")
    tok_in = sum(r.get("input_tokens", 0) for r in rows if r["kind"] == "llm")
    tok_out = sum(r.get("output_tokens", 0) for r in rows if r["kind"] == "llm")
    visits = len({r.get("call_id") for r in rows if r.get("call_id")}) or 1
    rates = workspace().get("rates_inr") or {}
    inr = None
    if any(rates.values()):
        inr = round(stt * rates.get("prisma_per_min", 0) + tts / 1000 * rates.get("timbre_per_1k_chars", 0)
                    + (tok_in + tok_out) / 1000 * rates.get("llm_per_1k_tokens", 0), 2)
    return {"stt_minutes": round(stt, 1), "tts_chars": tts, "llm_tokens": tok_in + tok_out, "inr": inr,
            "per_visit": {"stt_minutes": round(stt / visits, 2), "tts_chars": round(tts / visits), "llm_tokens": round((tok_in + tok_out) / visits),
                          "inr": round(inr / visits, 2) if inr is not None else None}, "visits": visits}


@app.get("/api/audit")
def audit_log(request: Request, limit: int = 100):
    user = current_user(request)
    require(user, "admin", "manager")
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(x) for x in reversed(lines)]
