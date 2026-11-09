"""Recording consent: no conversation is processed without a recorded notice and consent.

    python tools/consent.py record <call_id> --method verbal|rep-confirmed|written|notice \
        --by "<who confirmed>" [--subject "<customer name>"] [--evidence "<quote or note>"]
    python tools/consent.py check <call_id>          # exit 0 if consent is on file and not refuted
    python tools/consent.py scan <call_id>           # list spoken consent cues in the transcript
    python tools/consent.py verify <call_id>         # check "verbal" consent against the transcript
    python tools/consent.py confirm <call_id> --by <manager>   # manager review of unverified consent
    python tools/consent.py withdraw <call_id> --by "<who>"     # erase everything about the visit

Why: under India's DPDP Act 2023 (s.5 notice, s.6 consent; DPDP Rules 2025, core duties from
13 May 2027), a company recording a customer is processing personal data. Consent must be
specific to a purpose, and as easy to withdraw as to give.

What is enforced:
  * Nothing is stored or sent anywhere until a consent record exists (who, how, purpose, when).
  * "verbal" consent is VERIFIED against the transcript: the ask ("record kar loon?") and the
    customer's yes must be on tape in the first ~90 seconds. If not, the visit stops at
    "needs_consent_review": no AI analysis runs until a manager reviews it.
  * Withdrawal erases the visit everywhere Nabz stores it (call folder, CRM entries, usage rows),
    cancels any in-flight transcription job, and leaves only a tombstone and a pseudonymised
    audit event, so the erasure itself is provable without keeping the person's data.

consent.json fields: method, confirmed_by, subject, purpose, recorded_at, withdrawn,
verified (true|false for verbal; null for other methods), verified_segment, review.

Methods:
  verbal         the customer agreed on the recording ("haan, record kar lijiye")
  rep-confirmed  the rep attests the customer agreed before recording
  written        signed form / email on file
  notice         a published notice covers it (internal meetings); weakest, use sparingly
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone

from common import CALLS, CRM_FILE, DATA, ERASED_FILE, audit, is_erased, pseudonym, read_json, utf8_stdout, write_json

METHODS = ["verbal", "rep-confirmed", "written", "notice"]
PURPOSE = ("Meeting notes, coaching of our representative, CRM update and follow-up drafting "
           "for this business conversation. Not used for marketing or shared outside the company.")
VERIFY_WINDOW_SEC = 90

# The rep asks to record (English, Roman Hinglish, Devanagari).
ASK_CUES = [
    r"\brecord(ing)?\b", r"रिकॉर्ड", r"रेकॉर्ड", r"रिकार्ड", r"\bconsent\b", r"\bsahmati\b", r"सहमति",
]
# The customer agrees.
YES_CUES = [
    r"\b(yes|yeah|okay|ok|sure|fine|of course|go ahead|no problem)\b",
    r"\b(haan|haa|han|ha|ji haan|theek|thik|thick|chalega|kar lo|kar lijiye|koi baat nahi|bilkul)\b",
    r"हाँ", r"हां", r"हा\b", r"ठीक", r"चलेगा", r"कर लो", r"कर लीजिए", r"कोई बात नहीं", r"बिल्कुल", r"जी",
]
NO_CUES = [r"\b(no|nahi|mat karo|don't)\b.{0,15}\brecord", r"रिकॉर्ड.{0,15}(मत|नहीं)", r"\bmat record"]


def consent_path(call_id: str):
    return CALLS / call_id / "consent.json"


def has_consent(call_id: str) -> dict | None:
    """The consent record, unless it was withdrawn or refuted by the transcript (and not reviewed)."""
    path = consent_path(call_id)
    if not path.exists():
        return None
    rec = read_json(path)
    if rec.get("withdrawn"):
        return None
    if rec.get("verified") is False and not rec.get("review"):
        return None
    return rec


def record(call_id: str, method: str, by: str, subject: str = "", evidence: str = "") -> dict:
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    rec = {
        "call_id": call_id, "method": method, "confirmed_by": by, "subject": subject,
        "evidence": evidence, "purpose": PURPOSE,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "withdrawn": False,
        "verified": None, "verified_segment": None, "review": None,
    }
    write_json(consent_path(call_id), rec)
    audit("consent.recorded", actor=by, call_id=call_id, method=method, subject=pseudonym(subject))
    return rec


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def scan(call_id: str, window_sec: float | None = None) -> list[dict]:
    """Segments that mention recording/consent, each with whether a yes follows within 2 segments."""
    path = CALLS / call_id / "transcript.json"
    if not path.exists():
        return []
    segs = read_json(path)["segments"]
    hits = []
    for k, seg in enumerate(segs):
        if window_sec is not None and seg["start"] > window_sec:
            break
        low = seg["text"].lower()
        if not _any(ASK_CUES, low):
            continue
        refused = False
        yes_at = None
        asker = seg.get("speaker")
        # The agreement must be a REPLY: a later segment, by a different speaker when diarization
        # says who is who. The rep's own "theek hai?" in the question doesn't count.
        for j in range(k + 1, min(k + 4, len(segs))):
            reply = segs[j]
            if asker and reply.get("speaker") == asker:
                continue
            nxt = reply["text"].lower()
            if _any(NO_CUES, nxt) or re.match(r"^\s*(no|nahi|nahin|नहीं|ना)\b", nxt):
                refused = True
                break
            if _any(YES_CUES, nxt):
                yes_at = reply["i"]
                break
        hits.append({"i": seg["i"], "start": seg["start"], "text": seg["text"], "agreed_segment": yes_at, "refused": refused})
    return hits


def verify_spoken(call_id: str) -> dict:
    """Check consent against the transcript and record the result in consent.json.
    verbal: verified true/false.  Other methods: verified stays null (attested, not provable on tape),
    but a spoken consent found on tape is still noted in verified_segment."""
    path = consent_path(call_id)
    rec = read_json(path)
    hits = scan(call_id, VERIFY_WINDOW_SEC)
    good = next((h for h in hits if h["agreed_segment"] is not None and not h["refused"]), None)
    refused = any(h["refused"] for h in hits)
    if rec["method"] == "verbal":
        rec["verified"] = bool(good) and not refused
    rec["verified_segment"] = good["agreed_segment"] if good else None
    rec["spoken_refusal"] = refused
    rec["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(path, rec)
    audit("consent.verified", call_id=call_id, method=rec["method"], verified=rec["verified"],
          segment=rec["verified_segment"], refused=refused)
    return rec


def confirm(call_id: str, by: str, note: str = "") -> dict:
    """A manager reviewed a visit whose verbal consent could not be verified, and confirms it."""
    path = consent_path(call_id)
    rec = read_json(path)
    rec["review"] = {"confirmed_by": by, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": note}
    write_json(path, rec)
    audit("consent.reviewed", actor=by, call_id=call_id)
    return rec


def _purge_usage(call_id: str) -> int:
    usage = DATA / "usage.jsonl"
    if not usage.exists():
        return 0
    keep, dropped = [], 0
    for line in usage.read_text(encoding="utf-8").splitlines():
        try:
            if json.loads(line).get("call_id") == call_id:
                dropped += 1
                continue
        except ValueError:
            pass
        keep.append(line)
    tmp = usage.with_name(f"usage.jsonl.{os.getpid()}.tmp")
    tmp.write_text("".join(x + "\n" for x in keep), encoding="utf-8")
    os.replace(tmp, usage)
    return dropped


def _purge_crm(call_id: str) -> list[str]:
    if not CRM_FILE.exists():
        return []
    import crm

    db = read_json(CRM_FILE)
    removed = crm.purge_call(db, call_id)
    if removed:
        write_json(CRM_FILE, db)
    return removed


def _cancel_gnani_job(folder) -> bool:
    job = folder / "job.json"
    if not job.exists():
        return False
    try:
        from gnani import cancel_job

        return cancel_job(read_json(job)["job_id"], "consent withdrawn")
    except Exception:  # noqa: BLE001: best effort
        return False


def erase(call_id: str, by: str, reason: str = "consent withdrawn") -> dict:
    """Erase every trace of a visit Nabz controls. Order matters: the tombstone goes first, so a
    pipeline that is still running can no longer write into the folder (common.guard_not_erased)."""
    if "/" in call_id or "\\" in call_id or ".." in call_id or not call_id:
        raise ValueError("bad call id")
    folder = CALLS / call_id
    subject = None
    for name in ("consent.json", "visit.json"):
        p = folder / name
        if p.exists():
            try:
                d = read_json(p)
                subject = subject or d.get("subject") or d.get("contact")
            except ValueError:
                pass
    if not is_erased(call_id):
        ERASED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ERASED_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"call_id": call_id, "erased_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "by": by, "reason": reason, "subject": pseudonym(subject)}) + "\n")
    cancelled = _cancel_gnani_job(folder) if folder.exists() else False
    crm_removed = _purge_crm(call_id)
    usage_removed = _purge_usage(call_id)
    for attempt in range(5):  # Windows: a worker may briefly hold a file open
        try:
            if folder.exists():
                shutil.rmtree(folder)
            break
        except OSError:
            time.sleep(0.5)
    summary = {"folder_deleted": not folder.exists(), "crm": crm_removed, "usage_rows": usage_removed,
               "gnani_job_cancelled": cancelled}
    audit("erasure.done", actor=by, call_id=call_id, reason=reason, subject=pseudonym(subject),
          folder_deleted=summary["folder_deleted"], crm_items=len(crm_removed), usage_rows=usage_removed)
    return summary


def withdraw(call_id: str, by: str) -> dict:
    return erase(call_id, by, "consent withdrawn")


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
    for name in ("check", "scan", "verify"):
        sub.add_parser(name).add_argument("call_id")
    c = sub.add_parser("confirm")
    c.add_argument("call_id")
    c.add_argument("--by", required=True)
    w = sub.add_parser("withdraw")
    w.add_argument("call_id")
    w.add_argument("--by", required=True)
    args = parser.parse_args()

    if args.cmd == "record":
        rec = record(args.call_id, args.method, args.by, args.subject, args.evidence)
        print(f"consent recorded for {args.call_id}: {rec['method']}, confirmed by {rec['confirmed_by']}")
    elif args.cmd == "check":
        rec = has_consent(args.call_id)
        print(f"consent on file: {rec['method']} by {rec['confirmed_by']} (verified={rec.get('verified')})" if rec else "NO usable consent on file")
        raise SystemExit(0 if rec else 3)
    elif args.cmd == "scan":
        hits = scan(args.call_id)
        print(f"{len(hits)} consent cue(s)")
        for h in hits:
            print(f"  [{h['i']}] agreed_at={h['agreed_segment']} refused={h['refused']}  {h['text']}")
    elif args.cmd == "verify":
        rec = verify_spoken(args.call_id)
        print(f"method {rec['method']}: verified={rec['verified']} segment={rec['verified_segment']}")
    elif args.cmd == "confirm":
        confirm(args.call_id, args.by)
        print(f"consent for {args.call_id} confirmed by {args.by}")
    else:
        s = withdraw(args.call_id, args.by)
        print(f"erased {args.call_id}: {s}")


if __name__ == "__main__":
    main()
