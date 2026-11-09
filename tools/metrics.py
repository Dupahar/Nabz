"""Conversation metrics for one call, computed from the timed, speaker-labelled transcript.

    python tools/metrics.py <call_id>

Needs transcript.json and speakers.json. Writes metrics.json and scorecard.png
(talk-time timeline + talk ratio + questions) in the call folder.

These are the numbers a sales coach looks at, and they are measured, not guessed by an LLM:
talk ratio, longest monologue, questions asked, words per minute, filler words and
how often the conversation changes hands.
"""

from __future__ import annotations

import argparse
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import CUSTOMER_COLOR, OTHER_COLORS, REP_COLOR, call_dir, fmt_ts, read_json, utf8_stdout, write_json  # noqa: E402

FILLERS = ["um", "uh", "erm", "hmm", "like", "basically", "actually", "you know", "sort of", "kind of", "literally"]


def speaker_colors(names: dict[str, str], rep: str) -> dict[str, str]:
    colors, others = {}, iter(OTHER_COLORS)
    first_customer = True
    for label in names:
        if label == rep:
            colors[label] = REP_COLOR
        elif first_customer:
            colors[label] = CUSTOMER_COLOR
            first_customer = False
        else:
            colors[label] = next(others, "#94A3B8")
    return colors


def count_fillers(text: str) -> int:
    low = f" {text.lower()} "
    return sum(len(re.findall(rf"\b{re.escape(f)}\b", low)) for f in FILLERS)


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("call_id")
    args = parser.parse_args()

    folder = call_dir(args.call_id)
    transcript = read_json(folder / "transcript.json")
    spk_path = folder / "speakers.json"
    if not spk_path.exists():
        raise SystemExit("error: speakers.json missing. Run tools/speakers.py first.")
    spk = read_json(spk_path)
    names, rep, labels = spk["names"], spk["rep"], spk["labels"]
    segments = transcript["segments"]
    duration = transcript["duration_sec"] or (segments[-1]["end"] if segments else 0)

    per: dict[str, dict] = {
        label: {"name": full, "talk_sec": 0.0, "words": 0, "questions": 0, "fillers": 0, "longest_monologue_sec": 0.0, "turns": 0}
        for label, full in names.items()
    }

    # Merge consecutive segments of one speaker into turns.
    turns: list[dict] = []
    for seg, label in zip(segments, labels):
        p = per[label]
        length = max(0.0, seg["end"] - seg["start"])
        p["talk_sec"] += length
        p["words"] += len(seg["text"].split())
        p["questions"] += seg["text"].count("?")
        p["fillers"] += count_fillers(seg["text"])
        if turns and turns[-1]["speaker"] == label:
            turns[-1]["end"] = seg["end"]
        else:
            turns.append({"speaker": label, "start": seg["start"], "end": seg["end"]})

    for t in turns:
        p = per[t["speaker"]]
        p["turns"] += 1
        p["longest_monologue_sec"] = max(p["longest_monologue_sec"], t["end"] - t["start"])

    total_talk = sum(p["talk_sec"] for p in per.values()) or 1.0
    for p in per.values():
        p["talk_ratio"] = round(p["talk_sec"] / total_talk, 3)
        p["wpm"] = round(p["words"] / (p["talk_sec"] / 60), 1) if p["talk_sec"] > 0 else 0.0
        p["talk_sec"] = round(p["talk_sec"], 1)
        p["longest_monologue_sec"] = round(p["longest_monologue_sec"], 1)

    rep_ratio = per[rep]["talk_ratio"]
    flags = []
    if rep_ratio > 0.65:
        flags.append(f"Rep talked {rep_ratio:.0%} of the time. In Gong's 2025 data (326K calls, vendor research) won deals averaged ~57% rep talk and lost deals ~62%. Ask more, pitch less.")
    elif rep_ratio < 0.30:
        flags.append(f"Rep talked only {rep_ratio:.0%} of the time: check the rep steered toward next steps.")
    if per[rep]["longest_monologue_sec"] > 90:
        flags.append(f"Longest rep monologue was {fmt_ts(per[rep]['longest_monologue_sec'])}: break pitches up with check-in questions.")
    if per[rep]["questions"] < 4 and duration > 300:
        flags.append(f"Rep asked only {per[rep]['questions']} questions in {fmt_ts(duration)}: discovery looks thin.")

    metrics = {
        "call_id": args.call_id,
        "duration_sec": duration,
        "rep": rep,
        "speakers": per,
        "speaker_switches": max(0, len(turns) - 1),
        "switches_per_min": round((len(turns) - 1) / (duration / 60), 2) if duration else 0,
        "flags": flags,
    }
    write_json(folder / "metrics.json", metrics)
    draw(folder, transcript, names, rep, turns, per, duration)

    print(f"duration {fmt_ts(duration)}, {metrics['speaker_switches']} speaker switches")
    for label, p in per.items():
        tag = " (rep)" if label == rep else ""
        print(f"  {p['name']}{tag}: talk {p['talk_ratio']:.0%}, {p['questions']} questions, longest monologue {fmt_ts(p['longest_monologue_sec'])}, {p['wpm']} wpm, {p['fillers']} fillers")
    for f in flags:
        print(f"  flag: {f}")
    print(f"wrote: {folder / 'metrics.json'} and {folder / 'scorecard.png'}")


def draw(folder, transcript, names, rep, turns, per, duration) -> None:
    colors = speaker_colors(names, rep)
    labels = list(names)
    fig = plt.figure(figsize=(10, 4.6), dpi=150)
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.5], width_ratios=[1.4, 1], hspace=0.65, wspace=0.35)

    # Timeline: who held the floor, when.
    ax_t = fig.add_subplot(grid[0, :])
    for row, label in enumerate(labels):
        spans = [(t["start"], t["end"] - t["start"]) for t in turns if t["speaker"] == label]
        ax_t.broken_barh(spans, (row - 0.35, 0.7), color=colors[label])
    ax_t.set_yticks(range(len(labels)), [names[x].split("(")[0].strip() for x in labels], fontsize=9)
    ax_t.set_xlim(0, duration or 1)
    ticks = ax_t.get_xticks()
    ax_t.set_xticks(ticks, [fmt_ts(t) for t in ticks], fontsize=8)
    ax_t.set_xlim(0, duration or 1)
    ax_t.invert_yaxis()
    ax_t.set_title("Who held the floor", fontsize=10, loc="left", fontweight="bold")
    for s in ("top", "right"):
        ax_t.spines[s].set_visible(False)

    # Talk ratio.
    ax_r = fig.add_subplot(grid[1, 0])
    ratios = [per[x]["talk_ratio"] * 100 for x in labels]
    bars = ax_r.barh([names[x].split("(")[0].strip() for x in labels], ratios, color=[colors[x] for x in labels])
    ax_r.axvline(57, color="#64748B", linestyle="--", linewidth=1)
    ax_r.text(57.5, -0.5, "won-deal avg ~57% (Gong 2025)", fontsize=7, color="#64748B", va="bottom")
    for bar, r in zip(bars, ratios):
        ax_r.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2, f"{r:.0f}%", va="center", fontsize=9)
    ax_r.set_xlim(0, 100)
    ax_r.invert_yaxis()
    ax_r.set_title("Talk ratio", fontsize=10, loc="left", fontweight="bold")
    ax_r.tick_params(labelsize=8)
    for s in ("top", "right"):
        ax_r.spines[s].set_visible(False)

    # Questions and monologue.
    ax_q = fig.add_subplot(grid[1, 1])
    short = [names[x].split("(")[0].strip().split()[0] for x in labels]
    qs = [per[x]["questions"] for x in labels]
    bars = ax_q.bar(short, qs, color=[colors[x] for x in labels])
    for bar, q, label in zip(bars, qs, labels):
        ax_q.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, str(q), ha="center", fontsize=9)
    ax_q.set_title("Questions asked", fontsize=10, loc="left", fontweight="bold")
    ax_q.tick_params(labelsize=8)
    ax_q.set_ylim(0, max(qs + [1]) * 1.3)
    for s in ("top", "right"):
        ax_q.spines[s].set_visible(False)

    title = transcript.get("title") or transcript["call_id"]
    fig.suptitle(f"Nabz · {title} · {fmt_ts(duration)}", fontsize=11, x=0.01, ha="left", fontweight="bold")
    fig.savefig(folder / "scorecard.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
