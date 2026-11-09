# Nabz: business case

*Prepared 9 Nov 2026. Every number has a source and a reliability tag. Assumptions are labelled
**[A]** and can be changed in one place. Tags: [P] primary (regulator, filing, official price page),
[3P] third-party estimate or press, [V] vendor claim, [M] our own measurement, [A] assumption.*

---

## 1. The problem in one line

**India's revenue is won and lost in face-to-face conversations that no one at head office ever hears.**
Lakhs of field staff talk to kirana owners, chemists, doctors and borrowers every day, in Hinglish and
regional languages, over street noise. What the market tells them (why an outlet switched to a
competitor, which scheme confused them, which price hike hurt) never becomes data. Their conduct
(what they promised a doctor, how they spoke to a borrower) is invisible until it becomes a complaint
or a penalty.

## 2. The problem, with numbers

### The conversations happen in person, mostly through general trade
| Fact | Number | Source |
|---|---|---|
| Traditional trade's share of offline FMCG sales | **89%** (Jan–Mar 2026) | NIQ India FMCG Snapshot Q1'26 [P] |
| Kiranas' share of FMCG sales including e-commerce | **79%** (Dec 2024), down from 81% | Kantar via KNN [3P] |
| Kiranas' share of grocery | **~91%** in 2025, falling to ~86% by 2030 | Redseer [3P] |
| Outlets HUL reaches; distributors | **9M+** outlets; **3,500+** distributors | HUL performance highlights [P] |
| Distributors in India and outlets they serve | **4–4.5 lakh** distributors, **1.3 crore** outlets | AICPDF, a distributors' trade body (2025) [3P] |

### The people having them, and how fast they churn
| Workforce | Size | Churn or quality signal | Source |
|---|---|---|---|
| Pharma medical reps | **2–3 lakh** (no official count; Mankind alone has 18,000+, Sun ~11,000) | 30–35% first-year attrition (dated) | Academic/vendor estimates [3P]; Mankind investor deck [P] |
| FMCG and distributor salesmen | **~4–8 lakh** [A] (4–4.5 lakh distributors × 1–2 salesmen) | 26–27% FMCG attrition | AICPDF [3P]; TeamLease 2024 [3P] |
| Insurance agents | **31.2 lakh** registered (FY25); **7 lakh terminated in FY24** | LIC 13th-month persistency fell to **74.8%** (FY25) | IRDAI via press [3P]; LIC [P] |
| Microfinance loan officers | **2.09 lakh** field staff (of 3.29 lakh) | **52% attrition in FY25** | Sa-Dhan Bharat Microfinance Report 2025 [P] |
| Collection agents, DSAs, in-store promoters | Not reliably counted (unverified "5 lakh+ DSAs") | n/a | Excluded from sizing |

High churn means the know-how from good conversations leaves with the people who had them. Coaching
has to be continuous and cheap, and today it is neither. Managers spend about 9% of their time
coaching (Gartner, secondary), and they never hear the conversation itself.

### What it costs not to know, and what companies pay today to find out
| Fact | Number | Source |
|---|---|---|
| India research and insights industry | **₹29,008 Cr** in FY25 (+10.9%); about 80% of revenue from international clients, so roughly **₹5,800 Cr** is domestic | MRSI 2025 [P, industry body] |
| FMCG companies disputing retail-audit data | Tata Consumer, ITC and Adani Wilmar have challenged NielsenIQ for missing channels | Press [3P] |
| Sales teams that fully trust their CRM data | **35%** (global) | Salesforce State of Sales 2024 [V] |
| HUL ad spend | ₹6,199 Cr, about **10%** of turnover (FY25). Trade schemes are a further 8–25% of revenue (unverified vendor estimate) | Press [3P]; vendor blogs [V] |

### When the invisible becomes expensive
| Event | Detail | Source |
|---|---|---|
| RBI penalties for recovery-agent conduct | Bajaj Finance ₹2.5 Cr (2021), RBL ₹2.27 Cr (2023), HDFC Bank ₹1 Cr (Sep 2024), Navi ₹3.8 lakh (Feb 2026) | RBI press releases [P] |
| Recovery visit turned fatal | M&M Finance, Hazaribagh (2022). RBI barred its outsourced recovery | Business Standard [3P] |
| Insurance mis-selling complaints | **26,667** in FY25, **up 14%**; 22% of life-insurance grievances | IRDAI via press [3P] |
| Pharma freebies | ₹1,000 Cr allegation (Dolo-650, 2022, disputed); first UCPMP 2024 action against AbbVie over ₹1.91 Cr of doctor travel | Press [3P] |

## 3. Who has it, how, why now

**Who.** Three groups, with different reasons:
1. **Marketing, brand and product leaders**, who get competitor, price and demand intelligence late,
   from surveys and audits that cover only part of the market.
2. **Sales leaders**, who can't coach what they don't hear, in a workforce that turns over every
   2–4 years.
3. **Compliance and risk teams** in BFSI and pharma, who answer for conduct they can't see.

**How Nabz solves it.**
- The rep records the visit after the customer consents, using a mobile web app or a voice note in
  the team's chat. There's nothing to install.
- **Gnani Prisma** transcribes Hinglish and Indian languages: diarization, codemix output, denoising,
  and company vocabulary as keyterms.
- Personal data is redacted before any AI sees the text.
- An LLM extracts quoted market signals, a lens-specific score, coaching and compliance flags. Every
  claim is checked against the transcript in code.
- **Gnani Timbre** voices a debrief to the rep in their own language.
- Managers approve CRM updates, and the market dashboard updates in near real time.

**Why now.** Five things changed in 2024–26:
1. **Indian speech recognition became usable and cheap.**
   - Code-mixed Indic word-error rates of about 16–19% (Gnani Prisma v3.0, 28 Oct 2026, vendor
     figure; Sarvam about 19% on IndicVoices).
   - About ₹16–30 per audio hour (Sarvam ₹0.49/min [P]; Google Chirp batch about ₹16/hr [P]).
   - In 2023 the best open baseline was IndicWhisper on Vistaar.
   - These are sovereign-funded models: the IndiaAI Mission (₹10,372 Cr) backs Gnani's 14B voice model [P].
2. **Language-model analysis became 150–250x cheaper per conversation**: about $0.39 per
   analysed call at GPT-4 (2023) prices against under $0.003 now, with a measured ₹0.25 per visit on
   Claude Haiku 5.5 [M]. a16z puts the decline at about 10x a year at equal capability [3P].
3. **The regulation got sharper:**
   - **DPDP Rules notified 13 Nov 2025**: consent-manager provisions from 13 Nov 2026, notice and
     consent duties from about May 2027, penalties up to ₹250 Cr [P].
   - **RBI recovery directions (6 Aug 2026), in force 1 Jan 2027**: lenders must record recovery
     calls, keep them for 6 months, contact borrowers only 8am–7pm, and certify agents [P].
   - **Supreme Court, 8 Oct 2026**: ordered an expert panel on enforceable pharma marketing rules,
     next hearing 29 Jan 2027 [3P].
4. **General trade is under pressure.** Quick commerce was $10–11B GMV in 2025, heading for
   $65–70B by 2030 [3P, Bain]. Kirana share is falling 1–2 points a year. Brands defending general
   trade need to know what's happening at the counter now, not next quarter.
5. **The category is proven elsewhere:**
   - Rilla (~$70M ARR estimated, ~$757M valuation) and Siro ($50M Series B) [3P].
   - Salesforce added an In-Person Meeting Assistant in Apr 2026.
   - An Indian early entrant, VoClyp, appeared in Jun 2026, which confirms the same reading of the
     market.

## 4. Is it urgent? An honest answer

**Urgent for some, nice to have for others. We start where it's urgent.**

| Segment | Verdict | Why |
|---|---|---|
| **NBFC/MFI field collections and loan officers** | 🔥 **Urgent, with a deadline** | RBI directions from 1 Jan 2027 make recording the norm for recovery *calls*, and field *visits* are the obvious next gap. Repeated penalties, reputational incidents, 52% attrition (training cost) and a compliance budget owner all exist. Recording also protects the borrower: "this visit is recorded for your protection" |
| **FMCG and food brands (₹500–5,000 Cr) fighting for general trade** | 🔥 Urgent for the business, but competing for budget | Quick commerce and competitors' credit and schemes are taking counter share now (our demo shows the pattern: Britannia's 15-day credit in Delhi). Market intelligence competes with research budgets (about ₹5,800 Cr domestic) and trade spend. Win by tying insights to scheme ROI |
| **Pharma** | 💊 Nice to have today; could become urgent in 2027 | UCPMP is voluntary, with only 7 complaints in 5 years. The pull is self-policing and coaching on key messages. The Supreme Court panel could change that after Jan 2027 |
| **Insurance agents** | 💊 Nice to have | Mis-selling complaints are up 14%, but agents are not employees, and adoption and consent are harder. Later |

**Counterarguments we take seriously:**
1. **Regulation covers calls, not visits.** Field-visit recording is a sensible extension, not yet a
   legal requirement.
2. **Fear of surveillance.** Medical reps' unions protested GPS tracking (2023), and DPDP commentary
   narrows employee monitoring. *Mitigation:* coaching first. Reps get their own debrief first, a
   visible consent step, raw audio deleted within a day, no covert recording, and access by role.
3. **Accuracy on far-field audio is unproven,** since Prisma is tuned on phone audio. *Mitigation:*
   our open noise benchmark, denoising, keyterms from the CRM, and the quote checker, which drops any
   claim it can't verify.
4. **Indian deal sizes and AI budgets are small** (over 95% of firms spend less than 20% of IT budget
   on AI, EY-CII 2025), and sales cycles run 6–18 months. *Mitigation:* paid pilots, and selling
   through the sales-software vendors buyers already use.

## 5. Ideal customer and who pays

| | Beachhead 1: lending | Beachhead 2: consumer goods |
|---|---|---|
| **Who** | NBFC-MFIs and NBFCs with 1,000–20,000 field officers or collection agents | Indian FMCG, food and beverage brands with ₹500–5,000 Cr turnover, 200–2,000 reps and distributor salesmen, and over 70% of sales through general trade |
| **Economic buyer** | Chief Risk/Compliance Officer with the Head of Collections | VP or Head of Sales (owns trade spend), co-signed by the CMO or brand head (intelligence) |
| **Champion** | Head of Training or Field Quality | Head of Sales Excellence or Capability |
| **Budget line** | Compliance and risk, plus training | Sales capability and training, market research, trade-spend effectiveness |
| **Trigger** | RBI directions from 1 Jan 2027, a recent penalty or incident, or an audit finding | Lost share to quick commerce or a competitor scheme, a new product launch, a scheme redesign |
| **Already uses** | A loan management system and call-recording for telephony | A sales/distribution app (Bizom, FieldAssist) and a retail audit (NIQ) |
| **Why they pick Nabz** | It audits the in-person visit with consent, scores conduct against RBI rules, and keeps an audit log that is evidence for regulators | It gives a weekly view of what the market is saying, with quotes, plus coaching that improves scheme recall |

**Who pays:** the enterprise, never the rep. Annual SaaS **per field user per month**, tiered by
included audio hours, with a compliance tier for BFSI and pharma.

| Plan | ₹/rep/month | Includes | Benchmarks |
|---|---|---|---|
| Coach | 1,000 | 10 audio hrs, coaching and debriefs | Implied Bizom ~₹300 and FieldAssist ~₹550 per user per month (revenue ÷ users) [our calculation from 3P figures] |
| **Intelligence (base)** | **2,000** | 22 audio hrs, market dashboard, CRM sync | Zoho CRM Enterprise ₹2,400 [3P]; LeadSquared Pro ₹2,500 [3P] |
| Compliance | 4,000 | Plus compliance lenses, audit export, deployment in the customer's own cloud | Observe.AI ~$69 per agent per month [3P]; Gong $110–160 per seat per month [3P]; Rilla ~$350–400 per seat per month [3P] |

## 6. Precedents

| Company | What it proves | Data |
|---|---|---|
| **Rilla** (US) | In-person conversation intelligence is a venture-scale category | ~$70M ARR (Apr 2026 est.), 2,000+ accounts, ~$20K average contract, ~$757M valuation [3P] |
| **Siro** (US) | Same, in field and home sales | $50M Series B, May 2025 [3P] |
| **Salesforce** | The incumbent now covers in-person meetings | In-Person Meeting Assistant, Apr 2026 [P] |
| **Chorus → ZoomInfo** | Conversation-intelligence acquisitions happen | $575M, 2021 [3P] |
| **Bizom** (India) | Indian field-sales software scales to hundreds of thousands of users | ₹90.9 Cr revenue FY25, 250K+ users, $12M Series B (Dec 2024) [3P] |
| **FieldAssist** (India) | Indian buyers pay for field software; capital-efficient | ₹66.5 Cr revenue FY25 (+34%), ~100K users, essentially bootstrapped [3P] |
| **Convin** (India) | Indian buyers pay for conversation intelligence; in-person recorder exists | $6.5M Series A, 80+ clients, ₹9 Cr revenue FY24 [P/3P] |
| **Salesken** (India) | Expansion from pilot to scale | One insurer went 300 → 1,000 → 4,000 seats in 5 months [V] |
| **Gnani.ai** | Our speech partner has the same enterprise buyers | $10M Series B (Mar 2026), 200+ enterprise clients, mostly BFSI [P] |
| **VoClyp** (India) | Others read the market the same way | Domain registered Jun 2026; no named founders, customers or prices; free 3-week pilot [P] |

**Vendor-claimed uplift** (marketing claims, not independently verified): Rilla +33% close rate,
Siro +36%, Convin +23% conversion, Salesken 15–25% in 60 days.

## 7. Market size: TAM, SAM, SOM (bottom-up)

All rows are reps × ₹/rep/month × 12. Change any **[A]** and the totals follow.

### TAM: every field rep in sized segments who could use Nabz
| Segment | Conservative reps | Base reps | Basis |
|---|---|---|---|
| Pharma medical reps | 2,00,000 | 3,00,000 | Estimates [3P] |
| FMCG and distributor salesmen | 4,00,000 | 8,00,000 | 4–4.5 lakh distributors × 1–2 [A] |
| Microfinance field staff | 2,09,000 | 2,09,000 | Sa-Dhan [P] |
| Insurance agents (active subset) | 3,12,000 (10%) | 6,24,000 (20%) | 31.2 lakh registered [3P] × active share [A] |
| **Total reps** | **11.2 lakh** | **19.3 lakh** | Excludes collection agents, DSAs and promoters (upside) |
| **× price** | ₹1,000/mo | ₹2,000/mo | Pricing table |
| **TAM (annual)** | **₹1,343 Cr (~$153M)** | **₹4,637 Cr (~$527M)** | ₹88/$ |

*Sense-check:* India speech analytics is $113–182M [3P], India field-force automation $140M (2024)
[3P], and the domestic research industry about ₹5,800 Cr [P]. A TAM of ₹1,300–4,600 Cr sits between
the software and research budgets it draws from, which is plausible.

### SAM: what we can serve in 3 years
Mid and large enterprises with employed field forces in our two beachheads, plus pharma. Insurance
agents are excluded (non-employees, harder consent).
| Segment | Share in companies with 200+ reps | Reps |
|---|---|---|
| FMCG and distributor salesmen (top ~100 brands) | 50% [A] | 4,00,000 |
| Pharma (top ~100 companies; the top 20 alone have over 1 lakh medical reps [3P]) | 60% [A] | 1,80,000 |
| NBFC-MFI and NBFC field staff | 70% [A] | 1,46,000 |
| **SAM** | | **7.26 lakh reps × ₹24,000/yr = ₹1,742 Cr (~$198M)** |

### SOM: what we plan to win by year 3 (end of 2029)
| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Customers | 5 design partners → 4 paid | 15 | 40 |
| Paid reps | 2,000 | 8,000 | **15,000** (stretch 25,000) |
| ARR at ₹24,000/rep/yr | ₹4.8 Cr | ₹19.2 Cr | **₹36 Cr (~$4.1M)**; stretch ₹60 Cr |
| Share of SAM | 0.3% | 1.1% | **2.1%** |

*Precedent check:* 15,000 paid reps in year 3 is about 15% of FieldAssist's user base and 6% of
Bizom's after roughly a decade each. That's ambitious but grounded, and depends on selling through
those vendors (section 9).

## 8. Unit economics

Per rep per month at the base plan, assuming **1 hour of recorded conversation a day, 22 days, and
10 recorded visits a day** [A]:

| Cost line | Calculation | ₹/rep/month |
|---|---|---|
| Speech to text (Gnani Prisma batch) | 22 hrs × ₹20–27/hr (₹27/hr via a reseller [3P], ₹20 assumed direct [A]) | 440–594 |
| AI analysis, **routed** | 220 visits × ₹0.25 (Haiku 5.5, measured token profile [M]) + 10% escalated to Opus 5.5 × ₹10.16 [M] | 55 + 224 = **279** |
| Voice debrief (Timbre), one a day | 22 × ~350 characters [M] ≈ 7.7K chars (proxy ₹1 per 1K, Sarvam [P]) | ~8 |
| Hosting, storage, support | [A] | 150 |
| **Cost of goods** | | **~₹880–1,030** |
| **Gross margin at ₹2,000** | | **~49–56%**, rising to about 60%+ with batch pricing and Gnani volume rates |

**What we measured** [M], over 14 analysed visits: about 1K input and 5.6K output tokens each. All
on Opus 5.5 that's ₹10.16 per visit; on Haiku 5.5 it's ₹0.25.
- 220 visits on Opus alone would cost about ₹2,235 per rep per month, more than the price.
- **So production routing is required, not optional.** Use Haiku for routine visits and Opus only
  for compliance flags, low-confidence cases and the weekly market summary.
- Output size can also be cut. Notes and follow-ups get written only for visits that need them.
- The quote checker is what makes a cheaper model safe: any claim it can't verify is dropped.

## 9. Execution plan

**First 90 days: prove value with three design partners.**
- One NBFC-MFI (collections and loan officers), one regional FMCG brand, one mid-size pharma company.
- 3-week pilot with 50–100 reps each. Success metrics agreed in writing up front:
  - share of visits recorded;
  - share of quotes verified;
  - market insights acted on (e.g. a scheme changed);
  - debrief listen rate;
  - compliance issues caught.
- Product work:
  - a WhatsApp channel;
  - offline capture (record now, sync later);
  - model routing (Haiku/Opus) with an evaluation set built from pilot audio;
  - a DPDP consent-manager integration;
  - Hindi, Marathi, Tamil, Kannada and Bengali debriefs.
- **Gnani partnership:**
  - volume pricing for Prisma and Timbre;
  - access to their 200+ BFSI clients, who are the same buyers.
  - Nabz takes Gnani's speech models into field conversations, beyond the call centre.

**Months 3–12: from pilot to paid; sell through partners.**
- Integrations: Bizom, FieldAssist and LeadSquared (250K+ and 100K users already, a distribution
  channel), Zoho (data in India) and Salesforce.
- SOC 2 Type 1 and ISO 27001 readiness.
- The compliance tier, with RBI and UCPMP report packs.
- Target: **₹4–5 Cr ARR**, 4 paid customers, two public case studies.

**Months 12–36: scale and go sovereign.**
- On-premises deployment (Gnani Prisma on-prem plus open-weight Evon for reasoning) for banks and
  insurers.
- A weekly "market pulse" for leadership.
- More languages, then Southeast Asia (similar general-trade structure).
- Target: **₹36 Cr ARR, 15,000 reps.**

**Risks, and what we do about them.**
| Risk | Mitigation |
|---|---|
| Reps resist surveillance | Coaching first; the rep's own debrief comes first; visible consent; audio deleted within a day; no covert mode; unions and HR involved in pilot design |
| Accuracy on noisy audio | Public noise benchmark; denoising; CRM keyterms; claims dropped when quotes can't be verified |
| Long Indian sales cycles | Paid pilots with fixed scope; sell through SFA vendors; compliance deadline (1 Jan 2027) as the urgency |
| Dependence on one speech vendor | The speech engine is swappable (Whisper fallback built in; Sarvam as an option) |
| Margins | Model routing; batch processing; audio-hour tiers |
| VoClyp, Convin, and Salesforce moving in | Gnani-native Indic accuracy, quote verification, compliance lenses, no app to install, open benchmark, sovereign deployment |

## Sources

Fuller links are in the research notes (docs/research/). Key primary sources:
- NIQ India FMCG Snapshot Q1'26
- HUL FY24 performance highlights
- Sa-Dhan Bharat Microfinance Report 2025
- MRSI industry report FY25
- RBI press releases (Bajaj Finance 2021, HDFC Bank 2024, Navi 2026) and RBI recovery-agent directions (6 Aug 2026)
- PIB on the DPDP Rules 2025
- LIC persistency press release FY25
- Mankind Pharma investor disclosures
- Sarvam and Google Cloud price pages
- Gnani Series B (Business Today, 31 Mar 2026)

Third-party sources: Sacra (Rilla), Inc42 (Bizom, Convin, Salesken), Bain (quick commerce),
Redseer, Kantar, a16z and Epoch AI (LLM price trends), EY-CII (GenAI adoption).
