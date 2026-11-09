"""Attach speaker names to a transcript.

With Prisma (default) the transcript is already diarized: segments carry S1, S2, ... and the
scribe only says who each one is:

    python tools/speakers.py <call_id>         --name S1="Arjun Mehta (rep, Northwind)" --name S2="Priya Shah (customer, BrightMart)" --rep S1
        [--merge S3=S1]      # if diarization split one person into two labels
        [--fix 14:S2]        # correct individual segments the diarizer got wrong

With Whisper (no diarization) the scribe works out who said what from context and lists only
the segment numbers where the speaker CHANGES:

    python tools/speakers.py <call_id> \
        --name A="Arjun Mehta (rep, Northwind)" --name B="Priya Shah (customer, BrightMart)" \
        --rep A \
        --turns "0:A,3:B,9:A,12:B"

"0:A,3:B" means segments 0-2 are A and segment 3 onward is B until the next change.
Writes speakers.json and transcript_labeled.md in the call folder.
"""

from __future__ import annotations

import argparse

from common import call_dir, fmt_ts, read_json, utf8_stdout, write_json


def parse_turns(raw: str, n_segments: int, known: set[str]) -> list[str]:
    changes: list[tuple[int, str]] = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        idx_s, _, label = part.partition(":")
        if not idx_s.isdigit() or not label:
            raise SystemExit(f"error: bad turn '{part}', expected <segment>:<label>")
        if label not in known:
            raise SystemExit(f"error: turn '{part}' uses label '{label}' with no --name for it")
        changes.append((int(idx_s), label))
    changes.sort()
    if not changes or changes[0][0] != 0:
        raise SystemExit("error: --turns must start at segment 0")
    if changes[-1][0] >= n_segments:
        raise SystemExit(f"error: turn at segment {changes[-1][0]} but the transcript has only {n_segments} segments (0-{n_segments - 1})")

    labels: list[str] = []
    for k, (start, label) in enumerate(changes):
        end = changes[k + 1][0] if k + 1 < len(changes) else n_segments
        labels.extend([label] * (end - start))
    return labels


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("call_id")
    parser.add_argument("--name", action="append", required=True, help='LABEL="Full name (role, company)"')
    parser.add_argument("--rep", required=True, help="label of the salesperson / our side")
    parser.add_argument("--turns", default=None, help="whisper transcripts: 0:A,3:B,...")
    parser.add_argument("--merge", action="append", default=[], help="diarized: S3=S1 relabels S3 as S1")
    parser.add_argument("--fix", action="append", default=[], help="diarized: <segment>:<label>, repeatable")
    args = parser.parse_args()

    folder = call_dir(args.call_id)
    transcript = read_json(folder / "transcript.json")
    segments = transcript["segments"]

    names: dict[str, str] = {}
    for item in args.name:
        label, sep, full = item.partition("=")
        if not sep or not label.strip() or not full.strip():
            raise SystemExit(f"error: bad --name '{item}', expected LABEL=\"Full name\"")
        names[label.strip()] = full.strip().strip('"')
    if args.rep not in names:
        raise SystemExit(f"error: --rep {args.rep} has no --name")

    if args.turns:
        labels = parse_turns(args.turns, len(segments), set(names))
        source = "turns"
    elif transcript.get("diarized"):
        merge = dict(m.split("=", 1) for m in args.merge if "=" in m)
        labels = [merge.get(seg.get("speaker") or "", seg.get("speaker") or "") for seg in segments]
        for fix in args.fix:
            idx, _, label = fix.partition(":")
            if not idx.isdigit() or int(idx) >= len(labels):
                raise SystemExit(f"error: bad --fix '{fix}'")
            labels[int(idx)] = label
        missing = sorted({lab for lab in labels if lab not in names})
        if missing:
            raise SystemExit(f"error: diarized labels {missing} have no --name (or --merge them into another speaker)")
        source = "diarization" + (" + corrections" if args.merge or args.fix else "")
    else:
        raise SystemExit("error: this transcript has no diarization; pass --turns")
    write_json(folder / "speakers.json", {"names": names, "rep": args.rep, "source": source, "turns": args.turns,
                                          "merge": args.merge, "fix": args.fix, "labels": labels})
    from common import audit
    audit("speakers.labelled", call_id=args.call_id, source=source, speakers=len(names))

    lines = [f"# Transcript with speakers: {transcript.get('title') or args.call_id}", ""]
    lines += [f"- **{label}** = {full}" + ("  ← our side" if label == args.rep else "") for label, full in names.items()]
    lines.append("")
    prev = None
    for seg, label in zip(segments, labels):
        if label != prev:
            lines.append(f"\n**{names[label]}** ({fmt_ts(seg['start'])})")
            prev = label
        lines.append(f"[{seg['i']}] {seg['text']}")
    (folder / "transcript_labeled.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = {label: labels.count(label) for label in names}
    print(f"labelled {len(labels)} segments from {source}: " + ", ".join(f"{label}={n}" for label, n in counts.items()))
    print(f"wrote: {folder / 'speakers.json'} and transcript_labeled.md")


if __name__ == "__main__":
    main()
