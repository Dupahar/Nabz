/* Nabz: login page (demo: pick a team member). */
(function () {
  "use strict";
  const { api, esc, initials, mountFooter, PULSE_SVG } = window.Nabz;

  document.getElementById("mark").innerHTML = PULSE_SVG.replace('width="20" height="20"', 'width="30" height="30"');
  mountFooter();

  const ROLE_TEXT = { rep: "Field rep", manager: "Sales manager", admin: "Admin / compliance" };

  async function load() {
    const people = document.getElementById("people");
    try {
      const cfg = await api("/api/config", { noRedirect: true });
      document.getElementById("company").textContent = cfg.company || "";
      const team = cfg.team || [];
      if (!team.length) {
        people.innerHTML = '<div class="empty">No team in config/workspace.yaml yet.</div>';
        return;
      }
      people.innerHTML = team.map((p) => `
        <button class="person" data-handle="${esc(p.handle)}" data-role="${esc(p.role)}">
          <span class="avatar">${esc(initials(p.name))}</span>
          <span><span class="n">${esc(p.name)}</span><br>
            <span class="role-pill ${esc(p.role)}">${esc(p.role)}</span>
            <span class="r">${esc(ROLE_TEXT[p.role] || "")} · ${esc(p.region || "")}</span></span>
        </button>`).join("");
      people.querySelectorAll(".person").forEach((b) => b.addEventListener("click", () => login(b.dataset.handle)));
    } catch (e) {
      people.innerHTML = "";
      document.getElementById("err").innerHTML = `<div class="alert error">${esc(e.message)}</div>`;
    }
  }

  async function login(handle) {
    try {
      const user = await api("/api/login", { method: "POST", body: { handle }, noRedirect: true });
      location.href = user && user.role !== "rep" ? "/dashboard" : "/";
    } catch (e) {
      document.getElementById("err").innerHTML = `<div class="alert error">Sign-in failed: ${esc(e.message)}</div>`;
    }
  }

  load();
})();
