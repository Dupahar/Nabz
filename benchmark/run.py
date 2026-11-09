"""Nabz noise benchmark: Prisma v3.0 vs faster-whisper on far-field, noisy Hinglish/English sales visits.

    python benchmark/run.py all                 # every stage, each one cached
    python benchmark/run.py synth|mix|transcribe|score|plot
    python benchmark/run.py transcribe --whisper small,medium --force

Stages
  synth       Timbre TTS renders each scripts/*.txt line by line -> audio/clean/<name>.wav + refs/<name>.json
              (speaker turns with times). Also builds a babble-noise bed from overlapping Timbre speech.
  mix         pyroomacoustics shoebox "shop" (7 x 5 x 3 m, RT60 0.5 s), phone ~1.6-1.9 m from the speakers,
              plus DEMAND street-traffic / cafeteria noise or babble at 20/10/5/0 dB SNR -> audio/test/.
  transcribe  Prisma v3.0 variants (one batch job per variant) and faster-whisper; raw output cached in results/raw/.
  score       WER / CER after normalize.py, keyterm recall, Prisma speaker attribution, bootstrap 95% CIs.
  plot        results/wer_vs_snr.png and results/keyterm_recall.png
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(BENCH))

import gnani  # noqa: E402
from gnani import stt_config, synthesize  # noqa: E402
from normalize import normalize, phonetic  # noqa: E402

SR = 16000
SCRIPTS = BENCH / "scripts"
AUDIO = BENCH / "audio"
LINES = AUDIO / "lines"
CLEAN = AUDIO / "clean"
TEST = AUDIO / "test"
NOISE = BENCH / "noise"
REFS = BENCH / "refs"
RESULTS = BENCH / "results"
RAW = RESULTS / "raw"

CONDS = ["clean", "ff20", "ff10", "ff5", "ff0"]
COND_LABEL = {"clean": "Clean\n(close mic)", "ff20": "20 dB", "ff10": "10 dB", "ff5": "5 dB", "ff0": "0 dB"}
SNR = {"ff20": 20, "ff10": 10, "ff5": 5, "ff0": 0}
# which background each conversation gets (two conversations per noise type)
NOISE_FOR = {"kirana_distributor": "straffic", "loan_field_agent": "straffic", "pharma_detailing": "babble",
             "realestate_site_visit": "babble", "industrial_pumps_en": "pcafeter", "logistics_d2c_en": "pcafeter"}
NOISE_NAME = {"straffic": "street traffic (DEMAND STRAFFIC)", "pcafeter": "cafeteria (DEMAND PCAFETER)",
              "babble": "6-voice babble (Timbre)"}
DEMOS = {"demo_brightmart": "brightmart", "demo_kapoor": "kapoor-pharmacy"}  # Windows-TTS English, clean only

# conds = conditions run per speech source (the ElevenLabs set was added later with a smaller credit budget)
PRISMA_VARIANTS = {
    "prisma-v3": {"denoise": False, "keyterms": False, "label": "Prisma v3.0",
                  "conds": {"timbre": CONDS, "elevenlabs": CONDS}},
    "prisma-v3-denoise": {"denoise": True, "keyterms": False, "label": "Prisma v3.0 + denoise",
                          "conds": {"timbre": CONDS, "elevenlabs": ["ff10", "ff0"]}},
    "prisma-v3-keyterms": {"denoise": False, "keyterms": True, "label": "Prisma v3.0 + keyterms",
                           "conds": {"timbre": ["clean", "ff10", "ff0"], "elevenlabs": ["clean", "ff10", "ff0"]}},
    "prisma-v3-denoise-keyterms": {"denoise": True, "keyterms": True, "label": "Prisma v3.0 + denoise + keyterms",
                                   "conds": {"timbre": ["clean", "ff10", "ff0"], "elevenlabs": []}},
}
BUDGET_MIN = 125.0

# ---- speech sources ----------------------------------------------------------------------------
# timbre:      Gnani Timbre v3.0 voices (from the "# voices:" line of each script)
# elevenlabs:  ElevenLabs eleven_multilingual_v2, shared-library Indian voices: an independent TTS vendor,
#              so the test isn't only "Gnani TTS scored by Gnani ASR". Items are named "<script>-el".
SOURCES = ["timbre", "elevenlabs"]
EL_SUFFIX = "-el"
EL_MODEL = "eleven_multilingual_v2"
EL_VOICE_IDS = {"Raju": "zT03pEAEi0VHKciJODfn", "Bunty": "FZkK3TvQ0pjyDmT8fzIW", "Sia": "KYiVPerWcenyBTIvWbfY",
                "Simran": "9w21nMuk8CWXIME31V1S", "Kashvi": "t65y7fZZv3UrpG7b4PUD"}
EL_VOICES = {  # A/B per script, chosen to match the roles' gender and age; voices alternate across scripts
    "kirana_distributor": {"A": "Bunty", "B": "Raju"},
    "pharma_detailing": {"A": "Bunty", "B": "Sia"},
    "loan_field_agent": {"A": "Raju", "B": "Simran"},
    "realestate_site_visit": {"A": "Raju", "B": "Kashvi"},
    "industrial_pumps_en": {"A": "Raju", "B": "Kashvi"},
    "logistics_d2c_en": {"A": "Simran", "B": "Bunty"},
}
EL_CHAR_LIMIT = 30000


def base_name(item: str) -> str:
    return item[: -len(EL_SUFFIX)] if item.endswith(EL_SUFFIX) else item


def source_of(item: str) -> str:
    if item.startswith("demo_"):
        return "windows-sapi"
    return "elevenlabs" if item.endswith(EL_SUFFIX) else "timbre"


def items_for(sources: list[str]) -> list[str]:
    out = []
    for s in sources:
        out += [n if s == "timbre" else n + EL_SUFFIX for n in script_names()]
    return out


def el_usage() -> int:
    p = BENCH / "results" / "elevenlabs_usage.jsonl"
    if not p.exists():
        return 0
    return sum(json.loads(line)["chars"] for line in p.read_text(encoding="utf-8").splitlines() if line.strip())


def el_synthesize(text: str, voice: str, out: Path) -> None:
    import os

    import requests

    if el_usage() + len(text) > EL_CHAR_LIMIT:
        raise SystemExit(f"ElevenLabs character budget ({EL_CHAR_LIMIT}) would be exceeded")
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_IDS[voice]}?output_format=pcm_16000"
    for attempt in range(5):
        r = requests.post(url, headers={"xi-api-key": key, "Content-Type": "application/json", "User-Agent": "nabz-bench/0.1"},
                          json={"text": text, "model_id": EL_MODEL}, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * 2 ** attempt)
            continue
        break
    if r.status_code != 200:
        raise SystemExit(f"ElevenLabs HTTP {r.status_code}: {r.text[:300]}")
    save(out, np.frombuffer(r.content, np.int16).astype(np.float32) / 32768.0)
    usage = BENCH / "results" / "elevenlabs_usage.jsonl"
    usage.parent.mkdir(parents=True, exist_ok=True)
    with usage.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"voice": voice, "chars": int(r.headers.get("character-cost") or len(text)),
                             "file": str(out.relative_to(BENCH))}, ensure_ascii=False) + "\n")

BABBLE_LINES = [
    ("Riyaa", "hi-en", "भैया ये वाला packet कितने का है, और कोई offer चल रहा है क्या?"),
    ("Prakash", "hi-en", "अरे सुनो, कल शाम को दुकान जल्दी बंद करनी है, माल आने वाला है।"),
    ("Lakshmi", "en-IN", "I told him the order would come by Tuesday but it is still not here."),
    ("Yashraj", "hi-en", "Bill बना दो, और change पाँच सौ का नहीं है मेरे पास।"),
    ("Kalpana", "hi-en", "बच्चों के लिए वो biscuit वाला डिब्बा दिखाओ ज़रा।"),
    ("Avinash", "en-IN", "Can you check if the delivery boy has left, the customer is calling again."),
    ("Chetana", "hi-en", "आज बहुत भीड़ है, थोड़ा जल्दी करो भैया, bus निकल जाएगी।"),
    ("Devansh", "hi-en", "UPI से payment कर दिया है, screen पर दिख रहा है देखो।"),
]


# ---------------------------------------------------------------------------------------------
def load(path: Path) -> np.ndarray:
    """Decode anything to 16 kHz mono float32 with ffmpeg (Timbre's streamed WAV headers upset some readers)."""
    proc = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1",
                           "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0


def save(path: Path, x: np.ndarray) -> None:
    from scipy.io import wavfile

    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))


def parse_script(path: Path) -> dict:
    voices, language, lines = {}, "hi-en", []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if m := re.match(r"^#\s*voices:\s*(.+)$", raw):
            voices = {k.strip(): v.strip() for k, v in (p.split("=", 1) for p in m.group(1).split(","))}
        elif m := re.match(r"^#\s*language:\s*(\S+)", raw):
            language = m.group(1)
        elif raw.strip() and not raw.lstrip().startswith("#") and (m := re.match(r"^\s*(\w+):\s*(.+)$", raw)):
            lines.append((m.group(1), m.group(2).strip()))
    return {"voices": voices, "language": language, "lines": lines}


def script_names() -> list[str]:
    return sorted(p.stem for p in SCRIPTS.glob("*.txt"))


def active_power(x: np.ndarray) -> float:
    """Mean power over 20 ms frames within 40 dB of the loudest frame (i.e. ignoring the pauses)."""
    f = 320
    frames = x[: len(x) // f * f].reshape(-1, f)
    p = (frames ** 2).mean(axis=1) + 1e-12
    return float(p[p > p.max() * 1e-4].mean())


# ---------------------------------------------------------------------------------------------
def stage_synth(sources: list[str]) -> None:
    REFS.mkdir(parents=True, exist_ok=True)
    for item in items_for(sources):
        name, source = base_name(item), source_of(item)
        sc = parse_script(SCRIPTS / f"{name}.txt")
        voices = sc["voices"] if source == "timbre" else EL_VOICES[name]
        rng = random.Random(f"gap-{name}")  # same pauses for both sources
        parts, turns, t = [np.zeros(int(0.5 * SR), np.float32)], [], 0.5
        for i, (spk, text) in enumerate(sc["lines"]):
            wav = LINES / item / f"{i:02d}.wav"
            if not wav.exists():
                if source == "timbre":
                    synthesize(text, wav, voice=voices[spk], language=sc["language"], container="wav", sample_rate=SR)
                else:
                    el_synthesize(text, voices[spk], wav)
                print(f"  tts[{source}] {name} line {i}", flush=True)
            x = load(wav)
            turns.append({"speaker": spk, "text": text, "start": round(t, 3), "end": round(t + len(x) / SR, 3), "line": i})
            gap = rng.uniform(0.3, 0.5)
            parts += [x, np.zeros(int(gap * SR), np.float32)]
            t += len(x) / SR + int(gap * SR) / SR
        audio = np.concatenate(parts)
        save(CLEAN / f"{item}.wav", audio)
        ref = {"name": item, "script": name, "language": sc["language"], "voices": voices, "duration": round(len(audio) / SR, 2),
               "turns": turns, "text": " ".join(tt["text"] for tt in turns),
               "source": "timbre-v3.0" if source == "timbre" else f"elevenlabs/{EL_MODEL}"}
        (REFS / f"{item}.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"synth {item}: {ref['duration']:.1f}s, {len(turns)} lines")
    if "elevenlabs" in sources:
        print(f"ElevenLabs characters used so far: {el_usage()}")

    for stem, demo in DEMOS.items():
        sc = parse_script(ROOT / "demo" / f"{demo}.txt")
        x = load(ROOT / "demo" / f"{demo}.wav")
        save(CLEAN / f"{stem}.wav", x)
        ref = {"name": stem, "language": "en-IN", "duration": round(len(x) / SR, 2), "turns": None,
               "text": " ".join(t for _, t in sc["lines"]), "source": "windows-sapi-tts"}
        (REFS / f"{stem}.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"demo {stem}: {ref['duration']:.1f}s")

    babble = NOISE / "babble.wav"
    if not babble.exists():
        utts = []
        for i, (voice, lang, text) in enumerate(BABBLE_LINES):
            p = NOISE / "babble_parts" / f"{i:02d}.wav"
            if not p.exists():
                synthesize(text, p, voice=voice, language=lang, container="wav", sample_rate=SR)
            utts.append(load(p))
        rng = np.random.default_rng(7)
        bed = np.zeros(60 * SR, np.float32)
        for _ in range(48):  # ~6 voices overlapping at any time
            u = utts[rng.integers(len(utts))] * rng.uniform(0.5, 1.0)
            start = rng.integers(0, len(bed) - len(u))
            bed[start:start + len(u)] += u
        save(babble, bed / np.abs(bed).max() * 0.8)
        print("built babble noise bed (60 s)")


def room_rirs() -> tuple[np.ndarray, np.ndarray]:
    import pyroomacoustics as pra

    dims, rt60 = [7.0, 5.0, 3.0], 0.5
    absorption, max_order = pra.inverse_sabine(rt60, dims)
    room = pra.ShoeBox(dims, fs=SR, materials=pra.Material(absorption), max_order=max_order)
    room.add_source([2.5, 2.5, 1.6])   # speaker A (rep), standing at the counter
    room.add_source([4.0, 2.8, 1.5])   # speaker B (customer)
    room.add_microphone([3.25, 1.2, 1.0])  # phone lying on the counter
    room.compute_rir()
    return np.asarray(room.rir[0][0]), np.asarray(room.rir[0][1])


def stage_mix(sources: list[str]) -> None:
    from scipy.signal import fftconvolve

    rir_a, rir_b = room_rirs()
    noises = {}
    for key in ("straffic", "pcafeter", "babble"):
        p = NOISE / f"{key}.wav"
        if not p.exists():
            raise SystemExit(f"missing noise file {p} (see README: DEMAND download)")
        noises[key] = load(p)
    for item in items_for(sources):
        name = base_name(item)
        if all((TEST / f"{item}__{c}.wav").exists() for c in CONDS):
            continue  # already mixed (and possibly already transcribed): keep the exact files
        ref = json.loads((REFS / f"{item}.json").read_text(encoding="utf-8"))
        dry = load(CLEAN / f"{item}.wav")
        save(TEST / f"{item}__clean.wav", dry)
        track = {"A": np.zeros(len(dry) + SR, np.float32), "B": np.zeros(len(dry) + SR, np.float32)}
        for turn in ref["turns"]:
            x = load(LINES / item / f"{turn['line']:02d}.wav")
            s = int(round(turn["start"] * SR))
            track[turn["speaker"]][s:s + len(x)] += x
        wet = fftconvolve(track["A"], rir_a)[: len(dry) + SR // 2] + fftconvolve(track["B"], rir_b)[: len(dry) + SR // 2]
        wet *= np.sqrt(active_power(dry) / active_power(wet))
        noise = noises[NOISE_FOR[name]]
        rng = np.random.default_rng(sum(map(ord, name)))  # same room, noise type and seed for both speech sources
        for cond, snr in SNR.items():
            off = int(rng.integers(0, max(1, len(noise) - len(wet))))
            seg = np.resize(noise[off:], len(wet))
            seg = seg * np.sqrt(active_power(wet) / (np.mean(seg ** 2) * 10 ** (snr / 10)))
            mix = wet + seg
            peak = np.abs(mix).max()
            if peak > 0.95:
                mix *= 0.95 / peak
            save(TEST / f"{item}__{cond}.wav", mix)
        print(f"mix {item}: noise={NOISE_FOR[name]}, conditions {list(SNR)}")
    for stem in DEMOS:
        save(TEST / f"{stem}__clean.wav", load(CLEAN / f"{stem}.wav"))


# ---------------------------------------------------------------------------------------------
def all_keyterms() -> list[str]:
    terms: list[str] = []
    for p in sorted(SCRIPTS.glob("*.keyterms.json")):
        terms += json.loads(p.read_text(encoding="utf-8"))["prisma_keyterms"]
    return list(dict.fromkeys(terms))


def variant_files(variant: str, source: str) -> list[Path]:
    conds = PRISMA_VARIANTS[variant]["conds"][source]
    files = [TEST / f"{n}__{c}.wav" for n in items_for([source]) for c in conds]
    if variant == "prisma-v3" and source == "timbre":
        files += [TEST / f"{s}__clean.wav" for s in DEMOS]
    return files


def job_file(variant: str, source: str) -> Path:
    # the Timbre jobs were run first and keep the original file name
    return RAW / variant / ("_job.json" if source == "timbre" else f"_job_{source}.json")


def duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _get_with_retry(url: str, headers: dict, tries: int = 8):
    import requests

    delay = 3.0
    for i in range(tries):
        try:
            return gnani._request("GET", url, headers=headers)
        except requests.exceptions.ConnectionError:
            if i == tries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 60)


def run_prisma_job(variant: str, source: str, files: list[Path], cfg: dict) -> None:
    """Like gnani.transcribe_batch, but the job id is saved first, so a network failure while polling or
    downloading can be resumed (rerun the stage) without submitting, and paying for, the audio again."""
    out_dir = RAW / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    jf = job_file(variant, source)
    if jf.exists():
        job_id = json.loads(jf.read_text())["job_id"]
        print(f"{variant}: resuming job {job_id}")
    else:
        handles = [open(p, "rb") for p in files]
        try:
            parts = [("config", (None, json.dumps(cfg), "application/json"))]
            parts += [("files", (p.name, fh, "audio/wav")) for p, fh in zip(files, handles)]
            job = gnani._check(gnani._request("POST", gnani.BATCH, headers=gnani._headers(), files=parts), "create job")
        finally:
            for fh in handles:
                fh.close()
        job_id = job["job_id"]
        jf.write_text(json.dumps({"job_id": job_id, "source": source, "files": [p.name for p in files],
                                        "config": {k: v for k, v in cfg.items() if k != "keyterms"},
                                        "n_keyterms": len(cfg.get("keyterms") or [])}, indent=1))
        gnani._check(gnani._request("POST", f"{gnani.BATCH}/{job_id}/start", headers=gnani._headers()), "start job")
        print(f"{variant}: job {job_id} started ({len(files)} files)", flush=True)
    t0 = time.time()
    while True:
        st = gnani._check(_get_with_retry(f"{gnani.BATCH}/{job_id}", gnani._headers()), "status")
        if st.get("status") in gnani.TERMINAL:
            break
        time.sleep(12)
    print(f"{variant}: {st['status']} after {time.time() - t0:.0f}s of polling")
    time.sleep(3)
    listing = gnani._check(_get_with_retry(f"{gnani.BATCH}/{job_id}/files", gnani._headers()), "files")
    for entry in listing.get("data", []):
        stem = Path(entry.get("original_path", "")).stem
        dest = out_dir / f"{stem}.json"
        if dest.exists():
            continue
        if entry.get("status") != "COMPLETED":
            print(f"  {stem}: {entry.get('status')}")
            continue
        doc = gnani._check(_get_with_retry(entry["transcript_url"], {"User-Agent": gnani.USER_AGENT}), "download")
        doc["_job_id"] = job_id
        dest.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        gnani.log_usage("stt", model=cfg["model"], seconds=float(doc.get("duration_seconds") or 0),
                        denoise=cfg.get("with_denoise", False), job_id=job_id, file=entry.get("original_path"),
                        call_id=f"benchmark:{variant}")
    print(f"{variant}: {len(list(out_dir.glob('*__*.json')))} transcripts on disk")


def stage_transcribe(sources: list[str], whisper_sizes: list[str], force: bool, only: str | None,
                     whisper_conds: list[str] | None = None) -> None:
    pending: dict[tuple[str, str], list[Path]] = {}
    for v in PRISMA_VARIANTS:
        if only and only != v and only != "prisma":
            continue
        for src in sources:
            todo = [f for f in variant_files(v, src) if not (RAW / v / f"{f.stem}.json").exists()]
            if todo:
                pending[(v, src)] = todo
    minutes = {k: (0.0 if job_file(*k).exists() else sum(duration(f) for f in fs) / 60) for k, fs in pending.items()}
    total = sum(minutes.values())
    print("Prisma audio to submit: " + ", ".join(f"{v}/{s} {m:.1f} min" for (v, s), m in minutes.items())
          + f" | total {total:.1f} min")
    if total > BUDGET_MIN and not force:
        raise SystemExit(f"over the {BUDGET_MIN:.0f}-minute budget; rerun with --force if intended")
    for (v, src), files in pending.items():
        spec = PRISMA_VARIANTS[v]
        cfg = stt_config(model="prisma-v3.0", language="indic-auto", fmt="codemix", speakers=2,
                         denoise=spec["denoise"], keyterms=all_keyterms() if spec["keyterms"] else None)
        run_prisma_job(v, src, files, cfg)

    if only and not only.startswith("whisper"):
        return
    for size in whisper_sizes:
        out_dir = RAW / f"whisper-{size}"
        files = [TEST / f"{n}__{c}.wav" for n in items_for(sources) for c in (whisper_conds or CONDS)]
        if "timbre" in sources and "clean" in (whisper_conds or CONDS):
            files += [TEST / f"{s}__clean.wav" for s in DEMOS]
        todo = [f for f in files if not (out_dir / f"{f.stem}.json").exists()]
        if not todo:
            continue
        from faster_whisper import WhisperModel

        model = WhisperModel(size, device="cpu", compute_type="int8")
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in todo:
            name = f.stem.split("__")[0]
            lang = json.loads((REFS / f"{name}.json").read_text(encoding="utf-8"))["language"]
            hint = "en" if lang.startswith("en") else "hi"
            t0 = time.time()
            segs, info = model.transcribe(load(f), language=hint, vad_filter=True, beam_size=5)
            segs = [{"start_time": round(s.start, 2), "end_time": round(s.end, 2), "text": s.text.strip()} for s in segs]
            el = time.time() - t0
            doc = {"model": f"whisper-{size}", "language_hint": hint, "duration_seconds": info.duration,
                   "elapsed_seconds": round(el, 1), "full_transcript": " ".join(s["text"] for s in segs), "segments": segs}
            (out_dir / f"{f.stem}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  whisper-{size} {f.stem}: {el:.0f}s for {info.duration:.0f}s audio", flush=True)


# ---------------------------------------------------------------------------------------------
def hyp_text(doc: dict) -> str:
    if doc.get("full_transcript"):
        return doc["full_transcript"]
    return " ".join(s.get("text", "") for s in doc.get("segments", []))


def keyterm_hits(hyp: str, name: str) -> tuple[int, int, list[str]]:
    kt = SCRIPTS / f"{name}.keyterms.json"
    if not kt.exists():
        return 0, 0, []
    ents = json.loads(kt.read_text(encoding="utf-8"))["entities"]
    raw = re.sub(r"(?<=\d),(?=\d)", "", hyp.lower())
    norm = f" {normalize(hyp)} "
    missed = []
    for e in ents:
        ok = False
        for v in e["variants"]:
            vr = re.sub(r"(?<=\d),(?=\d)", "", v.lower())
            if re.search(r"(?<!\w)" + re.escape(vr) + r"(?!\w)", raw):
                ok = True
                break
            vn = normalize(v)
            if vn and f" {vn} " in norm:
                ok = True
                break
        if not ok:
            missed.append(e["name"])
    return len(ents) - len(missed), len(ents), missed


def speaker_accuracy(doc: dict, turns: list[dict]) -> float | None:
    segs = [s for s in doc.get("segments", []) if s.get("speaker_id") is not None and s.get("text")]
    if not segs or not turns:
        return None
    weight: dict[tuple, float] = {}
    for s in segs:
        mid, dur = (s["start_time"] + s["end_time"]) / 2, max(0.01, s["end_time"] - s["start_time"])
        best = min(turns, key=lambda t: 0 if t["start"] <= mid <= t["end"] else min(abs(mid - t["start"]), abs(mid - t["end"])))
        key = (s["speaker_id"], best["speaker"])
        weight[key] = weight.get(key, 0) + dur
    ids = sorted({k[0] for k in weight}, key=lambda i: -sum(w for (a, _), w in weight.items() if a == i))
    labels = sorted({t["speaker"] for t in turns})
    total = sum(weight.values())
    best_correct = 0.0
    from itertools import permutations

    for perm in permutations(labels, min(len(labels), len(ids))):
        mapping = dict(zip(ids, perm))
        correct = 0.0
        for i in ids:
            lab = mapping.get(i) or max(labels, key=lambda lb: weight.get((i, lb), 0))
            correct += weight.get((i, lab), 0)
        best_correct = max(best_correct, correct)
    return best_correct / total


def stage_score() -> None:
    import jiwer

    rows = []
    for sys_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        for f in sorted(sys_dir.glob("*__*.json")):
            name, cond = f.stem.split("__")
            ref = json.loads((REFS / f"{name}.json").read_text(encoding="utf-8"))
            doc = json.loads(f.read_text(encoding="utf-8"))
            r, h = normalize(ref["text"]), normalize(hyp_text(doc))
            ms = jiwer.process_words(r, h or "<empty>")
            errs_spell = ms.substitutions + ms.deletions + ms.insertions
            rp, hp = phonetic(ref["text"]), phonetic(hyp_text(doc))
            m = jiwer.process_words(rp, hp or "<empty>")
            errs = m.substitutions + m.deletions + m.insertions
            hit, n_ent, missed = keyterm_hits(hyp_text(doc), base_name(name))
            spk = speaker_accuracy(doc, ref.get("turns") or []) if sys_dir.name.startswith("prisma") else None
            rows.append({"system": sys_dir.name, "file": name, "source": source_of(name), "cond": cond,
                         "group": "demo-en" if name.startswith("demo_") else ("hinglish" if ref["language"] == "hi-en" else "english"),
                         "noise": NOISE_FOR.get(base_name(name), "none") if cond != "clean" else "none",
                         "ref_words": len(r.split()), "errors": errs, "wer": round(errs / max(1, len(r.split())), 4),
                         "errors_spell": errs_spell, "wer_spell": round(errs_spell / max(1, len(r.split())), 4),
                         "cer": round(jiwer.cer(r, h or "<empty>"), 4), "keyterms_hit": hit, "keyterms_total": n_ent,
                         "keyterms_missed": "; ".join(missed),
                         "speaker_acc": None if spk is None else round(spk, 4)})
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "per_file.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    rng = np.random.default_rng(0)

    def agg(sel: list[dict]) -> dict:
        e = np.array([x["errors"] for x in sel], float)
        n = np.array([x["ref_words"] for x in sel], float)
        kh = np.array([x["keyterms_hit"] for x in sel], float)
        kn = np.array([x["keyterms_total"] for x in sel], float)
        idx = rng.integers(0, len(sel), size=(2000, len(sel)))
        wer_bs = e[idx].sum(1) / n[idx].sum(1)
        kt_bs = kh[idx].sum(1) / np.maximum(1, kn[idx].sum(1))
        spk = [x["speaker_acc"] for x in sel if x["speaker_acc"] is not None]
        es = np.array([x["errors_spell"] for x in sel], float)
        return {"n_files": len(sel), "wer": e.sum() / n.sum(), "wer_lo": float(np.percentile(wer_bs, 2.5)),
                "wer_hi": float(np.percentile(wer_bs, 97.5)), "wer_spell": es.sum() / n.sum(),
                "cer": float(np.mean([x["cer"] for x in sel])),
                "keyterm_recall": kh.sum() / max(1, kn.sum()), "kt_lo": float(np.percentile(kt_bs, 2.5)),
                "kt_hi": float(np.percentile(kt_bs, 97.5)), "speaker_acc": float(np.mean(spk)) if spk else None}

    summary = []
    for system in sorted({x["system"] for x in rows}):
        for source in ("pooled", "timbre", "elevenlabs"):
            for group in ("all", "hinglish", "english", "demo-en"):
                if group == "demo-en" and source != "pooled":
                    continue
                for cond in CONDS:
                    sel = [x for x in rows if x["system"] == system and x["cond"] == cond and
                           (x["group"] == group if group != "all" else x["group"] != "demo-en") and
                           (source == "pooled" or x["source"] == source)]
                    # Only report a cell when the system covered every conversation in it (e.g. an interrupted
                    # run must not produce a 2-file average). Pooled cells therefore need both sources.
                    expected = {x["file"] for x in rows if x["cond"] == cond and
                                (x["group"] == group if group != "all" else x["group"] != "demo-en") and
                                (source == "pooled" or x["source"] == source)}
                    if group != "demo-en" and {x["file"] for x in sel} != expected:
                        continue
                    if source == "pooled" and group != "demo-en" and {x["source"] for x in sel} != {"timbre", "elevenlabs"}:
                        continue
                    if sel:
                        summary.append({"system": system, "source": source, "group": group, "cond": cond, **agg(sel)})
    with (RESULTS / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        for s in summary:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()})
    (RESULTS / "summary.md").write_text(summary_md(summary, rows), encoding="utf-8")
    print((RESULTS / "summary.md").read_text(encoding="utf-8"))


def system_label(s: str) -> str:
    if s in PRISMA_VARIANTS:
        return PRISMA_VARIANTS[s]["label"]
    return s.replace("whisper-", "Whisper ")


def summary_md(summary: list[dict], rows: list[dict]) -> str:
    systems = sorted({s["system"] for s in summary}, key=lambda s: (not s.startswith("prisma"), s))

    def table(source: str, group: str, fmt) -> list[str]:
        out = ["| System | " + " | ".join(COND_LABEL[c].replace("\n", " ") for c in CONDS) + " |",
               "|---|" + "---|" * len(CONDS)]
        for s in systems:
            cells = []
            for c in CONDS:
                hit = [x for x in summary if x["system"] == s and x["source"] == source and x["group"] == group and x["cond"] == c]
                cells.append(fmt(hit[0]) if hit else "–")
            if any(cell != "–" for cell in cells):
                out.append(f"| {system_label(s)} | " + " | ".join(cells) + " |")
        return out

    wer_ci = lambda h: f"{h['wer']:.1%} [{h['wer_lo']:.0%}–{h['wer_hi']:.0%}]"  # noqa: E731
    kt_ci = lambda h: f"{h['keyterm_recall']:.0%} [{h['kt_lo']:.0%}–{h['kt_hi']:.0%}]"  # noqa: E731
    src_title = {"pooled": "Pooled: both speech sources (12 recordings per condition)",
                 "timbre": "Gnani Timbre voices (6 recordings per condition)",
                 "elevenlabs": "ElevenLabs voices (6 recordings per condition; independent TTS vendor)"}
    lines = ["# Benchmark results", "",
             "6 scripted field-sales conversations (4 Hinglish, 2 Indian English), each rendered twice: with Gnani Timbre v3.0 "
             "voices and with ElevenLabs multilingual v2 voices. Phone ~1.7 m away in a simulated 7×5×3 m shop (RT60 0.5 s); "
             "street traffic, cafeteria (DEMAND) or 6-voice babble noise. WER = phonetic WER (`normalize.phonetic`, "
             "script-agnostic); spelling WER uses `normalize.normalize`. Brackets: 95% bootstrap CI over recordings. "
             "Pooled rows only include systems/conditions that ran on both sources.", ""]
    for source in ("pooled", "timbre", "elevenlabs"):
        lines += [f"## {src_title[source]}", "", "### Word error rate (phonetic; lower is better)", ""]
        lines += table(source, "all", wer_ci)
        lines += ["", "### Keyterm recall: brands, competitors, amounts, days captured (higher is better)", ""]
        lines += table(source, "all", kt_ci)
        lines += [""]
    lines += ["## WER by language", ""]
    for source in ("timbre", "elevenlabs"):
        for group, title in (("hinglish", "Hinglish (4 conversations)"), ("english", "Indian English (2 conversations)")):
            lines += [f"### {title}, {source}", ""]
            lines += table(source, group, lambda h: f"{h['wer']:.1%}")
            lines += [""]
    lines += ["## Spelling WER (stricter: a loanword written in Devanagari vs Latin counts as an error)", ""]
    for source in ("timbre", "elevenlabs"):
        lines += [f"### {source}", ""] + table(source, "all", lambda h: f"{h['wer_spell']:.1%}") + [""]
    lines += ["## Prisma speaker attribution (share of speech assigned to the right person)", ""]
    for source in ("timbre", "elevenlabs"):
        lines += [f"### {source}", ""]
        lines += [ln for ln in table(source, "all", lambda h: f"{h['speaker_acc']:.0%}" if h["speaker_acc"] is not None else "–")
                  if "Whisper" not in ln] + [""]
    demo = [x for x in summary if x["group"] == "demo-en"]
    if demo:
        lines += ["## Sanity check: original demo recordings (English, Windows TTS, clean, 2 files)", "",
                  "| System | WER |", "|---|---|"]
        lines += [f"| {system_label(x['system'])} | {x['wer']:.1%} |" for x in demo] + [""]
    lines += ["## Missed keyterms at 0 dB", ""]
    for s in systems:
        miss = [x for x in rows if x["system"] == s and x["cond"] == "ff0" and x["keyterms_missed"]]
        if miss:
            lines.append(f"- **{system_label(s)}**: " + " | ".join(f"{x['file']}: {x['keyterms_missed']}" for x in miss))
    lines += ["", "## Missed keyterms on clean audio", ""]
    for s in systems:
        miss = [x for x in rows if x["system"] == s and x["cond"] == "clean" and x["keyterms_missed"]]
        if miss:
            lines.append(f"- **{system_label(s)}**: " + " | ".join(f"{x['file']}: {x['keyterms_missed']}" for x in miss))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------
STYLE = {
    "prisma-v3": ("#2563EB", "-", "o"),
    "prisma-v3-denoise": ("#0EA5E9", "-", "s"),
    "prisma-v3-keyterms": ("#1E3A8A", "--", "D"),
    "prisma-v3-denoise-keyterms": ("#7C3AED", "--", "^"),
    "whisper-small": ("#F97316", "-", "o"),
    "whisper-medium": ("#DC2626", "-", "s"),
}


def stage_plot() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with (RESULTS / "summary.csv").open(encoding="utf-8") as fh:
        summary = [r for r in csv.DictReader(fh) if r["group"] == "all"]
    sources = [s for s in ("timbre", "elevenlabs") if any(r["source"] == s for r in summary)]
    # The hero charts show the main systems only (the keyterm variants track their base variant closely and are
    # reported in summary.md). Two panels, one per speech source, sharing the y axis: easier to read on a phone than
    # six interleaved line styles.
    hero = ["prisma-v3", "prisma-v3-denoise", "whisper-medium", "whisper-small"]
    systems = [s for s in hero if any(r["system"] == s for r in summary)]
    plt.rcParams.update({"font.size": 15, "axes.spines.top": False, "axes.spines.right": False,
                         "font.family": "DejaVu Sans"})
    panel_title = {"timbre": "Gnani Timbre voices", "elevenlabs": "ElevenLabs voices (independent)"}

    def draw(metric: str, lo: str, hi: str, ylabel: str, title: str, out: Path, ymax: float) -> None:
        fig, axes = plt.subplots(1, len(sources), figsize=(7.2 * len(sources), 7.4), dpi=160, sharey=True, squeeze=False)
        for ax, source in zip(axes[0], sources):
            ends = []
            for s in systems:
                pts = sorted((CONDS.index(r["cond"]), float(r[metric]), float(r[lo]), float(r[hi]))
                             for r in summary if r["system"] == s and r["source"] == source)
                if not pts:
                    continue
                color, ls, mk = STYLE.get(s, ("#64748B", "-", "o"))
                x = [p[0] for p in pts]
                ax.plot(x, [p[1] * 100 for p in pts], ls, marker=mk, color=color, lw=2.8, ms=8, label=system_label(s), zorder=3)
                if len(pts) > 1:
                    ax.fill_between(x, [p[2] * 100 for p in pts], [p[3] * 100 for p in pts], color=color, alpha=0.08, lw=0)
                if x[-1] == len(CONDS) - 1:
                    ends.append([pts[-1][1] * 100, pts[-1][1] * 100, color])
            ends.sort(key=lambda e: e[0])
            for i in range(1, len(ends)):  # spread end labels so they don't overlap
                ends[i][1] = max(ends[i][1], ends[i - 1][1] + ymax * 0.06)
            for value, ypos, color in ends:
                ax.annotate(f"{value:.0f}%", (len(CONDS) - 1, value), xytext=(len(CONDS) - 1 + 0.15, ypos),
                            textcoords="data", va="center", fontsize=15, color=color, fontweight="bold")
            ax.set_xticks(range(len(CONDS)), [COND_LABEL[c].replace(" (close mic)", "") for c in CONDS])
            ax.set_xlim(-0.3, len(CONDS) - 0.2)
            ax.set_ylim(0, ymax)
            ax.grid(axis="y", alpha=0.25)
            ax.set_title(panel_title[source], loc="left", fontsize=16, fontweight="bold", color="#334155")
            ax.set_xlabel("Background noise (SNR) →")
        axes[0][0].set_ylabel(ylabel)
        handles, labels = axes[0][0].get_legend_handles_labels()
        fig.legend(handles, labels, frameon=False, fontsize=13.5, loc="upper center", ncol=len(labels),
                   bbox_to_anchor=(0.5, 0.905))
        fig.suptitle(title, x=0.01, ha="left", fontsize=20, fontweight="bold", y=0.985)
        fig.text(0.01, 0.012, "6 scripted field-sales conversations (4 Hinglish, 2 Indian English) voiced by two TTS vendors; phone ~1.7 m "
                 "away in a simulated shop (RT60 0.5 s);\nstreet, cafeteria and babble noise. Whisper is told the correct language; "
                 "Prisma auto-detects. Shaded: 95% bootstrap CI. Method & code: Nabz benchmark/.",
                 fontsize=10.5, color="#475569", linespacing=1.4)
        fig.tight_layout(rect=(0, 0.06, 1, 0.86))
        fig.savefig(out)
        plt.close(fig)
        print(f"wrote {out}")

    top = max(float(r["wer_hi"]) for r in summary if r["system"] in systems) * 100
    draw("wer", "wer_lo", "wer_hi", "Word error rate (%)  ↓ better",
         "Speech-to-text on noisy, far-field Indian sales visits", RESULTS / "wer_vs_snr.png", min(100, top * 1.08))
    draw("keyterm_recall", "kt_lo", "kt_hi", "Business keyterms captured (%)  ↑ better",
         "Did the transcript keep the brands, prices and dates?", RESULTS / "keyterm_recall.png", 105)


# ---------------------------------------------------------------------------------------------
def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["synth", "mix", "transcribe", "score", "plot", "all"])
    ap.add_argument("--tts", default="both", choices=["timbre", "elevenlabs", "both"], help="speech source(s)")
    ap.add_argument("--whisper", default="small", help="comma-separated faster-whisper sizes, '' to skip")
    ap.add_argument("--only", default=None, help="transcribe only one system: a prisma variant name, 'prisma' or 'whisper'")
    ap.add_argument("--whisper-conds", default="", help="comma-separated conditions for whisper (default: all)")
    ap.add_argument("--force", action="store_true", help="allow Prisma submissions above the minute budget")
    args = ap.parse_args()
    wconds = [c for c in args.whisper_conds.split(",") if c] or None
    sources = SOURCES if args.tts == "both" else [args.tts]
    sizes = [s for s in args.whisper.split(",") if s]
    stages = ["synth", "mix", "transcribe", "score", "plot"] if args.stage == "all" else [args.stage]
    for st in stages:
        print(f"== {st}", flush=True)
        if st == "synth":
            stage_synth(sources)
        elif st == "mix":
            stage_mix(sources)
        elif st == "transcribe":
            stage_transcribe(sources, sizes, args.force, args.only, wconds)
        elif st == "score":
            stage_score()
        else:
            stage_plot()


if __name__ == "__main__":
    main()
