"""Recording consent: no conversation is processed without a recorded notice and consent.

    python tools/consent.py record <call_id> --method verbal|rep-confirmed|written|notice \
        --by "<who confirmed>" [--subject "<customer name>"] [--evidence "<quote or note>"]
    python tools/consent.py check <call_id>          # exit 0 if consent is on file
    python tools/consent.py scan <call_id>           # look for a spoken consent in the transcript
    python tools/consent.py withdraw <call_id> --by "<who>"   # erases the call's data

Why: under India's DPDP Act 2023 (s.5 notice, s.6 consent; DPDP Rules 2025, core duties from
13 May 2027), a company recording a customer is processing personal data. Consent must be
specific to a purpose, and as easy to withdraw as to give. Nabz records:
who consented, how, for what purpose, when, and who confirmed it, before transcription starts.

Methods:
  verbal         the customer agreed on the recording ("haan, record kar lijiye")
  rep-confirmed  the rep confirms in chat the customer agreed before recording
  written        signed form / email on file
  notice         a published notice covers it (e.g. internal meetings); weakest, use sparingly
"""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone

from common import CALLS, audit, read_json, utf8_stdout, write_json

METHODS = ["verbal", "rep-confirmed", "written", "notice"]
PURPOSE = ("Meeting notes, coaching of our representative, CRM update and follow-up drafting "
           "for this business conversation. Not used for marketing or shared outside the company.")

# Phrases that indicate the recording was announced/agreed on tape (English, Hinglish, Hindi).
CONSENT_CUES = [
    r"\brecord(ing)?\b.{0,40}\b(okay|ok|fine|theek|thik|chalega|sure|yes|haan|ha)\b",
    r"\b(okay|ok|fine|theek|thik|chalega|sure|yes|haan|ha)\b.{0,40}\brecord",
    r"\bmind if i record\b", r"\bcan i record\b", r"\brecord kar (lu|loon|sakta|sakti|lijiye|lo)\b",
    r"रिकॉर्ड", r"\bconsent\b", r"\bsahmati\b", r"सहमति",
]


def consent_path(call_id: str):
    return CALLS / call_id / "consent.json"


def has_consent(call_id: str) -> dict | None:
    path = consent_path(call_id)
    if not path.exists():
        return None
    rec = read_json(path)
    return None if rec.get("withdrawn") else rec


def record(call_id: str, method: str, by: str, subject: str = "", evidence: str = "") -> dict:
    if method not in METHODS:
        raise SystemExit(f"error: --method must be one of {METHODS}")
    rec = {
        "call_id": call_id, "method": method, "confirmed_by": by, "subject": subject,
        "evidence": evidence, "purpose": PURPOSE,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "withdrawn": False,
    }
    write_json(consent_path(call_id), rec)
    audit("consent.recorded", actor=by, call_id=call_id, method=method, subject=subject)
    return rec


def scan(call_id: str) -> list[dict]:
    path = CALLS / call_id / "transcript.json"
    if not path.exists():
        return []
    hits = []
    for seg in read_json(path)["segments"]:
        low = seg["text"].lower()
        if any(re.search(p, low) for p in CONSENT_CUES):
            hits.append({"i": seg["i"], "start": seg["start"], "text": seg["text"]})
    return hits


def withdraw(call_id: str, by: str) -> None:
    folder = CALLS / call_id
    if not folder.exists():
        raise SystemExit(f"error: no call {call_id}")
    shutil.rmtree(folder)
    folder.mkdir(parents=True)
    write_json(consent_path(call_id), {"call_id": call_id, "withdrawn": True,
                                       "withdrawn_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                       "withdrawn_by": by})
    audit("consent.withdrawn+erased", actor=by, call_id=call_id)


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("call_id")
    r.add_argument("--method", required=True, choices=METHODS)
    r.add_argument("--by", required=True)
    r.add_argument("--subject", default="")
    r.add_argument("--evidence", default="")
    for name in ("check", "scan"):
        sub.add_parser(name).add_argument("call_id")
    w = sub.add_parser("withdraw")
    w.add_argument("call_id")
    w.add_argument("--by", required=True)
    args = parser.parse_args()

    if args.cmd == "record":
        rec = record(args.call_id, args.method, args.by, args.subject, args.evidence)
        print(f"consent recorded for {args.call_id}: {rec['method']}, confirmed by {rec['confirmed_by']}")
    elif args.cmd == "check":
        rec = has_consent(args.call_id)
        print(f"consent on file: {rec['method']} by {rec['confirmed_by']} at {rec['recorded_at']}" if rec else "NO consent on file")
        raise SystemExit(0 if rec else 3)
    elif args.cmd == "scan":
        hits = scan(args.call_id)
        print(f"{len(hits)} spoken consent cue(s)")
        for h in hits:
            print(f"  [{h['i']}] {h['text']}")
    else:
        withdraw(args.call_id, args.by)
        print(f"consent withdrawn: all data for {args.call_id} erased; tombstone kept for the audit trail")


if __name__ == "__main__":
    main()
