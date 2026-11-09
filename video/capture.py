"""Capture the LIVE Nabz app for the video: a real login, a real upload, real processing.

    python video/capture.py [--reuse <call_id>]   (starts its own server on :8001)

Writes video/cache/shots/: rep_###.png (stop-motion of the rep flow, mobile), prog_###.png
(processing stages), visit_m.png / visit_d.png (full-page visit, mobile/desktop),
dash_d.png (manager dashboard), plus shots.json with frame timings, element boxes and the
visit's analysis (score, verified quotes, debrief text, debrief audio path).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHOTS = HERE / "cache" / "shots"
PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"
UPLOAD = ROOT / "demo" / "out" / "sharma-kirana-el.ogg"
FALLBACK_VISIT = "20261109-180804-sharma-kirana-store"
PIN = "1234"


def start_server() -> subprocess.Popen | None:
    try:
        requests.get(BASE + "/login", timeout=2)
        return None  # already running
    except requests.RequestException:
        pass
    proc = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "app.server:app",
                             "--host", "127.0.0.1", "--port", str(PORT)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            requests.get(BASE + "/login", timeout=2)
            return proc
        except requests.RequestException:
            time.sleep(0.5)
    raise RuntimeError("server did not start")


def login(page, handle: str) -> None:
    """Log in through the UI like a person: pick the card, enter the PIN if asked."""
    page.goto(BASE + "/login")
    page.wait_for_selector(f'button.person[data-handle="{handle}"]', timeout=20000)
    page.click(f'button.person[data-handle="{handle}"]')
    try:
        pin = page.wait_for_selector('input[type=password], input[name=pin], #pin, input[inputmode=numeric]', timeout=2500)
        pin.fill(PIN)
        pin.press("Enter")
    except Exception:  # noqa: BLE001 - no PIN step in this build
        pass
    try:
        page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
    except Exception:  # noqa: BLE001 - fall back to the API, then navigate
        page.request.post(BASE + "/api/login", data={"handle": handle, "pin": PIN}, headers={"X-Nabz": "1"})
        page.goto(BASE + "/")
    page.wait_for_timeout(800)


class Seq:
    """Stop-motion recorder: every shot is a frame with a hold time (seconds)."""

    def __init__(self, page, prefix: str):
        self.page, self.prefix, self.frames = page, prefix, []

    def shot(self, hold: float) -> None:
        name = f"{self.prefix}_{len(self.frames):03d}.png"
        self.page.screenshot(path=str(SHOTS / name))
        self.frames.append({"file": name, "hold": hold})


def boxes(page, selectors: dict[str, str]) -> dict:
    out = {}
    for key, sel in selectors.items():
        try:
            loc = page.locator(sel).first
            bb = loc.bounding_box()
            sy = page.evaluate("window.scrollY")
            if bb:
                out[key] = {"x": bb["x"], "y": bb["y"] + sy, "w": bb["width"], "h": bb["height"]}
        except Exception:  # noqa: BLE001
            pass
    return out


def smooth_scroll(seq: Seq, to_selector: str, steps: int = 8, offset: int = 90) -> None:
    page = seq.page
    target = page.evaluate(f"(() => {{ const e = document.querySelector('{to_selector}'); "
                           f"return e ? e.getBoundingClientRect().top + window.scrollY - {offset} : 0; }})()")
    start = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        k = i / steps
        k = k * k * (3 - 2 * k)
        page.evaluate(f"window.scrollTo(0, {start + (target - start) * k})")
        page.wait_for_timeout(30)
        seq.shot(0.045)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", help="skip the live upload; use this existing call_id")
    args = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    for f in SHOTS.glob("*.png"):
        f.unlink()
    server = start_server()
    meta: dict = {"base": BASE}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            # ---------------- mobile: the rep's flow
            m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2.75, is_mobile=True, has_touch=True)
            page = m.new_page()
            login(page, "arjun")
            page.goto(BASE + "/")
            page.wait_for_selector("#account", timeout=15000)
            page.wait_for_timeout(600)
            seq = Seq(page, "rep")
            seq.shot(0.6)
            page.click("#account")
            for i, ch in enumerate("Sharma Kirana Store"):
                page.keyboard.type(ch)
                if i % 2 == 1 or ch == " ":
                    seq.shot(0.05)
            seq.shot(0.25)
            page.click("#contact")
            for i, ch in enumerate("Sharma ji"):
                page.keyboard.type(ch)
                if i % 2 == 1:
                    seq.shot(0.05)
            page.select_option("#segment", label="Kirana")
            seq.shot(0.35)
            smooth_scroll(seq, "#consentCard")
            seq.shot(0.7)
            page.check("#consentOk")
            page.wait_for_timeout(250)
            seq.shot(0.6)
            smooth_scroll(seq, "#recordCard")
            seq.shot(0.35)

            call_id = args.reuse
            if not call_id:
                page.set_input_files("#fileInput", str(UPLOAD))
                page.wait_for_timeout(700)
                seq.shot(0.7)
                try:
                    with page.expect_response(lambda r: r.url.endswith("/api/visits") and r.request.method == "POST", timeout=60000) as resp:
                        page.click("#uploadBtn")
                    for _ in range(3):
                        page.wait_for_timeout(120)
                        seq.shot(0.12)
                    data = resp.value.json()
                    call_id = data.get("call_id")
                    page.wait_for_timeout(900)
                    seq.shot(0.6)
                except Exception as exc:  # noqa: BLE001
                    print("upload failed, falling back to an existing visit:", exc)
            meta["live_upload"] = bool(call_id and not args.reuse)
            call_id = call_id or FALLBACK_VISIT
            meta["call_id"] = call_id
            meta["rep_frames"] = seq.frames

            # Processing stages on the visit page (mobile)
            prog = Seq(page, "prog")
            page.goto(f"{BASE}/visit/{call_id}")
            page.wait_for_selector("#steps", timeout=20000)
            last, t0 = None, time.time()
            while time.time() - t0 < 300:
                status = page.evaluate("fetch('/api/visits/' + location.pathname.split('/').pop()).then(r => r.json()).then(d => d.visit.status)")
                if status != last:
                    page.wait_for_timeout(400)
                    prog.shot(0.7)
                    last = status
                if status in ("done", "error"):
                    break
                if status == "needs_consent_review" and not meta.get("consent_review"):
                    # The manager confirms consent through the real API (the visit resumes on its own).
                    meta["consent_review"] = True
                    mgr = requests.Session()
                    mgr.post(BASE + "/api/login", json={"handle": "kavita", "pin": PIN}, headers={"X-Nabz": "1"}, timeout=20)
                    r = mgr.post(f"{BASE}/api/visits/{call_id}/confirm-consent", json={}, headers={"X-Nabz": "1"}, timeout=20)
                    print("consent review -> manager confirmed:", r.status_code)
                page.wait_for_timeout(1500)
            meta["final_status"] = last
            meta["prog_frames"] = prog.frames
            page.wait_for_timeout(1500)
            page.reload()
            page.wait_for_selector("#ring", timeout=20000)
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")
            mb = boxes(page, {"ring": "#ring", "verified": "#verifiedBox", "debrief": "#debriefCard",
                              "signals": "#signals", "transcript": "#transcript", "redact": "#transcript .redact",
                              "checklist": "#checklist", "flags": "#flagsCard", "coaching": "#coaching"})
            # Viewport shots centred on each stop (full-page shots > 16k device px repeat content).
            stops = []
            for key, sel in (("verified", "#verifiedBox"), ("redact", "#transcript .redact"), ("signals", "#signals")):
                if not page.locator(sel).count():
                    sel = "#ring"
                page.evaluate(f"document.querySelector('{sel}').scrollIntoView({{block: 'center'}})")
                page.wait_for_timeout(600)
                bb = page.locator(sel).first.bounding_box()   # viewport coordinates, after nested scrolling
                fname = f"visit_m_{key}.png"
                page.screenshot(path=str(SHOTS / fname))
                stops.append({"key": key, "top": page.evaluate("window.scrollY"), "h": 844, "file": fname,
                              "box": {"x": bb["x"], "y": bb["y"], "w": bb["width"], "h": bb["height"]} if bb else None})
            meta["visit_m"] = {"boxes": mb, "width": 390, "dsf": 2.75, "stops": stops,
                               "height": page.evaluate("document.documentElement.scrollHeight")}
            m.close()

            # ---------------- desktop: visit page + manager dashboard
            d = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
            page = d.new_page()
            login(page, "arjun")
            page.goto(f"{BASE}/visit/{call_id}")
            page.wait_for_selector("#ring", timeout=20000)
            page.wait_for_timeout(1800)
            db = boxes(page, {"ring": "#ring", "verified": "#verifiedBox", "debrief": "#debriefCard", "signals": "#signals",
                              "transcript": "#transcript", "redact": "#transcript .redact", "checklist": "#checklist",
                              "coaching": "#coaching", "proposal": "#proposalCard"})
            page.screenshot(path=str(SHOTS / "visit_d.png"), full_page=True)
            dstops = []
            for key, sel in (("verified", "#verifiedBox"), ("redact", "#transcript .redact"), ("signals", "#signals")):
                if not page.locator(sel).count():
                    sel = "#ring"
                page.evaluate(f"document.querySelector('{sel}').scrollIntoView({{block: 'center'}})")
                page.wait_for_timeout(600)
                bb = page.locator(sel).first.bounding_box()
                fname = f"visit_d_{key}.png"
                page.screenshot(path=str(SHOTS / fname))
                dstops.append({"key": key, "file": fname, "box": {"x": bb["x"], "y": bb["y"], "w": bb["width"], "h": bb["height"]} if bb else None})
            meta["visit_d"] = {"boxes": db, "width": 1440, "vh": 900, "dsf": 1.5, "stops": dstops,
                               "height": page.evaluate("document.documentElement.scrollHeight")}
            # manager
            page.context.clear_cookies()
            login(page, "kavita")
            page.goto(BASE + "/dashboard")
            page.wait_for_selector("#kpis", timeout=20000)
            page.wait_for_timeout(3500)   # charts animate in
            sec = lambda inner: f"section.card:has({inner})"  # noqa: E731
            dd = boxes(page, {"kpis": "#kpis", "competitors": sec("#cCompetitors"), "trust": sec("#trust"),
                              "signals": sec("#cSignals"), "voc": sec("#voc"), "compliance": "#complianceCard",
                              "reps": sec("#reps"), "demand": sec("#demand")})
            page.screenshot(path=str(SHOTS / "dash_d.png"), full_page=True)
            meta["dash_d"] = {"boxes": dd, "width": 1440, "dsf": 1.5,
                              "height": page.evaluate("document.documentElement.scrollHeight")}
            d.close()
            b.close()
    finally:
        if server:
            server.terminate()

    # analysis facts for overlays
    folder = ROOT / "data" / "calls" / meta["call_id"]
    a = json.loads((folder / "analysis.json").read_text(encoding="utf-8")) if (folder / "analysis.json").exists() else {}
    g = a.get("grounding") or {}
    meta["analysis"] = {"score": a.get("score"), "verified": g.get("verified"), "checked": g.get("checked"),
                        "debrief": a.get("debrief"), "lens": a.get("lens"),
                        "signals": [s.get("text") for s in a.get("market_signals", [])][:6]}
    deb = folder / "debrief.ogg"
    meta["debrief_audio"] = str(deb) if deb.exists() else None
    (SHOTS / "shots.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k not in ("rep_frames", "prog_frames")}, ensure_ascii=False, indent=1)[:2500])
    print(f"rep frames {len(meta['rep_frames'])}, progress frames {len(meta['prog_frames'])}")


if __name__ == "__main__":
    sys.exit(main())
