"""The analyst's schema, lenses, grounding check and chat scorecard.

    python tools/analysis.py lenses                    # list conversation lenses (lenses/*.yaml)
    python tools/analysis.py detect <call_id>          # rank lenses by cues in the transcript
    python tools/analysis.py template [--lens sales]   # print an empty analysis.json for that lens
    python tools/analysis.py check <call_id>           # validate schema + verify every quote (exit 1 on problems)
    python tools/analysis.py card  <call_id>           # validate, then print the chat-ready scorecard

One core schema works for ANY business conversation (needs, concerns, commitments, risks,
coaching). A lens (sales, fmcg-retail, pharma-detailing, collections, support, general) adds a
checklist, a score definition, and compliance rules. Teams add lenses as YAML; no code changes.

Grounding: every judgement carries a verbatim `quote` and the `segment` it came from. `check`
verifies each quote against the (redacted) transcript. A judgement whose quote can't be found
fails the check, and the analyst must fix the quote or drop the claim ("not discussed").
LLMs are known to cite unsupported evidence (ALCE, Gao et al., EMNLP 2023), so this is enforced
in code rather than trusted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher

from common import LENSES_DIR, call_dir, fmt_ts, read_json, utf8_stdout, write_json

SENTIMENTS = ["positive", "neutral", "negative", "mixed"]
CHECK_STATUS = ["yes", "partial", "no", "unknown"]
SEVERITIES = ["low", "medium", "high"]
SPIN = ["situation", "problem", "implication", "need-payoff", "other"]
SIGNAL_TYPES = ["demand", "competitor", "price", "product_feedback", "availability", "scheme", "other"]
POLARITY = ["positive", "negative", "neutral"]


# ---------------------------------------------------------------- lenses

def load_lens(lens_id: str) -> dict:
    import yaml

    path = LENSES_DIR / f"{lens_id}.yaml"
    if not path.exists():
        sys.exit(f"error: no lens '{lens_id}'. Available: {', '.join(all_lens_ids())}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def all_lens_ids() -> list[str]:
    return sorted(p.stem for p in LENSES_DIR.glob("*.yaml"))


def detect(call_id: str) -> list[tuple[str, int, list[str]]]:
    text = " ".join(s["text"] for s in read_json(call_dir(call_id) / "transcript.json")["segments"]).lower()
    ranked = []
    for lid in all_lens_ids():
        lens = load_lens(lid)
        hits = [c for c in lens.get("cues") or [] if re.search(rf"(?<!\w){re.escape(c.lower())}", text)]
        ranked.append((lid, len(hits), hits))
    ranked.sort(key=lambda r: (-r[1], r[0] != "general"))
    return ranked


def template(lens: dict) -> dict:
    t = {
        "call_id": "<call_id>",
        "lens": lens["id"],
        "account": "BrightMart (the customer's organisation, or the person if an individual)",
        "contact": "Priya Shah, Head of Operations",
        "rep": "Arjun Mehta",
        "region": "Delhi NCR (from the rep's profile or the visit form)",
        "segment": "Kirana / Chemist / Modern trade / ... (config/workspace.yaml segments)",
        "language": "en-IN / hi-en / kn-IN ... (what was mostly spoken)",
        "summary": "Two or three sentences a manager can read in ten seconds.",
        "sentiment": "positive",
        "score": 68,
        "score_reason": "One line: why this score, per the lens score guide.",
        "needs": [{"text": "Real-time stock visibility across 40 stores", "quote": "exact words from the transcript", "segment": 5}],
        "concerns": [{"category": lens["concern_categories"][0], "quote": "exact words", "segment": 31, "handled": False,
                      "how": "what the rep said in response, or empty"}],
        "signals": [{"text": "Asked about rollout time", "quote": "exact words", "segment": 12}],
        "risks": [{"text": "CFO not yet involved", "quote": "exact words", "segment": 33}],
        "commitments": [{"owner": "us", "action": "Send pilot proposal for 5 stores", "due": "2026-11-16", "quote": "exact words", "segment": 40}],
        "market_signals": [{"type": "competitor", "product": "Parle-G", "competitor": "Britannia", "polarity": "negative",
                            "text": "Britannia offering 15-day credit to this outlet", "quote": "exact words", "segment": 22}],
        "entities": {"products": [], "competitors": [], "amounts": ["₹12,000 per store per month"], "people": []},
        "checklist": {k: {"status": "unknown", "quote": "", "segment": None} for k in lens.get("checklist", {})},
        "compliance_flags": [],
        "coaching": [{"kind": "well-done", "tip": "Specific praise", "segment": 6},
                     {"kind": "try-next", "tip": "One concrete thing to do differently next time", "segment": 31}],
        "debrief": "A 20-30 second spoken debrief for the rep, in the rep's language (see voice.py). Numbers in words.",
    }
    if lens.get("stages"):
        t["stage_suggested"] = lens["stages"][3] if len(lens["stages"]) > 3 else lens["stages"][0]
    if lens.get("spin"):
        t["question_types"] = {k: [] for k in SPIN}
    if lens.get("compliance"):
        t["compliance_flags"] = [{"rule": lens["compliance"][0]["id"], "severity": lens["compliance"][0]["severity"],
                                  "quote": "only if it actually happened", "segment": None}]
    return t


# ---------------------------------------------------------------- grounding

def _norm(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^\w\s']", " ", text)  # \w keeps Devanagari and other Indic letters
    return re.sub(r"\s+", " ", text).strip()


def find_quote(quote: str, segments: list[dict], hint: int | None) -> tuple[bool, int | None, float]:
    """Is `quote` in the transcript? Look near the hinted segment first, then everywhere.
    Exact (normalised) substring = 1.0; otherwise best fuzzy match over a sliding window."""
    q = _norm(quote)
    if not q:
        return False, None, 0.0
    order = list(range(len(segments)))
    if isinstance(hint, int) and 0 <= hint < len(segments):
        order.sort(key=lambda i: abs(i - hint))
    best = (False, None, 0.0)
    for i in order:
        window = _norm(" ".join(s["text"] for s in segments[max(0, i - 1): i + 3]))
        if q in window:
            return True, i, 1.0
        if len(q) > 8:
            words, qw = window.split(), q.split()
            for j in range(0, max(1, len(words) - len(qw) + 1)):
                cand = " ".join(words[j: j + len(qw)])
                r = SequenceMatcher(None, q, cand).ratio()
                if r > best[2]:
                    best = (r >= 0.85, i, r)
        if best[2] >= 0.97:
            break
    return best


def quoted_items(a: dict) -> list[tuple[str, dict]]:
    items: list[tuple[str, dict]] = []
    for key in ("needs", "concerns", "signals", "risks", "commitments", "compliance_flags", "market_signals"):
        for n, it in enumerate(a.get(key) or []):
            if isinstance(it, dict):
                items.append((f"{key}[{n}]", it))
    for k, it in (a.get("checklist") or {}).items():
        if isinstance(it, dict) and it.get("status") in ("yes", "partial"):
            items.append((f"checklist.{k}", it))
    return items


def ground(a: dict, segments: list[dict]) -> dict:
    checked, verified, failed = 0, 0, []
    for path, it in quoted_items(a):
        quote = (it.get("quote") or "").strip()
        if not quote:
            failed.append({"field": path, "problem": "no quote"})
            checked += 1
            continue
        checked += 1
        ok, seg, score = find_quote(quote, segments, it.get("segment"))
        if ok:
            verified += 1
            if seg is not None and it.get("segment") is None:
                it["segment"] = seg
        else:
            failed.append({"field": path, "quote": quote[:80], "best_match": round(score, 2)})
    return {"checked": checked, "verified": verified, "failed": failed}


# ---------------------------------------------------------------- validation

def validate(a: dict, lens: dict, n_segments: int) -> list[str]:
    errs: list[str] = []

    def need(key: str, kind) -> None:
        if key not in a:
            errs.append(f"missing '{key}'")
        elif not isinstance(a[key], kind):
            errs.append(f"'{key}' should be {kind.__name__ if isinstance(kind, type) else kind}")

    for key in ("call_id", "lens", "account", "rep", "summary", "sentiment", "score_reason", "debrief"):
        need(key, str)
    need("score", int)
    for key in ("needs", "concerns", "signals", "risks", "commitments", "coaching", "compliance_flags", "market_signals"):
        need(key, list)
    need("checklist", dict)
    if errs:
        return errs

    if a["sentiment"] not in SENTIMENTS:
        errs.append(f"sentiment '{a['sentiment']}' not in {SENTIMENTS}")
    if not 0 <= a["score"] <= 100:
        errs.append("score must be 0-100")
    if lens.get("stages") and a.get("stage_suggested") not in lens["stages"]:
        errs.append(f"stage_suggested must be one of {lens['stages']}")
    for k in lens.get("checklist", {}):
        item = a["checklist"].get(k)
        if not isinstance(item, dict) or item.get("status") not in CHECK_STATUS:
            errs.append(f"checklist.{k}.status must be one of {CHECK_STATUS}")
    for i, c in enumerate(a["concerns"]):
        if c.get("category") not in lens["concern_categories"]:
            errs.append(f"concerns[{i}].category must be one of {lens['concern_categories']}")
        if not isinstance(c.get("handled"), bool):
            errs.append(f"concerns[{i}].handled must be true/false")
    rules = {r["id"]: r for r in lens.get("compliance") or []}
    for i, f in enumerate(a["compliance_flags"]):
        if f.get("rule") not in rules:
            errs.append(f"compliance_flags[{i}].rule must be one of {list(rules) or 'none for this lens'}")
        if f.get("severity") not in SEVERITIES:
            errs.append(f"compliance_flags[{i}].severity must be one of {SEVERITIES}")
    for i, m in enumerate(a["market_signals"]):
        if m.get("type") not in SIGNAL_TYPES:
            errs.append(f"market_signals[{i}].type must be one of {SIGNAL_TYPES}")
        if m.get("polarity") not in POLARITY:
            errs.append(f"market_signals[{i}].polarity must be one of {POLARITY}")
    for i, c in enumerate(a["commitments"]):
        if not c.get("action"):
            errs.append(f"commitments[{i}] needs an 'action'")
        if c.get("due") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(c["due"])):
            errs.append(f"commitments[{i}].due must be YYYY-MM-DD (convert 'next Thursday' to a date)")
    if lens.get("spin"):
        qt = a.get("question_types")
        if not isinstance(qt, dict) or any(k not in SPIN for k in qt):
            errs.append(f"question_types must map {SPIN} to lists of segment numbers")
        else:
            for k, segs in qt.items():
                if any(not isinstance(s, int) or not 0 <= s < n_segments for s in segs):
                    errs.append(f"question_types.{k} has segment numbers outside 0-{n_segments - 1}")
    if len(a["debrief"].split()) > 110:
        errs.append("debrief is too long for a voice note (keep it under ~90 words)")
    return errs


# ---------------------------------------------------------------- scorecard

def card(a: dict, lens: dict, metrics: dict | None) -> str:
    icon = {"positive": "🟢", "neutral": "⚪", "negative": "🔴", "mixed": "🟡"}[a["sentiment"]]
    st = {"yes": "✅", "partial": "🟡", "no": "❌", "unknown": "❓"}
    out = [f"📊 {lens['name']}: {a['account']}" + (f" ({a['contact']})" if a.get("contact") else ""),
           f"{lens['score_label']} {a['score']}/100 {icon} {a['sentiment']}"
           + (f" · suggested stage: {a['stage_suggested']}" if a.get("stage_suggested") else ""),
           f"Why: {a['score_reason']}", "", a["summary"], ""]
    labels = {k: k.replace("_", " ") for k in lens.get("checklist", {})}
    out.append(" · ".join(f"{labels[k].title()} {st[a['checklist'][k]['status']]}" for k in labels))
    if metrics:
        r = metrics["speakers"][metrics["rep"]]
        out.append(f"Rep talk {r['talk_ratio']:.0%} · {r['questions']} questions · longest monologue {fmt_ts(r['longest_monologue_sec'])}")
    if lens.get("spin") and a.get("question_types"):
        qt = a["question_types"]
        out.append("Question mix: " + " · ".join(f"{k} {len(qt.get(k, []))}" for k in SPIN[:4]))
    if a["compliance_flags"]:
        out += ["", "🚩 Compliance:"] + [f"• [{f['severity']}] {f['rule']}: \"{f.get('quote', '')}\"" for f in a["compliance_flags"]]
    if a.get("market_signals"):
        pol = {"positive": "📈", "negative": "📉", "neutral": "•"}
        out += ["", "Market signals:"] + [f"{pol.get(m['polarity'], '•')} [{m['type']}] {m['text']}" for m in a["market_signals"][:5]]
    if a["concerns"]:
        out += ["", "Concerns:"] + [f"• [{c['category']}] \"{c.get('quote', '')}\" {'✅ handled' if c['handled'] else '⚠️ not handled'}" for c in a["concerns"]]
    if a["commitments"]:
        out += ["", "Commitments:"] + [f"• {c.get('owner', '?')}: {c['action']}" + (f" (by {c['due']})" if c.get("due") else "") for c in a["commitments"]]
    if a["coaching"]:
        mark = {"well-done": "👏", "try-next": "🎯", "do-more": "➕"}
        out += ["", "Coaching:"] + [f"{mark.get(c.get('kind'), '•')} {c['tip']}" for c in a["coaching"]]
    g = a.get("grounding")
    if g:
        out += ["", f"🔎 {g['verified']}/{g['checked']} judgements verified against the transcript"]
    return "\n".join(out)


def load_call(call_id: str) -> tuple:
    folder = call_dir(call_id)
    path = folder / "analysis.json"
    if not path.exists():
        sys.exit(f"error: {path} does not exist yet. `python tools/analysis.py template --lens <id>` shows the shape.")
    try:
        a = read_json(path)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: analysis.json is not valid JSON: {exc}")
    segments = read_json(folder / "transcript.json")["segments"]
    return folder, path, a, segments


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["lenses", "detect", "template", "check", "card"])
    parser.add_argument("call_id", nargs="?")
    parser.add_argument("--lens", default="general")
    args = parser.parse_args()

    if args.command == "lenses":
        for lid in all_lens_ids():
            lens = load_lens(lid)
            print(f"{lid:<18} {lens['name']}: {lens['score_label']}; checklist: {', '.join(lens.get('checklist', {}))}")
        return
    if args.command == "template":
        lens = load_lens(args.lens)
        print(f"# lens {lens['id']}: {lens['name']}\n# score: {lens['score_label']}: {lens['score_guide'].strip()}")
        for k, q in lens.get("checklist", {}).items():
            print(f"# checklist.{k}: {q}")
        for r in lens.get("compliance") or []:
            print(f"# compliance rule '{r['id']}' ({r['severity']}): {r['rule']}")
        print(f"# coaching focus: {lens['coaching_focus'].strip()}")
        print(json.dumps(template(lens), indent=2, ensure_ascii=False))
        return
    if not args.call_id:
        sys.exit("error: call_id required")
    if args.command == "detect":
        for lid, n, hits in detect(args.call_id):
            print(f"{lid:<18} {n:>2} cues  {', '.join(hits[:10])}")
        print("pick the lens that fits; 'general' if none clearly does")
        return

    folder, path, a, segments = load_call(args.call_id)
    lens = load_lens(a.get("lens") or "general")
    errs = validate(a, lens, len(segments))
    if not errs:
        a["grounding"] = ground(a, segments)
        write_json(path, a)
        errs += [f"{f['field']}: quote not found in transcript ({f.get('problem') or 'best match ' + str(f.get('best_match'))}): "
                 f"\"{f.get('quote', '')}\". Fix the quote to the exact words, or remove the claim."
                 for f in a["grounding"]["failed"]]
    if errs:
        print("analysis.json has problems:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    if args.command == "check":
        g = a["grounding"]
        print(f"analysis.json OK · lens {lens['id']} · {g['verified']}/{g['checked']} quotes verified against the transcript")
        from common import audit
        audit("analysis.checked", call_id=args.call_id, lens=lens["id"], score=a["score"], verified=g["verified"], checked=g["checked"])
        return
    metrics = read_json(folder / "metrics.json") if (folder / "metrics.json").exists() else None
    print(card(a, lens, metrics))


if __name__ == "__main__":
    main()
