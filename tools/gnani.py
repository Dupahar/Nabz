"""Thin client for Gnani AI's Prisma (speech-to-text) and Timbre (text-to-speech) APIs.

    python tools/gnani.py stt <audio> [--language indic-auto] [--speakers 2] [--denoise] [--keyterms "Tally,Zoho"]
    python tools/gnani.py tts "Namaste Arjun..." --out hello.ogg [--voice Shivani] [--language hi-en]

Used by transcribe.py, voice.py and the benchmark. Reads GNANI_API_KEY from the environment or
from .env in the project root. Every billed call is appended to data/usage.jsonl (see cost.py).

API notes (docs.gnani.ai):
  * Batch STT is the only mode with diarization and long audio (4 h, 10 MB per multipart file;
    phone formats like ogg/opus, m4a, mp3 and wav are accepted). REST STT is limited to 30 s clips.
  * Create a job, then start it; poll at least 10 s apart; transcript_url expires after 1 h.
  * Cloudflare in front of the API rejects clients without a User-Agent (HTTP 403, error 1010).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from common import DATA, ROOT, utf8_stdout

BASE = "https://api.vachana.ai"
BATCH = f"{BASE}/stt/v3/batch/jobs"
TTS = f"{BASE}/api/v1/tts/inference"
USER_AGENT = "nabz/0.1 (+https://github.com/Dupahar/Nabz)"
TERMINAL = {"COMPLETED", "PARTIAL_FAILURE", "FAILED", "START_FAILED", "CANCELLED"}
USAGE = DATA / "usage.jsonl"

AUDIO_TYPES = {".wav": "audio/wav", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg",
               ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac"}

# Timbre v3.0 voices speak all ten languages; v2.5 voices each have one preferred language.
TIMBRE_V3_VOICES = ["Avinash", "Shivani", "Lakshmi", "Kalpana", "Shubham", "Prakash", "Devansh",
                    "Yashraj", "Chetana", "Vasudha", "Riyaa", "Tarika", "Harshad"]
LANGUAGES = ["auto", "hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "bn-IN", "gu-IN", "hi-en"]


class GnaniError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("GNANI_API_KEY", "").strip()
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GNANI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise GnaniError("GNANI_API_KEY is not set. Put it in .env (see .env.example).")
    return key


def _headers() -> dict:
    return {"X-API-Key-ID": api_key(), "User-Agent": USER_AGENT}


def _request(method: str, url: str, *, retries: int = 6, **kw) -> requests.Response:
    """HTTP with backoff on 429/5xx. The batch API rate-limits bursts of polling calls."""
    delay = 4.0
    for attempt in range(retries):
        resp = requests.request(method, url, timeout=kw.pop("timeout", 120), **kw)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == retries - 1:
                break
            wait = float(resp.headers.get("Retry-After") or delay)
            time.sleep(wait)
            delay = min(delay * 2, 60)
            for value in kw.get("files") or []:  # rewind uploads before retrying
                fh = value[1][1] if isinstance(value[1], tuple) and len(value[1]) > 1 else None
                if hasattr(fh, "seek"):
                    fh.seek(0)
            continue
        return resp
    raise GnaniError(f"{method} {url.split('?')[0]} failed after {retries} tries: HTTP {resp.status_code} {resp.text[:300]}")


def _check(resp: requests.Response, what: str) -> dict:
    if resp.status_code >= 400:
        raise GnaniError(f"{what}: HTTP {resp.status_code} {resp.text[:400]}")
    return resp.json()


def log_usage(kind: str, **fields) -> None:
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind, **fields}
    with USAGE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def stt_config(*, model: str = "prisma-v3.0", language: str = "indic-auto", fmt: str | None = "codemix",
               speakers: int | None = 2, denoise: bool = False, keyterms: list[str] | None = None,
               topic: str | None = None, speaker_names: list[str] | None = None) -> dict:
    cfg: dict = {"model": model, "language_code": language, "mode": "transcribe", "with_diarization": True,
                 "is_multi_channel": False, "with_denoise": denoise}
    if speakers:
        cfg["num_speakers"] = speakers
    if model.startswith("prisma-v3"):
        if fmt:
            cfg["format"] = fmt
        # Gnani rejects keyterms together with speaker_names; keyterms (product names, prices,
        # competitors) matter more for business accuracy, so they win.
        if keyterms:
            cfg["keyterms"] = [k for k in dict.fromkeys(keyterms) if k and "<|" not in k][:200]
        elif speaker_names:
            cfg["speaker_names"] = speaker_names[:4]
        if topic:
            cfg["topic"] = topic[:1600]
    elif keyterms:
        cfg["bias_list"] = keyterms[:100]
    return cfg


def transcribe_batch(paths: list[Path], config: dict, *, poll: float = 10.0, call_ids: list[str] | None = None,
                     verbose: bool = True) -> dict[str, dict]:
    """Run one batch job over up to 100 files. Returns {file name: transcript document}."""
    if not paths:
        return {}
    handles = []
    try:
        files = [("config", (None, json.dumps(config), "application/json"))]
        for p in paths:
            fh = open(p, "rb")
            handles.append(fh)
            ctype = AUDIO_TYPES.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            files.append(("files", (p.name, fh, ctype)))
        job = _check(_request("POST", BATCH, headers=_headers(), files=files), "create job")
    finally:
        for fh in handles:
            fh.close()
    job_id = job["job_id"]
    _check(_request("POST", f"{BATCH}/{job_id}/start", headers=_headers()), "start job")
    if verbose:
        print(f"prisma job {job_id}: {len(paths)} file(s), model {config['model']}", flush=True)

    t0 = time.time()
    while True:
        time.sleep(poll)
        status = _check(_request("GET", f"{BATCH}/{job_id}", headers=_headers()), "job status")
        if verbose:
            prog = status.get("progress") or {}
            print(f"  {time.time() - t0:4.0f}s {status.get('status')} {prog.get('completed_files', 0)}/{prog.get('total_files', len(paths))}", flush=True)
        if status.get("status") in TERMINAL:
            break
    if status["status"] not in {"COMPLETED", "PARTIAL_FAILURE"}:
        reasons = []
        try:
            listing = _check(_request("GET", f"{BATCH}/{job_id}/files", headers=_headers()), "list files")
            reasons = [e.get("error_message") for e in listing.get("data", []) if e.get("error_message")]
        except GnaniError:
            pass
        raise GnaniError("; ".join(reasons) or f"Prisma job {job_id} ended {status['status']}")

    time.sleep(2)
    listing = _check(_request("GET", f"{BATCH}/{job_id}/files", headers=_headers()), "list files")
    out: dict[str, dict] = {}
    call_of = dict(zip([p.name for p in paths], call_ids or []))
    for entry in listing.get("data", []):
        name = Path(entry.get("original_path", "")).name
        if entry.get("status") != "COMPLETED" or not entry.get("transcript_url"):
            out[name] = {"error": entry.get("status"), "detail": entry}
            continue
        doc = _check(_request("GET", entry["transcript_url"], headers={"User-Agent": USER_AGENT}), "download transcript")
        doc["_job_id"] = job_id
        out[name] = doc
        log_usage("stt", model=config["model"], seconds=float(doc.get("duration_seconds") or entry.get("duration_seconds") or 0),
                  denoise=config.get("with_denoise", False), job_id=job_id, file=name, call_id=call_of.get(name))
    return out


def synthesize(text: str, out: Path, *, voice: str = "Shivani", language: str = "hi-en", model: str = "timbre-v3.0",
               speed: float = 1.0, container: str = "ogg", sample_rate: int = 24000, call_id: str | None = None) -> Path:
    """Text to speech. container='ogg' gives an Opus voice note that Telegram/WhatsApp play inline."""
    audio_config: dict = {"container": container, "sample_rate": sample_rate}
    if container == "ogg":
        audio_config["encoding"] = "oggopus"
    body = {"text": text, "model": model, "voice": voice, "language": language, "speed": speed, "audio_config": audio_config}
    resp = _request("POST", TTS, headers={**_headers(), "Content-Type": "application/json"}, data=json.dumps(body))
    if resp.status_code >= 400:
        raise GnaniError(f"tts: HTTP {resp.status_code} {resp.text[:300]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    log_usage("tts", model=model, voice=voice, language=language, chars=len(text), call_id=call_id)
    return out


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stt")
    s.add_argument("audio", type=Path, nargs="+")
    s.add_argument("--model", default="prisma-v3.0")
    s.add_argument("--language", default="indic-auto")
    s.add_argument("--format", default="codemix")
    s.add_argument("--speakers", type=int, default=2)
    s.add_argument("--denoise", action="store_true")
    s.add_argument("--keyterms", default="")
    s.add_argument("--topic", default=None)
    s.add_argument("--out", type=Path, default=None, help="write the raw transcript JSON here (single file)")
    t = sub.add_parser("tts")
    t.add_argument("text")
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--voice", default="Shivani")
    t.add_argument("--language", default="hi-en", choices=LANGUAGES)
    t.add_argument("--model", default="timbre-v3.0")
    t.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    if args.cmd == "stt":
        cfg = stt_config(model=args.model, language=args.language, fmt=args.format or None, speakers=args.speakers,
                         denoise=args.denoise, keyterms=[k.strip() for k in args.keyterms.split(",") if k.strip()],
                         topic=args.topic)
        docs = transcribe_batch(args.audio, cfg)
        for name, doc in docs.items():
            if args.out and len(docs) == 1:
                args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"wrote {args.out}")
            for seg in doc.get("segments", [])[:200]:
                print(f"{name} {seg['start_time']:7.1f} spk{seg.get('speaker_id')} {seg['text']}")
    else:
        path = synthesize(args.text, args.out, voice=args.voice, language=args.language, model=args.model, speed=args.speed)
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
