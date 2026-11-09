/* Nabz: one visit (scorecard, voice debrief, verified quotes, transcript, approvals, consent). */
(function () {
  "use strict";
  const N = window.Nabz;
  const $ = (id) => document.getElementById(id);
  const esc = N.esc;

  const callId = decodeURIComponent(
    new URLSearchParams(location.search).get("id") || location.pathname.replace(/\/+$/, "").split("/").pop() || ""
  );
  const ORDER = ["queued", "transcribing", "analysing", "voicing", "done"];
  const STEP_LABELS = [
    ["consent", "Consent ✓"],
    ["transcribing", "Transcribing (Gnani Prisma)"],
    ["analysing", "Analysing"],
    ["voicing", "Voice debrief (Gnani Timbre)"],
    ["done", "Done"],
  ];
  const LANG_NAMES = {
    "hi-en": "Hinglish", "hi-IN": "Hindi", "en-IN": "English", "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "mr-IN": "Marathi", "bn-IN": "Bengali", "gu-IN": "Gujarati", "pa-IN": "Punjabi",
  };
  const CHECK_ICON = { yes: "✅", partial: "🟡", no: "❌", unknown: "❓" };
  const SIGNAL_LABEL = {
    demand: "Demand", competitor: "Competitor", price: "Price", product_feedback: "Product feedback",
    availability: "Availability", scheme: "Scheme", other: "Other",
  };
  const COACH = { "well-done": ["👏", "Well done"], "try-next": ["🎯", "Try next time"], "do-more": ["➕", "Do more"] };

  let user = null;
  let cfg = null;
  let pollTimer = null;
  let renderedDone = false;

  async function init() {
    N.mountFooter();
    user = await N.mountTopbar("visit");
    if (!user) return;
    if (user.role !== "rep") { $("backLink").href = "/dashboard"; $("backLink").textContent = "← Market intelligence"; }
    try { cfg = await N.config(); } catch (e) { cfg = { team: [] }; }
    if (!callId) { $("title").textContent = "No visit selected"; return; }
    $("eraseBtn").addEventListener("click", erase);
    load();
  }

  async function load() {
    clearTimeout(pollTimer);
    let d;
    try {
      d = await N.api(`/api/visits/${encodeURIComponent(callId)}`);
    } catch (e) {
      if (e.message === "login") return;
      $("title").textContent = e.status === 404 ? "Visit not found" : e.status === 403 ? "Not your visit" : "Couldn't load visit";
      $("errBox").innerHTML = `<div class="alert error">${esc(e.message)}</div>`;
      return;
    }
    renderHeader(d);
    const st = (d.visit && d.visit.status) || "queued";
    if (st === "done") {
      if (!renderedDone) { renderBody(d); renderedDone = true; } else { renderProposal(d); renderAudit(d); }
    } else if (!["error", "needs_consent_review"].includes(st) && !(d.visit && d.visit.stalled)) {
      pollTimer = setTimeout(load, 3000);
    }
    applyPermissions(d);
  }

  function applyPermissions(d) {
    const perm = d.permissions || {};
    const btn = $("eraseBtn");
    if (btn) {
      btn.disabled = !perm.erase;
      btn.title = perm.erase ? "" : (perm.erase_reason || "Not allowed");
      const why = document.getElementById("eraseWhy");
      if (!perm.erase && perm.erase_reason && !why) {
        btn.insertAdjacentHTML("afterend", `<div id="eraseWhy" class="muted" style="font-size:.78rem;margin-top:.3rem">${esc(perm.erase_reason)}</div>`);
      }
    }
  }

  async function action(path, okMsg) {
    try {
      await N.api(`/api/visits/${encodeURIComponent(callId)}/${path}`, { method: "POST", body: {} });
      N.toast(okMsg);
      renderedDone = false;
      load();
    } catch (e) {
      N.toast(`Failed: ${e.message}`, 3500);
    }
  }

  // ------------------------------------------------------------------ header & steps
  function renderHeader(d) {
    const v = d.visit || {};
    document.title = `Nabz · ${v.account || callId}`;
    $("title").textContent = v.account || callId;
    const tr = d.transcript || {};
    const langs = (tr.languages && tr.languages.length ? tr.languages : tr.language ? [tr.language] : []).map((l) => LANG_NAMES[l] || l);
    const bits = [
      v.contact && `👤 ${esc(v.contact)}`,
      v.segment && `🏪 ${esc(v.segment)}`,
      v.region && `📍 ${esc(v.region)}`,
      v.rep && `🧑‍💼 ${esc(v.rep)}`,
      v.recorded_at && `🗓 ${esc(N.fmtDate(v.recorded_at))}`,
      v.duration_sec && `⏱ ${esc(N.fmtDuration(v.duration_sec))}`,
      langs.length && `🗣 ${esc(langs.join(", "))}`,
      v.note && `📝 ${esc(v.note)}`,
    ].filter(Boolean);
    $("metaLine").innerHTML = bits.map((b) => `<span>${b}</span>`).join("");
    const chips = [];
    if (v.synthetic) chips.push(N.syntheticBadge(v));
    if (v.lens_name) chips.push(`<span class="chip brand">${esc(v.lens_name)}</span>`);
    if (v.status !== "done") chips.push(N.statusChip(v.status, v.stage, v.stalled));
    if (v.flags) chips.push(`<span class="chip bad">🚩 ${esc(v.flags)} flag${v.flags > 1 ? "s" : ""}</span>`);
    $("headChips").innerHTML = chips.join("");

    const idx = ORDER.indexOf(v.status);
    const err = v.status === "error";
    $("steps").innerHTML = STEP_LABELS.map(([key, label], i) => {
      let cls = "";
      if (key === "consent") cls = !d.consent ? "" : (d.consent.verified === false && !d.consent.review ? "error" : "done");
      else {
        const k = ORDER.indexOf(key);
        if (v.status === "done" || k < idx) cls = "done";
        else if (k === idx) cls = err ? "error" : "active";
        if (key === "done" && v.status === "done") cls = "done";
      }
      return `<span class="step ${cls}"><span class="dot"></span>${esc(label)}</span>`;
    }).join("");
    const perm = d.permissions || {};
    if (v.status === "needs_consent_review") {
      $("errBox").innerHTML = `<div class="alert warn-box" role="alert"><b>⚠️ Consent not verified.</b> ${esc(v.error || "")}
        No AI analysis has run on this recording. ${perm.confirm_consent
          ? 'Listen to the start of the recording, then confirm if the customer did agree.<div style="margin-top:.5rem"><button class="btn primary sm" id="confirmConsentBtn">I reviewed it: the customer consented</button> <button class="btn secondary sm" id="eraseNowBtn">Erase the recording</button></div>'
          : "A manager needs to review it before anything else happens."}</div>`;
      const cb = $("confirmConsentBtn"), eb = $("eraseNowBtn");
      if (cb) cb.addEventListener("click", () => action("confirm-consent", "Consent confirmed: processing continues"));
      if (eb) eb.addEventListener("click", erase);
    } else if (err || v.stalled) {
      if (err) $("steps").innerHTML += `<span class="step error"><span class="dot"></span>Error</span>`;
      const msgText = err ? `Processing failed: ${esc(v.error || v.stage || "unknown error")}` : "This visit has made no progress for a while.";
      $("errBox").innerHTML = `<div class="alert error">${msgText}${perm.retry ? ' <button class="btn secondary sm" id="retryBtn" style="margin-left:.5rem">Retry</button>' : ""}</div>`;
      const rb = $("retryBtn");
      if (rb) rb.addEventListener("click", () => action("retry", "Queued again"));
    } else if (v.status !== "done") {
      $("errBox").innerHTML = `<div class="alert info">${esc(v.stage || "Processing…")} This page updates by itself.</div>`;
    } else {
      $("errBox").innerHTML = "";
    }
  }

  // ------------------------------------------------------------------ body
  function renderBody(d) {
    $("body").classList.remove("hidden");
    const a = d.analysis || {};
    const lens = d.lens || {};
    renderScore(d, a, lens);
    renderDebrief(d, a);
    renderFlags(a);
    renderChecklist(a, lens);
    renderSignals(a);
    renderConcerns(a);
    renderNeedsRisks(a);
    renderCoaching(a);
    renderMetrics(d, a);
    renderCommitments(a);
    renderProposal(d);
    renderTranscript(d);
    renderNotes(d.notes_md);
    renderConsent(d);
    renderAudit(d);
    bindQuotes(document.body);
  }

  function quoteHtml(q, seg) {
    if (!q) return "";
    const s = seg == null || seg === "" ? "" : ` data-seg="${esc(seg)}"`;
    return `<button class="quote-btn"${s} title="Show in transcript"><span class="quote">“${N.renderRedactions(q)}”</span></button>`;
  }

  function bindQuotes(root) {
    root.querySelectorAll(".quote-btn[data-seg]").forEach((b) => {
      if (b.dataset.bound) return;
      b.dataset.bound = "1";
      b.addEventListener("click", () => jumpTo(b.dataset.seg));
    });
  }

  function jumpTo(seg) {
    const el = document.getElementById(`seg-${seg}`);
    if (!el) return;
    const box = $("transcript");
    box.scrollTop = el.offsetTop - box.offsetTop - 60;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    document.querySelectorAll(".bubble.hl").forEach((x) => x.classList.remove("hl"));
    el.classList.add("hl");
    setTimeout(() => el.classList.remove("hl"), 3500);
  }

  function renderScore(d, a, lens) {
    const score = a.score;
    const r = 48, c = 2 * Math.PI * r;
    const frac = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
    const color = score == null ? "#CBD5E1" : score >= 65 ? "#059669" : score >= 40 ? "#D97706" : "#DC2626";
    $("ring").innerHTML = `
      <svg width="112" height="112" viewBox="0 0 112 112">
        <circle cx="56" cy="56" r="${r}" fill="none" stroke="#EEF2FF" stroke-width="10"/>
        <circle cx="56" cy="56" r="${r}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"
          stroke-dasharray="${(c * frac).toFixed(1)} ${c.toFixed(1)}"/>
      </svg>
      <div class="val"><div><b>${score == null ? "–" : esc(score)}</b><span>${esc(lens.score_label || (d.visit && d.visit.score_label) || "Score")}</span></div></div>`;
    const sentIcon = { positive: "🟢", neutral: "⚪", negative: "🔴", mixed: "🟡" }[a.sentiment] || "";
    const chips = [];
    if (a.sentiment) chips.push(`<span class="chip">${sentIcon} ${esc(a.sentiment)}</span>`);
    if (a.stage_suggested) chips.push(`<span class="chip brand">Stage → ${esc(a.stage_suggested)}</span>`);
    if (lens.name) chips.push(`<span class="chip">${esc(lens.name)}</span>`);
    $("scoreChips").innerHTML = chips.join("");
    $("summary").innerHTML = N.renderRedactions(a.summary || "");
    $("scoreReason").textContent = a.score_reason ? `Why: ${a.score_reason}` : "";
    const g = a.grounding;
    if (g && g.checked) {
      const all = g.verified === g.checked;
      $("verifiedBox").innerHTML = `<span class="verified ${all ? "" : "partial"}" title="Every judgement carries a verbatim quote, checked against the transcript in code">🔎 ${esc(g.verified)}/${esc(g.checked)} judgements verified against the transcript</span>`;
    }
  }

  function renderDebrief(d, a) {
    const url = d.assets && d.assets.debrief;
    if (!url && !a.debrief) return;
    $("debriefCard").classList.remove("hidden");
    const v = d.visit || {};
    const member = (cfg.team || []).find((m) => m.name === v.rep || m.handle === v.rep_handle);
    const lang = member && member.language ? (LANG_NAMES[member.language] || member.language) : (LANG_NAMES[a.language] || a.language || "their language");
    $("debriefCaption").textContent = `Coaching for ${v.rep || "the rep"} in ${lang}, voiced by Gnani Timbre`;
    if (url) $("debriefAudio").src = url; else $("debriefAudio").classList.add("hidden");
    $("debriefText").innerHTML = a.debrief ? `“${esc(a.debrief)}”` : "";
  }

  function renderFlags(a) {
    const flags = a.compliance_flags || [];
    if (!flags.length) return;
    $("flagsCard").classList.remove("hidden");
    $("flags").innerHTML = flags.map((f) => `
      <div class="item">
        <div class="t"><span class="chip bad">${esc(f.severity || "")}</span> ${esc(String(f.rule || "").replace(/_/g, " "))}</div>
        <div class="q">${quoteHtml(f.quote, f.segment)}</div>
      </div>`).join("");
  }

  function renderChecklist(a, lens) {
    const qs = lens.checklist || {};
    const items = a.checklist || {};
    const keys = Object.keys(qs).length ? Object.keys(qs) : Object.keys(items);
    $("checklistTitle").textContent = lens.name ? `${lens.name.split("/")[0].trim()} checklist` : "Checklist";
    $("lensChip").textContent = lens.id || "";
    if (!keys.length) { $("checklist").innerHTML = '<div class="muted">No checklist for this lens.</div>'; return; }
    $("checklist").innerHTML = keys.map((k) => {
      const it = items[k] || { status: "unknown" };
      return `<div class="check-row">
        <span class="ic" title="${esc(it.status)}">${CHECK_ICON[it.status] || "❓"}</span>
        <div class="q"><div class="k">${esc(k.replace(/_/g, " "))}</div>
          <div class="muted" style="font-size:.8rem">${esc(qs[k] || "")}</div>
          ${it.quote ? `<div style="margin-top:.2rem">${quoteHtml(it.quote, it.segment)}</div>` : ""}</div>
      </div>`;
    }).join("");
  }

  function renderSignals(a) {
    const sig = a.market_signals || [];
    if (!sig.length) { $("signals").innerHTML = '<div class="muted">No market signals in this conversation.</div>'; return; }
    const groups = {};
    sig.forEach((s) => { (groups[s.type] = groups[s.type] || []).push(s); });
    $("signals").innerHTML = Object.keys(groups).map((t) => `
      <div class="section-label">${esc(SIGNAL_LABEL[t] || t)}</div>
      ${groups[t].map((s) => {
        const pol = s.polarity === "positive" ? "ok" : s.polarity === "negative" ? "bad" : "";
        const polIc = s.polarity === "positive" ? "📈" : s.polarity === "negative" ? "📉" : "•";
        const tags = [s.product && `<span class="chip brand">${esc(s.product)}</span>`, s.competitor && `<span class="chip them">vs ${esc(s.competitor)}</span>`].filter(Boolean).join(" ");
        return `<div class="item"><div class="t"><span class="chip ${pol}">${polIc} ${esc(s.polarity || "")}</span> ${esc(s.text || "")} ${tags}</div>
          <div class="q">${quoteHtml(s.quote, s.segment)}</div></div>`;
      }).join("")}`).join("");
  }

  function renderConcerns(a) {
    const cs = a.concerns || [];
    if (!cs.length) { $("concerns").innerHTML = '<div class="muted">No objections raised.</div>'; return; }
    $("concerns").innerHTML = cs.map((c) => `
      <div class="item">
        <div class="t"><span class="chip ${c.handled ? "ok" : "warn"}">${c.handled ? "✅ handled" : "⚠️ not handled"}</span>
          <span class="chip">${esc(c.category || "")}</span></div>
        <div class="q">${quoteHtml(c.quote, c.segment)}</div>
        ${c.how ? `<div class="muted" style="font-size:.82rem;margin-top:.2rem">Rep: ${esc(c.how)}</div>` : ""}
      </div>`).join("");
  }

  function renderNeedsRisks(a) {
    const needs = (a.needs || []).map((n) => `<div class="item"><div class="t">🧩 ${esc(n.text || "")}</div><div class="q">${quoteHtml(n.quote, n.segment)}</div></div>`);
    const sigs = (a.signals || []).map((n) => `<div class="item"><div class="t">✨ ${esc(n.text || "")}</div><div class="q">${quoteHtml(n.quote, n.segment)}</div></div>`);
    const risks = (a.risks || []).map((n) => `<div class="item"><div class="t">⚠️ ${esc(n.text || "")}</div><div class="q">${quoteHtml(n.quote, n.segment)}</div></div>`);
    const html = [
      needs.length && `<div class="section-label">Needs</div>${needs.join("")}`,
      sigs.length && `<div class="section-label">Positive signals</div>${sigs.join("")}`,
      risks.length && `<div class="section-label">Risks</div>${risks.join("")}`,
    ].filter(Boolean).join("");
    $("needsRisks").innerHTML = html || '<div class="muted">Nothing noted.</div>';
  }

  function renderCoaching(a) {
    const cs = a.coaching || [];
    if (!cs.length) { $("coaching").innerHTML = '<div class="muted">No coaching notes.</div>'; return; }
    $("coaching").innerHTML = cs.map((c) => {
      const [ic, label] = COACH[c.kind] || ["•", c.kind || ""];
      const seg = c.segment != null ? ` <button class="quote-btn muted" data-seg="${esc(c.segment)}" style="font-size:.78rem">(see segment ${esc(c.segment)})</button>` : "";
      return `<div class="item"><div class="muted" style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em">${ic} ${esc(label)}</div>
        <div style="margin-top:.15rem">${esc(c.tip || "")}${seg}</div></div>`;
    }).join("");
  }

  function renderMetrics(d, a) {
    const m = d.metrics;
    if (!m || !m.speakers) { $("metrics").innerHTML = '<div class="muted">Metrics appear once speakers are identified.</div>'; return; }
    const repKey = m.rep;
    const rep = m.speakers[repKey] || {};
    const others = Object.keys(m.speakers).filter((k) => k !== repKey);
    const themRatio = others.reduce((s, k) => s + (m.speakers[k].talk_ratio || 0), 0);
    const us = Math.round((rep.talk_ratio || 0) * 100), them = Math.round(themRatio * 100);
    const qt = a.question_types;
    const spin = qt ? ["situation", "problem", "implication", "need-payoff"].map((k) => `<span class="chip ${k === "implication" || k === "need-payoff" ? "brand" : ""}">${esc(k)} ${esc((qt[k] || []).length)}</span>`).join(" ") : "";
    $("metrics").innerHTML = `
      <div class="muted" style="font-size:.82rem;margin-bottom:.35rem">Talk ratio</div>
      <div class="bar2"><div class="us" style="width:${us}%"></div><div class="them" style="width:${them}%"></div></div>
      <div class="legend"><span><i style="background:var(--brand)"></i>Rep ${us}%</span><span><i style="background:var(--them)"></i>Customer ${them}%</span>
        <span>Gong 2025 (vendor data): won deals avg ~57% rep talk</span></div>
      <div class="stat-mini">
        <div><b>${esc(rep.questions != null ? rep.questions : "–")}</b><span>rep questions</span></div>
        <div><b>${esc(N.fmtDuration(rep.longest_monologue_sec || 0))}</b><span>longest monologue</span></div>
        <div><b>${esc(m.speaker_switches != null ? m.speaker_switches : "–")}</b><span>speaker switches</span></div>
      </div>
      ${spin ? `<div class="section-label">Question mix (SPIN)</div><div class="chips">${spin}</div>` : ""}
      ${(m.flags || []).length ? `<div class="section-label">Flags</div>${m.flags.map((f) => `<div class="muted" style="font-size:.85rem">• ${esc(f)}</div>`).join("")}` : ""}`;
  }

  function renderCommitments(a) {
    const cs = a.commitments || [];
    if (!cs.length) { $("commitments").innerHTML = '<div class="muted">No commitments made.</div>'; return; }
    const ownerChip = (o) => {
      const cls = o === "us" ? "brand" : o === "them" ? "them" : "";
      return `<span class="chip ${cls}">${esc(o || "?")}</span>`;
    };
    $("commitments").innerHTML = cs.map((c) => `
      <div class="item"><div class="t">${ownerChip(c.owner)} ${esc(c.action || "")} ${c.due ? `<span class="chip">📅 ${esc(c.due)}</span>` : ""}</div>
        <div class="q">${quoteHtml(c.quote, c.segment)}</div></div>`).join("");
  }

  function renderProposal(d) {
    const p = d.crm_proposal;
    const f = d.followup;
    if (!p && !f) { $("proposalCard").classList.add("hidden"); return; }
    $("proposalCard").classList.remove("hidden");
    const status = (p && p.status) || (f && f.status === "drafted" ? "proposed" : f && f.status);
    const rows = [];
    if (p) {
      rows.push(`<dl class="kv">
        <dt>Account</dt><dd>${esc(p.account || "")}</dd>
        ${p.stage ? `<dt>Stage</dt><dd>${esc(p.stage)}</dd>` : ""}
        ${p.value_inr != null ? `<dt>Value</dt><dd>₹${esc(Number(p.value_inr).toLocaleString("en-IN"))}</dd>` : ""}
        ${p.next_step ? `<dt>Next step</dt><dd>${esc(p.next_step)}</dd>` : ""}
        ${p.next_date ? `<dt>Due</dt><dd>${esc(p.next_date)}</dd>` : ""}
      </dl>`);
    }
    if (f && (f.subject || f.body)) {
      rows.push(`<div class="section-label">Follow-up draft${f.to ? ` to ${esc(f.to)}` : ""}</div>
        <div style="background:#F8FAFC;border-radius:12px;padding:.7rem .8rem;font-size:.9rem">
          ${f.subject ? `<b>${esc(f.subject)}</b><br>` : ""}<span style="white-space:pre-wrap">${N.renderRedactions(f.body || "")}</span></div>`);
    }
    const perm = d.permissions || {};
    if ((status === "proposed" || status === "drafted") && !perm.approve) {
      rows.push(`<div class="alert info" style="margin-top:.8rem">${esc(perm.approve_reason || "Waiting for a manager to approve.")}</div>`);
    } else if (status === "proposed" || status === "drafted") {
      rows.push(`<div class="row" style="margin-top:.8rem">
        <button class="btn secondary" id="rejectBtn">Reject</button>
        <button class="btn ok" id="approveBtn">✅ Approve &amp; save to CRM</button></div>
        <div class="muted" style="font-size:.78rem;margin-top:.4rem">Nothing changes in the CRM and nothing goes to the customer until a person approves.</div>`);
    } else if (status === "approved" || status === "sent") {
      rows.push(`<div class="alert ok" style="margin-top:.8rem">✅ Approved${p && p.approved_by ? ` by ${esc(p.approved_by)}` : ""}${p && p.self_approved ? " (self-approved by the rep)" : ""}, saved to CRM, audit logged</div>`);
    } else if (status === "rejected") {
      const by = (p && p.rejected_by) || (f && f.rejected_by);
      rows.push(`<div class="alert info" style="margin-top:.8rem">Rejected${by ? ` by ${esc(by)}` : ""}. Nothing was saved.</div>`);
    }
    $("proposal").innerHTML = rows.join("");
    const ab = $("approveBtn"), rb = $("rejectBtn");
    if (ab) ab.addEventListener("click", approve);
    if (rb) rb.addEventListener("click", reject);
  }

  async function approve() {
    $("approveBtn").disabled = true;
    try {
      await N.api(`/api/visits/${encodeURIComponent(callId)}/approve`, { method: "POST", body: { crm: true, followup: true } });
      N.toast("Approved: CRM updated and audit logged");
      refreshSmall();
    } catch (e) {
      $("approveBtn").disabled = false;
      N.toast(`Approve failed: ${e.message}`, 4000);
    }
  }

  async function reject() {
    try {
      await N.api(`/api/visits/${encodeURIComponent(callId)}/reject`, { method: "POST", body: {} });
      N.toast("Rejected: nothing saved");
      refreshSmall();
    } catch (e) {
      N.toast(`Reject failed: ${e.message}`, 3500);
    }
  }

  async function refreshSmall() {
    try {
      const d = await N.api(`/api/visits/${encodeURIComponent(callId)}`);
      renderProposal(d);
      renderAudit(d);
    } catch (e) { /* ignore */ }
  }

  function renderTranscript(d) {
    const tr = d.transcript || {};
    const segs = tr.segments || [];
    $("trMeta").textContent = segs.length ? `${segs.length} segments · ${tr.engine || ""} ${tr.model || ""}${tr.diarized ? " · diarized" : ""}` : "";
    const speakers = {};
    segs.forEach((s) => { if (s.speaker_label) speakers[s.speaker_label] = { name: s.speaker_name || s.speaker_label, side: s.side }; });
    $("trLegend").innerHTML = Object.keys(speakers).map((k) => {
      const sp = speakers[k];
      const col = sp.side === "us" ? "var(--brand)" : sp.side === "them" ? "var(--them)" : "#94A3B8";
      return `<span><i style="background:${col}"></i>${esc(sp.name)}</span>`;
    }).join("");
    if (!segs.length) { $("transcript").innerHTML = '<div class="muted">Transcript not ready yet.</div>'; return; }
    $("transcript").innerHTML = segs.map((s) => {
      const side = s.side === "us" ? "us" : s.side === "them" ? "them" : "other";
      return `<div class="bubble ${side}" id="seg-${esc(s.i)}">
        <div class="who">${esc(s.speaker_name || s.speaker_label || "Speaker")}<span class="ts">${esc(N.fmtDuration(s.start))} · #${esc(s.i)}</span></div>
        <div>${N.renderRedactions(s.text)}</div></div>`;
    }).join("");
  }

  function renderNotes(md) {
    if (!md) { $("notes").innerHTML = '<div class="muted">Notes appear after analysis.</div>'; return; }
    const lines = String(md).split(/\r?\n/);
    let html = "", inList = false;
    const inline = (t) => N.renderRedactions(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<i>$2</i>");
    lines.forEach((ln) => {
      const t = ln.trim();
      if (/^[-*•]\s+/.test(t)) {
        if (!inList) { html += "<ul style='margin:.2rem 0 .6rem;padding-left:1.2rem'>"; inList = true; }
        html += `<li>${inline(t.replace(/^[-*•]\s+/, ""))}</li>`;
        return;
      }
      if (inList) { html += "</ul>"; inList = false; }
      if (!t) return;
      const h = t.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        const lvl = Math.min(4, h[1].length + 1);
        html += `<h${lvl} style="margin:.8rem 0 .3rem">${inline(h[2])}</h${lvl}>`;
      } else {
        html += `<p style="margin:.2rem 0 .5rem">${inline(t)}</p>`;
      }
    });
    if (inList) html += "</ul>";
    $("notes").innerHTML = html;
  }

  function renderConsent(d) {
    const c = d.consent;
    if (!c) { $("consent").innerHTML = "<dt>Consent</dt><dd>Not on file</dd>"; return; }
    const methods = { verbal: "Verbal, on tape", "rep-confirmed": "Agreed before recording (rep confirmed)", written: "Written" };
    $("consent").innerHTML = `
      <dt>Method</dt><dd>${esc(methods[c.method] || c.method || "")}</dd>
      <dt>Confirmed by</dt><dd>${esc(c.confirmed_by || "")}</dd>
      ${c.subject ? `<dt>Customer</dt><dd>${esc(c.subject)}</dd>` : ""}
      <dt>When</dt><dd>${esc(N.fmtDate(c.recorded_at))}</dd>
      <dt>Verified</dt><dd>${c.verified === true
        ? `✅ Customer's yes found on the recording${c.verified_segment != null ? ` (segment #${esc(c.verified_segment)})` : ""}`
        : c.verified === false
          ? (c.review ? `Reviewed and confirmed by ${esc(c.review.confirmed_by)}` : "⚠️ Not found on the recording: waiting for manager review")
          : `Attested by the rep (not checkable on tape)${c.verified_segment != null ? `; a spoken yes was also found (#${esc(c.verified_segment)})` : ""}`}</dd>
      <dt>Purpose</dt><dd style="font-size:.82rem">${esc(c.purpose || "")}</dd>`;
    const counts = (d.redactions && d.redactions.counts) || {};
    const keys = Object.keys(counts);
    $("redactions").innerHTML = keys.length
      ? `<div class="muted" style="font-size:.82rem;margin-bottom:.3rem">Removed before any AI read the transcript:</div><div class="chips">${keys.map((k) => `<span class="redact">🔒 ${esc(k.toLowerCase())} × ${esc(counts[k])}</span>`).join("")}</div>`
      : `<div class="muted" style="font-size:.82rem">PII scan: nothing to redact.</div>`;
  }

  function renderAudit(d) {
    const ev = d.audit || [];
    $("auditCount").textContent = ev.length ? `(${ev.length} events)` : "";
    $("audit").innerHTML = ev.length ? ev.map((e) => {
      const det = e.detail ? Object.entries(e.detail).map(([k, v]) => `${k}=${v}`).join(", ") : "";
      return `<div class="audit-row"><span class="mono muted">${esc(N.fmtDate(e.ts))}</span><b>${esc(e.actor || "")}</b>
        <span><span class="mono">${esc(e.action || "")}</span> <span class="muted">${esc(det)}</span></span></div>`;
    }).join("") : '<div class="muted">No events.</div>';
  }

  async function erase() {
    if (!confirm("Erase this visit? The recording, transcript, notes and scores are deleted permanently. Only an audit tombstone remains.")) return;
    try {
      await N.api(`/api/visits/${encodeURIComponent(callId)}/erase`, { method: "POST", body: {} });
      N.toast("Visit erased");
      setTimeout(() => { location.href = user && user.role !== "rep" ? "/dashboard" : "/"; }, 900);
    } catch (e) {
      N.toast(`Erase failed: ${e.message}`, 4000);
    }
  }

  init();
})();
