"""Snapshot the synthetic demo visits into deploy/seed/ for the container image.

    python deploy/make_seed.py

Copies only what the app shows (redacted transcript, analysis, notes, proposals, scorecard, voice
debrief). Never copies raw audio, unredacted transcripts or Prisma output, and only visits marked
synthetic (call_id starts with "demo-").
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "data" / "calls", ROOT / "deploy" / "seed" / "calls"
KEEP = {"analysis.json", "transcript.json", "transcript.md", "transcript_labeled.md", "speakers.json", "metrics.json",
        "scorecard.png", "notes.md", "followup.md", "followup.json", "crm_proposal.json", "consent.json", "visit.json",
        "status.json", "redactions.json", "debrief.ogg"}

if DST.exists():
    shutil.rmtree(DST)
n = 0
for folder in sorted(SRC.glob("demo-*")):
    out = DST / folder.name
    out.mkdir(parents=True)
    for f in folder.iterdir():
        if f.name in KEEP:
            shutil.copy2(f, out / f.name)
    n += 1
size = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file())
print(f"seeded {n} synthetic visits into {DST} ({size / 1e6:.1f} MB)")
