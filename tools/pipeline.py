"""Process one visit end to end (what the web app runs for each upload).

    python tools/pipeline.py <audio> --rep arjun --account "Sharma Kirana" --segment Kirana \
        --consent rep-confirmed [--contact "Sharma ji"] [--region "Delhi NCR"] [--note "..."]

consent (recorded first) → Gnani Prisma transcription + PII redaction → Claude analysis with
verified quotes → speakers + measured metrics → Gnani Timbre voice debrief → done.
Progress is written to data/calls/<call_id>/status.json, which the web app polls.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

from common import CALLS, audit, read_json, slugify, utf8_stdout, workspace, write_json

TOOLS = Path(__file__).resolve().parent
STAGES = {
    "queued": "Waiting to start…",
    "transcribing": "Transcribing with Gnani Prisma (diarization, Hinglish, denoise)…",
    "analysing": "Analysing with Claude: every quote verified against the transcript…",
    "voicing": "Recording the voice debrief with Gnani Timbre…",
    "done": "Done",
    "error": "Something went wrong",
}


def member(handle: str) -> dict:
    for m in workspace().get("team", []):
        if m.get("handle") == handle:
            return m
    raise ValueError(f"unknown team member '{handle}'")


def set_status(call_id: str, status: str, **extra) -> None:
    path = CALLS / call_id / "status.json"
    data = read_json(path) if path.exists() else {}
    data.update({"status": status, "stage": STAGES.get(status, status), "updated": datetime.now().isoformat(timespec="seconds"), **extra})
    write_json(path, data)


def new_call_id(account: str) -> str:
    base = f"{datetime.now():%Y%m%d-%H%M%S}-{slugify(account or 'visit')}"
    return base


def create_visit(audio: Path, meta: dict) -> str:
    """Store the upload and the visit details, record consent, and queue it. Returns call_id."""
    from consent import record

    call_id = meta.get("call_id") or new_call_id(meta.get("account", ""))
    folder = CALLS / call_id
    folder.mkdir(parents=True, exist_ok=True)
    rep = member(meta["rep_handle"])
    meta = {**meta, "call_id": call_id, "rep_name": rep["name"], "rep_language": rep.get("language", "hi-en"),
            "region": meta.get("region") or rep.get("region", ""), "created": datetime.now().isoformat(timespec="seconds")}
    upload = folder / f"upload{audio.suffix.lower() or '.webm'}"
    if audio.resolve() != upload.resolve():
        shutil.copyfile(audio, upload)
    meta["upload"] = upload.name
    write_json(folder / "visit.json", meta)
    record(call_id, meta["consent_method"], rep["handle"], meta.get("contact") or meta.get("account", ""), meta.get("note", ""))
    set_status(call_id, "queued")
    audit("visit.created", actor=rep["handle"], call_id=call_id, account=meta.get("account"), segment=meta.get("segment"))
    return call_id


def audio_problem(path: Path, min_seconds: float = 5.0) -> str | None:
    """Catch empty or silent recordings before spending an API call on them."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True)
    try:
        secs = float(probe.stdout.strip())
    except ValueError:
        return "This file doesn't look like audio we can read. Record again, or upload an m4a, mp3, ogg or wav file."
    if secs < min_seconds:
        return f"The recording is only {secs:.0f} seconds long. Record the whole conversation (at least {min_seconds:.0f} seconds)."
    vol = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True)
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
}


def friendly(msg: str) -> str:
    for key, text in FRIENDLY.items():
        if key.lower() in msg.lower():
            return text
    return msg


def run(call_id: str, py: str = sys.executable) -> None:
    folder = CALLS / call_id
    meta = read_json(folder / "visit.json")
    try:
        upload = folder / meta["upload"]
        # Browsers record webm/opus; Prisma takes ogg/opus. Re-wrap without re-encoding where possible.
        if upload.suffix in (".webm", ".weba", ".mp4", ".3gp", ".caf"):
            ogg = folder / "upload.ogg"
            res = subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(upload), "-vn", "-c:a", "copy", str(ogg)],
                                 capture_output=True)
            if res.returncode != 0 or ogg.stat().st_size == 0:
                subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(upload), "-vn", "-ac", "1", "-ar", "16000",
                                "-c:a", "libopus", "-b:a", "24k", str(ogg)], check=True, capture_output=True)
            upload.unlink()
            upload = ogg

        problem = audio_problem(upload)
        if problem:
            set_status(call_id, "error", error=problem)
            audit("visit.rejected_audio", call_id=call_id, reason=problem)
            return

        set_status(call_id, "transcribing")
        subprocess.run([py, str(TOOLS / "transcribe.py"), str(upload), "--title", meta.get("account", ""),
                        "--call-id", call_id], check=True, capture_output=True, text=True, encoding="utf-8")
        if upload.exists() and upload.name.startswith("upload"):
            upload.unlink()  # the call folder keeps audio.<ext>; retention.py deletes it on schedule

        set_status(call_id, "analysing")
        from llm import analyse
        analyse(call_id, meta, meta.get("lens", "auto"), verbose=False)
        spk = read_json(folder / "speakers.json") if (folder / "speakers.json").exists() else {}
        if spk.get("rep_present", True):  # talk ratio etc. only make sense if our rep is on the recording
            subprocess.run([py, str(TOOLS / "metrics.py"), call_id], check=True, capture_output=True)

        if (workspace().get("voice_debrief") or {}).get("enabled", True):
            set_status(call_id, "voicing")
            subprocess.run([py, str(TOOLS / "voice.py"), "debrief", call_id, "--language", meta.get("rep_language", "hi-en")],
                           check=True, capture_output=True, text=True, encoding="utf-8")
        set_status(call_id, "done")
        audit("visit.processed", call_id=call_id)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        set_status(call_id, "error", error=friendly(detail[-1] if detail else str(exc))[:300])
        audit("visit.failed", call_id=call_id, error=(detail[-1] if detail else str(exc))[:200])
    except Exception as exc:  # noqa: BLE001: report any failure to the UI
        traceback.print_exc()
        set_status(call_id, "error", error=friendly(f"{exc}")[:300])
        audit("visit.failed", call_id=call_id, error=f"{type(exc).__name__}: {exc}"[:200])


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
    args = parser.parse_args()
    call_id = create_visit(args.audio, {"rep_handle": args.rep, "account": args.account, "contact": args.contact,
                                        "segment": args.segment, "region": args.region, "consent_method": args.consent,
                                        "note": args.note, "lens": args.lens, "call_id": args.call_id})
    print(f"call_id: {call_id}")
    run(call_id)
    print(read_json(CALLS / call_id / "status.json"))


if __name__ == "__main__":
    main()
