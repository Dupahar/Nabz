"""Render a few still frames for layout checks: python video/preview.py [portrait|landscape] t1 t2 ...
(times in seconds; default: one frame per scene). Writes video/out/preview/<orient>_<t>.jpg"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

orient = sys.argv[1] if len(sys.argv) > 1 else "portrait"
p = B.plan()
shots = json.loads((B.CACHE / "shots" / "shots.json").read_text(encoding="utf-8"))
deb_scene = next(s for s in p["scenes"] if s["id"] == "debrief")
deb = B.debrief_info(shots, deb_scene["b"] - deb_scene["a"] - 0.5)
B.shrink_mobile()
B.crop_visit_m(shots)
B.write_timeline(p, shots, deb, B.SIZES[orient])
times = [float(x) for x in sys.argv[2:]] or [round(s["a"] + min(3.0, (s["b"] - s["a"]) * .6), 2) for s in p["scenes"]]
out = B.OUT / "preview"
out.mkdir(parents=True, exist_ok=True)
w, h = B.SIZES[orient]
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--allow-file-access-from-files"])
    page = b.new_page(viewport={"width": w, "height": h})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto((HERE / "timeline.html").as_uri())
    page.wait_for_function("window.ready && window.ready()", timeout=60000)
    for t in times:
        page.evaluate(f"render({t})")
        page.wait_for_timeout(60)
        page.screenshot(path=str(out / f"{orient}_{t:05.2f}.jpg"), type="jpeg", quality=85)
    b.close()
print("scenes:", [(s["id"], s["a"], s["b"]) for s in p["scenes"]])
print("errors:", errs)
print("wrote", len(times), "frames to", out)
