"""Process one visit end to end (what the web app runs for each upload).

    python tools/pipeline.py <audio> --rep arjun --account "Sharma Kirana" --segment Kirana \
        --consent rep-confirmed [--contact "Sharma ji"] [--region "Delhi NCR"] [--note "..."]

consent recorded → Gnani Prisma transcription + in-process PII redaction → spoken-consent check
(verbal consent must be on tape, else the visit waits for a manager's review) → Claude analysis
with verified quotes → speakers + measured metrics → Gnani Timbre voice debrief → done.

Every stage is resumable: run() skips work whose output already exists, so a visit interrupted by
a restart (see app/server.py startup) continues where it stopped. Between stages it checks the
visit hasn't been erased, and it never recreates an erased folder. Every external step has a
timeout. Progress goes to data/calls/<call_id>/status.json, which the web app polls.
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

from common import CALLS, CallErased, audit, is_erased, read_json, slugify, utf8_stdout, workspace, write_json

TOOLS = Path(__file__).resolve().parent
STAGES = {
    "queued": "Waiting to start…",
    "transcribing": "Transcribing with Gnani Prisma (Hinglish, code-mix, speaker diarization)…",
    "analysing": "Analysing with Claude: every quote verified against the transcript…",
    "voicing": "Recording the voice debrief with Gnani Timbre…",
    "needs_consent_review": "Waiting for a manager: verbal consent was not found on the recording",
    "done": "Done",
    "error": "Something went wrong",
}
PROCESSING = {"queued", "transcribing", "analysing", "voicing"}
FFMPEG_SAFE = ["-nostdin", "-protocol_whitelist", "file,pipe"]
ALLOWED_FORMATS = {"mov", "mp4", "m4a", "3gp", "matroska", "webm", "ogg", "mp3", "wav", "aac", "flac"}
ALLOWED_EXTENSIONS = {".webm", ".weba", ".ogg", ".oga", ".opus", ".m4a", ".mp4", ".mp3", ".wav", ".aac", ".flac"}


def limits() -> dict:
    srv = workspace().get("server") or {}
    return {"max_upload_mb": float(srv.get("max_upload_mb", 50)), "max_minutes": float(srv.get("max_minutes", 60)),
            "min_seconds": float(srv.get("min_seconds", 5)), "step_timeout": float(srv.get("step_timeout_minutes", 20)) * 60}


def member(handle: str) -> dict:
    for m in workspace().get("team", []):
        if m.get("handle") == handle:
            return m
    raise ValueError(f"unknown team member '{handle}'")


def set_status(call_id: str, status: str, **extra) -> None:
    path = CALLS / call_id / "status.json"
    data = read_json(path) if path.exists() else {}
    if status != "error":
        data.pop("error", None)
    data.update({"status": status, "stage": STAGES.get(status, status), "updated": datetime.now().isoformat(timespec="seconds"), **extra})
    write_json(path, data)


def safe_status(call_id: str, status: str, **extra) -> None:
    try:
        set_status(call_id, status, **extra)
    except (CallErased, FileNotFoundError, ValueError):
        pass


def new_call_id(account: str) -> str:
    now = datetime.now()
    return f"{now:%Y%m%d-%H%M%S}{now.microsecond // 1000:03d}-{secrets.token_hex(2)}-{slugify(account or 'visit')}"


def probe_audio(path: Path) -> tuple[str | None, float]:
    """Validate an uploaded file before anything else touches it: a known container, exactly one
    audio stream, sensible duration. ffprobe runs with a file-only protocol whitelist (no URLs,
    no playlists that fetch remote content) and a timeout. Returns (problem or None, seconds)."""
    lim = limits()
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type {path.suffix or '(none)'}. Use m4a, mp3, ogg, opus, webm or wav.", 0.0
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries",
                              "stream=codec_type,codec_name:format=format_name,duration", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=30)
        info = json.loads(out.stdout or "{}")
    except (subprocess.TimeoutExpired, ValueError):
        return "This file doesn't look like audio we can read.", 0.0
    fmt = info.get("format") or {}
    if not set((fmt.get("format_name") or "").split(",")) & ALLOWED_FORMATS:
        return "This file doesn't look like audio we can read. Record again, or upload an m4a, mp3, ogg or wav file.", 0.0
    streams = info.get("streams") or []
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    video = [s for s in streams if s.get("codec_type") == "video" and s.get("codec_name") not in ("mjpeg", "png")]
    if len(audio) != 1 or video:
        return "The file must contain exactly one audio track (no video).", 0.0
    try:
        secs = float(fmt.get("duration") or 0)
    except ValueError:
        secs = 0.0
    if secs < lim["min_seconds"]:
        return f"The recording is only {secs:.0f} seconds long. Record the whole conversation (at least {lim['min_seconds']:.0f} seconds).", secs
    if secs > lim["max_minutes"] * 60:
        return f"The recording is {secs / 60:.0f} minutes long; the limit is {lim['max_minutes']:.0f} minutes. Split it and upload the parts.", secs
    return None, secs


def create_visit(audio: Path, meta: dict) -> str:
    """Store the upload and the visit details, record consent, and queue it. Returns call_id."""
    from consent import record

    call_id = meta.get("call_id") or new_call_id(meta.get("account", ""))
    folder = CALLS / call_id
    folder.mkdir(parents=True, exist_ok=True)
    rep = member(meta["rep_handle"])
    note = meta.get("note", "") or ""
    meta = {**meta, "call_id": call_id, "rep_name": rep["name"], "rep_language": rep.get("language", "hi-en"),
            "region": meta.get("region") or rep.get("region", ""), "created": datetime.now().isoformat(timespec="seconds"),
            "synthetic": bool(meta.get("synthetic")) or "synthetic" in note.lower() or call_id.startswith("demo-")}
    upload = folder / f"upload{audio.suffix.lower() or '.webm'}"
    if audio.resolve() != upload.resolve():
        shutil.copyfile(audio, upload)
    meta["upload"] = upload.name
    write_json(folder / "visit.json", meta)
    record(call_id, meta["consent_method"], rep["handle"], meta.get("contact") or meta.get("account", ""), note)
    set_status(call_id, "queued")
    audit("visit.created", actor=rep["handle"], call_id=call_id, account=meta.get("account"), segment=meta.get("segment"),
          synthetic=meta["synthetic"])
    return call_id


def audio_problem(path: Path) -> str | None:
    """Catch empty, too-long or silent recordings before spending an API call on them."""
    problem, _ = probe_audio(path)
    if problem:
        return problem
    try:
        vol = subprocess.run(["ffmpeg", *FFMPEG_SAFE, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                             capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None
    for line in vol.stderr.splitlines():
        if "max_volume" in line:
            try:
                if float(line.split("max_volume:")[1].split("dB")[0]) < -50:
                    return "The recording is silent. Check the microphone isn't muted and the browser has permission to use it, then record again."
            except ValueError:
                pass
    return None


FRIENDLY = {
    "no speech detected": "No speech was detected. Check the microphone isn't muted, keep the phone near the conversation, and record again.",
    "Empty transcript": "No speech was detected. Check the microphone isn't muted, keep the phone near the conversation, and record again.",
    "did not finish within": "Transcription is taking longer than usual. Tap Retry in a few minutes.",
}


def friendly(msg: str) -> str:
    for key, text in FRIENDLY.items():
        if key.lower() in msg.lower():
            return text
    return msg


def _alive(call_id: str) -> bool:
    return (CALLS / call_id).is_dir() and not is_erased(call_id)


def _source_audio(folder: Path) -> Path | None:
    for pattern in ("upload.*", "audio.*"):
        for p in sorted(folder.glob(pattern)):
            if p.suffix.lower() in ALLOWED_EXTENSIONS:
                return p
    return None


def _step(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def run(call_id: str, py: str = sys.executable) -> None:
    """Process (or resume) one visit. Never raises; every outcome ends in status.json."""
    import consent

    if not _alive(call_id):
        return
    folder = CALLS / call_id
    timeout = limits()["step_timeout"]
    try:
        meta = read_json(folder / "visit.json")

        # 1. Transcription (skipped if a redacted transcript already exists)
        if not (folder / "transcript.json").exists():
            src = _source_audio(folder)
            if src is None:
                safe_status(call_id, "error", error="The original audio is no longer available (deleted by the retention policy).")
                return
            if src.suffix.lower() in (".webm", ".weba", ".mp4"):
                ogg = folder / "upload.ogg"
                res = subprocess.run(["ffmpeg", *FFMPEG_SAFE, "-y", "-loglevel", "error", "-i", str(src), "-vn", "-c:a", "copy", str(ogg)],
                                     capture_output=True, timeout=300)
                if res.returncode != 0 or not ogg.exists() or ogg.stat().st_size == 0:
                    _step(["ffmpeg", *FFMPEG_SAFE, "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                           "-c:a", "libopus", "-b:a", "24k", str(ogg)], 300)
                if src.name.startswith("upload"):
                    src.unlink()
                src = ogg
            problem = audio_problem(src)
            if problem:
                safe_status(call_id, "error", error=problem)
                audit("visit.rejected_audio", call_id=call_id, reason=problem)
                return
            set_status(call_id, "transcribing")
            cmd = [py, str(TOOLS / "transcribe.py"), str(src), "--title", meta.get("account", ""), "--call-id", call_id]
            if meta.get("recorded_at"):
                cmd += ["--recorded-at", meta["recorded_at"]]
            _step(cmd, timeout)
            for p in folder.glob("upload.*"):
                p.unlink()  # the folder keeps audio.<ext>; retention.py deletes it on schedule
        if not _alive(call_id):
            return

        # 2. Consent: verbal consent must be on tape, otherwise a manager reviews before any AI analysis.
        rec = consent.verify_spoken(call_id)
        if (rec["verified"] is False or rec.get("spoken_refusal")) and not rec.get("review"):
            reason = ("The customer appears to refuse recording on tape." if rec.get("spoken_refusal")
                      else "No spoken consent found in the first 90 seconds of the recording.")
            set_status(call_id, "needs_consent_review", error=reason)
            audit("visit.held_for_consent_review", call_id=call_id, reason=reason)
            return
        if not _alive(call_id):
            return

        # 3. Analysis (skipped if done)
        if not (folder / "analysis.json").exists():
            set_status(call_id, "analysing")
            import llm

            try:
                llm.analyse(call_id, meta, meta.get("lens", "auto"), verbose=False)
            except Exception as exc:
                rejected = getattr(llm, "AnalysisRejected", None)
                if rejected and isinstance(exc, rejected):
                    safe_status(call_id, "error", error="The AI analysis could not be verified against the transcript, so nothing "
                                                        "was saved. Tap Retry, or ask a manager to review the transcript.")
                    audit("visit.analysis_rejected", call_id=call_id, reason=str(exc)[:200])
                    return
                raise
        if not _alive(call_id):
            return

        # 4. Measured metrics, only if our rep is on the recording
        spk = read_json(folder / "speakers.json") if (folder / "speakers.json").exists() else {}
        if spk.get("rep_present", True) and not (folder / "metrics.json").exists():
            _step([py, str(TOOLS / "metrics.py"), call_id], 120)
        if not _alive(call_id):
            return

        # 5. Voice debrief
        if (workspace().get("voice_debrief") or {}).get("enabled", True) and not (folder / "debrief.ogg").exists():
            set_status(call_id, "voicing")
            _step([py, str(TOOLS / "voice.py"), "debrief", call_id, "--language", meta.get("rep_language", "hi-en")], 180)
        set_status(call_id, "done")
        audit("visit.processed", call_id=call_id)
    except CallErased:
        return  # consent was withdrawn mid-processing: stop quietly, the erasure is already logged
    except subprocess.TimeoutExpired as exc:
        safe_status(call_id, "error", error="A processing step took too long. Tap Retry.")
        audit("visit.failed", call_id=call_id, error=f"timeout: {Path(str(exc.cmd[1])).name if exc.cmd else ''}")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        last = detail[-1] if detail else str(exc)
        safe_status(call_id, "error", error=friendly(last)[:300])
        audit("visit.failed", call_id=call_id, error=last[:200])
    except BaseException as exc:  # noqa: BLE001: SystemExit from helpers included; no visit is left stuck
        if isinstance(exc, KeyboardInterrupt):
            raise
        traceback.print_exc()
        safe_status(call_id, "error", error=friendly(f"{exc}")[:300])
        try:
            audit("visit.failed", call_id=call_id, error=f"{type(exc).__name__}: {exc}"[:200])
        except Exception:  # noqa: BLE001
            pass


def pending_visits() -> list[str]:
    """Visits that were mid-processing when the server stopped (requeued on startup)."""
    out = []
    if not CALLS.exists():
        return out
    for folder in CALLS.iterdir():
        st = folder / "status.json"
        if st.exists() and not is_erased(folder.name):
            try:
                if read_json(st).get("status") in PROCESSING:
                    out.append(folder.name)
            except ValueError:
                continue
    return sorted(out)


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--rep", required=True, help="team handle")
    parser.add_argument("--account", required=True)
    parser.add_argument("--contact", default="")
    parser.add_argument("--segment", default="Other")
    parser.add_argument("--region", default="")
    parser.add_argument("--consent", required=True, choices=["verbal", "rep-confirmed", "written"])
    parser.add_argument("--note", default="")
    parser.add_argument("--lens", default="auto")
    parser.add_argument("--call-id", default=None)
    parser.add_argument("--recorded-at", default=None)
    args = parser.parse_args()
    problem, _ = probe_audio(args.audio)
    if problem:
        raise SystemExit(problem)
    call_id = create_visit(args.audio, {"rep_handle": args.rep, "account": args.account, "contact": args.contact,
                                        "segment": args.segment, "region": args.region, "consent_method": args.consent,
                                        "note": args.note, "lens": args.lens, "call_id": args.call_id,
                                        "recorded_at": args.recorded_at})
    print(f"call_id: {call_id}")
    run(call_id)
    print(read_json(CALLS / call_id / "status.json"))


if __name__ == "__main__":
    main()
