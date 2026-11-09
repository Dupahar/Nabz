"""Measure UI element boxes in the cached rep-flow frames by replaying the same scroll positions
(no upload). Adds shots.json['rep_boxes'] = {name: {x, y, w, h}} in phone viewport css px.

    python video/measure_rep.py [--base http://127.0.0.1:8000] [--live-call <id>]
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from capture import ROOT, SHOTS, UPLOAD, login  # noqa: E402


def scroll_to(page, sel, offset=90):
    page.evaluate(f"(() => {{ const e = document.querySelector('{sel}'); "
                  f"window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - {offset}); }})()")
    page.wait_for_timeout(400)


def box(page, sel):
    bb = page.locator(sel).first.bounding_box()
    return {"x": bb["x"], "y": bb["y"], "w": bb["width"], "h": bb["height"]} if bb else None


ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8000")
args = ap.parse_args()
meta = json.loads((SHOTS / "shots.json").read_text(encoding="utf-8"))
live = meta.get("live_call_id")
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    login(page, "arjun", args.base)
    page.goto(args.base + "/")
    page.wait_for_selector("#account")
    page.fill("#account", "Sharma Kirana Store")
    page.fill("#contact", "Sharma ji")
    page.select_option("#segment", label="Kirana")
    scroll_to(page, "#consentCard")
    out["notice"] = box(page, "#consentCard .notice")
    out["consent"] = box(page, "#consentCard label.check")
    page.check("#consentOk")
    scroll_to(page, "#recordCard")
    page.set_input_files("#fileInput", str(UPLOAD))
    page.wait_for_timeout(700)
    out["upload"] = box(page, "#uploadBtn")
    out["record"] = box(page, "#recBtn")
    # The progress chips: measured from the cached live frame (the live visit has moved on since).
    out["steps"] = {"x": 34, "y": 262, "w": 322, "h": 104}
    b.close()
meta["rep_boxes"] = out
(SHOTS / "shots.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
