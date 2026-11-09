/* Nabz: market intelligence + team dashboard (managers and admins). */
(function () {
  "use strict";
  const N = window.Nabz;
  const $ = (id) => document.getElementById(id);
  const esc = N.esc;

  const BRAND = "#4F46E5", THEM = "#F97316", OK = "#059669", MUTED = "#94A3B8";
  // Categorical palette for regions: brand first, then distinct, colour-blind-friendlier hues.
  const PALETTE = ["#4F46E5", "#0EA5E9", "#10B981", "#A855F7", "#EAB308", "#64748B", "#EC4899", "#14B8A6"];
  const SIGNAL_LABEL = {
    demand: "Demand", competitor: "Competitor", price: "Price", product_feedback: "Product feedback",
    availability: "Availability", scheme: "Scheme", other: "Other",
  };

  const charts = {};
  let intel = null;
  let vocFilter = "all";

  async function init() {
    N.mountFooter();
    const user = await N.mountTopbar("dashboard");
    if (!user) return;
    if (user.role === "rep") {
      $("dash").classList.add("hidden");
      $("denied").classList.remove("hidden");
      document.querySelector(".filters").classList.add("hidden");
      return;
    }
    try {
      const cfg = await N.config();
      $("sub").textContent = `${cfg.company || ""}: what the market is telling your field team, from every in-person conversation.`;
    } catch (e) { /* optional */ }
    if (window.Chart) {
      Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
      Chart.defaults.font.size = 12;
      Chart.defaults.color = "#334155";
      Chart.defaults.plugins.legend.labels.boxWidth = 10;
      Chart.defaults.plugins.legend.labels.boxHeight = 10;
    }
    ["fDays", "fRegion", "fSegment"].forEach((id) => $(id).addEventListener("change", load));
    load();
    loadTrust();
  }

  function q() {
    const p = new URLSearchParams({ days: $("fDays").value, region: $("fRegion").value, segment: $("fSegment").value });
    return p.toString();
  }

  async function load() {
    $("err").innerHTML = "";
    try {
      intel = await N.api(`/api/intel?${q()}`);
    } catch (e) {
      if (e.status === 403) { $("dash").classList.add("hidden"); $("denied").classList.remove("hidden"); return; }
      if (e.message !== "login") $("err").innerHTML = `<div class="alert error">${esc(e.message)}</div>`;
      return;
    }
    fillFilter("fRegion", intel.regions || [], "All regions");
    fillFilter("fSegment", intel.segments || [], "All segments");
    renderKpis(intel.kpis || {});
    renderCompetitors(intel.competitors || []);
    renderSignals(intel.signals_by_type || [], intel.regions || []);
    renderPrice(intel.price_sensitivity || []);
    renderConcerns(intel.concerns || []);
    renderVocTabs(intel.voice_of_customer || []);
    renderVoc();
    renderDemand(intel.demand || []);
    renderCompliance(intel.compliance || []);
    renderReps(intel.reps || []);
    renderTrend(intel.trend || []);
    loadRecent();
    loadCost();
  }

  function fillFilter(id, values, allLabel) {
    const sel = $(id);
    const cur = sel.value;
    const opts = [`<option value="All">${esc(allLabel)}</option>`].concat(values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`));
    sel.innerHTML = opts.join("");
    sel.value = values.includes(cur) ? cur : "All";
  }

  // ------------------------------------------------------------------ KPIs
  function renderKpis(k) {
    const tiles = [
      { label: "Visits", value: k.visits != null ? k.visits : 0, hint: `${k.reps || 0} reps`, cls: "accent" },
      { label: "Avg score", value: k.avg_score != null ? Math.round(k.avg_score) : "–", hint: "lens-specific score" },
      { label: "Hours of audio", value: k.hours_audio != null ? Number(k.hours_audio).toFixed(1) : "0", hint: "transcribed by Gnani Prisma" },
      { label: "Compliance flags", value: k.compliance_flags || 0, hint: "UCPMP / RBI / company rules", cls: k.compliance_flags ? "alert" : "" },
      { label: "Consent rate", value: N.pct(k.consent_rate), hint: "DPDP: no consent, no processing" },
      { label: "Quotes verified", value: N.pct(k.quotes_verified), hint: "AI claims checked in code" },
    ];
    $("kpis").innerHTML = tiles.map((t) => `
      <div class="card kpi ${t.cls || ""} fade-in"><div class="label">${esc(t.label)}</div>
        <div class="value">${esc(t.value)}</div><div class="hint">${esc(t.hint)}</div></div>`).join("");
  }

  // ------------------------------------------------------------------ charts
  function chart(id, cfg, emptyId, isEmpty) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
    const canvas = $(id);
    const box = canvas.parentElement;
    if (emptyId) $(emptyId).classList.toggle("hidden", !isEmpty);
    box.classList.toggle("hidden", !!isEmpty);
    if (isEmpty) return;
    if (!window.Chart) {
      box.innerHTML = '<div class="empty">Charts need internet (Chart.js CDN).</div>';
      return;
    }
    charts[id] = new Chart(canvas.getContext("2d"), cfg);
    // Accessibility: a text alternative for screen readers, built from the chart's own data.
    const title = (box.closest(".card") && box.closest(".card").querySelector("h2, h3")) || null;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `${title ? title.textContent.trim() + ": " : ""}${summarizeChart(cfg)}`);
  }

  function summarizeChart(cfg) {
    const labels = (cfg.data && cfg.data.labels) || [];
    return ((cfg.data && cfg.data.datasets) || []).slice(0, 4).map((ds) => {
      const pairs = labels.slice(0, 8).map((l, i) => `${l} ${ds.data[i] == null ? "–" : (typeof ds.data[i] === "number" ? Math.round(ds.data[i] * 10) / 10 : ds.data[i])}`);
      return `${ds.label ? ds.label + ": " : ""}${pairs.join(", ")}`;
    }).join("; ") || "no data";
  }

  const gridless = { grid: { display: false }, border: { display: false } };
  const lightGrid = { grid: { color: "#EEF2F7" }, border: { display: false } };

  function renderCompetitors(list) {
    const top = list.slice(0, 8);
    const regions = Array.from(new Set(top.flatMap((c) => Object.keys(c.regions || {}))));
    const datasets = regions.length
      ? regions.map((r, i) => ({ label: r, data: top.map((c) => (c.regions || {})[r] || 0), backgroundColor: PALETTE[i % PALETTE.length], borderRadius: 4, maxBarThickness: 34, stack: "s" }))
      : [{ label: "Mentions", data: top.map((c) => c.mentions), backgroundColor: THEM, borderRadius: 4 }];
    chart("cCompetitors", {
      type: "bar",
      data: { labels: top.map((c) => c.name), datasets },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        scales: { x: { ...lightGrid, stacked: true, ticks: { precision: 0 } }, y: { ...gridless, stacked: true } },
        plugins: {
          legend: { position: "bottom", display: regions.length > 1 },
          tooltip: {
            callbacks: {
              afterBody: (items) => {
                const c = top[items[0].dataIndex];
                const lines = [`${c.mentions} mentions · ${c.negative_for_us || 0} negative for us`];
                const qq = (c.quotes || [])[0];
                if (qq) lines.push(`“${String(qq.quote || qq.text || "").slice(0, 70)}” (${qq.account || ""})`);
                return lines;
              },
            },
          },
        },
      },
    }, "compEmpty", !top.length);
  }

  function renderSignals(list, regions) {
    const types = list.map((s) => s.type);
    const regs = regions.length ? regions : Array.from(new Set(list.flatMap((s) => Object.keys(s.by_region || {}))));
    const datasets = regs.length
      ? regs.map((r, i) => ({ label: r, data: list.map((s) => (s.by_region || {})[r] || 0), backgroundColor: PALETTE[i % PALETTE.length], borderRadius: 4, maxBarThickness: 34, stack: "s" }))
      : [{ label: "Signals", data: list.map((s) => s.count), backgroundColor: BRAND, borderRadius: 4 }];
    chart("cSignals", {
      type: "bar",
      data: { labels: types.map((t) => SIGNAL_LABEL[t] || t), datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { x: { ...gridless, stacked: true }, y: { ...lightGrid, stacked: true, ticks: { precision: 0 } } },
        plugins: { legend: { position: "bottom", display: regs.length > 1 } },
      },
    }, "sigEmpty", !list.length);
  }

  function renderPrice(list) {
    chart("cPrice", {
      type: "bar",
      data: {
        labels: list.map((p) => p.segment),
        datasets: [{ label: "Visits with a price concern", data: list.map((p) => Math.round((p.price_concern_rate || 0) * 100)), backgroundColor: THEM, borderRadius: 6, maxBarThickness: 42 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { x: gridless, y: { ...lightGrid, min: 0, max: 100, ticks: { callback: (v) => v + "%" } } },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${c.parsed.y}% of ${list[c.dataIndex].visits} visits` } },
        },
      },
    }, "priceEmpty", !list.length);
  }

  function renderConcerns(list) {
    chart("cConcerns", {
      type: "bar",
      data: {
        labels: list.map((c) => c.category),
        datasets: [
          { label: "Handled", data: list.map((c) => (c.count || 0) - (c.unhandled || 0)), backgroundColor: BRAND, borderRadius: 4, maxBarThickness: 34, stack: "s" },
          { label: "Not handled", data: list.map((c) => c.unhandled || 0), backgroundColor: THEM, borderRadius: 4, maxBarThickness: 34, stack: "s" },
        ],
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        scales: { x: { ...lightGrid, stacked: true, ticks: { precision: 0 } }, y: { ...gridless, stacked: true } },
        plugins: { legend: { position: "bottom" } },
      },
    }, "concEmpty", !list.length);
  }

  function renderTrend(list) {
    chart("cTrend", {
      type: "bar",
      data: {
        labels: list.map((t) => N.fmtDate(t.date, false)),
        datasets: [
          { type: "bar", label: "Visits", data: list.map((t) => t.visits), backgroundColor: "#C7D2FE", borderRadius: 4, maxBarThickness: 34, yAxisID: "y" },
          { type: "line", label: "Avg score", data: list.map((t) => t.avg_score), borderColor: BRAND, backgroundColor: BRAND, tension: .3, pointRadius: 3, yAxisID: "y1" },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          x: gridless,
          y: { ...lightGrid, position: "left", ticks: { precision: 0 }, title: { display: true, text: "visits" } },
          y1: { ...gridless, position: "right", min: 0, max: 100, title: { display: true, text: "score" } },
        },
        plugins: { legend: { position: "bottom" } },
      },
    }, "trendEmpty", !list.length);
  }

  // ------------------------------------------------------------------ voice of customer
  function renderVocTabs(items) {
    const types = Array.from(new Set(items.map((i) => i.type)));
    if (vocFilter !== "all" && !types.includes(vocFilter)) vocFilter = "all";
    const tabs = [["all", "All"]].concat(types.map((t) => [t, SIGNAL_LABEL[t] || t]));
    $("vocTabs").innerHTML = tabs.map(([k, l]) => `<button data-k="${esc(k)}" class="${k === vocFilter ? "on" : ""}">${esc(l)}</button>`).join("");
    $("vocTabs").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      vocFilter = b.dataset.k;
      $("vocTabs").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      renderVoc();
    }));
  }

  function renderVoc() {
    const items = ((intel && intel.voice_of_customer) || []).filter((i) => vocFilter === "all" || i.type === vocFilter);
    if (!items.length) {
      $("voc").innerHTML = '<div class="empty"><span class="big">🗣️</span>No customer quotes yet. They appear here as visits are analysed.</div>';
      return;
    }
    $("voc").innerHTML = items.slice(0, 60).map((i) => {
      const pol = i.polarity === "positive" ? "ok" : i.polarity === "negative" ? "bad" : "";
      const polIc = i.polarity === "positive" ? "📈" : i.polarity === "negative" ? "📉" : "•";
      return `<a class="voc-card fade-in" href="/visit/${encodeURIComponent(i.call_id)}">
        <div class="chips"><span class="chip brand">${esc(SIGNAL_LABEL[i.type] || i.type)}</span>
          <span class="chip ${pol}">${polIc} ${esc(i.polarity || "")}</span>
          ${i.product ? `<span class="chip">${esc(i.product)}</span>` : ""}
          ${i.competitor ? `<span class="chip them">vs ${esc(i.competitor)}</span>` : ""}</div>
        <div class="text">${esc(i.text || "")}</div>
        ${i.quote ? `<div class="quote-text">“${N.renderRedactions(i.quote)}”</div>` : ""}
        <div class="src">${esc([i.account, i.segment, i.region, N.timeAgo(i.recorded_at)].filter(Boolean).join(" · "))}</div>
      </a>`;
    }).join("");
  }

  function renderDemand(list) {
    if (!list.length) { $("demand").innerHTML = '<div class="muted">No product demand signals yet.</div>'; return; }
    const max = Math.max(...list.map((d) => d.count || 0), 1);
    $("demand").innerHTML = list.slice(0, 8).map((d) => {
      const pos = d.positive || 0, neg = d.negative || 0, neu = Math.max(0, (d.count || 0) - pos - neg);
      const w = (x) => `${(x / max) * 100}%`;
      return `<div style="margin-bottom:.55rem">
        <div style="display:flex;justify-content:space-between;font-size:.86rem"><b>${esc(d.product)}</b><span class="muted">${esc(d.count)} mention${d.count === 1 ? "" : "s"}</span></div>
        <div class="bar2" style="height:9px;margin-top:.2rem">
          <div style="width:${w(pos)};background:${OK}"></div><div style="width:${w(neu)};background:${MUTED}"></div><div style="width:${w(neg)};background:${THEM}"></div></div>
      </div>`;
    }).join("") + `<div class="legend"><span><i style="background:${OK}"></i>positive</span><span><i style="background:${MUTED}"></i>neutral</span><span><i style="background:${THEM}"></i>negative</span></div>`;
  }

  function renderCompliance(list) {
    $("complianceCard").classList.toggle("flags-box", list.length > 0);
    if (!list.length) { $("compliance").innerHTML = '<div class="muted">✅ No compliance flags in this period.</div>'; return; }
    $("compliance").innerHTML = list.map((f) => `
      <a class="item" style="display:block;color:inherit" href="/visit/${encodeURIComponent(f.call_id)}">
        <div class="t"><span class="chip bad">${esc(f.severity || "")}</span> ${esc(String(f.rule || "").replace(/_/g, " "))}</div>
        <div class="muted" style="font-size:.8rem">${esc(f.account || "")} · ${esc(f.rep || "")}</div>
        ${f.quote ? `<div class="quote-text" style="font-size:.85rem;font-style:italic">“${N.renderRedactions(f.quote)}”</div>` : ""}
      </a>`).join("");
  }

  function renderReps(list) {
    if (!list.length) { $("reps").innerHTML = '<tr><td><div class="empty">No rep activity yet.</div></td></tr>'; return; }
    $("reps").innerHTML = `<thead><tr><th>Rep</th><th>Region</th><th>Visits</th><th>Avg score</th><th>Talk ratio</th><th>Questions</th><th>Impl. + need-payoff</th><th>Top coaching tip</th></tr></thead>
      <tbody>${list.map((r) => {
        const spin = r.spin || {};
        const ip = (spin.implication || 0) + (spin["need-payoff"] || 0);
        const tr = r.talk_ratio != null ? Math.round(r.talk_ratio * 100) : null;
        const trCls = tr == null ? "" : tr > 65 ? "warn" : "ok";
        return `<tr>
          <td><b>${esc(r.name)}</b></td><td>${esc(r.region || "")}</td><td>${esc(r.visits)}</td>
          <td>${r.avg_score != null ? N.scoreBadge(Math.round(r.avg_score)).replace("score-badge", "score-badge sm") : "–"}</td>
          <td>${tr == null ? "–" : `<span class="chip ${trCls}">${tr}%</span>`}</td>
          <td>${r.questions != null ? esc(Number(r.questions).toFixed(1)) : "–"}</td>
          <td title="SPIN classification runs on sales-lens visits only">${Object.keys(spin).length ? esc(ip) : "–"}</td>
          <td style="max-width:320px;font-size:.84rem">${esc(r.top_tip || "")}</td></tr>`;
      }).join("")}</tbody>`;
  }

  // ------------------------------------------------------------------ side panels
  async function loadTrust() {
    try {
      const t = await N.api("/api/trust");
      const row = (ok, label, value, title) => `<div class="trust-row" ${title ? `title="${esc(title)}"` : ""}>
        <span class="ic ${ok ? "" : "bad"}">${ok ? "✓" : "!"}</span><span>${esc(label)}</span><span class="v">${value}</span></div>`;
      const ret = t.retention || {};
      $("trust").innerHTML = [
        row(t.audit_ok, "Audit chain", `${t.audit_ok ? "verified" : "BROKEN"} · ${esc(t.audit_events || 0)} events<br><span class="mono muted">${esc(String(t.audit_head || "").slice(0, 12))}</span>`,
          "SHA-256 hash chain: editing or deleting any past event breaks it"),
        row((t.consent_rate == null ? 1 : t.consent_rate) >= 1, "Consent before processing", esc(N.pct(t.consent_rate))),
        row(true, "PII redacted before AI", `${esc(t.pii_redacted || 0)} items`),
        row((t.quotes_verified == null ? 1 : t.quotes_verified) >= 0.95, "AI quotes verified", esc(N.pct(t.quotes_verified, 1))),
        row(true, "Data region", `<span style="font-size:.8rem">${esc(t.data_region || "India")}</span>`),
        row(true, "Retention", `audio ${esc(ret.audio_days != null ? ret.audio_days : "?")}d · transcripts ${esc(ret.transcripts_days != null ? ret.transcripts_days : "?")}d`),
      ].join("");
    } catch (e) {
      $("trust").innerHTML = `<div class="muted">${esc(e.status === 403 ? "Admins and managers only." : "Trust data unavailable.")}</div>`;
    }
  }

  async function loadCost() {
    try {
      const c = await N.api(`/api/cost?days=${$("fDays").value}`);
      const inr = c.inr != null ? `₹${Number(c.inr).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "set rates in workspace.yaml";
      $("cost").innerHTML = `<div class="section-label">Cost (last ${esc($("fDays").value)} days)</div>
        <div class="stat-mini">
          <div><b>${esc(Number(c.stt_minutes || 0).toFixed(1))}</b><span>Prisma min</span></div>
          <div><b>${esc(c.tts_chars || 0)}</b><span>Timbre chars</span></div>
          <div><b>${esc(Math.round((c.llm_tokens || 0) / 1000))}k</b><span>LLM tokens</span></div>
        </div><div class="muted" style="font-size:.8rem;margin-top:.4rem">Total: ${esc(inr)}</div>`;
    } catch (e) {
      $("cost").innerHTML = "";
    }
  }

  async function loadRecent() {
    try {
      const all = await N.api("/api/visits?scope=all&limit=200");
      const syn = Array.isArray(all) ? all.filter((v) => v.synthetic).length : 0;
      $("synBanner").innerHTML = syn
        ? `<div class="banner-synthetic">ℹ️ Includes <b>${esc(syn)}</b> synthetic demo visit${syn > 1 ? "s" : ""}: voices generated with Gnani Timbre or ElevenLabs from written scripts, then processed by the real pipeline (Prisma, Claude, Timbre). Real recordings carry no badge.</div>`
        : "";
      const vs = Array.isArray(all) ? all.slice(0, 15) : all;
      if (!Array.isArray(vs) || !vs.length) {
        $("recent").innerHTML = '<tr><td><div class="empty"><span class="big">🎙️</span>No visits yet. Reps record them from <a href="/">the rep app</a>.</div></td></tr>';
        $("recentMeta").textContent = "";
        return;
      }
      $("recentMeta").textContent = `${vs.length} most recent`;
      $("recent").innerHTML = `<thead><tr><th>When</th><th>Account</th><th>Rep</th><th>Segment · Region</th><th>Lens</th><th>Score</th><th>Status</th></tr></thead>
        <tbody>${vs.map((v) => `<tr class="click rowlink" tabindex="0" role="link" aria-label="Open visit: ${esc(v.account || v.call_id)}" data-id="${esc(v.call_id)}">
          <td class="muted">${esc(N.fmtDate(v.recorded_at))}</td>
          <td><b>${esc(v.account || "")}</b> ${N.syntheticBadge(v)}${v.summary ? `<div class="muted" style="font-size:.8rem;max-width:380px">${esc(String(v.summary).slice(0, 120))}${String(v.summary).length > 120 ? "…" : ""}</div>` : ""}</td>
          <td>${esc(v.rep || "")}</td><td>${esc([v.segment, v.region].filter(Boolean).join(" · "))}</td>
          <td>${v.lens_name ? `<span class="chip brand">${esc(v.lens_name)}</span>` : ""}</td>
          <td>${v.score != null ? N.scoreBadge(v.score) : ""}</td>
          <td>${N.statusChip(v.status, v.stage, v.stalled)}${v.flags ? ` <span class="chip bad">🚩 ${esc(v.flags)}</span>` : ""}</td></tr>`).join("")}</tbody>`;
      $("recent").querySelectorAll("tr.click").forEach((tr) => {
        const go = () => { location.href = `/visit/${encodeURIComponent(tr.dataset.id)}`; };
        tr.addEventListener("click", go);
        tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      });
    } catch (e) {
      $("recent").innerHTML = "";
    }
  }

  init();
})();
