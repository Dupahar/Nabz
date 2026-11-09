"""Voiceover (Gnani Timbre), synthesized music (heartbeat pulse + pads) and the final mix.

    python video/audio.py vo        # synthesize/cache the voiceover lines, print durations
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / "cache"
SR = 48000
sys.path.insert(0, str(ROOT / "tools"))


def read_audio(path: Path, sr: int = SR) -> np.ndarray:
    """Any audio file -> mono float32 at `sr` via ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                          "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def vo_lines(scenes: list[dict], narrator: dict) -> list[dict]:
    """Synthesize each voiceover line once (cached by text) and return their durations."""
    from gnani import synthesize
    import hashlib

    out = []
    for si, sc in enumerate(scenes):
        for li, (lang, text) in enumerate(sc.get("vo", [])):
            key = hashlib.sha256(f"{narrator}|{lang}|{text}".encode()).hexdigest()[:16]
            path = CACHE / "vo" / f"{key}.wav"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                synthesize(text, path, voice=narrator["voice"], language=lang, model=narrator["model"],
                           speed=narrator.get("speed", 1.0), container="wav", sample_rate=24000)
            x = read_audio(path)
            # trim leading/trailing silence so timing is tight
            idx = np.where(np.abs(x) > 0.01)[0]
            if len(idx):
                x = x[max(0, idx[0] - 1200): idx[-1] + 2400]
            trimmed = CACHE / "vo" / f"{key}.trim.wav"
            write_wav(trimmed, x)
            out.append({"scene": si, "line": li, "lang": lang, "text": text, "path": str(trimmed), "dur": len(x) / SR})
    return out


# ---------------------------------------------------------------- music

def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    # vectorised one-pole via lfilter-like recursion in chunks (numpy only)
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def music(total: float, bpm: float = 66, swell_at: float | None = None) -> np.ndarray:
    n = int(total * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    # Heartbeat: lub-dub (two low thumps) every beat.
    beat = 60 / bpm
    def thump(freq: float, dur: float, amp: float) -> np.ndarray:
        tt = np.arange(int(dur * SR)) / SR
        env = np.exp(-tt * 18) * (1 - np.exp(-tt * 400))
        f = freq * (1 + 0.6 * np.exp(-tt * 30))  # quick pitch drop = body
        return (amp * env * np.sin(2 * np.pi * np.cumsum(f) / SR)).astype(np.float32)
    lub, dub = thump(52, 0.35, 0.9), thump(46, 0.3, 0.6)
    k = 0.4
    while k < total - 0.5:
        i = int(k * SR)
        out[i:i + len(lub)] += lub[: n - i]
        j = int((k + 0.28) * SR)
        out[j:j + len(dub)] += dub[: max(0, n - j)]
        k += beat
    # Pads: detuned sines on a minor-ish chord, slowly breathing; brighter in the final swell.
    chord = [110.0, 130.81, 164.81, 196.0, 220.0]
    pad = np.zeros(n, np.float32)
    for f in chord:
        for det in (-0.4, 0.4):
            pad += np.sin(2 * np.pi * (f + det) * t + f).astype(np.float32)
    pad *= (0.5 + 0.5 * np.sin(2 * np.pi * t / 7.0)).astype(np.float32)
    pad /= np.abs(pad).max() + 1e-9
    fade_in = np.clip(t / 6.0, 0, 1)
    swell = np.ones(n) if swell_at is None else 1 + 0.8 * np.clip((t - swell_at) / 3, 0, 1)
    out += (0.22 * pad * fade_in * swell).astype(np.float32)
    # gentle shimmer (high sine plucks on beats) in the second half
    for kk in np.arange(total * 0.45, total - 1, beat * 2):
        i = int(kk * SR)
        tt = np.arange(int(0.8 * SR)) / SR
        pl = 0.05 * np.exp(-tt * 5) * np.sin(2 * np.pi * 880 * tt)
        out[i:i + len(pl)] += pl[: n - i].astype(np.float32)
    end_fade = np.clip((total - t) / 2.5, 0, 1)
    out *= end_fade.astype(np.float32)
    return out / (np.abs(out).max() + 1e-9) * 0.5


def mix(total: float, vo: list[dict], scene_starts: list[float], extras: list[tuple[float, Path, float, float]],
        out_path: Path, ambience: tuple[Path, float, float] | None = None) -> Path:
    """Place VO lines at scene starts (+offset), duck the music under speech, add extras
    (start, file, gain, max_len) and ambience (file, start, end)."""
    n = int(total * SR)
    voice = np.zeros(n, np.float32)
    for v in vo:
        start = scene_starts[v["scene"]] + v.get("offset", 0.25)
        x = read_audio(Path(v["path"]))
        i = int(start * SR)
        voice[i:i + len(x)] += x[: max(0, n - i)]
    extra = np.zeros(n, np.float32)
    for start, path, gain, max_len in extras:
        x = read_audio(path)[: int(max_len * SR)]
        fade = np.ones(len(x), np.float32)
        f = min(len(x), int(0.4 * SR))
        fade[-f:] = np.linspace(1, 0, f)
        i = int(start * SR)
        extra[i:i + len(x)] += (gain * x * fade)[: max(0, n - i)]
    if ambience:
        path, a, b = ambience
        x = read_audio(path)
        seg = np.zeros(n, np.float32)
        i, j = int(a * SR), int(b * SR)
        reps = np.tile(x, int(np.ceil((j - i) / len(x))) + 1)[: j - i]
        env = np.ones(j - i, np.float32)
        f = int(0.8 * SR)
        env[:f] = np.linspace(0, 1, f)
        env[-f:] = np.linspace(1, 0, f)
        seg[i:j] = reps * env * 0.18
        extra += seg
    m = music(total, swell_at=total - 9)
    # sidechain-ish ducking from voice + extras envelope
    speech = np.abs(voice) + np.abs(extra) * 0.6
    win = int(0.25 * SR)
    env = np.convolve(speech, np.ones(win) / win, mode="same")
    duck = 1 - 0.65 * np.clip(env / (env.max() + 1e-9) * 6, 0, 1)
    mixed = voice * 1.0 + extra + m * duck.astype(np.float32)
    peak = np.abs(mixed).max()
    mixed = mixed / peak * 10 ** (-1.0 / 20)   # peaks at -1 dBFS
    write_wav(out_path, mixed)
    return out_path


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    from script import NARRATOR, SCENES, SCENES_DEMO

    for v in vo_lines(SCENES_DEMO if "demo" in sys.argv else SCENES, NARRATOR):
        print(f"scene {v['scene']} {v['dur']:5.2f}s  {v['text'][:70]}")
