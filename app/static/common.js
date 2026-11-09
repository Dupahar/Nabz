/* Nabz: shared helpers for every page (no build step, no framework). */
(function () {
  "use strict";

  const PULSE_SVG =
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12h4l2.5-6 4 12 3-8 1.5 2H22"/></svg>';

  const STATUS = {
    queued: { label: "Queued", cls: "", pulse: true },
    transcribing: { label: "Transcribing", cls: "brand", pulse: true },
    analysing: { label: "Analysing", cls: "brand", pulse: true },
    voicing: { label: "Voice debrief", cls: "brand", pulse: true },
    done: { label: "Ready", cls: "ok", pulse: false },
    error: { label: "Error", cls: "bad", pulse: false },
  };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  async function api(path, opts) {
    opts = opts || {};
    const init = { method: opts.method || "GET", credentials: "same-origin", headers: {} };
    if (opts.body !== undefined) {
      if (opts.body instanceof FormData) {
        init.body = opts.body;
      } else {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(opts.body);
      }
    }
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      throw new Error("Can't reach the Nabz server. Is it running?");
    }
    if (res.status === 401 && !opts.noRedirect) {
      if (!location.pathname.startsWith("/login")) location.href = "/login";
      throw new Error("login");
    }
    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("application/json") ? await res.json().catch(() => null) : await res.text();
    if (!res.ok) {
      const msg = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
      const err = new Error(msg || "Request failed");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function initials(name) {
    return String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
  }

  function fmtDuration(sec) {
    sec = Math.max(0, Math.round(Number(sec) || 0));
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    const mm = String(m).padStart(h ? 2 : 1, "0"), ss = String(s).padStart(2, "0");
    return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  }

  function fmtDate(iso, withTime) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return String(iso);
    const opts = { day: "numeric", month: "short" };
    if (withTime !== false) { opts.hour = "2-digit"; opts.minute = "2-digit"; }
    return d.toLocaleString("en-IN", opts);
  }

  function timeAgo(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const s = (Date.now() - d.getTime()) / 1000;
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    return fmtDate(iso, false);
  }

  function pct(x, digits) {
    if (x == null || isNaN(x)) return "–";
    return `${(Number(x) * 100).toFixed(digits == null ? 0 : digits)}%`;
  }

  function scoreClass(score) {
    if (score == null) return "";
    return score >= 65 ? "hi" : score >= 40 ? "mid" : "lo";
  }

  function statusChip(status, stage) {
    const st = STATUS[status] || { label: status || "Unknown", cls: "", pulse: false };
    const title = stage ? ` title="${esc(stage)}"` : "";
    return `<span class="chip ${st.cls} ${st.pulse ? "pulse" : ""}"${title}><span class="dot"></span>${esc(st.label)}</span>`;
  }

  function scoreBadge(score) {
    if (score == null) return "";
    return `<span class="score-badge ${scoreClass(score)}">${esc(score)}</span>`;
  }

  /** Replace [PHONE], [AADHAAR], ... with grey "redacted" pills. Input is plain text, output is HTML. */
  function renderRedactions(text) {
    return esc(text).replace(/\[([A-Z_]{2,12})\]/g, (m, kind) => {
      const label = kind.toLowerCase().replace(/_/g, " ");
      return `<span class="redact" title="Removed before any AI read it">🔒 ${esc(label)} redacted</span>`;
    });
  }

  function toast(msg, ms) {
    const el = document.createElement("div");
    el.className = "toast fade-in";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms || 2600);
  }

  let mePromise = null;
  function me() {
    if (!mePromise) mePromise = api("/api/me");
    return mePromise;
  }
  let cfgPromise = null;
  function config() {
    if (!cfgPromise) cfgPromise = api("/api/config");
    return cfgPromise;
  }

  /** Render the top bar into #topbar. `active` is "rep" | "dashboard" | "visit". */
  async function mountTopbar(active) {
    const host = document.getElementById("topbar");
    if (!host) return null;
    host.className = "topbar";
    host.innerHTML = `
      <a class="brand" href="/">
        <span class="brand-mark">${PULSE_SVG}</span>
        <span><span class="brand-name">Nabz</span><span class="brand-tag">the pulse of every field conversation</span></span>
      </a>
      <nav class="nav" id="nav"></nav>
      <div class="spacer"></div>
      <div class="userbox" id="userbox"></div>`;
    let user = null;
    try {
      user = await me();
    } catch (e) {
      return null;
    }
    const nav = document.getElementById("nav");
    const links = [{ id: "rep", href: "/", label: user.role === "rep" ? "My visits" : "Record" }];
    if (user.role !== "rep") links.push({ id: "dashboard", href: "/dashboard", label: "Market intelligence" });
    nav.innerHTML = links.map((l) => `<a href="${l.href}" class="${l.id === active ? "active" : ""}">${esc(l.label)}</a>`).join("");
    document.getElementById("userbox").innerHTML = `
      <span class="avatar">${esc(initials(user.name))}</span>
      <span class="uname"><b>${esc(user.name)}</b><br><span class="role-pill ${esc(user.role)}">${esc(user.role)}</span>
        <span class="muted" style="font-size:.78rem">${esc(user.region || "")}</span></span>
      <button class="btn ghost sm" id="logoutBtn" title="Switch user">Switch user</button>`;
    document.getElementById("logoutBtn").addEventListener("click", async () => {
      try { await api("/api/logout", { method: "POST", noRedirect: true }); } catch (e) { /* ignore */ }
      location.href = "/login";
    });
    return user;
  }

  function mountFooter() {
    const f = document.getElementById("footer");
    if (!f) return;
    f.className = "footer";
    f.innerHTML = `Speech by <b>Gnani AI Prisma</b> · Voice by <b>Gnani Timbre</b> · Analysis by <b>Claude</b><br>
      Consent-first · PII redacted before AI · Every judgement quote-verified · Tamper-evident audit log`;
  }

  window.Nabz = {
    api, esc, me, config, initials, fmtDuration, fmtDate, timeAgo, pct, scoreClass, statusChip, scoreBadge,
    renderRedactions, toast, mountTopbar, mountFooter, STATUS, PULSE_SVG,
  };
})();
