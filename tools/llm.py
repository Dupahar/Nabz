"""Analyse one visit with Claude: one structured call produces everything the web app needs.

    python tools/llm.py <call_id> [--lens auto|sales|fmcg-retail|...]

Reads the redacted transcript (never the raw one) and writes, in the call folder:
  analysis.json      the lens-based analysis (same schema the chat agents write; see analysis.py)
  speakers.json + transcript_labeled.md   who S1/S2/... are
  notes.md           meeting notes in English
  followup.md, crm_proposal.json          for human approval

How it stays honest:
  * A JSON example built from the lens is part of the (cached) system prompt; the response is
    parsed and checked field by field by analysis.validate(). (A strict output_config schema for
    this many nested fields exceeds the API's grammar size limit, so validation lives in our code.)
  * Every judgement quotes the transcript; analysis.py verifies each quote in code. If any fail,
    the errors go back to the model once to fix (append-only conversation), then the check runs
    again. Claims that still can't be verified are dropped, never shown.
  * The system prompt (rules + lens) is cached; only the transcript changes per call.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from analysis import SENTIMENTS, SPIN, detect, ground, load_lens, validate
from common import CALLS, audit, call_dir, fmt_ts, read_json, utf8_stdout, workspace, write_json

STR = {"type": "string"}
INT = {"type": "integer"}
# The API allows at most 16 union-typed (nullable) parameters per schema, so "none" is encoded
# as a sentinel instead: segment -1, empty string, value 0. to_analysis() turns them back into null.
NSTR = {"type": "string"}
NINT = {"type": "integer"}
NNUM = {"type": "number"}


def obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


def quoted(extra: dict | None = None) -> dict:
    return obj({**(extra or {}), "quote": STR, "segment": NINT})


def schema_for(lens: dict, ws: dict) -> dict:
    """Structure only. Enum values are listed in the prompt and enforced by analysis.validate()
    (plus one retry): enums nested in arrays make the compiled grammar too large."""
    checklist = obj({k: obj({"status": STR, "quote": STR, "segment": NINT})
                     for k in lens.get("checklist", {})})
    props = {
        "speaker_map": arr(obj({"label": STR, "name": STR, "role": STR, "side": STR})),
        "account": STR, "contact": STR, "rep": STR,
        "segment": STR,
        "language": STR,
        "summary": STR,
        "sentiment": {"enum": SENTIMENTS},
        "score": INT,
        "score_reason": STR,
        "needs": arr(quoted({"text": STR})),
        "concerns": arr(quoted({"category": STR, "handled": {"type": "boolean"}, "how": STR})),
        "signals": arr(quoted({"text": STR})),
        "risks": arr(quoted({"text": STR})),
        "commitments": arr(quoted({"owner": STR, "action": STR, "due": NSTR})),
        "market_signals": arr(quoted({"type": STR, "product": NSTR, "competitor": NSTR,
                                      "polarity": STR, "text": STR})),
        "entities": obj({"products": arr(STR), "competitors": arr(STR), "amounts": arr(STR), "people": arr(STR)}),
        "checklist": checklist,
        "compliance_flags": arr(quoted({"rule": STR, "severity": STR})),
        "coaching": arr(obj({"kind": STR, "tip": STR, "segment": NINT})),
        "debrief": STR,
        "notes_md": STR,
        "crm_proposal": obj({"stage": NSTR, "value_inr": NNUM, "next_step": STR, "next_date": NSTR}),
        "followup": obj({"to": STR, "subject": STR, "body": STR}),
    }
    if lens.get("stages"):
        props["stage_suggested"] = STR
    if lens.get("spin"):
        props["question_types"] = obj({k: arr(INT) for k in SPIN})
    return obj(props)


SYSTEM_RULES = """You are Nabz, a conversation-intelligence analyst for an Indian field team. You analyse ONE
recorded in-person conversation (a shop visit, doctor visit, collection visit, sales meeting) and
return a single JSON object that matches the schema.

The transcript was produced by Gnani AI's Prisma speech model. It may be in English, Hindi, Hinglish
or another Indian language, often code-mixed (Hindi in Devanagari, English words in Latin script).
Speaker labels S1, S2, ... come from diarization and may occasionally be wrong on short turns.
Personal data has already been redacted as [PHONE], [AADHAAR], etc. Never try to reconstruct it.

Hard rules
1. Every `quote` must be copied EXACTLY from the transcript text, in its original script and
   language, 3-25 words, with the `segment` number it comes from (use -1 only when there is no quote). Quotes are verified by code;
   a quote that is not in the transcript gets your whole analysis rejected. Do not translate,
   paraphrase, fix spelling or merge segments inside a quote.
2. If there is no evidence for something, leave it out (empty list) or mark the checklist item
   "unknown" with an empty quote and segment -1. Use "" for an unknown date, product or
   competitor, and 0 for an unknown value_inr. Never invent numbers, names, prices, dates or
   commitments. Transcription errors may be corrected in `text`/`notes_md` (e.g. "Zohal" -> "Zoho")
   but never inside `quote`.
3. `speaker_map`: identify every diarized label: name (as said in the conversation or from the
   visit details), role, and side ("us" = our company's rep, "them" = the customer).
4. `score` 0-100 follows the lens score guide. `score_reason` is one honest sentence.
5. `market_signals` are what marketing and product leaders need to hear from the field: demand for
   a product (positive or negative), competitor activity (offers, credit, pricing, presence), price
   sensitivity, product feedback (quality, packaging, taste, complaints), availability / stock-outs,
   and schemes. One signal per distinct observation, each with a quote. Use canonical product and
   competitor names from the workspace vocabulary when they match.
6. `commitments[].due` and `crm_proposal.next_date`: real dates (YYYY-MM-DD) computed from the
   recording date for "Friday", "next Thursday", "kal" (tomorrow), "parso"; "" if no date was said.
7. `coaching`: exactly 2 or 3 items for OUR rep: one "well-done", one "try-next", optionally one
   "do-more". Specific, kind, actionable, citing a segment.
8. `debrief`: what the rep will HEAR as a 20-30 second voice note (60-80 words), in the rep's
   language given in the visit details. For Hinglish ("hi-en") write natural Roman-script
   Hinglish; for "hi-IN" write Hindi in Devanagari; for "en-IN" Indian English; for other codes
   write in that language. Write numbers as words ("chaar lakh", "sixty-six"). Structure: how it
   went, one specific praise, one thing to try, the next step. Address the rep by first name.
9. `notes_md`: meeting notes in English for a manager, in markdown: attendees, 3-line summary,
   what the customer told us (needs, numbers), what we offered, decisions, action items, open
   questions, and 2-4 key quotes in the original language with an English gloss.
10. `crm_proposal` and `followup`: what the CRM should record and a short follow-up message to the
    customer in the language that suits them (often Hinglish on WhatsApp for kiranas), only with
    promises the rep actually made. A person approves both before anything is saved or sent.
11. `question_types` (when present): classify each question OUR rep asked (segment numbers) as
    situation / problem / implication / need-payoff / other (Rackham, SPIN Selling).
12. `compliance_flags` (when the lens has rules): only for things that actually happened, quoted.
    If nothing happened, return an empty list.

Allowed values (anything else is rejected):
  sentiment: positive | neutral | negative | mixed
  checklist.*.status: yes | partial | no | unknown
  market_signals.type: demand | competitor | price | product_feedback | availability | scheme | other
  market_signals.polarity (for our business): positive | negative | neutral
  coaching.kind: well-done | try-next | do-more
  speaker_map.side: us | them | other
  compliance_flags.severity: low | medium | high
  concerns.category, compliance_flags.rule, stage_suggested and crm_proposal.stage: from the LENS below
  segment: from the visit details' allowed segments
"""


def lens_block(lens: dict) -> str:
    lines = [f"LENS: {lens['id']}: {lens['name']}", f"Score: {lens['score_label']}: {lens['score_guide'].strip()}", "Checklist:"]
    lines += [f"  - {k}: {q}" for k, q in lens.get("checklist", {}).items()]
    if lens.get("compliance"):
        lines.append("Compliance rules:")
        lines += [f"  - {r['id']} ({r['severity']}): {r['rule']}" for r in lens["compliance"]]
    lines.append(f"Concern categories: {', '.join(lens['concern_categories'])}")
    if lens.get("stages"):
        lines.append(f"Deal stages: {', '.join(lens['stages'])}")
    lines.append(f"Coaching focus: {lens['coaching_focus'].strip()}")
    return "\n".join(lines)


def transcript_text(transcript: dict) -> str:
    return "\n".join(f"[{s['i']}] ({fmt_ts(s['start'])}) {s.get('speaker') or '?'}: {s['text']}" for s in transcript["segments"])


def visit_block(meta: dict, ws: dict, transcript: dict) -> str:
    vocab = ws.get("vocabulary") or {}
    recorded = transcript.get("recorded_at", "")[:10]
    weekday = datetime.fromisoformat(transcript["recorded_at"]).strftime("%A") if transcript.get("recorded_at") else ""
    return "\n".join([
        f"OUR COMPANY: {ws.get('company', '')}. {(ws.get('about') or '').strip()}",
        f"Our products: {', '.join(vocab.get('products', []))}. Competitors: {', '.join(vocab.get('competitors', []))}.",
        "",
        "VISIT DETAILS (from the rep's app):",
        f"  Rep (our side): {meta.get('rep_name')} · rep's language for the debrief: {meta.get('rep_language') or 'hi-en'}",
        f"  Account: {meta.get('account') or 'unknown'} · contact: {meta.get('contact') or 'unknown'} · segment: {meta.get('segment') or 'unknown'} · region: {meta.get('region') or 'unknown'}",
        f"  Recorded: {recorded} ({weekday}) · duration {fmt_ts(transcript.get('duration_sec') or 0)} · languages detected: {', '.join(transcript.get('languages') or [transcript.get('language') or '?'])}",
        f"  Rep's note: {meta.get('note') or 'none'}",
        f"  Allowed segments: {', '.join(ws.get('segments') or ['Other'])}",
        "",
        "TRANSCRIPT (redacted; segment number, time, diarized speaker, text):",
        transcript_text(transcript),
    ])


def example_for(lens: dict, ws: dict) -> str:
    """A filled-in example object with every field, so the model sees the exact shape."""
    ex = {
        "speaker_map": [{"label": "S1", "name": "Arjun Mehta", "role": "Sales rep, Northwind", "side": "us"},
                        {"label": "S2", "name": "Sharma ji", "role": "Owner, Sharma Kirana", "side": "them"}],
        "account": "Sharma Kirana", "contact": "Sharma ji", "rep": "Arjun Mehta",
        "segment": (ws.get("segments") or ["Kirana"])[0], "language": "hi-en",
        "summary": "Two or three sentences a manager can read in ten seconds.",
        "sentiment": "positive", "score": 70, "score_reason": "One honest sentence per the score guide.",
        "needs": [{"text": "...", "quote": "exact transcript words", "segment": 4}],
        "concerns": [{"category": lens["concern_categories"][0], "handled": False, "how": "what our rep said, or empty",
                      "quote": "exact transcript words", "segment": 9}],
        "signals": [{"text": "...", "quote": "exact transcript words", "segment": 12}],
        "risks": [{"text": "...", "quote": "exact transcript words", "segment": 13}],
        "commitments": [{"owner": "us", "action": "...", "due": "2026-11-13", "quote": "exact transcript words", "segment": 15}],
        "market_signals": [{"type": "competitor", "product": "Parle-G", "competitor": "Britannia", "polarity": "negative",
                            "text": "Britannia offering 15-day credit", "quote": "exact transcript words", "segment": 8}],
        "entities": {"products": ["Parle-G"], "competitors": ["Britannia"], "amounts": ["5 cartons"], "people": ["Sharma ji"]},
        "checklist": {k: {"status": "yes", "quote": "exact transcript words", "segment": 3} for k in lens.get("checklist", {})},
        "compliance_flags": [],
        "coaching": [{"kind": "well-done", "tip": "...", "segment": 5}, {"kind": "try-next", "tip": "...", "segment": 9}],
        "debrief": "Spoken 60-80 word voice note in the rep's language.",
        "notes_md": "# Sharma Kirana: outlet visit, 9 Nov 2026\n...",
        "crm_proposal": {"stage": (lens.get("stages") or [""])[min(3, len(lens.get("stages") or [""]) - 1)], "value_inr": 0,
                         "next_step": "...", "next_date": "2026-11-13"},
        "followup": {"to": "Sharma ji", "subject": "...", "body": "..."},
    }
    if lens.get("stages"):
        ex["stage_suggested"] = lens["stages"][min(3, len(lens["stages"]) - 1)]
    if lens.get("spin"):
        ex["question_types"] = {k: [] for k in SPIN}
    return json.dumps(ex, ensure_ascii=False, indent=1)


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def call_claude(client, model: str, effort: str, system: list, messages: list, schema: dict | None = None):
    """One analysis call. Server-side refusal fallback is enabled so a safety-classifier decline
    re-runs on a fallback model instead of failing the visit."""
    with client.beta.messages.stream(
        model=model,
        max_tokens=32000,
        system=system,
        messages=messages,
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        return stream.get_final_message()


def analyse(call_id: str, meta: dict, lens_id: str = "auto", verbose: bool = True) -> dict:
    import anthropic

    ws = workspace()
    cfg = ws.get("llm") or {}
    model, effort = cfg.get("model", "claude-opus-5-5"), cfg.get("effort", "medium")
    folder = call_dir(call_id)
    transcript = read_json(folder / "transcript.json")
    if lens_id == "auto":
        ranked = detect(call_id)
        lens_id = ranked[0][0] if ranked and ranked[0][1] >= 2 else "general"
    lens = load_lens(lens_id)
    schema = None  # see module docstring

    system = [
        {"type": "text", "text": SYSTEM_RULES},
        {"type": "text", "text": lens_block(lens) + "\n\nRESPOND WITH ONE JSON OBJECT ONLY (no prose, no code fence), "
         "with exactly these fields (values here are only an example of the shape):\n" + example_for(lens, ws),
         "cache_control": {"type": "ephemeral"}},
    ]
    messages = [{"role": "user", "content": visit_block(meta, ws, transcript)}]
    client = anthropic.Anthropic()

    usage = {"input": 0, "output": 0, "cache_read": 0}
    attempts = int(cfg.get("max_retries_on_check", 1)) + 1
    result, errs = None, []
    for attempt in range(attempts):
        t0 = time.time()
        msg = call_claude(client, model, effort, system, messages, schema)
        usage["input"] += msg.usage.input_tokens
        usage["output"] += msg.usage.output_tokens
        usage["cache_read"] += getattr(msg.usage, "cache_read_input_tokens", 0) or 0
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"analysis declined by the model ({getattr(msg.stop_details, 'category', None)})")
        if msg.stop_reason == "max_tokens":
            raise RuntimeError("analysis was cut off (max_tokens)")
        text = "".join(b.text for b in msg.content if b.type == "text")
        try:
            result = denull(parse_json(text))
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"model did not return valid JSON: {exc}")
            messages = messages + [{"role": "assistant", "content": msg.content},
                                   {"role": "user", "content": f"That was not valid JSON ({exc}). Return the full JSON object only."}]
            continue
        a = to_analysis(result, call_id, lens, meta)
        errs = validate(a, lens, len(transcript["segments"]))
        g = ground(a, transcript["segments"])
        if verbose:
            print(f"  claude {model} attempt {attempt + 1}: {time.time() - t0:.0f}s, {msg.usage.output_tokens} output tokens, "
                  f"{g['verified']}/{g['checked']} quotes verified, {len(errs)} schema problems", flush=True)
        if not errs and not g["failed"]:
            break
        if attempt < attempts - 1:
            problems = errs + [f"{f['field']}: quote not found verbatim in the transcript: \"{f.get('quote', '')}\"" for f in g["failed"]]
            messages = messages + [
                {"role": "assistant", "content": msg.content},
                {"role": "user", "content": "These problems were found when checking your JSON against the transcript:\n- "
                 + "\n- ".join(problems) + "\nReturn the full corrected JSON. Fix each quote to the exact transcript "
                 "words, or remove the claim if the transcript does not support it."},
            ]

    # Anything still unverified is dropped: never shown to anyone.
    g = ground(a, transcript["segments"])
    dropped = drop_unverified(a, g)
    a["grounding"] = ground(a, transcript["segments"])
    a["grounding"]["dropped_after_retry"] = dropped
    a["llm"] = {"model": model, "effort": effort, "attempts": attempt + 1, "usage": usage}
    write_outputs(folder, a, result, transcript, meta)
    from gnani import log_usage
    log_usage("llm", model=model, input_tokens=usage["input"], output_tokens=usage["output"],
              cache_read=usage["cache_read"], call_id=call_id)
    audit("analysis.done", actor="nabz-analyst", call_id=call_id, lens=lens["id"], score=a["score"], model=model,
          verified=a["grounding"]["verified"], checked=a["grounding"]["checked"], dropped=dropped)
    return a


def denull(x):
    """Sentinels back to null: segment -1, empty optional strings."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k == "segment" and v == -1:
                out[k] = None
            elif k in ("due", "product", "competitor", "next_date", "stage") and v == "":
                out[k] = None
            elif k == "value_inr" and v == 0:
                out[k] = None
            else:
                out[k] = denull(v)
        return out
    if isinstance(x, list):
        return [denull(v) for v in x]
    return x


def to_analysis(r: dict, call_id: str, lens: dict, meta: dict) -> dict:
    r = denull(r)
    a = {k: v for k, v in r.items() if k not in ("speaker_map", "notes_md", "crm_proposal", "followup")}
    a.update({"call_id": call_id, "lens": lens["id"], "region": meta.get("region") or "", "rep": meta.get("rep_name") or r.get("rep", "")})
    if meta.get("account"):
        a["account"] = meta["account"]
    if meta.get("segment"):
        a["segment"] = meta["segment"]
    a["compliance_flags"] = [f for f in a.get("compliance_flags", []) if f.get("rule") != "none"]
    if not lens.get("spin"):
        a.pop("question_types", None)
    if not lens.get("stages"):
        a.pop("stage_suggested", None)
    if lens.get("stages") and not a.get("stage_suggested"):
        a["stage_suggested"] = lens["stages"][0]
    return a


def drop_unverified(a: dict, g: dict) -> int:
    n = 0
    for f in sorted(g["failed"], key=lambda f: f["field"], reverse=True):
        field = f["field"]
        if field.startswith("checklist."):
            key = field.split(".", 1)[1]
            a["checklist"][key] = {"status": "unknown", "quote": "", "segment": None}
            n += 1
            continue
        name, _, idx = field.partition("[")
        idx = int(idx.rstrip("]"))
        if 0 <= idx < len(a.get(name, [])):
            a[name].pop(idx)
            n += 1
    return n


def write_outputs(folder: Path, a: dict, r: dict, transcript: dict, meta: dict) -> None:
    write_json(folder / "analysis.json", a)
    (folder / "notes.md").write_text(r.get("notes_md", ""), encoding="utf-8")
    fu = r.get("followup") or {}
    (folder / "followup.md").write_text(f"To: {fu.get('to', '')}\nSubject: {fu.get('subject', '')}\n\n{fu.get('body', '')}\n", encoding="utf-8")
    write_json(folder / "followup.json", {**fu, "status": "drafted"})
    crm = r.get("crm_proposal") or {}
    write_json(folder / "crm_proposal.json", {**crm, "account": a.get("account"), "contact": a.get("contact"),
                                              "owner": meta.get("rep_name"), "status": "proposed"})

    # Speakers: labels from diarization, names and sides from the model.
    smap = {s["label"]: s for s in r.get("speaker_map", [])}
    labels = sorted({s.get("speaker") for s in transcript["segments"] if s.get("speaker")})
    names, rep = {}, None
    for lab in labels:
        info = smap.get(lab) or {"name": lab, "role": "unknown", "side": "other"}
        names[lab] = f"{info['name']} ({info['role']})"
        if info.get("side") == "us" and rep is None:
            rep = lab
    if labels:
        rep = rep or labels[0]
        args = [sys.executable, str(Path(__file__).with_name("speakers.py")), transcript["call_id"], "--rep", rep]
        for lab, full in names.items():
            args += ["--name", f"{lab}={full}"]
        subprocess.run(args, check=True, capture_output=True)
        spk = read_json(folder / "speakers.json")
        spk["sides"] = {lab: (smap.get(lab) or {}).get("side", "other") for lab in labels}
        spk["rep_present"] = any(v == "us" for v in spk["sides"].values())
        write_json(folder / "speakers.json", spk)


def main() -> None:
    utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("call_id")
    parser.add_argument("--lens", default="auto")
    parser.add_argument("--rep", default="Arjun Mehta")
    parser.add_argument("--rep-language", default="hi-en")
    parser.add_argument("--account", default="")
    parser.add_argument("--segment", default="")
    parser.add_argument("--region", default="")
    args = parser.parse_args()
    if not (CALLS / args.call_id / "transcript.json").exists():
        sys.exit("error: transcribe first")
    a = analyse(args.call_id, {"rep_name": args.rep, "rep_language": args.rep_language, "account": args.account,
                               "segment": args.segment, "region": args.region}, args.lens)
    print(f"lens {a['lens']} · score {a['score']} · {a['grounding']['verified']}/{a['grounding']['checked']} quotes verified"
          f" · {len(a['market_signals'])} market signals · dropped {a['grounding']['dropped_after_retry']}")


if __name__ == "__main__":
    main()
