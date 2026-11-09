"""Seed the Nabz dashboard with synthetic field visits, run through the REAL pipeline.

    .venv/Scripts/python demo/seed/seed.py [--only slug,slug] [--workers 3]

For each visit in visits.yaml:
  1. every script line is spoken by Gnani Timbre v3.0 (cached in demo/seed/audio/lines/),
  2. lines are joined with natural gaps and mixed with light background noise (~17 dB SNR,
     street / cafeteria / babble from the benchmark's noise set when available),
  3. the result (ogg/opus 24 kbps) goes through tools/pipeline.py: consent, Gnani Prisma
     transcription and PII redaction, Claude analysis with verified quotes, Timbre voice debrief.
All voices, names, shops and numbers are invented.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import pipeline  # noqa: E402
from common import CALLS, read_json  # noqa: E402
from gnani import synthesize  # noqa: E402

SR = 16000
NOISE_DIR = Path("C:/Users/mahaj/Downloads/Gnani/benchmark/noise")
LINES = HERE / "audio" / "lines"
MIXED = HERE / "audio" / "visits"
LINE_RE = re.compile(r"^(?P<spk>[AB])(?:@(?P<lang>[\w-]+))?:\s*(?P<text>.+)$")


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError(f"{path}: expected 16-bit audio")
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        n = int(len(x) * SR / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x


def write_wav(path: Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())


def speak_line(text: str, voice: str, lang: str) -> np.ndarray:
    key = hashlib.sha1(f"{voice}|{lang}|{text}".encode()).hexdigest()[:16]
    path = LINES / f"{key}.wav"
    if not path.exists():
        LINES.mkdir(parents=True, exist_ok=True)
        synthesize(text, path, voice=voice, language=lang, container="wav", sample_rate=SR)
    return read_wav(path)


def noise_bed(name: str, n: int, rng: np.random.Generator) -> np.ndarray:
    path = NOISE_DIR / f"{name}.wav"
    if path.exists():
        bed = read_wav(path)
        if len(bed) < n:
            bed = np.tile(bed, n // len(bed) + 1)
        start = int(rng.integers(0, len(bed) - n + 1))
        return bed[start:start + n]
    # Fallback: brown-ish noise.
    w = rng.standard_normal(n).astype(np.float32)
    b = np.cumsum(w)
    b -= np.convolve(b, np.ones(400) / 400, mode="same")
    return b / (np.abs(b).max() + 1e-9)


def build_audio(v: dict) -> Path:
    out = MIXED / f"{v['slug']}.ogg"
    if out.exists():
        return out
    rng = np.random.default_rng(int(hashlib.sha1(v["slug"].encode()).hexdigest()[:8], 16))
    pieces = []
    for line in v["script"]:
        m = LINE_RE.match(line.strip())
        if not m:
            raise ValueError(f"{v['slug']}: bad line {line!r}")
        spk, lang, text = m["spk"], m["lang"] or v.get("lang", "hi-en"), m["text"]
        x = speak_line(text, v["voices"][spk], lang)
        # trim leading/trailing silence a little for a conversational pace
        idx = np.where(np.abs(x) > 0.01)[0]
        if len(idx):
            x = x[max(0, idx[0] - 800): idx[-1] + 1600]
        pieces.append(x)
    speech = [np.zeros(int(0.4 * SR), np.float32)]
    for p in pieces:
        speech.append(p)
        speech.append(np.zeros(int(rng.uniform(0.25, 0.6) * SR), np.float32))
    speech = np.concatenate(speech)
    bed = noise_bed(v.get("noise", "straffic"), len(speech), rng)
    snr_db = float(rng.uniform(15, 20))
    ps, pn = np.mean(speech ** 2), np.mean(bed ** 2) + 1e-12
    mix = speech + bed * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    wav = MIXED / f"{v['slug']}.wav"
    write_wav(wav, mix)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libopus", "-b:a", "24k", str(out)], check=True)
    wav.unlink()
    print(f"[{v['slug']}] audio {len(mix) / SR:.0f}s at {snr_db:.1f} dB SNR ({v.get('noise')})", flush=True)
    return out


def process(v: dict) -> tuple[str, dict]:
    call_id = f"demo-{v['slug']}"
    status_path = CALLS / call_id / "status.json"
    if status_path.exists() and read_json(status_path).get("status") == "done":
        return call_id, read_json(status_path)
    audio = build_audio(v)
    if not (CALLS / call_id / "visit.json").exists() or read_json(status_path).get("status") == "error":
        pipeline.create_visit(audio, {"rep_handle": v["rep"], "account": v["account"], "contact": v.get("contact", ""),
                                      "segment": v["segment"], "region": "", "consent_method": v.get("consent", "rep-confirmed"),
                                      "note": "Synthetic demo visit (Timbre voices)", "call_id": call_id})
    print(f"[{v['slug']}] running pipeline...", flush=True)
    pipeline.run(call_id)
    return call_id, read_json(status_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default="")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    visits = yaml.safe_load((HERE / "visits.yaml").read_text(encoding="utf-8"))["visits"]
    if args.only:
        keep = set(args.only.split(","))
        visits = [v for v in visits if v["slug"] in keep]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process, v): v["slug"] for v in visits}
        for f in as_completed(futs):
            try:
                call_id, st = f.result()
                print(f"[{futs[f]}] {call_id}: {st.get('status')} {st.get('error') or ''}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{futs[f]}] FAILED: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
