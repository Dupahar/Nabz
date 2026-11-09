/* Nabz: rep app (record a visit with consent, upload, list my visits). */
(function () {
  "use strict";
  const N = window.Nabz;
  const $ = (id) => document.getElementById(id);

  let user = null;
  let mediaRecorder = null;
  let chunks = [];
  let stream = null;
  let audioCtx = null;
  let meterRaf = null;
  let timerInt = null;
  let startedAt = 0;
  let blob = null;          // the recording or chosen file to upload
  let blobName = "visit.webm";
  let pollTimer = null;

  // ------------------------------------------------------------------ setup
  async function init() {
    N.mountFooter();
    user = await N.mountTopbar("rep");
    if (!user) return;
    $("hello").textContent = `Namaste, ${user.name.split(" ")[0]} 👋`;
    $("region").value = user.region && user.region !== "All" ? user.region : "";
    if (user.role !== "rep") {
      $("listTitle").textContent = "Recent visits (team)";
    }
    try {
      const cfg = await N.config();
      $("segment").innerHTML = (cfg.segments || ["Other"]).map((s) => `<option>${N.esc(s)}</option>`).join("");
    } catch (e) {
      $("segment").innerHTML = "<option>Other</option>";
    }
    $("consentOk").addEventListener("change", updateRecordable);
    $("account").addEventListener("input", updateRecordable);
    $("recBtn").addEventListener("click", toggleRecording);
    $("discardBtn").addEventListener("click", discard);
    $("uploadBtn").addEventListener("click", upload);
    $("fileInput").addEventListener("change", onFile);
    updateRecordable();
    loadVisits();
  }

  function consentOk() { return $("consentOk").checked; }

  function updateRecordable() {
    const ok = consentOk();
    const recording = mediaRecorder && mediaRecorder.state === "recording";
    $("recBtn").disabled = !ok && !recording;
    $("fileLabel").classList.toggle("disabled", !ok);
    $("fileLabel").style.opacity = ok ? "1" : ".5";
    $("fileLabel").style.pointerEvents = ok ? "auto" : "none";
    if (!recording) {
      $("recState").textContent = ok ? "Ready" : "Waiting for consent";
      $("recHint").textContent = ok
        ? (consentMethod() === "verbal"
          ? 'Tap to start. Begin by asking: "Record kar loon? Training ke liye hai."'
          : "Tap to start recording. Tap again to stop.")
        : 'Tick "Customer agreed" to start. Keep the phone on the counter, not in a pocket.';
    }
  }

  function consentMethod() {
    const r = document.querySelector('input[name="cmethod"]:checked');
    return r ? r.value : "verbal";
  }

  function msg(html, kind) {
    $("msg").innerHTML = html ? `<div class="alert ${kind || "info"} fade-in">${html}</div>` : "";
  }

  // ------------------------------------------------------------------ recording
  async function toggleRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }
    if (!consentOk()) return;
    msg("");
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      msg("This browser can't record audio. Use \"Choose audio file\" below, or open Nabz in Chrome.", "error");
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true } });
    } catch (e) {
      msg("Microphone permission was denied. Allow the mic for this site, or upload a file instead.", "error");
      return;
    }
    const types = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"];
    const mime = types.find((t) => window.MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t)) || "";
    try {
      mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    } catch (e) {
      mediaRecorder = new MediaRecorder(stream);
    }
    chunks = [];
    mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    mediaRecorder.onstop = onStopped;
    mediaRecorder.start(1000);
    startedAt = Date.now();
    $("recBtn").classList.add("recording");
    $("recBtn").setAttribute("aria-label", "Stop recording");
    $("recIcon").innerHTML = '<rect x="6" y="6" width="12" height="12" rx="2" fill="#fff" stroke="none"/>';
    $("recState").innerHTML = '<span class="chip them pulse"><span class="dot"></span>Recording</span>';
    $("recHint").textContent = "Recording… tap to stop.";
    $("preview").classList.add("hidden");
    timerInt = setInterval(() => { $("timer").textContent = N.fmtDuration((Date.now() - startedAt) / 1000); }, 250);
    startMeter(stream);
  }

  let peakRms = 0;
  function startMeter(s) {
    peakRms = 0;
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const src = audioCtx.createMediaStreamSource(s);
      const an = audioCtx.createAnalyser();
      an.fftSize = 512;
      src.connect(an);
      const buf = new Uint8Array(an.fftSize);
      const loop = () => {
        an.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
        const rms = Math.sqrt(sum / buf.length);
        peakRms = Math.max(peakRms, rms);
        $("level").style.width = Math.min(100, Math.round(rms * 320)) + "%";
        meterRaf = requestAnimationFrame(loop);
      };
      loop();
    } catch (e) { /* the meter is cosmetic */ }
  }

  function stopMeter() {
    if (meterRaf) cancelAnimationFrame(meterRaf);
    meterRaf = null;
    if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
    $("level").style.width = "0%";
  }

  function onStopped() {
    clearInterval(timerInt);
    stopMeter();
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
    const type = (mediaRecorder && mediaRecorder.mimeType) || "audio/webm";
    blob = new Blob(chunks, { type });
    const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
    const acct = ($("account").value || "visit").trim().replace(/[^\w-]+/g, "-").slice(0, 30) || "visit";
    blobName = `${acct}.${ext}`;
    $("recBtn").classList.remove("recording");
    $("recIcon").innerHTML = '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="17" x2="12" y2="22"/>';
    const secs = (Date.now() - startedAt) / 1000;
    showPreview(`${N.fmtDuration(secs)} recorded · ${(blob.size / 1024).toFixed(0)} KB`);
    updateRecordable();
    if (secs < 5) {
      msg("That recording is under 5 seconds. Record the whole conversation, then tap stop.", "error");
      $("uploadBtn").disabled = true;
    } else if (peakRms < 0.02) {
      msg("We didn't hear anything. Check the microphone isn't muted, and that the browser is using the right mic, then record again.", "error");
    }
  }

  function onFile(e) {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    if (!consentOk()) {
      msg('Tick "Customer agreed" first: Nabz never processes a recording without consent.', "error");
      e.target.value = "";
      return;
    }
    blob = f;
    blobName = f.name;
    showPreview(`${N.esc(f.name)} · ${(f.size / 1024 / 1024).toFixed(2)} MB`);
  }

  function showPreview(meta) {
    const a = $("previewAudio");
    if (a.dataset.url) URL.revokeObjectURL(a.dataset.url);
    const url = URL.createObjectURL(blob);
    a.src = url;
    a.dataset.url = url;
    $("previewMeta").innerHTML = meta;
    $("preview").classList.remove("hidden");
    $("uploadProg").classList.add("hidden");
    $("uploadBtn").disabled = false;
    $("recState").textContent = "Ready to upload";
  }

  function discard() {
    blob = null;
    $("preview").classList.add("hidden");
    $("fileInput").value = "";
    $("timer").textContent = "0:00";
    msg("");
    updateRecordable();
  }

  // ------------------------------------------------------------------ upload
  function upload() {
    if (!blob) return;
    const account = $("account").value.trim();
    if (!account) { msg("Add the account (shop) name first.", "error"); $("account").focus(); return; }
    if (!consentOk()) { msg('Consent is required: tick "Customer agreed".', "error"); return; }
    const fd = new FormData();
    fd.append("audio", blob, blobName);
    fd.append("account", account);
    fd.append("contact", $("contact").value.trim());
    fd.append("segment", $("segment").value);
    fd.append("region", $("region").value.trim());
    fd.append("consent_method", consentMethod());
    fd.append("consent_confirmed", "true");

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/visits");
    xhr.withCredentials = true;
    $("uploadProg").classList.remove("hidden");
    $("uploadBtn").disabled = true;
    $("discardBtn").disabled = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) $("uploadBar").style.width = Math.round((e.loaded / e.total) * 100) + "%";
    };
    xhr.onload = () => {
      $("discardBtn").disabled = false;
      if (xhr.status === 401) { location.href = "/login"; return; }
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300 && data && data.call_id) {
        $("uploadBar").style.width = "100%";
        msg(`✅ Uploaded. Nabz is processing it now. <a href="/visit/${encodeURIComponent(data.call_id)}">Open visit →</a>`, "ok");
        blob = null;
        $("preview").classList.add("hidden");
        $("fileInput").value = "";
        $("timer").textContent = "0:00";
        $("consentOk").checked = false;
        updateRecordable();
        loadVisits();
      } else {
        $("uploadBtn").disabled = false;
        const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : xhr.statusText;
        msg(`Upload failed: ${N.esc(detail || "unknown error")}`, "error");
      }
    };
    xhr.onerror = () => {
      $("uploadBtn").disabled = false;
      $("discardBtn").disabled = false;
      msg("Upload failed: can't reach the server. Your recording is still here; try again.", "error");
    };
    xhr.send(fd);
  }

  // ------------------------------------------------------------------ list
  async function loadVisits() {
    clearTimeout(pollTimer);
    const host = $("visits");
    let visits = [];
    try {
      const scope = user && user.role === "rep" ? "mine" : "all";
      visits = await N.api(`/api/visits?scope=${scope}&limit=30`);
    } catch (e) {
      if (e.message !== "login") host.innerHTML = `<div class="alert error">${N.esc(e.message)}</div>`;
      return;
    }
    if (!Array.isArray(visits) || !visits.length) {
      host.innerHTML = '<div class="empty"><span class="big">🎙️</span>No visits yet. Record your first one above.</div>';
      $("listMeta").textContent = "";
      return;
    }
    $("listMeta").textContent = `${visits.length} visit${visits.length > 1 ? "s" : ""}`;
    host.innerHTML = visits.map((v) => {
      const done = v.status === "done";
      const right = done && v.score != null ? N.scoreBadge(v.score) : N.statusChip(v.status, v.stage);
      const sub = [v.segment, v.region, N.timeAgo(v.recorded_at)].filter(Boolean).map(N.esc).join(" · ");
      const extra = done
        ? `${v.lens_name ? `<span class="chip brand">${N.esc(v.lens_name)}</span>` : ""}${v.debrief ? ' <span class="chip" title="Voice debrief ready">🎙️ debrief</span>' : ""}${v.flags ? ` <span class="chip bad">🚩 ${N.esc(v.flags)}</span>` : ""}`
        : `<span class="muted" style="font-size:.78rem">${N.esc(v.stage || "")}</span>`;
      const who = user && user.role !== "rep" && v.rep ? ` · ${N.esc(v.rep)}` : "";
      return `<a class="list-item fade-in" href="/visit/${encodeURIComponent(v.call_id)}">
        <div class="main">
          <div class="title">${N.esc(v.account || v.call_id)}${v.contact ? ` <span class="muted" style="font-weight:500">· ${N.esc(v.contact)}</span>` : ""}</div>
          <div class="meta">${sub}${who}</div>
          <div style="margin-top:.3rem">${extra}</div>
        </div>${right}</a>`;
    }).join("");
    if (visits.some((v) => v.status !== "done" && v.status !== "error")) {
      pollTimer = setTimeout(loadVisits, 3000);
    }
  }

  init();
})();
