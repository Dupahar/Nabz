# Nabz: independent audit (9 Nov 2026)

Three independent auditors (engineering and security, problem and business case, product and
UX) were given the files, not the authors' conclusions. Their findings were then cross-checked
against the code. Scores are strict: 1–10, judged against pre-seed product standards.
This is the audit of the first prototype; the fixes since are in the git history.

## Scorecard

| # | Aspect | Score | Verdict |
|---|---|---|---|
| 1 | Problem clarity | **4** | "Head office never hears the field" is a symptom. Three buyers have three pains, and each doc leads with a different one |
| 2 | Pain severity / urgency | **3** | The only hard deadline (RBI, 1 Jan 2027) covers recovery **calls**, which telephony vendors already serve. Nothing mandates recording field visits |
| 3 | Evidence quality | **5** | Sources are real and honestly tagged (14 spot-checked). Several are applied to the wrong denominator, and one is misquoted ("200+ BFSI clients") |
| 4 | Market sizing | **3** | The TAM is headcount × our own price. It includes insurance, which the SAM drops, and leaves out the collections beachhead. The base TAM is ~3.8× India's whole field-force-automation market |
| 5 | Pricing and unit economics | **3** | Cost arithmetic is right, but ₹2,000 is 3.6–6.6× incumbent SFA tools with no willingness-to-pay evidence. No CAC, churn or implementation costs. **As shipped (all-Opus) it loses money per rep** |
| 6 | Competition and moat | **2** | Convin, Gnani and the SFA vendors are each one feature away. "Built on Gnani" is a dependency, not a moat |
| 7 | GTM and execution plan | **2** | Three verticals, no named team. Year-1 ARR contradicts the plan's own 6–18-month sales cycle |
| 8 | Risk analysis | **5** | Better than most. Misses selection bias (reps choose what to record) and coerced consent at a borrower's door |
| 9 | Internal consistency | **3** | README = market intelligence, business case = collections, landscape = coaching. Stale "FieldNotes" docs remain |
| 10 | Security | **2** | Unsigned cookie login: anyone can become admin. No CSRF token. Unbounded uploads into ffmpeg |
| 11 | Privacy / DPDP | **3** | Consent is a client-side checkbox. Erasure leaves CRM and usage residue. Names are never redacted. Retention never runs |
| 12 | Correctness | **4** | **The quote check accepts negated or altered quotes** ("will switch" vs "will **not** switch" scores 0.87, "5" vs "50" scores 0.98). The drop-unverified sort bug can keep a fabricated claim |
| 13 | Reliability | **3** | No timeouts. Queued visits are lost on restart. An exception raised by a helper (`SystemExit`) can leave a visit stuck forever |
| 14 | Code quality | **6** | Readable and lint-clean. Library code calls `sys.exit`, and some docstrings overstate what the code does |
| 15 | Testing | **0** | No tests, no CI |
| 16 | Ops / deployability | **2** | Localhost only. No HTTPS, so phone recording can't work. No health check, logging or pinned dependencies |
| 17 | Gnani usage depth | **5** | Prisma is used well (diarization, codemix, keyterms, denoise) and Timbre is real, but the brain is Claude, not Evon |
| 18 | Innovation | **5** | The category exists (Rilla, Convin, VoClyp). Novel: quote-verified market signals and native-language voice debriefs |
| 19 | Real-world usefulness | **7** | Credible pain, plausible buyer, a believable workflow |
| 20 | UX and polish | **6** | Clean and modern. English-only rep UI, dense pages, demo debris (an error row, "set rates") |
| 21 | Demo-ability / engagement | **4** | No video, no live URL. An enterprise dashboard doesn't land in 3 seconds |
| 22 | Claims vs code | **5** | Synthetic data is disclosed in the README only, not in the UI. At least 6 "Why trust it" claims overreach. No real human recording yet |
| 23 | Release readiness | **2** | No remote, no video, no deployment, stale FieldNotes docs, benchmark unfinished and not in the repo |
| | **Overall** | **3.7 / 10** | **A strong prototype with honest instincts, but over-claimed, not yet releasable, and not yet a business** |

## Auditor errors (findings rejected on verification)
- "docs/API.md, playbooks/, .env.example and demo/kirana_snippet.ogg don't exist": they do exist in Nabz. The auditor looked in the wrong place.
- "Visible 'Rep 100%' talk-ratio bug": from an outdated screenshot. That visit was erased, and the pipeline now skips metrics when the rep isn't recorded. `metrics.py` itself still lacks the guard, so that part is a valid Low.
- No XSS found: every `innerHTML` sink is escaped. (Credit, not a flaw.)

## Findings by severity (verified)

**Critical**
1. Anyone can log in as any user, including admin (unsigned handle cookie, team list served before login). `app/server.py:44-49, 105-114, 133`
2. The quote check accepts fabricated quotes through fuzzy matching (0.85 threshold, no digit or negation check, a 4-segment window that crosses speakers). `tools/analysis.py:111-135`
3. Not releasable: no public repo, video or live URL. Some docs are stale.

**High**
4. `drop_unverified` sorts field names as text, so `needs[10]` before `needs[9]` drops the wrong item. `tools/llm.py` (drop_unverified)
5. After the last retry, schema errors are written anyway. `tools/llm.py` (analyse)
6. Prompt injection: transcript and rep note go into the prompt with no data delimiters. Score, follow-up and CRM fields aren't grounded. `tools/llm.py` visit_block
7. Consent is self-attested. "Verbal, on tape" is never checked against the transcript (`consent.scan` is unused).
8. Erasure is incomplete (CRM and usage rows remain, names stay in the audit log) and can be undone by a pipeline still running.
9. No timeouts on subprocesses or the Gnani poll loop; 3 stuck jobs block all workers.
10. Unbounded uploads; ffmpeg runs on untrusted input with no protocol or format whitelist.
11. Queued or in-progress visits are never resumed after a restart.
12. README "Why trust it" overclaims. PII *does* reach the AI (names, the rep's note). Retention never runs. Managers can read the audit log. The agent permissions allow `grep`, which can read `.env`.
13. The beachhead (collections) contradicts the product, demo and sizing (FMCG intelligence). Collections isn't in the TAM, and MFI centre meetings exceed `max_speakers: 3`.
14. Unit economics as shipped: every visit goes to Opus, about ₹2,235 per rep per month in LLM alone against a ₹2,000 price.

**Medium**
15. Redaction gaps: "ninety-eight forty-five…" style numbers, splits across segments, lowercase IFSC. The digit-collapse rule can merge prices into one number.
16. CRM contact names are sent to Gnani as keyterms. `prisma.json` and a brief window of `transcript.json` are unredacted.
17. The audit chain has no key and no external anchor. Truncating it from the end goes undetected.
18. The trust KPIs are true by construction (consent rate always 100%; quotes-verified computed after dropping failures).
19. `recorded_at` is the processing time, not the recording time, so relative dates ("kal", "Friday") and retention ages are off.
20. A rep can erase their own flagged visit and approve their own CRM proposal.
21. CSRF: SameSite=Lax with no token; another localhost app could POST `/erase`.
22. Lens cue matching checks only the left word boundary ("deal" matches "dealer"). The visit's segment is ignored.
23. Chart.js is unpinned with no integrity hash; no Content Security Policy.
24. Synthetic demo data isn't labelled in the UI.
25. LLM cost logging ignores cache-write tokens, and demo visits average about 1 minute, so the per-visit cost is understated.

**Low**
26. Call-ID collisions within the same second. A fixed `.tmp` name in `write_json`. Full directory scans on every poll. Unbounded `limit`. Rejected-by not shown. Dead code (`schema`, `NSTR`/`NINT`). A legacy reference to `tools/calls.py`. Unpinned requirements. No logging or health endpoint. English-only rep UI. Accessibility gaps (keyboard access to table rows, chart alternatives, reduced motion). The Telegram channel was never exercised as Nabz.
