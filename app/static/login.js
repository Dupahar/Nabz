/* Nabz: login page. Pick a person (demo mode lists names and roles) and enter the PIN. */
(function () {
  "use strict";
  const { api, esc, initials, mountFooter, PULSE_SVG } = window.Nabz;

  document.getElementById("mark").innerHTML = PULSE_SVG.replace('width="20" height="20"', 'width="30" height="30"');
  mountFooter();

  const ROLE_TEXT = { rep: "Field rep", manager: "Sales manager", admin: "Admin / compliance" };
  let chosen = null;

  async function load() {
    const people = document.getElementById("people");
    try {
      const opts = await api("/api/login-options", { noRedirect: true });
      if (!opts.demo_mode || !(opts.people || []).length) {
        people.innerHTML = '<div class="empty">Sign-in is managed by your company (SSO). Demo mode is off.</div>';
        return;
      }
      document.getElementById("demoNote").textContent = "Demo mode: the demo PIN is shown in the README.";
      people.innerHTML = opts.people.map((p) => `
        <button class="person" type="button" data-handle="${esc(p.handle)}" data-name="${esc(p.name)}" data-role="${esc(p.role)}">
          <span class="avatar" aria-hidden="true">${esc(initials(p.name))}</span>
          <span><span class="n">${esc(p.name)}</span><br>
            <span class="role-pill ${esc(p.role)}">${esc(p.role)}</span>
            <span class="r">${esc(ROLE_TEXT[p.role] || "")}</span></span>
        </button>`).join("");
      people.querySelectorAll(".person").forEach((b) => b.addEventListener("click", () => choose(b)));
    } catch (e) {
      people.innerHTML = "";
      document.getElementById("err").innerHTML = `<div class="alert error">${esc(e.message)}</div>`;
    }
  }

  function choose(btn) {
    chosen = { handle: btn.dataset.handle, role: btn.dataset.role };
    document.getElementById("pinWho").textContent = btn.dataset.name;
    document.getElementById("people").classList.add("hidden");
    document.getElementById("pinForm").classList.remove("hidden");
    document.getElementById("err").innerHTML = "";
    const pin = document.getElementById("pin");
    pin.value = "";
    pin.focus();
  }

  document.getElementById("pinCancel").addEventListener("click", () => {
    chosen = null;
    document.getElementById("pinForm").classList.add("hidden");
    document.getElementById("people").classList.remove("hidden");
  });

  document.getElementById("pinForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!chosen) return;
    const pin = document.getElementById("pin").value.trim();
    try {
      const user = await api("/api/login", { method: "POST", body: { handle: chosen.handle, pin }, noRedirect: true });
      location.href = user && user.role !== "rep" ? "/dashboard" : "/";
    } catch (err) {
      document.getElementById("err").innerHTML = `<div class="alert error">${esc(err.message)}</div>`;
      document.getElementById("pin").select();
    }
  });

  load();
})();
