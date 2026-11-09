"""Capture the extra LIVE footage for the 2-minute demo, on a SANDBOX copy of the app (:8001).

    python video/capture_demo.py [--visit 20261109-180804-sharma-kirana-store]

The sandbox (video/cache/sandbox) is a copy of app/, tools/, lenses/, config/ and data/. Only two
things differ:
  * the manager's demo PIN is set to the documented 1234;
  * the filmed visit's CRM proposal is reset to "proposed".
The manager's real Approve click therefore happens on the copy, never on the main data. No API
keys are copied, so nothing is processed or billed.

Writes video/cache/demo/: login_###.png (phone login), d_*.png (desktop viewport stops) and demo.json
(boxes in viewport css px for every stop).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SB = HERE / "cache" / "sandbox"
OUT = HERE / "cache" / "demo"
PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"
PIN = "1234"


def make_sandbox(visit: str) -> None:
    if SB.exists():
        shutil.rmtree(SB)
    SB.mkdir(parents=True)
    for d in ("app", "tools", "lenses", "config", "data"):
        shutil.copytree(ROOT / d, SB / d, ignore=shutil.ignore_patterns("__pycache__", "*.lock"))
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    subprocess.run([py, "tools/set_pin.py", "--handle", "kavita", "--pin", PIN], cwd=SB, check=True, capture_output=True)
    folder = SB / "data" / "calls" / visit
    for name, status in (("crm_proposal.json", "proposed"), ("followup.json", "drafted")):
        p = folder / name
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            for k in ("approved_by", "approved_at", "rejected_by", "self_approved"):
                d.pop(k, None)
            d["status"] = status
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def start() -> subprocess.Popen:
    proc = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "app.server:app", "--host", "127.0.0.1",
                             "--port", str(PORT)], cwd=SB, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env={**__import__("os").environ, "GNANI_API_KEY": "", "ANTHROPIC_API_KEY": ""})
    for _ in range(80):
        try:
            requests.get(BASE + "/login", timeout=2)
            return proc
        except requests.RequestException:
            time.sleep(.5)
    raise RuntimeError("sandbox server did not start")


def login(page, handle: str, shots: list | None = None) -> None:
    page.goto(BASE + "/login")
    page.wait_for_selector(f'button.person[data-handle="{handle}"]', timeout=20000)
    page.wait_for_timeout(500)
    if shots is not None:
        shots.append(snap(page, "login", 0.9))
    page.click(f'button.person[data-handle="{handle}"]')
    pin = page.wait_for_selector("#pin", timeout=5000)
    page.wait_for_timeout(300)
    if shots is not None:
        shots.append(snap(page, "login", 0.6))
    for ch in PIN:
        pin.type(ch)
        page.wait_for_timeout(120)
        if shots is not None:
            shots.append(snap(page, "login", 0.18))
    pin.press("Enter")
    page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
    page.wait_for_timeout(900)
    if shots is not None:
        shots.append(snap(page, "login", 0.8))


_n = {"login": 0}


def snap(page, prefix: str, hold: float) -> dict:
    name = f"{prefix}_{_n[prefix]:03d}.png"
    _n[prefix] += 1
    page.screenshot(path=str(OUT / name))
    return {"file": name, "hold": hold}


def box(page, sel: str):
    loc = page.locator(sel).first
    if not loc.count():
        return None
    bb = loc.bounding_box()
    return {"x": bb["x"], "y": bb["y"], "w": bb["width"], "h": bb["height"]} if bb else None


def stop(page, name: str, center_sel: str | None, boxes: dict[str, str]) -> dict:
    if center_sel:
        page.evaluate(f"(() => {{ const e = document.querySelector('{center_sel}'); if (e) e.scrollIntoView({{block: 'center'}}); }})()")
    else:
        page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"d_{name}.png"))
    return {"file": f"d_{name}.png", "boxes": {k: box(page, v) for k, v in boxes.items()}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--visit", default="20261109-180804-sharma-kirana-store")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"):
        f.unlink()
    make_sandbox(args.visit)
    proc = start()
    meta: dict = {"visit": args.visit, "stops": {}}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            # phone login (the rep)
            m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2.75, is_mobile=True, has_touch=True)
            pg = m.new_page()
            shots: list = []
            login(pg, "arjun", shots)
            meta["login_frames"] = shots
            m.close()
            # desktop: the visit, as the rep
            d = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
            pg = d.new_page()
            login(pg, "arjun")
            pg.goto(f"{BASE}/visit/{args.visit}")
            pg.wait_for_selector("#ring", timeout=20000)
            pg.wait_for_timeout(1500)
            S = meta["stops"]
            S["top"] = stop(pg, "top", None, {"ring": "#ring", "verified": "#verifiedBox", "lens": "#lensChip", "summary": "#summary"})
            S["transcript"] = stop(pg, "transcript", "#transcript .redact", {"redact": "#transcript .redact", "transcript": "#transcript"})
            S["checklist"] = stop(pg, "checklist", "#checklist", {"checklist": "#checklist"})
            S["signals"] = stop(pg, "signals", "#signals", {"signals": "#signals"})
            # click a quote: the transcript jumps to it and highlights the line
            qsel = "#signals .quote-btn[data-seg]"
            S["quote"] = stop(pg, "quote", qsel, {"quote": qsel})
            seg = pg.locator(qsel).first.get_attribute("data-seg")
            pg.locator(qsel).first.click()
            pg.wait_for_timeout(1100)
            pg.screenshot(path=str(OUT / "d_quote_hit.png"))
            S["quote_hit"] = {"file": "d_quote_hit.png", "boxes": {"hit": box(pg, f"#seg-{seg}")}}
            S["verified"] = stop(pg, "verified", "#verifiedBox", {"verified": "#verifiedBox"})
            S["coaching"] = stop(pg, "coaching", "#coaching", {"coaching": "#coaching"})
            d.close()
            # desktop: the manager approves, then the dashboard
            d = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
            pg = d.new_page()
            login(pg, "kavita")
            pg.goto(f"{BASE}/visit/{args.visit}")
            pg.wait_for_selector("#ring", timeout=20000)
            pg.wait_for_timeout(1500)
            S["proposal"] = stop(pg, "proposal", "#proposalCard", {"card": "#proposalCard", "approve": "#approveBtn"})
            if pg.locator("#approveBtn").count():
                pg.locator("#approveBtn").hover()
                pg.wait_for_timeout(300)
                pg.screenshot(path=str(OUT / "d_proposal_hover.png"))
                S["proposal_hover"] = {"file": "d_proposal_hover.png", "boxes": {"approve": box(pg, "#approveBtn")}}
                pg.locator("#approveBtn").click()
                pg.wait_for_timeout(1800)
                S["approved"] = stop(pg, "approved", "#proposalCard", {"card": "#proposalCard", "done": "#proposalCard .alert.ok"})
            pg.goto(BASE + "/dashboard")
            pg.wait_for_selector("#kpis", timeout=20000)
            pg.wait_for_timeout(3500)
            sec = lambda inner: f"section.card:has({inner})"  # noqa: E731
            S["dash_top"] = stop(pg, "dash_top", None, {"kpis": "#kpis", "trust": sec("#trust"), "competitors": sec("#cCompetitors")})
            S["dash_comp"] = stop(pg, "dash_comp", "#cCompetitors", {"competitors": sec("#cCompetitors")})
            S["dash_voc"] = stop(pg, "dash_voc", "#voc", {"voc": sec("#voc")})
            S["dash_flag"] = stop(pg, "dash_flag", "#complianceCard", {"compliance": "#complianceCard"})
            S["dash_trust"] = stop(pg, "dash_trust", "#trust", {"trust": sec("#trust")})
            d.close()
            b.close()
    finally:
        proc.terminate()
    (OUT / "demo.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("stops:", {k: [n for n, v in s["boxes"].items() if v] for k, s in meta["stops"].items()})
    print("login frames:", len(meta["login_frames"]))


if __name__ == "__main__":
    main()
