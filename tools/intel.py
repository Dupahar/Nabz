"""Market intelligence across visits: what the field is hearing, by region and segment.

    python tools/intel.py [--days 30] [--region "Delhi NCR"] [--segment Kirana] [--json]

Every number traces back to quoted moments in real conversations: competitor activity, demand
signals, price sensitivity, product feedback, concerns, plus the team coaching view and compliance
flags. The web dashboard (/api/intel) and the chat analyst both use this.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from common import CALLS, read_json, utf8_stdout, workspace

SIDE_US = "us"


def consent_ok(folder) -> bool:
    """Consent counts if recorded and not contradicted: a verbal consent the transcript scan could
    not find (verified == False) only counts once a manager has reviewed it."""
    path = folder / "consent.json"
    if not path.exists():
        return False
    c = read_json(path)
    if c.get("withdrawn"):
        return False
    return c.get("verified") is not False or bool(c.get("review"))


def load_visits(days: int | None = None, region: str | None = None, segment: str | None = None, rep_handle: str | None = None,
                include_unconsented: bool = False) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days) if days else None
    out = []
    if not CALLS.exists():
        return out
    for folder in sorted(CALLS.iterdir()):
        a_path, t_path = folder / "analysis.json", folder / "transcript.json"
        if not (a_path.exists() and t_path.exists()):
            continue
        a, t = read_json(a_path), read_json(t_path)
        if "lens" not in a or "market_signals" not in a:
            continue
        v = read_json(folder / "visit.json") if (folder / "visit.json").exists() else {}
        if not include_unconsented and not consent_ok(folder):
            continue  # never aggregate a conversation without valid consent
        when = datetime.fromisoformat(t["recorded_at"])
        if when.tzinfo is not None:
            when = when.replace(tzinfo=None)
        reg = a.get("region") or v.get("region") or "Unknown"
        seg = a.get("segment") or v.get("segment") or "Other"
        if cutoff and when < cutoff:
            continue
        if region and region != "All" and reg != region:
            continue
        if segment and segment != "All" and seg != segment:
            continue
        if rep_handle and v.get("rep_handle") != rep_handle:
            continue
        m = read_json(folder / "metrics.json") if (folder / "metrics.json").exists() else None
        synthetic = bool(v.get("synthetic")) or folder.name.startswith("demo-") or "synthetic" in (v.get("note") or "").lower()
        out.append({"id": folder.name, "when": when, "a": a, "t": t, "m": m, "v": v, "region": reg, "segment": seg,
                    "synthetic": synthetic})
    return out


def build(days: int | None = 30, region: str | None = None, segment: str | None = None) -> dict:
    visits = load_visits(days, region, segment)
    ws = workspace()
    regions = sorted({v["region"] for v in load_visits(days)} | {m.get("region") for m in ws.get("team", []) if m.get("region") not in (None, "All")})

    n = len(visits)
    flags = [(v, f) for v in visits for f in v["a"].get("compliance_flags", [])]
    # First-pass numbers: how often the model's quotes were right before any retry or dropping.
    # (Final numbers are 100% by construction, because unverified claims are dropped.)
    def fp(v, k):
        g = v["a"].get("grounding") or {}
        return (g.get("first_pass") or g).get(k, 0)
    checked = sum(fp(v, "checked") for v in visits)
    verified = sum(fp(v, "verified") for v in visits)
    dropped = sum((v["a"].get("grounding") or {}).get("dropped_after_retry", 0) for v in visits)
    pii = 0
    for v in visits:
        r = CALLS / v["id"] / "redactions.json"
        if r.exists():
            pii += sum(read_json(r).get("counts", {}).values())
    all_recent = load_visits(days, region, segment, include_unconsented=True)
    pending_review = len(all_recent) - n

    kpis = {
        "visits": n,
        "avg_score": round(sum(v["a"]["score"] for v in visits) / n) if n else None,
        "reps": len({v["a"].get("rep") for v in visits}),
        "hours_audio": round(sum(v["t"].get("duration_sec") or 0 for v in visits) / 3600, 2),
        "compliance_flags": len(flags),
        "consent_rate": round(n / len(all_recent), 3) if all_recent else None,
        "consent_pending_review": pending_review,
        "pii_redacted": pii,
        "quotes_verified": round(verified / checked, 3) if checked else None,
        "quotes_verified_basis": "first pass, before retry",
        "claims_dropped": dropped,
        "synthetic_visits": sum(1 for v in visits if v["synthetic"]),
    }

    signals = [(v, s) for v in visits for s in v["a"].get("market_signals", [])]

    comp: dict[str, dict] = {}
    for v, s in signals:
        names = [s.get("competitor")] if s.get("competitor") else []
        for c in names:
            e = comp.setdefault(c, {"name": c, "mentions": 0, "negative_for_us": 0, "regions": Counter(), "quotes": []})
            e["mentions"] += 1
            e["negative_for_us"] += s.get("polarity") == "negative"
            e["regions"][v["region"]] += 1
            e["quotes"].append({"call_id": v["id"], "account": v["a"]["account"], "text": s.get("text"), "quote": s.get("quote")})
    # Competitors named in entities but without a signal still count as mentions.
    for v in visits:
        for c in (v["a"].get("entities") or {}).get("competitors", []):
            if c not in comp:
                comp[c] = {"name": c, "mentions": 1, "negative_for_us": 0, "regions": Counter({v["region"]: 1}), "quotes": []}
    competitors = sorted(({**e, "regions": dict(e["regions"]), "quotes": e["quotes"][:5]} for e in comp.values()),
                         key=lambda e: -e["mentions"])

    by_type: dict[str, Counter] = defaultdict(Counter)
    for v, s in signals:
        by_type[s.get("type", "other")][v["region"]] += 1
    signals_by_type = sorted(({"type": t, "count": sum(c.values()), "by_region": dict(c)} for t, c in by_type.items()),
                             key=lambda x: -x["count"])

    dem: dict[str, Counter] = defaultdict(Counter)
    for v, s in signals:
        if s.get("product") and s.get("type") in ("demand", "product_feedback", "availability", "price", "scheme"):
            dem[s["product"]][s.get("polarity", "neutral")] += 1
    demand = sorted(({"product": p, "count": sum(c.values()), "positive": c["positive"], "negative": c["negative"]}
                     for p, c in dem.items()), key=lambda x: -x["count"])

    seg_v: dict[str, list] = defaultdict(list)
    for v in visits:
        has_price = any(c.get("category") == "price" for c in v["a"].get("concerns", [])) or \
            any(s.get("type") == "price" for s in v["a"].get("market_signals", []))
        seg_v[v["segment"]].append(has_price)
    price_sensitivity = sorted(({"segment": s, "visits": len(x), "price_concern_rate": round(sum(x) / len(x), 2)}
                                for s, x in seg_v.items()), key=lambda x: -x["price_concern_rate"])

    cc, cu = Counter(), Counter()
    for v in visits:
        for c in v["a"].get("concerns", []):
            cc[c["category"]] += 1
            cu[c["category"]] += not c.get("handled")
    concerns = [{"category": k, "count": n_, "unhandled": cu[k]} for k, n_ in cc.most_common()]

    voc = sorted(({"call_id": v["id"], "account": v["a"]["account"], "segment": v["segment"], "region": v["region"],
                   "type": s.get("type"), "polarity": s.get("polarity"), "product": s.get("product"),
                   "competitor": s.get("competitor"), "text": s.get("text"), "quote": s.get("quote"),
                   "recorded_at": v["t"]["recorded_at"]} for v, s in signals), key=lambda x: x["recorded_at"], reverse=True)

    reps = []
    by_rep: dict[str, list] = defaultdict(list)
    for v in visits:
        by_rep[v["a"].get("rep", "?")].append(v)
    team = {m["name"]: m for m in ws.get("team", [])}
    for name, vs in sorted(by_rep.items()):
        ms = [v["m"] for v in vs if v["m"]]
        tr = [m["speakers"][m["rep"]]["talk_ratio"] for m in ms]
        qs = [m["speakers"][m["rep"]]["questions"] for m in ms]
        spin = Counter()
        for v in vs:
            qt = v["a"].get("question_types")
            for k, segs in (qt.items() if isinstance(qt, dict) else []):
                spin[k] += len(segs)
        tips = [c["tip"] for v in vs for c in v["a"].get("coaching", []) if c.get("kind") == "try-next"]
        reps.append({"name": name, "handle": team.get(name, {}).get("handle"), "region": team.get(name, {}).get("region"),
                     "visits": len(vs), "avg_score": round(sum(v["a"]["score"] for v in vs) / len(vs)),
                     "talk_ratio": round(sum(tr) / len(tr), 3) if tr else None,
                     "questions": round(sum(qs) / len(qs), 1) if qs else None,
                     "spin": dict(spin), "top_tip": tips[0] if tips else None})

    compliance = [{"call_id": v["id"], "account": v["a"]["account"], "rep": v["a"].get("rep"), "rule": f.get("rule"),
                   "severity": f.get("severity"), "quote": f.get("quote")} for v, f in flags]

    days_c: dict[str, list] = defaultdict(list)
    for v in visits:
        days_c[v["when"].strftime("%Y-%m-%d")].append(v["a"]["score"])
    trend = [{"date": d, "visits": len(s), "avg_score": round(sum(s) / len(s))} for d, s in sorted(days_c.items())]

    return {"kpis": kpis, "competitors": competitors, "signals_by_type": signals_by_type, "demand": demand,
            "price_sensitivity": price_sensitivity, "concerns": concerns, "voice_of_customer": voc[:60], "reps": reps,
            "compliance": compliance, "trend": trend, "regions": regions, "segments": ws.get("segments", [])}


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--region")
    parser.add_argument("--segment")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = build(args.days, args.region, args.segment)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1, default=str))
        return
    k = data["kpis"]
    print(f"Market intelligence · last {args.days} days · {k['visits']} visits · avg score {k['avg_score']}")
    if data["competitors"]:
        print("Competitors: " + ", ".join(f"{c['name']} ({c['mentions']}, {c['negative_for_us']} against us)" for c in data["competitors"][:6]))
    for s in data["signals_by_type"]:
        print(f"  {s['type']}: {s['count']}  {s['by_region']}")
    for p in data["price_sensitivity"]:
        print(f"  price concern in {p['price_concern_rate']:.0%} of {p['segment']} visits ({p['visits']})")
    for q in data["voice_of_customer"][:6]:
        print(f"  [{q['type']}/{q['polarity']}] {q['account']} ({q['region']}): {q['text']}")


if __name__ == "__main__":
    main()
