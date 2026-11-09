"""Make a test visit recording with ElevenLabs voices (independent of Gnani's own Timbre TTS).

    python demo/elevenlabs_visit.py demo/scripts/sharma-kirana.txt --out demo/out/sharma-kirana.ogg [--snr 15]

Script format (same as demo/*.txt):
    # voices: A=FZkK3TvQ0pjyDmT8fzIW, B=zT03pEAEi0VHKciJODfn      (ElevenLabs voice ids)
    A: Namaste Sharma ji! ...
    B: ...

Each line is synthesized with eleven_multilingual_v2 (write Hindi in Devanagari and English words in
Latin for the most natural Hinglish), joined with short, slightly random pauses, then mixed with
shop/street-like noise at the given SNR, and saved as 16 kHz mono Opus, like a phone voice note.
Synthesized lines are cached in demo/out/cache/ so re-runs don't spend ElevenLabs characters.
Needs ELEVENLABS_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "demo" / "out" / "cache"
SR = 16000


def tts(text: str, voice: str, model: str = "eleven_multilingual_v2") -> np.ndarray:
    key = hashlib.sha256(f"{voice}|{model}|{text}".encode()).hexdigest()[:20]
    path = CACHE / f"{key}.pcm"
    if not path.exists():
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}", params={"output_format": "pcm_16000"},
                          headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
                          json={"text": text, "model_id": model}, timeout=120)
        r.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return np.frombuffer(path.read_bytes(), np.int16).astype(np.float32) / 32768.0


def shop_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """Brown-ish street rumble plus intermittent clatter and a far-off horn: rough, but not white noise."""
    brown = np.cumsum(rng.normal(0, 1, n))
    brown -= np.convolve(brown, np.ones(4000) / 4000, mode="same")
    brown /= np.abs(brown).max() + 1e-9
    clatter = np.zeros(n)
    for _ in range(max(1, n // (SR * 3))):
        at = rng.integers(0, max(1, n - SR // 4))
        burst = rng.normal(0, 1, SR // 8) * np.exp(-np.linspace(0, 8, SR // 8))
        clatter[at: at + len(burst)] += burst[: n - at] * 0.6
    t = np.arange(n) / SR
    horn = np.zeros(n)
    for _ in range(max(1, n // (SR * 12))):
        at = rng.integers(0, max(1, n - SR))
        horn[at: at + SR // 2] += 0.25 * np.sin(2 * np.pi * 420 * t[: SR // 2])[: n - at]
    return brown + clatter + horn


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--snr", type=float, default=15.0, help="speech-to-noise ratio in dB (lower = noisier)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    lines = args.script.read_text(encoding="utf-8").splitlines()
    voices = dict(p.split("=", 1) for p in re.sub(r"^#\s*voices:\s*", "", next(l for l in lines if l.startswith("# voices:"))).replace(" ", "").split(","))
    parts, chars = [], 0
    for line in lines:
        m = re.match(r"^\s*(\w+):\s*(.+)$", line)
        if line.startswith("#") or not m:
            continue
        who, text = m.groups()
        parts.append(tts(text, voices[who]))
        parts.append(np.zeros(int(SR * rng.uniform(0.25, 0.6))))
        chars += len(text)
    speech = np.concatenate(parts)
    noise = shop_noise(len(speech), rng)
    p_s, p_n = np.mean(speech ** 2), np.mean(noise ** 2)
    noise *= np.sqrt(p_s / (p_n * 10 ** (args.snr / 10)))
    mix = speech + noise
    mix /= max(1.0, np.abs(mix).max() / 0.95)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "wav", "-i", "-", "-c:a", "libopus", "-b:a", "24k",
                    str(args.out)], input=buf.getvalue(), check=True)
    print(f"wrote {args.out}: {len(speech) / SR:.0f}s speech, SNR {args.snr} dB, {chars} characters synthesized (cached lines cost nothing)")


if __name__ == "__main__":
    main()
