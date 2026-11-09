"""Voice debriefs with Gnani AI's Timbre: the rep hears their coaching, in their language.

    python tools/voice.py debrief <call_id> [--language hi-en] [--voice Shivani]
    python tools/voice.py say "text" --out file.ogg [--language kn-IN]
    python tools/voice.py voices

Field reps are on bikes and in shops, not at desks. A 20-30 second voice note in the language
they think in ("Arjun, BrightMart ki meeting achhi rahi...") is heard; a scorecard is skimmed.

`debrief` reads the `debrief` text the analyst wrote in analysis.json, speaks it with Timbre and
writes data/calls/<call_id>/debrief.ogg: an Opus voice note that Telegram and WhatsApp play
inline. The rep's language comes from config/workspace.yaml (team[].language) unless given.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import audit, call_dir, read_json, utf8_stdout, workspace
from gnani import LANGUAGES, TIMBRE_V3_VOICES, synthesize


def rep_language(ws: dict, rep: str) -> str | None:
    rep_l = rep.lower()
    for m in ws.get("team", []):
        if m.get("name", "").lower() in rep_l or rep_l in m.get("name", "").lower() or m.get("handle", "").lower() == rep_l:
            return m.get("language")
    return None


def chunks(text: str, limit: int = 450) -> list[str]:
    """Timbre returns 500 on very long text; split on sentence boundaries."""
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?।])\s+", text.strip()):
        if cur and len(cur) + len(sent) > limit:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    return parts + ([cur] if cur else [])


def speak(text: str, out: Path, language: str, voice: str, model: str, call_id: str | None = None) -> Path:
    pieces = chunks(text)
    if len(pieces) == 1:
        return synthesize(text, out, voice=voice, language=language, model=model, call_id=call_id)
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        files = [synthesize(p, Path(tmp) / f"{i}.ogg", voice=voice, language=language, model=model, call_id=call_id)
                 for i, p in enumerate(pieces)]
        listing = Path(tmp) / "list.txt"
        listing.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c:a", "libopus", "-b:a", "32k", str(out)], check=True)
    return out


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("debrief")
    d.add_argument("call_id")
    d.add_argument("--language", choices=LANGUAGES)
    d.add_argument("--voice")
    s = sub.add_parser("say")
    s.add_argument("text")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--language", default="hi-en", choices=LANGUAGES)
    s.add_argument("--voice", default="Shivani")
    sub.add_parser("voices")
    args = parser.parse_args()

    ws = workspace()
    cfg = ws.get("voice_debrief") or {}
    model = cfg.get("model", "timbre-v3.0")
    if args.cmd == "voices":
        print(f"{model} voices (each speaks: {', '.join(LANGUAGES)}):")
        print(", ".join(TIMBRE_V3_VOICES))
        return
    if args.cmd == "say":
        path = speak(args.text, args.out, args.language, args.voice, model)
        print(f"wrote {path}")
        return

    folder = call_dir(args.call_id)
    a = read_json(folder / "analysis.json")
    text = (a.get("debrief") or "").strip()
    if not text:
        raise SystemExit("error: analysis.json has no 'debrief' text. The analyst writes it (see playbooks/analyst.md).")
    language = args.language or rep_language(ws, a.get("rep", "")) or cfg.get("default_language", "hi-en")
    voice = args.voice or cfg.get("voice", "Shivani")
    out = speak(text, folder / "debrief.ogg", language, voice, model, call_id=args.call_id)
    audit("debrief.voiced", call_id=args.call_id, language=language, voice=voice, chars=len(text))
    print(f"wrote {out} ({out.stat().st_size // 1024} KB, {language}, voice {voice}). Send it with send_attachment.")


if __name__ == "__main__":
    main()
