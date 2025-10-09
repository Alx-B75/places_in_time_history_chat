(function () {
  const $ = (s) => document.querySelector(s);

  const state = {
    userToken: sessionStorage.getItem("user_token") || null,
    adminToken: sessionStorage.getItem("admin_token") || null,
    password: null, // only set if we prompt
  };

  function parseJwt(token) {
    try {
      const payload = token.split(".")[1];
      const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(decodeURIComponent(escape(json)));
    } catch { return null; }
  }
  function validToken(tok, scope) {
    const p = parseJwt(tok);
    return p && p.scope === scope && p.exp && p.exp * 1000 > Date.now() + 10_000;
  }

  async function fetchJSON(path, opts = {}, requireAdmin = true) {
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const tok = requireAdmin ? state.adminToken : state.userToken;
    if (tok) headers["Authorization"] = `Bearer ${tok}`;

    let res = await fetch(path, { ...opts, headers });
    if ((res.status === 401 || res.status === 403) && requireAdmin) {
      const ok = await interactiveLoginAndStepUp();
      if (ok) {
        const headers2 = { ...headers, Authorization: `Bearer ${state.adminToken}` };
        res = await fetch(path, { ...opts, headers: headers2 });
      }
    }
    if (res.status === 204) return { ok: true, status: 204 };
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || res.statusText || "Request failed");
    return data;
  }

  const API = {
    listFigures: () => fetchJSON("/admin/figures"),
  };

  const dom = {
    tbody: $("#tbody"),
    status: $("#status"),
    refreshBtn: $("#refreshBtn"),
  };

  function escapeHTML(s) {
    return (s || "")
      .replaceAll("&","&amp;").replaceAll("<","&lt;")
      .replaceAll(">","&gt;").replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }

  async function interactiveLoginAndStepUp() {
    const email = prompt("Admin email:") || "";
    const pw = prompt("Password:") || "";
    if (!email || !pw) return false;
    // login
    const login = await fetchJSON("/auth/login", {
      method: "POST", body: JSON.stringify({ username: email, password: pw })
    }, /*requireAdmin*/ false);
    if (!login?.access_token) return false;
    state.userToken = login.access_token;
    sessionStorage.setItem("user_token", state.userToken);
    state.password = pw;
    // step up
    const r = await fetch("/auth/admin/stepup", {
      method: "POST",
      headers: { Authorization: `Bearer ${state.userToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw })
    }).then(r => r.json());
    if (!r?.admin_access_token) return false;
    state.adminToken = r.admin_access_token;
    sessionStorage.setItem("admin_token", state.adminToken);
    return true;
  }

  async function load() {
    dom.status.textContent = "Loading…";
    dom.tbody.innerHTML = "";
    const rows = await API.listFigures();
    dom.status.textContent = `${rows.length} figures`;
    for (const f of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${f.id}</td>
        <td>${escapeHTML(f.name || "")}</td>
        <td>${escapeHTML(f.slug || "")}</td>
        <td>${escapeHTML(f.era || "")}</td>
        <td class="muted">${escapeHTML(f.short_summary || "")}</td>
        <td>
          <a class="btn" href="/admin/figure-ui/${encodeURIComponent(f.slug)}">Edit</a>
        </td>
      `;
      dom.tbody.appendChild(tr);
    }
  }

  dom.refreshBtn.addEventListener("click", () => load().catch(e => alert(e.message)));

  // boot
  (async () => {
    if (!validToken(state.adminToken, "admin")) {
      await interactiveLoginAndStepUp();
    }
    try { await load(); } catch (e) { alert(e.message); }
  })();
})();
