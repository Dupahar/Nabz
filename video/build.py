"""Build the Nabz video: `python video/build.py`  (add --capture to re-capture the live app first).

    python video/build.py                 # both cuts: out/nabz_60s.mp4 (9:16) and out/nabz_60s_16x9.mp4
    python video/build.py --only portrait # one cut
    python video/build.py --capture       # run video/capture.py (live upload through the real app) first
    python video/build.py --check         # also export check frames to out/check/

Pipeline: script.py (scenes + voiceover) → Gnani Timbre voiceover (cached) → scene timing fitted to
the voiceover → timeline.html rendered frame by frame (virtual clock, 30 fps) in Chrome via
Playwright → ffmpeg (x264) → mixed with the voiceover, the real Timbre debrief from the captured
visit, synthesized heartbeat music and street ambience.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / "cache"
OUT = HERE / "out"
sys.path.insert(0, str(HERE))

import audio as A  # noqa: E402
from script import CAPTION_FIX, FPS, MAX_SECONDS, NARRATOR, REPO_URL, SCENES  # noqa: E402

AMBIENCE = Path("C:/Users/mahaj/Downloads/Gnani/benchmark/noise/straffic.wav")
DISCLAIMER = "Demo visits use AI-generated voices (Gnani Timbre / ElevenLabs), processed live by the real Nabz pipeline."
SIZES = {"portrait": (1080, 1920), "landscape": (1920, 1080)}


def chunk_caption(text: str, a: float, b: float, max_words: int = 7) -> list[dict]:
    for k, v in CAPTION_FIX.items():
        text = text.replace(k, v)
    parts = [p.strip() for p in re.split(r"(?<=[.,!?])\s+", text) if p.strip()]
    chunks: list[str] = []
    for p in parts:
        words = p.split()
        while len(words) > max_words:
            cut = max_words if len(words) - max_words > 2 else len(words) // 2
            chunks.append(" ".join(words[:cut]))
            words = words[cut:]
        if words:
            chunks.append(" ".join(words))
    total = sum(len(c) for c in chunks) or 1
    out, t = [], a
    for c in chunks:
        dur = (b - a) * len(c) / total
        out.append({"a": round(t, 3), "b": round(t + dur, 3), "text": c})
        t += dur
    return out


def plan() -> dict:
    vo = A.vo_lines(SCENES, NARRATOR)
    by_scene: dict[int, list[dict]] = {}
    for v in vo:
        by_scene.setdefault(v["scene"], []).append(v)
    scenes, t = [], 0.0
    for i, sc in enumerate(SCENES):
        lines = by_scene.get(i, [])
        need = 0.25 + sum(v["dur"] for v in lines) + 0.12 * max(0, len(lines) - 1) + 0.45 if lines else 0
        dur = max(sc["min"], need)
        scenes.append({"id": sc["id"], "a": round(t, 3), "b": round(t + dur, 3)})
        off = 0.25
        for v in lines:
            v["offset"] = off
            off += v["dur"] + 0.12
        t += dur
    total = round(t, 3)
    if total > MAX_SECONDS:
        raise SystemExit(f"cut is {total:.1f}s, over {MAX_SECONDS}s: shorten script.py lines or min durations")
    captions = []
    for v in vo:
        a = scenes[v["scene"]]["a"] + v["offset"]
        captions += chunk_caption(v["text"], a, a + v["dur"])
    return {"vo": vo, "scenes": scenes, "total": total, "captions": captions}


def debrief_info(shots: dict, play: float) -> dict:
    path = shots.get("debrief_audio")
    if not path or not Path(path).exists():
        return {"env": [], "text": (shots.get("analysis") or {}).get("debrief") or "", "wps": 2.6, "path": None}
    x = A.read_audio(Path(path))
    total = len(x) / A.SR
    hop = A.SR // FPS
    seg = x[: int(play * A.SR)]
    env = [float(np.sqrt(np.mean(seg[i:i + hop] ** 2))) for i in range(0, len(seg), hop)]
    m = max(env) or 1
    text = (shots.get("analysis") or {}).get("debrief") or ""
    return {"env": [round(e / m, 3) for e in env], "text": text, "wps": len(text.split()) / max(total, 1), "path": path, "dur": total}


def shrink_mobile() -> None:
    """Mobile screenshots are captured at 2.75x; the phone in the video is ~530 px wide, so
    downscale to 600 px JPEGs (the 24k-px-tall visit page decodes much faster)."""
    src, dst = CACHE / "shots", CACHE / "shots" / "small"
    dst.mkdir(parents=True, exist_ok=True)
    for f in list(src.glob("rep_*.png")) + list(src.glob("prog_*.png")):
        if not f.exists():
            continue
        out = dst / (f.stem + ".jpg")
        if out.exists() and out.stat().st_mtime > f.stat().st_mtime:
            continue
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-vf", "scale=600:-2:flags=lanczos",
                        "-q:v", "2", str(out)], check=True)


def crop_visit_m(shots: dict) -> None:
    """Phone-sized JPEGs of the per-stop viewport shots; adds shots['visit_m']['crops']."""
    M = shots.get("visit_m")
    if not M or not M.get("stops"):
        return
    crops = []
    for st in M["stops"]:
        src = CACHE / "shots" / st["file"]
        out = CACHE / "shots" / "small" / (Path(st["file"]).stem + ".jpg")
        if src.exists() and not (out.exists() and out.stat().st_mtime > src.stat().st_mtime):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", "scale=600:-2:flags=lanczos",
                            "-q:v", "2", str(out)], check=True)
        crops.append({"key": st["key"], "top": st["top"], "h": st["h"], "file": out.name, "box": st.get("box")})
    M["crops"] = crops


def write_timeline(p: dict, shots: dict, deb: dict, size: tuple[int, int]) -> None:
    tl = {"W": size[0], "H": size[1], "fps": FPS, "total": p["total"], "scenes": p["scenes"], "captions": p["captions"],
          "shots": {**shots, "dir": "cache/shots/", "dirSmall": "cache/shots/small/"}, "debriefEnv": deb["env"], "debriefText": deb["text"],
          "debriefWps": deb["wps"], "debriefPlay": next(s["b"] - s["a"] for s in p["scenes"] if s["id"] == "debrief") - 0.5,
          "repo": REPO_URL, "disclaimer": DISCLAIMER}
    (CACHE / "timeline.js").write_text("window.TL = " + json.dumps(tl, ensure_ascii=False) + ";\n", encoding="utf-8")


def render(orient: str, p: dict, check: bool) -> Path:
    from playwright.sync_api import sync_playwright

    w, h = SIZES[orient]
    vid = CACHE / f"video_{orient}.mp4"
    n = int(round(p["total"] * FPS))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
                           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", str(vid)], stdin=subprocess.PIPE)
    checks = {"hook": 2.6, "reveal": 3.4, "stats": 4.8, "rep": 3.5, "visit": 4.0, "debrief": 3.0, "dash": 4.5, "trust": 5.0, "cta": 3.0}
    check_frames = {int((s["a"] + min(checks.get(s["id"], 2), s["b"] - s["a"] - .2)) * FPS): s["id"] for s in p["scenes"]}
    t0 = time.time()
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", args=["--allow-file-access-from-files"])
        page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.goto((HERE / "timeline.html").as_uri())
        page.wait_for_function("window.ready && window.ready()", timeout=60000)
        for i in range(n):
            page.evaluate(f"render({i / FPS})")
            jpg = page.screenshot(type="jpeg", quality=93)
            ff.stdin.write(jpg)
            if check and i in check_frames:
                (OUT / "check").mkdir(parents=True, exist_ok=True)
                (OUT / "check" / f"{orient}_{check_frames[i]}.jpg").write_bytes(jpg)
            if i % 300 == 0:
                print(f"  {orient}: frame {i}/{n} ({time.time() - t0:.0f}s)", flush=True)
        b.close()
    ff.stdin.close()
    ff.wait()
    return vid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=list(SIZES))
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.capture:
        subprocess.run([sys.executable, str(HERE / "capture.py")], check=True)

    p = plan()
    print(f"cut: {p['total']:.2f}s · " + " · ".join(f"{s['id']} {s['b'] - s['a']:.1f}" for s in p["scenes"]))
    shots_path = CACHE / "shots" / "shots.json"
    shots = json.loads(shots_path.read_text(encoding="utf-8")) if shots_path.exists() else {}
    deb_scene = next(s for s in p["scenes"] if s["id"] == "debrief")
    play = deb_scene["b"] - deb_scene["a"] - 0.5
    deb = debrief_info(shots, play)
    shrink_mobile()
    crop_visit_m(shots)

    extras = []
    if deb.get("path"):
        extras.append((deb_scene["a"] + 0.15, Path(deb["path"]), 1.0, play))
    hook = p["scenes"][0]
    amb = (AMBIENCE, 0.0, hook["b"] + 0.6) if AMBIENCE.exists() else None
    mix = A.mix(p["total"], p["vo"], [s["a"] for s in p["scenes"]], extras, CACHE / "mix.wav", ambience=amb)
    print(f"audio mixed: {mix}")

    names = {"portrait": "nabz_60s.mp4", "landscape": "nabz_60s_16x9.mp4"}
    for orient in ([args.only] if args.only else list(SIZES)):
        write_timeline(p, shots, deb, SIZES[orient])
        vid = render(orient, p, args.check)
        final = OUT / names[orient]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid), "-i", str(mix), "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)],
                             capture_output=True, text=True).stdout.strip()
        print(f"wrote {final} ({float(dur):.2f}s)")


if __name__ == "__main__":
    main()
