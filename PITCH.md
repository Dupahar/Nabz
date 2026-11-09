# Nabz (नब्ज़): the pulse of every field conversation

**Kirana-counter intelligence for Indian FMCG brands, built on Gnani AI Prisma and Timbre.**

**Problem.** 89% of India's offline FMCG sales go through traditional trade (NIQ, Q1 2026). Why an
outlet switched to a competitor, which scheme confused it, and what isn't moving is said out loud to a
salesman, in Hinglish, at the counter. The brand finds out a quarter later, if ever. Retail audits show
*what* sold, not *why*. Sales apps log orders, not conversations. Quick commerce and competitor credit
are taking the counter now.

**Solution.**
- **Capture, with consent.** The rep records the visit after the owner agrees. It's a mobile web app with nothing to install, and verbal consent is checked on the recording.
- **Understands Hinglish.** Gnani **Prisma v3.0** transcribes the noisy, code-mixed audio, separates the speakers, and uses the brand's vocabulary. Phone, Aadhaar and PAN numbers are redacted before any AI sees the text.
- **Insight you can trust.** An FMCG lens scores the visit and extracts market signals (competitor credit, scheme confusion, slow movers, stock-outs). **Each one is backed by a quote that code verifies against the transcript.**
- **Coaching in his language.** Gnani **Timbre** speaks a 20-second debrief to the rep.
- **Leaders see the market live:** competitor share of voice, demand and price sensitivity by region and outlet type. CRM updates need human approval, and everything goes into a tamper-evident audit log.

**Customer.** FMCG, food and beverage brands with ₹500–5,000 Cr turnover, 200–2,000 field reps and
distributor salesmen, and over 70% general trade. The buyer is the Head of Sales, co-signed by the CMO.

**Business model.**
- ₹700 per salesman per month as an add-on to the existing sales app.
- ₹1,500 for the intelligence tier, plus a brand platform fee of ₹2–5 lakh a year.
- Measured analysis cost: about ₹0.3 per visit (Claude Haiku first, Opus only when needed).
- Speech costs about ₹20–27 per audio hour.

**Market.** 4–8 lakh FMCG field users in India: a TAM of ₹144–672 Cr a year and a SAM of about ₹231 Cr.
- Year 1: 2 design-partner brands.
- Year 3: about 12 brands, about ₹2.5–3 Cr ARR.

**Why now.**
1. Code-mixed Indic speech recognition became accurate and cheap (Prisma v3.0, Oct 2026).
2. LLM analysis costs under a rupee a visit.
3. Kiranas are under quick-commerce pressure.
4. In-person conversation intelligence is proven in the US (Rilla, Siro, Salesforce 2026).

**Proof.**
- **A working end-to-end product:** recorder, Prisma, verified analysis, Timbre debrief, dashboard. 50 automated tests.
- **An open noise benchmark** using two independent voice vendors.
  - Prisma made about **2% word errors on clean Hinglish and 11–14% at 10 dB of street noise**.
  - Whisper medium made 8–12% and 23–31%.
  - On Indian English, Whisper was as good or better.
  - Prisma's own `denoise` setting hurt accuracy, so it's off.

**Competition.** Convin (an in-person recorder app). Bizom and FieldAssist
own the rep's app; they're the partner channel. Nabz's edge is Indic-native speech, verified quotes,
an FMCG lens, and nothing for reps to install. The moat to build is a consented Indic
field-conversation dataset, plus distribution through the sales apps brands already use.

**Next.** Three design-partner FMCG brands for a 6-week pilot with agreed success metrics; volume
pricing from Gnani.

[Repo](https://github.com/Dupahar/Nabz) · [Business case](docs/BUSINESS_CASE.md) · [Benchmark](benchmark/)
