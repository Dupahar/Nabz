"""Remove Indian PII from a transcript before any agent or LLM reads it.

    python tools/redact.py <call_id>            # redact transcript.json in place, keep transcript.raw.json
    python tools/redact.py --text "my PAN is ABCDE1234F, number nine eight four five..."   # try it

Speech-to-text writes numbers the way people say them ("nine eight four five...", "नौ आठ चार",
"double seven"), so spoken digit runs are normalised to digits first, then matched:

  AADHAAR   12 digits, first 2-9, valid Verhoeff checksum (UIDAI's check digit)
  PAN       AAAAA9999A
  GSTIN     99AAAAA9999A9Z9
  PHONE     Indian mobile, optional +91/0
  CARD      13-19 digits passing the Luhn check
  ACCOUNT   9-18 digits near "account" / "a/c" / "khata" / "खाता"
  IFSC      AAAA0XXXXXX
  UPI/EMAIL user@handle

Amounts ("4,80,000", "four lakh") are not touched: they matter to the deal and are not personal.
The raw transcript stays in the call folder for the record (and is deleted by retention.py);
redactions.json logs WHAT was removed and WHERE, never the values.
"""

from __future__ import annotations

import argparse
import re

from common import audit, call_dir, read_json, utf8_stdout, write_json

DIGIT_WORDS = {
    # English
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Hindi, romanised
    "shunya": "0", "sunya": "0", "ek": "1", "do": "2", "teen": "3", "tin": "3", "char": "4", "chaar": "4",
    "paanch": "5", "panch": "5", "chhe": "6", "chhah": "6", "che": "6", "saat": "7", "sat": "7",
    "aath": "8", "ath": "8", "nau": "9",
    # Hindi, Devanagari
    "शून्य": "0", "जीरो": "0", "ज़ीरो": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5",
    "छह": "6", "छः": "6", "छे": "6", "सात": "7", "आठ": "8", "नौ": "9",
}
REPEAT_WORDS = {"double": 2, "triple": 3, "डबल": 2, "ट्रिपल": 3}
TEENS = {"ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
         "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19"}
TENS = {"twenty": "2", "thirty": "3", "forty": "4", "fourty": "4", "fifty": "5", "sixty": "6", "seventy": "7",
        "eighty": "8", "ninety": "9"}
# Written identifiers are grouped like this; prices and quantities ("120 150 180 200") are not.
ID_GROUPS = {(4, 4, 4), (5, 5), (3, 3, 4), (4, 3, 3), (3, 4, 3), (2, 4, 4), (4, 4, 4, 4), (4, 6, 5), (10,), (12,)}
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PUNCT = ".,;:!?।\"'()[]"

# Verhoeff tables (UIDAI uses this for the Aadhaar check digit).
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(num: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def normalise_spoken_digits(text: str, min_run: int = 6) -> str:
    """Collapse runs of spoken/written digits into one digit string when the run is long enough
    to be an identifier (>= min_run digits). Short runs ("do log", "one store") are left alone."""
    text = text.translate(DEVANAGARI_DIGITS)
    tokens = text.split()
    out: list[str] = []
    run: list[str] = []   # original tokens in the current run
    digits = ""
    repeat = 1

    spoken = False         # did the run contain spoken digit words?
    groups: list[int] = []  # lengths of written digit groups in the run

    def flush() -> None:
        nonlocal run, digits, repeat, spoken, groups
        looks_like_id = spoken or tuple(groups) in ID_GROUPS
        if len(digits) >= min_run and looks_like_id:
            trail = run[-1][len(run[-1].rstrip(PUNCT)):] if run else ""
            out.append(digits + trail)
        else:
            out.extend(run)
        run, digits, repeat, spoken, groups = [], "", 1, False, []

    pending_tens = ""  # "ninety" waiting for "eight" -> "98"
    for tok in tokens:
        core = tok.strip(PUNCT).lower().replace("-", "")
        if core in REPEAT_WORDS:
            run.append(tok)
            repeat = REPEAT_WORDS[core]
            continue
        if core in TENS:
            if pending_tens:
                digits += pending_tens + "0"
            pending_tens = TENS[core]
            spoken = True
            run.append(tok)
            continue
        if core in TEENS or core in DIGIT_WORDS or (core.isdigit() and len(core) <= 12):
            if core in TEENS:
                d = TEENS[core]
                spoken = True
            elif core in DIGIT_WORDS:
                d = DIGIT_WORDS[core]
                spoken = True
            else:
                d = core
                groups.append(len(core))
            if pending_tens:
                d = pending_tens + d if (len(d) == 1 and d != "0") else pending_tens + "0" + d
                pending_tens = ""
            digits += d * repeat if len(d) == 1 else d
            repeat = 1
            run.append(tok)
            if tok != tok.rstrip(".,;!?।"):  # sentence punctuation ends a number
                flush()
            continue
        if pending_tens:
            digits += pending_tens + "0"
            pending_tens = ""
        flush()
        out.append(tok)
    if pending_tens:
        digits += pending_tens + "0"
    flush()
    return " ".join(out)


PATTERNS: list[tuple[str, re.Pattern, object]] = [
    ("GSTIN", re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.I), None),
    ("PAN", re.compile(r"\b[A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z]\b", re.I), None),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.I), None),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), None),
    ("UPI", re.compile(r"\b[\w.-]{2,}@(?:ok)?[a-z]{2,}\b", re.I), None),
    ("AADHAAR", re.compile(r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)"), lambda m: verhoeff_ok(re.sub(r"\D", "", m))),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), lambda m: luhn_ok(re.sub(r"\D", "", m))),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?!\d)"), None),
    ("ACCOUNT", re.compile(r"(?:account|a/c|acct|khata|खाता)\D{0,25}(\d{9,18})", re.I), None),
]


def redact_text(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    norm = normalise_spoken_digits(text)
    for label, pat, check in PATTERNS:
        def sub(m: re.Match) -> str:
            value = m.group(1) if label == "ACCOUNT" else m.group(0)
            if check and not check(value):
                return m.group(0)
            found.append(label)
            return m.group(0).replace(value, f"[{label}]")
        norm = pat.sub(sub, norm)
    return (norm if found else text), found


TAIL_DIGITS = re.compile(r"(\d[\d ]*)\W*$")
HEAD_DIGITS = re.compile(r"^\W*(\d[\d ]*)")


def redact_segments(segments: list[dict]) -> list[dict]:
    """Redact every segment in place, including identifiers split across two consecutive
    segments of the same speaker ("...nine eight four five" | "zero one two three four five").
    Returns the hits [{segment, type}]: types only, never values."""
    hits: list[dict] = []
    for seg in segments:
        seg["text"], found = redact_text(seg["text"])
        hits += [{"segment": seg["i"], "type": t} for t in found]
    for a, b in zip(segments, segments[1:]):
        if a.get("speaker") != b.get("speaker"):
            continue
        ta, tb = normalise_spoken_digits(a["text"], min_run=3), normalise_spoken_digits(b["text"], min_run=3)
        ma, mb = TAIL_DIGITS.search(ta), HEAD_DIGITS.search(tb)
        if not (ma and mb):
            continue
        joined = re.sub(r"\D", "", ma.group(1)) + re.sub(r"\D", "", mb.group(1))
        kind = None
        if re.fullmatch(r"(?:91|0)?[6-9]\d{9}", joined):
            kind = "PHONE"
        elif len(joined) == 12 and joined[0] in "23456789" and verhoeff_ok(joined):
            kind = "AADHAAR"
        if kind:
            a["text"] = ta[: ma.start(1)] + f"[{kind}]" + ta[ma.end(1):]
            b["text"] = tb[: mb.start(1)] + f"[{kind}]" + tb[mb.end(1):]
            hits.append({"segment": a["i"], "type": kind})
    return hits


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("call_id", nargs="?")
    parser.add_argument("--text")
    args = parser.parse_args()

    if args.text:
        red, found = redact_text(args.text)
        print(red)
        print(f"found: {found or 'nothing'}")
        return
    if not args.call_id:
        raise SystemExit("error: give a call_id or --text")

    folder = call_dir(args.call_id)
    raw_path, path = folder / "transcript.raw.json", folder / "transcript.json"
    transcript = read_json(raw_path if raw_path.exists() else path)
    if not raw_path.exists():
        write_json(raw_path, transcript)

    hits = redact_segments(transcript["segments"])
    transcript["redacted"] = True
    write_json(path, transcript)

    # Rewrite the readable transcript from the redacted one.
    md = folder / "transcript.md"
    if md.exists():
        head = md.read_text(encoding="utf-8").split("\n\n[")[0]
        from common import fmt_ts
        body = "\n".join(f"[{s['i']}] ({fmt_ts(s['start'])}){' ' + s['speaker'] if s.get('speaker') else ''} {s['text']}" for s in transcript["segments"])
        md.write_text(head + "\n\n" + body + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for h in hits:
        counts[h["type"]] = counts.get(h["type"], 0) + 1
    write_json(folder / "redactions.json", {"call_id": args.call_id, "counts": counts, "hits": hits})
    audit("transcript.redacted", call_id=args.call_id, **{k.lower(): v for k, v in counts.items()})
    print(f"redacted {len(hits)} item(s): " + (", ".join(f"{k}×{v}" for k, v in counts.items()) or "none found"))
    print(f"wrote: {path} (raw copy kept as transcript.raw.json; agents read only transcript.json)")


if __name__ == "__main__":
    main()
