# FieldNotes × Gnani: landscape, precedents, enterprise plan (2026-11-09)

Tags: [V] vendor or blog · [PR] peer-reviewed · [PP] preprint · [est] third-party estimate. Re-check anything you quote publicly.

---

## 1. Verdict

**In-person conversation intelligence is a proven, well-funded category in the US. In India nobody has built it as a product yet.**

- **Rilla** (US): about a $757M valuation after a $68.5M Series B in June 2025, and roughly $70M ARR estimated for April 2026 [est, [Sacra](https://sacra.com/c/rilla)].
- **Siro** (US): $50M Series B in May 2025 [[Pulse2](https://pulse2.com/siro-50-million-series-b-raised-for-bringing-ai-to-in-person-sales)].
- **Salesforce** added an In-Person Meeting Assistant in April 2026 [[SF](https://admin.salesforce.com/blog/2026/turn-conversations-into-data-with-the-in-person-meeting-assistant)], and **Revenue.io** added in-person capture in June 2026 [[Revenue.io](https://www.revenue.io/blog/revenue-io-brings-conversation-intelligence-to-in-person-meetings)].
- **Granola** raised a $125M Series C at a $1.5B valuation in March 2026 and is expanding into in-person mobile capture [[TechCrunch](https://techcrunch.com/2026/03/25/granola-raises-125m-hits-1-5b-valuation-as-it-expands-from-meeting-notetaker-to-enterprise-ai-app/)].
- Only **28% of field teams** that use AI use conversation intelligence, against about 80% of inside-sales teams [V, [Sybill](https://www.sybill.ai/blogs/conversation-intelligence-for-field-sales)].

**The gap FieldNotes fills.** Every in-person tool requires its own app. The US leaders don't support Indian languages. The Indian speech vendors (Observe.AI, Uniphore, Level AI, Ozonetel, Exotel, and Gnani's own Assist365) are built for telephony and contact centres. None of them has pharma-detailing or FMCG-beat workflows. The closest competitor is **Convin**, whose phone app has a "Physical Conversation Recorder" aimed at collections and home services [[Convin](https://convin.ai/product/convin-mobile-app)].

**Positioning.**
> *Rilla-grade field coaching for India. A rep drops a voice note into the team's WhatsApp or Telegram group, with no app to install. Gnani's Prisma understands Hinglish recorded at a noisy shop counter. Managers get a scorecard, the CRM is updated, and a person approves every follow-up.*

**The risk, and how to answer it.** Prisma v3.0 is marketed for 8 kHz telephony audio, and there's no public benchmark of it on far-field phone-mic recordings [[LDS](https://letsdatascience.com/news/gnani-ai-launches-prisma-v30-speech-to-text-model-for-indian-7163adda)]. **Our noise benchmark (§4) would be the first public one for in-person audio.** It reduces our risk, it's the evidence for the Noise Canceller award, and it's a useful finding to bring to Gnani's interviewers.

---

## 2. Competitive map

| Player | In-person? | Indian languages | Channel | Notes |
|---|---|---|---|---|
| Rilla, Siro | Yes, their core use | No | Own app | US home services; ~$4–5k per seat per year [est] |
| Salesforce, Revenue.io | Yes, since 2026 | Not stated | Own app | Bundled into large CRM suites |
| Granola, Fireflies, Avoma, Otter | Generic recorder | Fireflies claims Hindi; Otter has none | Own app | Horizontal notetakers with no sales scoring for field teams |
| Plaud | Hardware recorder | 112 languages | Device, ₹20k | Notes only; no CRM or coaching |
| Convin | Yes | 23 Indic languages (vendor claim) | Own app | Closest competitor; collections and home-services framing |
| Observe.AI, Uniphore, Level AI, Sprinklr, Ozonetel, Exotel, Gnani Assist365 | No | Yes | Telephony | Contact-centre QA |
| FieldAssist, Bizom, LeadSquared | Log visits only | n/a | Own SFA app | **Partners or channels, not competitors.** FieldNotes writes into them. |
| BoldReach | Rep's voice debrief only | Hinglish | App | Summarises the rep's debrief, not the meeting |

**Market size.**
- Conversation intelligence: $1.9B in 2025, projected $6.4B by 2030 (28% CAGR) [est].
- India pharma medical reps: estimates run from 2 to 6 lakh. Use "lakhs of medical reps", not one number. Sun Pharma and Mankind have about 12k reps each, and sales and marketing cost up to 8% of revenue [[BVP](https://www.bvp.com/atlas/india-pharma-techs-next-big-opportunity-the-sales-and-marketing-stack)].
- FMCG: HUL reaches 9M+ outlets, and India has 6.5M+ kiranas. I found no national count of distributor salesmen.

---

## 3. Research precedents, and what each changes in the product

| Precedent | Finding | What changes in FieldNotes |
|---|---|---|
| Gong Labs [V] | The "43:57" talk ratio comes from 2016. 2025 data on 326K calls: won deals average 57% rep talk, lost deals 62%; long monologues go with lost deals. Correlational, US B2B. | Show talk ratio as a **"vendor-reported benchmark"**, not a target. Don't quote 43:57 or "76 s monologue". |
| Franke & Park 2006, JMR [PR]; Ramsey & Sohi 1997, JAMS [PR] | Adaptive selling and listening are linked to sales performance (meta-analysis of more than 31K reps). | The defensible claim: *"listening and adaptive questioning are linked to performance in peer-reviewed work."* |
| SPIN Selling, Rackham 1988 (35K calls, book) | Implication and Need-payoff questions predict success in large sales. | **Classify every question as S, P, I or N.** This replaces raw question counts as a coaching signal. |
| Vistaar (arXiv 2305.15386) [PR] | Speech-to-text rankings change a lot from benchmark to benchmark. Hindi WER on phone audio (Gramvaani) is 26.8, against 42–60 for commercial APIs. | Claim wins per condition only. Publish the normaliser we score with. |
| MUCS 2021 (Interspeech 2021-1339) [PR] | Hindi-English code-switching baseline WER is 32.45%. | Gives a code-mix reference point for the benchmark write-up. |
| Whisper paper §3.7 (arXiv 2212.04356) | Accuracy degrades sharply below 10 dB SNR. | The SNR grid: 0, 5, 10, 20 dB, plus clean. |
| Ko et al. ICASSP 2017 (RIR); MUSAN (1510.08484); DEMAND | The standard recipe for synthetic far-field noisy audio. | The benchmark method (§4). |
| PIER / MER code-switch metrics (2502.18913, 2507.07741) | WER can improve while the code-switched words get worse. Transliterate both sides into one script before scoring. | Report WER, CER, and **keyterm error rate** on SKUs, prices and competitor names. |
| pyannote 3.1 (2310.13025) | DER is 22.4% on AMI single far-field mic. Overlap and short back-channels are the main failures. | Talk ratio inherits diarization errors. **Show it only when diarization is confident**, and have the rep say their own name at the start. |
| LLM-as-judge (2306.05685, NeurIPS 2023) [PR] | Over 80% agreement with humans, but with position, verbosity and self-preference biases. | Use a fixed schema and temperature 0. Plan a check against human raters (Cohen's κ) as the roadmap. |
| ALCE (2305.14627, EMNLP 2023) [PR] | Even the best models lack full citation support about 50% of the time. | **A grounding verifier:** every BANT, objection or risk field quotes the transcript with timestamps, and code checks the quote exists. If it doesn't, the field becomes "not discussed". |
| QMSum-Mistake (2407.11919, COLING 2025) | 9 error types in meeting summaries, including hallucination and omission. | Use these error types for the evaluation harness. |
| CRMArena-Pro (2505.18878) | LLM agents succeed on about 35% of multi-turn CRM tasks and are close to zero on confidentiality. | **CRM writes go through a diff a person approves**, not straight from the LLM. |
| Green 2021 (2109.05067) [PR] | Human oversight drifts into rubber-stamping. | Track edit rate and approve rate as metrics. |
| *No peer-reviewed study of LLM scoring of BANT or field sales found* | A gap in the literature. | **A novelty claim:** "first open benchmark of in-person Indian sales-call intelligence". |

---

## 4. The noise benchmark (Noise Canceller award evidence)

1. **Scripts.** 8–10 Hinglish field-sales role-plays (a kirana visit, a distributor, a pharmacy), containing SKUs, prices in lakh and crore, and competitor names. Reference transcripts are written by hand.
2. **Audio.**
   - Timbre v3.0 with two voices per call. Disclose that the test speech is synthetic.
   - **2–3 recordings of real humans** reading the scripts on a phone, so we aren't only testing Gnani's own speech on Gnani's own recogniser.
3. **Far-field simulation.** Convolve with room impulse responses from OpenSLR SLR28, then add noise from MUSAN and DEMAND (street and market), scaled to 0, 5, 10 and 20 dB SNR, plus clean. Use a fixed random seed.
4. **Systems compared.**
   - Prisma v3.0 (`codemix`, `indic-auto`), with and without `with_denoise`, and with and without `keyterms`
   - faster-whisper small and large-v3
5. **Metrics.** WER and CER after transliterating to one script, **keyterm error rate**, and diarization accuracy where we have references. Bootstrap 95% confidence intervals.
6. **Output.** A table plus one chart: WER against SNR. This is the hero image for the LinkedIn post.

---

## 5. Enterprise readiness: what to build vs. what goes on the roadmap

### Build now: high impact, can be done in about 1 day
| # | Feature | Hours | Why a buyer cares | Precedent or rule |
|---|---|---|---|---|
| 1 | **Prisma batch speech-to-text** with diarization, `keyterms` taken from the CRM catalogue, `with_denoise`, and the `codemix` format | 3 | Accurate Hinglish transcripts of noisy audio, with speaker labels | Gnani docs |
| 2 | **Timbre voice debrief**, a 20–30 s voice note to the rep in their language | 2 | Reps on bikes don't read; managers can hear the coaching | Gnani docs |
| 3 | **Consent gate**: no processing without a logged consent (spoken "consent hai?" or a rep confirmation), with purpose and timestamp | 2 | DPDP s.5–6. Core duties apply from 13 May 2027, so we're **ready before enforcement** | DPDP Rules 2025 |
| 4 | **PII redaction**: Aadhaar, PAN, phone, GSTIN, with spoken numbers normalised to digits first | 3 | Mandatory for BFSI; a DPDP risk otherwise | Presidio Indian recognisers |
| 5 | **Grounding verifier**: every judgement's quote must exist in the transcript | 1.5 | Trust and no hallucinated deal data | ALCE |
| 6 | **Append-only, hash-chained audit log** of agent and human actions | 2 | RBI and IRDAI audit rights, CERT-In logs, DPDP one-year logs | RBI IT Outsourcing 2023 |
| 7 | **Cost per call in rupees**: speech-to-text minutes, LLM tokens, TTS characters | 1.5 | Budget approval and return on investment | — |
| 8 | **Vertical playbooks**: FMCG outlet visit (order, scheme pitched, stock-outs, competitor shelf) and pharma detailing (key messages, samples, UCPMP inducement flags), replacing generic BANT | 2 | BANT fits field sales in FMCG and pharma poorly; vertical playbooks show domain depth | UCPMP 2024 |
| 9 | **Noise benchmark** (§4) | 4 | Proof, and the Noise Canceller award | Vistaar, MUSAN |

About 21 hours of work in total, which leaves time for the video and the post.

### Roadmap: show on one slide, don't build
- **WhatsApp Cloud API adapter.** About 5 hours. Media URLs expire in 5 minutes. Free-form replies only within the 24-hour window. Mono OGG/Opus for voice notes.
- **CRM adapters.** Zoho (`.zoho.in`, data kept in India), LeadSquared (one-call upsert plus activity), FieldAssist and Bizom through partnerships.
- **Deployment and access.** Docker Compose for a customer VPC in an India region. Gnani Artha / Evon on-prem for a fully sovereign setup. SSO and role-based access for reps, managers and admins.
- **Data rights.** Per-tenant retention, plus erase and export.
- **Certification.** Map our controls to SOC 2 and ISO 27001, and state plainly that we are **not certified**.
- **Rater study.** Cohen's κ against human raters on 50–100 calls.

---

## 6. Claims to avoid
- "43:57 ideal talk ratio", "76-second monologue", "4–5 lakh MRs" as an exact figure.
- "Offline / audio never leaves the machine". With Prisma it's now: *Indian speech stack; deployable sovereign via Gnani Artha*.
- That Prisma is better than Whisper on in-person audio, until our own benchmark shows it.
- Any compliance certification.
