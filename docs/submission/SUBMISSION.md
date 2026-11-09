# Nabz: Great Indian AI Internship Challenge submission (copy and paste)

> Fill in the `{{...}}` placeholders once the repo, video and posts are live.

## Project title
**Nabz: the pulse of every field conversation.** Kirana-counter intelligence for FMCG brands, built
on Gnani Prisma and Timbre.

## Problem
89% of India's offline FMCG sales go through traditional trade (NIQ, Q1 2026). The decisive
conversations happen at the kirana counter, in Hinglish, over street noise: *"Britannia wala pandrah
din ka credit de raha hai"*, *"das carton pe ek free? itni jagah nahi hai"*. Brands design schemes,
credit and pricing without ever hearing them. Retail audits show what sold, not why, and SFA apps log
orders, not conversations.

## Users
- **FMCG distributor salesmen (DSRs) and field reps:** record a visit with the owner's consent, and
  get a 20-second coaching voice note in their own language.
- **Sales and brand leaders at FMCG brands:** a live view of scheme confusion, competitor credit,
  demand and stock-outs by region, where every insight is a verified quote from a real conversation.

## Gnani AI models and APIs used
- **Prisma v3.0 (Batch Speech-to-Text):**
  - `with_diarization` labels who said what.
  - `indic-auto` detects the language.
  - `format: codemix` keeps "Parle-G", "carton" and "scheme" in Latin script inside Hindi.
  - `keyterms` carries the brand's products, competitors and account names.
  - `with_denoise` handles shop-floor noise.
  - Phone and browser recordings are uploaded directly.
- **Timbre v3.0 (Text-to-Speech):**
  - Voice debriefs for the rep in Hinglish, Hindi, English or another Indian language.
  - Synthetic test conversations for the demo data and the noise benchmark.
- **Reasoning:** Evon has no hosted API today. Claude handles the reasoning step behind one narrow
  interface (`tools/llm.py`), the same pattern as Gnani's own call-analytics guide. Every claim it
  makes must quote the Prisma transcript verbatim; code checks this, and drops claims that fail.

## Each member's contribution
Solo: I built everything. Product and problem research, the Gnani Prisma and Timbre integration,
the analysis and quote-verification pipeline, the privacy layer (consent, PII redaction, audit log,
retention), the web app (recorder and dashboard), the noise benchmark, the demo and the video.

## Written explanation (400 words or fewer)
India sells face to face. A distributor salesman visits 30–40 kiranas a day. In those conversations
the owner says exactly why they switched to a competitor, which scheme confused them, and what isn't
selling. None of it reaches the brand. Scheme and credit decisions get made on month-old audits.

**Nabz turns those conversations into evidence.**
1. The rep opens Nabz on their phone (mobile web, nothing to install), reads a one-line consent
   notice to the owner, and taps record.
2. **Gnani Prisma** transcribes the noisy, code-mixed audio, separates the speakers, and gets brand
   names right using the company's own vocabulary.
3. Personal data such as phone numbers is redacted before any AI sees the transcript, including
   numbers spoken as words ("nau aath chaar…").
4. An analysis step scores the visit through an FMCG lens: order taken, scheme explained, stock
   checked, competitor activity, shelf.
5. It extracts **market signals** such as "Britannia offering 15-day credit" or "Mom's Magic not
   selling: price". **Every signal carries a verbatim quote that code verifies against the
   transcript.** If the quote isn't there, the claim is dropped.
6. **Gnani Timbre** then speaks a 20-second debrief to the rep in their own language: what went well,
   and what to try next.
7. Brand and sales leaders see a dashboard of competitor share of voice by region, scheme confusion,
   demand by product and price sensitivity, each insight one click from the quote behind it. CRM
   updates wait for a human to approve.

**Trust is designed in:**
- No consent, no processing.
- Audio is deleted on a schedule.
- A tamper-evident audit log.
- Role-based access.

**Honest scope:**
- The dashboard data in the demo comes from synthetic visits voiced by Timbre and ElevenLabs. It
  still runs through the real pipeline, and the video marks which clips are real.
- The open noise benchmark compares Prisma with Whisper on noisy, far-field Hinglish audio, using
  independent ElevenLabs voices so Gnani's TTS isn't grading Gnani's ASR.
- Willingness to pay is unvalidated; the next step is three design-partner pilots with FMCG brands.

Repo: {{https://github.com/Dupahar/Nabz}} · Video: {{url}} · Benchmark: {{repo}}/benchmark

## Nominated posts
- LinkedIn: {{url}}
- X: {{url}}
