"""Team-wide analytics across every analysed call, plus the CRM pipeline.

    python tools/dashboard.py [--rep "Arjun"] [--account "BrightMart"] [--days 30]

Prints a markdown summary (for the chat) and writes data/reports/team-<date>.png
and data/reports/team-<date>.md. This is what answers a manager asking
"what objections keep coming up?" or "how is Arjun's discovery going?".
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analysis import load_lens, validate  # noqa: E402
from common import CALLS, CRM_FILE, CUSTOMER_COLOR, DATA, REP_COLOR, read_json, utf8_stdout  # noqa: E402
from crm import STAGES  # noqa: E402


def load_calls(rep: str | None, account: str | None, days: int | None) -> list[dict]:
    calls = []
    cutoff = datetime.now() - timedelta(days=days) if days else None
    for folder in sorted(CALLS.glob("*")):
        a_path = folder / "analysis.json"
        if not a_path.exists():
            continue
        a = read_json(a_path)
        t = read_json(folder / "transcript.json")
        if "lens" not in a or validate(a, load_lens(a["lens"]), len(t["segments"])):
            continue  # not analysed yet, or an old-format analysis
        when = datetime.fromisoformat(t["recorded_at"])
        if cutoff and when < cutoff:
            continue
        if rep and rep.lower() not in a["rep"].lower():
            continue
        if account and account.lower() not in a["account"].lower():
            continue
        m = read_json(folder / "metrics.json") if (folder / "metrics.json").exists() else None
        calls.append({"id": folder.name, "when": when, "a": a, "m": m})
    return calls


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rep")
    parser.add_argument("--account")
    parser.add_argument("--days", type=int)
    args = parser.parse_args()

    calls = load_calls(args.rep, args.account, args.days)
    crm = read_json(CRM_FILE) if CRM_FILE.exists() else {"accounts": {}}
    scope = ", ".join(x for x in [f"rep {args.rep}" if args.rep else "", f"account {args.account}" if args.account else "", f"last {args.days} days" if args.days else ""] if x) or "all calls"

    if not calls:
        print(f"No analysed calls for {scope} yet.")
        return

    objections = Counter(o["category"] for c in calls for o in c["a"]["concerns"])
    unhandled = Counter(o["category"] for c in calls for o in c["a"]["concerns"] if not o["handled"])
    competitors = Counter(x for c in calls for x in (c["a"].get("entities") or {}).get("competitors", []))
    flags = [(c, f) for c in calls for f in c["a"]["compliance_flags"]]
    lenses = Counter(c["a"]["lens"] for c in calls)
    by_rep: dict[str, list[dict]] = defaultdict(list)
    for c in calls:
        by_rep[c["a"]["rep"]].append(c)

    lines = [f"## Nabz team report ({scope})", "", f"{len(calls)} conversations analysed · avg score {sum(c['a']['score'] for c in calls) / len(calls):.0f}/100 · "
             + ", ".join(f"{k} {v}" for k, v in lenses.most_common()), ""]
    lines.append("**By rep**")
    for rep, rc in sorted(by_rep.items()):
        ratios = [c["m"]["speakers"][c["m"]["rep"]]["talk_ratio"] for c in rc if c["m"]]
        qs = [c["m"]["speakers"][c["m"]["rep"]]["questions"] for c in rc if c["m"]]
        avg_ratio = f"{sum(ratios) / len(ratios):.0%}" if ratios else "n/a"
        avg_q = f"{sum(qs) / len(qs):.1f}" if qs else "n/a"
        lines.append(f"• {rep}: {len(rc)} calls, avg score {sum(c['a']['score'] for c in rc) / len(rc):.0f}, talk ratio {avg_ratio}, {avg_q} questions/call")
    if flags:
        lines += ["", f"**🚩 Compliance flags: {len(flags)}**"]
        lines += [f"• {c['a']['account']} ({c['a']['rep']}): [{f['severity']}] {f['rule']}" for c, f in flags]
    if objections:
        lines += ["", "**Concerns / objections heard**"]
        lines += [f"• {cat}: {n}× ({unhandled.get(cat, 0)} not handled)" for cat, n in objections.most_common()]
    if competitors:
        lines += ["", "**Competitors mentioned**: " + ", ".join(f"{k} ({v})" for k, v in competitors.most_common())]
    lines += ["", "**Calls**"]
    for c in sorted(calls, key=lambda c: c["when"], reverse=True):
        a = c["a"]
        lines.append(f"• {c['when']:%d %b} {a['account']} ({a['rep']}): {a['lens']} score {a['score']}, {a['sentiment']}, next: {a['commitments'][0]['action'] if a['commitments'] else '—'}")

    accounts = crm["accounts"]
    if accounts:
        open_value = sum(v.get("value") or 0 for v in accounts.values() if not str(v.get("stage", "")).startswith("closed"))
        lines += ["", f"**Pipeline**: {len(accounts)} accounts, open value ₹{open_value:,.0f}"]
        stale = [k for k, v in accounts.items() if v.get("next_date") and v["next_date"] < f"{datetime.now():%Y-%m-%d}" and not str(v.get("stage", "")).startswith("closed")]
        if stale:
            lines.append("⚠️ Overdue next steps: " + ", ".join(stale))

    report_dir = DATA / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M}"
    md_path = report_dir / f"team-{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    png_path = report_dir / f"team-{stamp}.png"
    draw(png_path, calls, by_rep, objections, unhandled, accounts, scope)

    print("\n".join(lines))
    print(f"\nwrote: {md_path}\nwrote: {png_path}")


def draw(path, calls, by_rep, objections, unhandled, accounts, scope) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), dpi=150)
    fig.subplots_adjust(hspace=0.55, wspace=0.35)

    ax = axes[0][0]
    cats = [c for c, _ in objections.most_common()]
    handled = [objections[c] - unhandled.get(c, 0) for c in cats]
    missed = [unhandled.get(c, 0) for c in cats]
    ax.barh(cats, handled, color=REP_COLOR, label="handled")
    ax.barh(cats, missed, left=handled, color=CUSTOMER_COLOR, label="not handled")
    ax.invert_yaxis()
    ax.set_title("Concerns across conversations", loc="left", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[0][1]
    reps = sorted(by_rep)
    ratios = []
    for r in reps:
        vals = [c["m"]["speakers"][c["m"]["rep"]]["talk_ratio"] * 100 for c in by_rep[r] if c["m"]]
        ratios.append(sum(vals) / len(vals) if vals else 0)
    bars = ax.bar(reps, ratios, color=REP_COLOR)
    ax.axhline(57, color="#64748B", linestyle="--", linewidth=1)
    ax.text(len(reps) - 0.5, 58, "won-deal avg 57% (Gong 2025, vendor data)", fontsize=6.5, color="#64748B", ha="right")
    for b, v in zip(bars, ratios):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_title("Rep talk ratio", loc="left", fontsize=10, fontweight="bold")

    ax = axes[1][0]
    ordered = sorted(calls, key=lambda c: c["when"])
    scores = [c["a"]["score"] for c in ordered]
    bars = ax.bar([f"{c['a']['account'][:12]}\n{c['when']:%d %b}" for c in ordered], scores, color=[REP_COLOR if s >= 50 else CUSTOMER_COLOR for s in scores])
    for b, s in zip(bars, scores):
        ax.text(b.get_x() + b.get_width() / 2, s + 1.5, str(s), ha="center", fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_title("Score per conversation", loc="left", fontsize=10, fontweight="bold")
    ax.tick_params(axis="x", labelsize=7)

    ax = axes[1][1]
    stage_vals = [sum((v.get("value") or 0) for v in accounts.values() if v.get("stage") == s) / 1000 for s in STAGES]
    ax.bar(STAGES, stage_vals, color=[REP_COLOR if not s.startswith("closed") else "#94A3B8" for s in STAGES])
    ax.set_title("Pipeline by stage (₹ thousands)", loc="left", fontsize=10, fontweight="bold")
    ax.tick_params(axis="x", labelsize=7, rotation=30)

    for row in axes:
        for a in row:
            a.spines["top"].set_visible(False)
            a.spines["right"].set_visible(False)
            a.tick_params(labelsize=8)
    fig.suptitle(f"Nabz team report · {scope}", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
