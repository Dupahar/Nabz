<div align="center">

# Nabz · नब्ज़

**The pulse of every field conversation.**

*"Bazaar ki nabz pakadna"*: to have your finger on the market's pulse.

Nabz turns the conversations India's field teams have every day (at a kirana counter, a chemist,
a doctor's chamber, a borrower's door) into **market intelligence** for marketing and product
leaders, and **coaching** for the reps who had them. It is built on **Gnani AI's Indian speech models**,
and every insight is backed by a quote verified against the transcript.

![Gnani Prisma](https://img.shields.io/badge/speech--to--text-Gnani%20Prisma%20v3.0-6D28D9)
![Gnani Timbre](https://img.shields.io/badge/voice-Gnani%20Timbre%20v3.0-6D28D9)
![Languages](https://img.shields.io/badge/languages-10%20Indian%20%2B%20Hinglish-orange)
![Privacy](https://img.shields.io/badge/DPDP-consent%20%C2%B7%20redaction%20%C2%B7%20audit-2563EB)

Built for the **Great Indian AI Internship Challenge** by Gnani AI · #GnaniAI #GreatIndianAIInternshipChallenge

</div>

---

## The problem

India sells face to face. Lakhs of FMCG salesmen, pharma medical reps, insurance and loan agents and
service technicians talk to customers every day, in Hinglish and a dozen other languages, over traffic
and shop noise. **What the market tells them never reaches head office**:
- why outlets switched to a competitor;
- which scheme confused them;
- which price hike hurt;
- which product is gathering dust.

CRMs record outcomes, not reasons. Surveys are slow. Mystery audits are expensive. And reps, who have
the hardest conversations, are almost never coached on them.

## What Nabz does

| For | They get |
|---|---|
| **Marketing and product leaders** | A **market-intelligence dashboard** built from real conversations: competitor share of voice by region, demand signals per product, price sensitivity by customer segment, scheme confusion, product feedback, and a voice-of-customer feed where every card is a verbatim quote |
| **Sales managers** | Visit scorecards through the right **lens** (sales, FMCG outlet visit, pharma detailing, collections, support, general), team coaching (talk ratio, SPIN question mix, the top tip per rep), and approve-before-save CRM updates |
| **Field reps** | A one-tap recorder on their phone (no install: a mobile web app, or a voice note in the team's Telegram group), and a **20-second voice debrief in their own language, voiced by Gnani Timbre** |
| **Compliance and IT** | A consent gate, PII redaction before any AI sees the text, quote verification in code, compliance rules (UCPMP 2024 for pharma, RBI recovery rules for collections), a tamper-evident audit log, retention, erasure and role-based access |

### How a visit flows

```text
Rep's phone ─► consent captured ─► Gnani Prisma v3.0 batch STT ─► PII redaction ─► Claude analysis ─► quote check (code)
 (web app or     (DPDP s.5-6)       diarization · indic-auto        Aadhaar, PAN,     lens + market      every claim must
  Telegram)                         codemix · denoise · keyterms    phone (incl.      signals + notes    exist verbatim in
                                                                     spoken "nau aath") + CRM + follow-up the transcript
                                                                                            │
          Manager approves CRM + follow-up ◄── Gnani Timbre voice debrief to rep ◄──────────┘
          Market intelligence dashboard ◄── every visit's quoted signals, by region × segment
```

## Gnani AI inside

| Gnani model | Used for |
|---|---|
| **Prisma v3.0** (Batch STT) | **Diarization** (speaker labels matched the script on 59/60 segments in our demo) · `indic-auto` across 10 Indian languages · **`codemix`** keeps "carton", "scheme" and "Parle-G" in Latin script inside Hindi · **`keyterms`** from the company's products, competitors and CRM accounts · **`with_denoise`** for shop floors · Telegram/WhatsApp Opus voice notes and browser recordings uploaded directly |
| **Timbre v3.0** (TTS) | Voice debriefs to reps in Hinglish, Hindi, English, Tamil, Kannada and other languages, returned as an Opus voice note · the synthetic demo visits · the noise benchmark's test speech |

Gnani's own call-analytics guide pairs Prisma with an LLM for reasoning, and Nabz does the same
(Claude Opus 5.5), behind a swappable interface. The sovereign path is Prisma on-premises plus Gnani's
open-weight **Evon v3.3** for reasoning, inside the customer's VPC (see [Roadmap](#roadmap)).

## Why trust it

| | |
|---|---|
| **No consent, no processing** | The upload is refused without a recorded consent (who, how, purpose, when). Erasing a visit deletes everything; the audit log keeps the tombstone. |
| **PII never reaches the AI** | Aadhaar (Verhoeff checksum), PAN, GSTIN, phone, card (Luhn), account, IFSC, UPI and email are redacted, **including numbers spoken as English or Hindi words**. Raw audio is deleted on a schedule (1 day by default). |
| **No invented evidence** | Every judgement and market signal carries a verbatim quote. `analysis.py` verifies each one against the transcript in code. Failures go back to the model once, and anything still unverified is dropped, never shown. |
| **Humans approve the system of record** | CRM updates and follow-ups are proposals until a person clicks Approve. |
| **Auditable** | A SHA-256 hash-chained log of every consent, transcription, redaction, analysis, approval and erasure, verified live on the dashboard. |
| **Least privilege** | Reps see their own visits; managers see the team and intelligence; admins see the audit log. Chat agents are blocked by permission rules from reading raw transcripts and secrets. |
| **Data in India** | Gnani batch results are served from AWS `ap-south-1` (Mumbai). |

We are not SOC 2 or ISO 27001 certified. The controls above map to them; certification is on the roadmap.

## Noise benchmark: Prisma vs Whisper on in-person audio

Prisma is trained on telephone audio, but field recordings come from one phone a metre away in a
shop. We measured it with the standard recipe: synthetic far-field rooms; street, cafeteria and
babble noise at 20/10/5/0 dB SNR; and WER, CER and **keyterm recall** (did the SKU, price and
competitor survive?). See [`benchmark/`](benchmark/).

## Research behind the design

| Design choice | Evidence |
|---|---|
| Talk ratio shown as a vendor reference, not a target | Gong 2025 (326K calls, vendor data): won deals averaged ~57% rep talk, lost deals ~62% |
| SPIN question mix in the sales lens | Rackham, *SPIN Selling* (1988), a study of 35,000 sales calls |
| Listening and adaptive questioning matter | Franke & Park 2006 (JMR meta-analysis, 31K+ reps); Ramsey & Sohi 1997 |
| Quotes verified in code | ALCE (EMNLP 2023): even the best models lack full citation support about half the time |
| Human approval for CRM writes | CRMArena-Pro (2025): agents complete only ~35% of multi-turn CRM tasks |
| ASR evaluation method | Vistaar (Interspeech 2023), MUCS 2021, MUSAN, DEMAND, Ko et al. 2017 RIR |
| Talk ratio only when diarization is trustworthy | pyannote 3.1: about 22% DER on single far-field mics |

More in [`docs/research/`](docs/research/).

## Run it

**You need:** Python 3.10+, ffmpeg, a [Gnani AI API key](https://docs.gnani.ai), and an Anthropic API key.

```bash
git clone https://github.com/Dupahar/Nabz.git && cd Nabz
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
cp .env.example .env              # GNANI_API_KEY=..., plus ANTHROPIC_API_KEY in your environment
.venv/Scripts/python -m uvicorn app.server:app --port 8000
```

Open <http://localhost:8000>, pick a user (reps record; Kavita the manager sees the dashboard), and
record or upload a visit. To process a file without the UI:

```bash
./py tools/pipeline.py demo/kirana_snippet.ogg --rep arjun --account "Sharma Kirana" --segment Kirana --consent rep-confirmed
./py tools/intel.py --days 30
```

**Chat channel (optional):** Telegram via [Switch](https://github.com/sandbox-quantum/switch). Import
[`switch/nabz.template.yaml`](switch/nabz.template.yaml) in Switch Console. Three Claude Code agents
(`nabz-scribe`, `nabz-analyst`, `nabz-dealdesk`) follow the plain-English playbooks in `playbooks/`
and share the same data and tools.

**Configure** your company, team (roles, languages, regions), customer segments, product and competitor
vocabulary, and privacy rules in [`config/workspace.yaml`](config/workspace.yaml). Add a conversation type by
writing a YAML file in [`lenses/`](lenses/).

## Project structure

```text
app/server.py            FastAPI: API (docs/API.md) + role checks
app/static/              mobile recorder, visit page, market-intelligence dashboard
config/workspace.yaml    company, team, segments, vocabulary, privacy, LLM, rates
lenses/*.yaml            sales · fmcg-retail · pharma-detailing · collections · support · general
tools/
  pipeline.py            consent → transcribe → analyse → metrics → debrief
  gnani.py               Prisma batch STT + Timbre TTS client
  transcribe.py          consent gate, Prisma, redaction
  llm.py                 Claude analysis: lens, market signals, notes, CRM + follow-up proposal, quote retry
  analysis.py            schema, lenses, quote verification, scorecard
  intel.py               market-intelligence aggregation
  redact.py · consent.py · audit.py · retention.py · cost.py · metrics.py · voice.py · crm.py
playbooks/ + switch/     the Telegram agents
benchmark/               Prisma vs Whisper noise benchmark
demo/                    sample recordings, synthetic seed visits (Timbre voices), scripts to record
docs/                    API contract, research, submission
```

## Roadmap

- **WhatsApp Business** channel. Offline capture in a PWA, synced later.
- **CRM and SFA connectors:** Zoho (`.zoho.in`), LeadSquared, Salesforce; FieldAssist and Bizom through partnerships.
- **Sovereign deployment:** Prisma on-premises plus Evon v3.3 for reasoning, in the customer's VPC (Gnani Artha).
- A real-audio benchmark, a human-rater agreement study (Cohen's κ), SSO/OIDC, and a weekly market digest to the leadership channel.

## Honesty notes

- The demo dashboard is populated with **synthetic visits** whose voices were generated by Gnani
  Timbre; they still run through the real pipeline. Real recordings are marked as such in the demo video.
- Benchmark caveats are in [`benchmark/README.md`](benchmark/README.md).
- Nabz extends ideas and code from the author's earlier project
  [FieldNotes](https://github.com/Dupahar/FieldNotes) (Telegram-only sales notetaker, Nov 2026).
