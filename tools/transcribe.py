"""Transcribe a recorded in-person conversation with Gnani AI's Prisma (default) or local Whisper.

    python tools/transcribe.py <audio> --title "BrightMart" --consent rep-confirmed --consent-by arjun
                               [--engine prisma|whisper] [--speakers 3] [--language indic-auto]
                               [--topic "..."] [--no-denoise] [--call-id ID]

Steps, in order (each is logged to the audit trail):
  1. Consent gate: refuses to process unless consent is given with --consent or already on file
     (config/workspace.yaml privacy.consent_required). DPDP Act 2023 s.5-6.
  2. Speech to text. Prisma v3.0 batch: speaker diarization, Indian languages and code-mixed
     speech (format=codemix keeps English words in Latin script), optional denoising, and
     `keyterms`: your products, competitors and CRM account/contact names, so the words that
     matter to the business come out right.
  3. PII redaction (tools/redact.py): Aadhaar, PAN, phone numbers, etc. are removed before any
     agent or LLM reads the transcript.

Creates data/calls/<call_id>/ with audio.<ext>, consent.json, transcript.json (redacted; segments
with start/end/speaker), transcript.raw.json, transcript.md and redactions.json.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from common import CALLS, CRM_FILE, audit, fmt_ts, read_json, slugify, utf8_stdout, workspace, write_json

PRISMA_MAX_BYTES = 10 * 1024 * 1024


def decode_audio(path: Path):
    """16 kHz mono float32 via ffmpeg (for the Whisper fallback)."""
    import numpy as np

    proc = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                          capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"error: ffmpeg could not decode {path}: {proc.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0


def upload_copy(audio: Path, folder: Path) -> Path:
    """Prisma takes phone formats directly; re-encode only if the file is over 10 MB
    (mono Opus at 24 kbps fits ~55 minutes in 10 MB)."""
    if audio.stat().st_size <= PRISMA_MAX_BYTES:
        return audio
    if shutil.which("ffmpeg") is None:
        raise SystemExit("error: recording is over 10 MB and ffmpeg is not installed to compress it")
    out = folder / "upload.ogg"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(audio), "-ac", "1", "-ar", "16000",
                    "-c:a", "libopus", "-b:a", "24k", str(out)], check=True)
    if out.stat().st_size > PRISMA_MAX_BYTES:
        raise SystemExit("error: recording is longer than ~55 minutes; split it and send the parts")
    return out


def keyterms_for(ws: dict, title: str) -> list[str]:
    vocab = ws.get("vocabulary") or {}
    terms = [*vocab.get("products", []), *vocab.get("competitors", []), *vocab.get("terms", [])]
    terms += [m["name"] for m in ws.get("team", []) if m.get("name")]
    if CRM_FILE.exists():
        for name, acc in read_json(CRM_FILE).get("accounts", {}).items():
            terms.append(name)
            if acc.get("contact"):
                terms.append(acc["contact"].split(",")[0].strip())
    if title:
        terms.append(title)
    return [t for t in dict.fromkeys(t.strip() for t in terms) if t]


def run_prisma(audio: Path, folder: Path, ws: dict, args) -> tuple[list[dict], dict]:
    from gnani import stt_config, transcribe_batch

    speech = ws.get("speech") or {}
    company = ws.get("company", "our company")
    topic = args.topic or (f"In-person business conversation between a representative of {company} and a customer"
                           + (f" ({args.title})" if args.title else "") + ". Products, prices in rupees, lakh and crore, and next steps.")
    cfg = stt_config(model=speech.get("model", "prisma-v3.0"), language=args.language or speech.get("language", "indic-auto"),
                     fmt=speech.get("format", "codemix"), speakers=args.speakers or speech.get("max_speakers", 3),
                     denoise=speech.get("denoise", True) and not args.no_denoise,
                     keyterms=keyterms_for(ws, args.title), topic=topic)
    upload = upload_copy(audio, folder)
    docs = transcribe_batch([upload], cfg, call_ids=[folder.name])
    doc = docs.get(upload.name) or next(iter(docs.values()))
    if "segments" not in doc:
        raise SystemExit(f"error: Prisma could not transcribe the file: {doc}")
    write_json(folder / "prisma.json", doc)

    segments = []
    for seg in doc["segments"]:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        spk = seg.get("speaker_id")
        segments.append({"i": len(segments), "start": round(float(seg["start_time"]), 2), "end": round(float(seg["end_time"]), 2),
                         "speaker": f"S{spk}" if spk is not None else None, "lang": seg.get("language_detected"), "text": text})
    langs = [s["lang"] for s in segments if s.get("lang")]
    info = {"engine": "gnani-prisma", "model": cfg["model"], "duration": float(doc.get("duration_seconds") or (segments[-1]["end"] if segments else 0)),
            "language": max(set(langs), key=langs.count) if langs else doc.get("language_code"),
            "languages": sorted(set(langs)), "denoise": cfg["with_denoise"], "keyterms": len(cfg.get("keyterms", [])),
            "job_id": doc.get("_job_id")}
    return segments, info


def run_whisper(audio: Path, args) -> tuple[list[dict], dict]:
    from faster_whisper import WhisperModel

    name = os.environ.get("FIELDNOTES_WHISPER_MODEL", "small")
    model = WhisperModel(name, device="cpu", compute_type="int8")
    lang = None if (args.language or "").startswith(("indic", "auto")) else (args.language or None)
    it, info = model.transcribe(decode_audio(audio), language=lang and lang.split("-")[0], vad_filter=True, beam_size=5)
    segments = [{"i": i, "start": round(s.start, 2), "end": round(s.end, 2), "speaker": None, "text": s.text.strip()}
                for i, s in enumerate(x for x in it if x.text.strip())]
    return segments, {"engine": "whisper-local", "model": name, "duration": info.duration, "language": info.language, "languages": [info.language]}


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--title", default="", help="short label, e.g. the account name")
    parser.add_argument("--consent", choices=["verbal", "rep-confirmed", "written", "notice"], help="how the customer consented")
    parser.add_argument("--consent-by", default="", help="who confirmed consent (chat handle of the rep)")
    parser.add_argument("--subject", default="", help="the customer who consented")
    parser.add_argument("--engine", choices=["prisma", "whisper"], default=None)
    parser.add_argument("--speakers", type=int, default=None, help="max speakers (Prisma, 1-8)")
    parser.add_argument("--language", default=None, help="e.g. indic-auto, hi-IN, 'hi-IN,en-IN', kn-IN")
    parser.add_argument("--topic", default=None, help="one line of context for the speech model")
    parser.add_argument("--no-denoise", action="store_true")
    parser.add_argument("--call-id", default=None)
    args = parser.parse_args()

    if not args.audio.is_file():
        raise SystemExit(f"error: audio file not found: {args.audio}")
    ws = workspace()
    privacy = ws.get("privacy") or {}
    engine = args.engine or (ws.get("speech") or {}).get("engine", "prisma")

    started = datetime.now()
    call_id = args.call_id or f"{started:%Y%m%d-%H%M}-{slugify(args.title or args.audio.stem)}"
    folder = CALLS / call_id

    # 1. Consent gate, before anything is stored or sent anywhere.
    from consent import has_consent, record

    if args.consent:
        folder.mkdir(parents=True, exist_ok=True)
        record(call_id, args.consent, args.consent_by or "unknown", args.subject)
    elif privacy.get("consent_required", True) and not has_consent(call_id):
        audit("transcribe.blocked_no_consent", call_id=call_id, file=args.audio.name)
        print(f"call_id: {call_id}")
        raise SystemExit("BLOCKED: no recording consent on file. Ask the rep: \"Did the customer agree to this "
                         "conversation being recorded?\" then rerun with --consent rep-confirmed --consent-by <handle> "
                         "(or --consent verbal if they agreed on the recording).")

    folder.mkdir(parents=True, exist_ok=True)
    audio_copy = folder / f"audio{args.audio.suffix.lower() or '.bin'}"
    if args.audio.resolve() != audio_copy.resolve():
        shutil.copyfile(args.audio, audio_copy)
    print(f"call_id: {call_id}")

    # 2. Speech to text.
    t0 = time.time()
    if engine == "prisma":
        segments, info = run_prisma(audio_copy, folder, ws, args)
    else:
        print("transcribing locally with Whisper (first run downloads the model)...", flush=True)
        segments, info = run_whisper(audio_copy, args)
    elapsed = time.time() - t0
    audit("transcribe.done", call_id=call_id, engine=info["engine"], model=info["model"], seconds=round(info["duration"], 1))

    transcript = {
        "call_id": call_id, "title": args.title, "source_file": args.audio.name,
        "recorded_at": started.isoformat(timespec="seconds"), "language": info["language"],
        "languages": info.get("languages"), "duration_sec": round(info["duration"], 1),
        "engine": info["engine"], "model": info["model"], "diarized": any(s.get("speaker") for s in segments),
        "segments": segments,
    }
    write_json(folder / "transcript.json", transcript)
    speakers = sorted({s["speaker"] for s in segments if s.get("speaker")})
    head = [f"# Transcript: {args.title or call_id}", "",
            f"Duration {fmt_ts(info['duration'])} · {info['engine']} {info['model']} · language {info['language']} · "
            f"{len(segments)} segments" + (f" · speakers {', '.join(speakers)}" if speakers else "")]
    body = [f"[{s['i']}] ({fmt_ts(s['start'])}){' ' + s['speaker'] if s.get('speaker') else ''} {s['text']}" for s in segments]
    (folder / "transcript.md").write_text("\n".join(head) + "\n\n" + "\n".join(body) + "\n", encoding="utf-8")

    # 3. PII redaction before any agent reads it.
    if privacy.get("redact_pii", True):
        subprocess.run([os.sys.executable, str(Path(__file__).with_name("redact.py")), call_id], check=True)

    words = sum(len(s["text"].split()) for s in segments)
    print(f"engine: {info['engine']} {info['model']}, language: {info['language']}, duration {fmt_ts(info['duration'])}")
    if speakers:
        talk = {sp: sum(s["end"] - s["start"] for s in segments if s.get("speaker") == sp) for sp in speakers}
        print("diarized speakers: " + ", ".join(f"{sp} ({fmt_ts(t)} talk)" for sp, t in talk.items()))
    print(f"segments: {len(segments)}, words: {words}, transcribed in {elapsed:.0f}s")
    print(f"wrote: {folder / 'transcript.md'}")
    print("next: map speakers with tools/speakers.py --map (diarized) or --turns (whisper), then write notes.md")


if __name__ == "__main__":
    main()
