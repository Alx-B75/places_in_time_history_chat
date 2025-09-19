(function () {
  const $ = (sel) => document.querySelector(sel);

  const state = {
    userToken: null,
    adminToken: null,
    password: null,
    adminRefreshTimer: null,
    autoRefresh: false,
  };

  const dom = {
    email: $("#email"),
    password: $("#password"),
    loginBtn: $("#loginBtn"),
    loginStatus: $("#loginStatus"),
    autoRefresh: $("#autoRefresh"),
    authStatus: $("#authStatus"),
    adminStatus: $("#adminStatus"),
    checkHealthBtn: $("#checkHealthBtn"),
    healthStatus: $("#healthStatus"),
    lockAdminBtn: $("#lockAdminBtn"),
    logoutBtn: $("#logoutBtn"),
    tabs: document.querySelectorAll(".tab"),
    panelUsers: $("#panel-users"),
    panelFigures: $("#panel-figures"),
    usersBody: $("#usersBody"),
    usersStatus: $("#usersStatus"),
    refreshUsers: $("#refreshUsers"),
    figuresBody: $("#figuresBody"),
    figuresStatus: $("#figuresStatus"),
    refreshFigures: $("#refreshFigures"),
    figName: $("#figName"),
    figSlug: $("#figSlug"),
    figShort: $("#figShort"),
    figLong: $("#figLong"),
    figEra: $("#figEra"),
    figImage: $("#figImage"),
    figQuote: $("#figQuote"),
    createFigureBtn: $("#createFigureBtn"),
    updateFigureBtn: $("#updateFigureBtn"),
  };

  function setAuthUI() {
    if (state.userToken) {
      dom.authStatus.textContent = "Signed in";
      dom.authStatus.classList.remove("bad");
      dom.authStatus.classList.add("good");
    } else {
      dom.authStatus.textContent = "Signed out";
      dom.authStatus.classList.add("bad");
      dom.authStatus.classList.remove("good");
    }
    if (state.adminToken) {
      dom.adminStatus.textContent = "Admin active";
      dom.adminStatus.classList.add("good");
    } else {
      dom.adminStatus.textContent = "Admin inactive";
      dom.adminStatus.classList.remove("good");
    }
    const adminReady = Boolean(state.adminToken);
    dom.tabs.forEach((t) => {
      if (adminReady) t.classList.remove("disabled");
      else t.classList.add("disabled");
    });
  }

  function parseJwt(token) {
    try {
      const payload = token.split(".")[1];
      const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(decodeURIComponent(escape(json)));
    } catch {
      return null;
    }
  }

  function scheduleAdminRefresh() {
    clearTimeout(state.adminRefreshTimer);
    if (!state.autoRefresh || !state.adminToken || !state.password || !state.userToken) return;
    const payload = parseJwt(state.adminToken);
    if (!payload || !payload.exp) return;
    const msUntilExp = payload.exp * 1000 - Date.now();
    const bufferMs = 60 * 1000;
    const wait = Math.max(5_000, msUntilExp - bufferMs);
    state.adminRefreshTimer = setTimeout(async () => {
      try { await stepUp(); } catch (e) { /* ignore; UI will reflect */ }
    }, wait);
  }

  async function fetchJSON(path, opts = {}, requireAdmin = false) {
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const token = requireAdmin ? state.adminToken : state.userToken;
    if (token) headers["Authorization"] = `Bearer ${token}`;
    let res = await fetch(path, { ...opts, headers });
    if (res.status === 401 || res.status === 403) {
      if (requireAdmin && state.userToken && state.password) {
        try {
          await stepUp();
          const headers2 = { ...headers, Authorization: `Bearer ${state.adminToken}` };
          res = await fetch(path, { ...opts, headers: headers2 });
        } catch {}
      }
    }
    if (res.status === 204) return { ok: true, status: 204 };
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data?.detail || res.statusText || "Request failed";
      throw new Error(`${res.status}: ${msg}`);
    }
    return data;
  }

  const API = {
    login: (username, password) =>
      fetchJSON("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    stepUp: (password) =>
      fetch("/auth/admin/stepup", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${state.userToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password }),
      }).then((r) => r.json()),
    health: () => fetchJSON("/admin/health", {}, true),
    listUsers: () => fetchJSON("/admin/users", {}, true),
    setUserRole: (id, role) =>
      fetchJSON(`/admin/users/${id}/role`, { method: "PATCH", body: JSON.stringify({ role }) }, true),
    listFigures: () => fetchJSON("/admin/figures", {}, true),
    createFigure: (payload) =>
      fetchJSON("/admin/figures", { method: "POST", body: JSON.stringify(payload) }, true),
    updateFigure: (slug, payload) =>
      fetchJSON(`/admin/figures/${encodeURIComponent(slug)}`, { method: "PATCH", body: JSON.stringify(payload) }, true),
    deleteFigure: (slug) =>
      fetchJSON(`/admin/figures/${encodeURIComponent(slug)}`, { method: "DELETE" }, true),
  };

  async function loginAndStepUp() {
    dom.loginStatus.textContent = "Signing in…";
    const username = dom.email.value.trim();
    const password = dom.password.value;
    if (!username || !password) {
      dom.loginStatus.innerHTML = `<span class="bad">Email and password required</span>`;
      return;
    }
    try {
      const login = await API.login(username, password);
      if (!login?.access_token) throw new Error("Login failed");
      state.userToken = login.access_token;
      state.password = password;
      setAuthUI();

      dom.loginStatus.textContent = "Stepping up to admin…";
      const r = await API.stepUp(password);
      if (!r?.admin_access_token) {
        dom.loginStatus.innerHTML = `<span class="bad">${r?.detail || "Step-up failed"}</span>`;
        state.adminToken = null;
        setAuthUI();
        return;
      }
      state.adminToken = r.admin_access_token;
      setAuthUI();
      dom.loginStatus.innerHTML = `<span class="good">Admin active</span>`;
      scheduleAdminRefresh();
      await hydrate();
    } catch (e) {
      dom.loginStatus.innerHTML = `<span class="bad">${e.message}</span>`;
      state.userToken = null;
      state.adminToken = null;
      setAuthUI();
    }
  }

  async function stepUp() {
    const r = await API.stepUp(state.password);
    if (!r?.admin_access_token) throw new Error(r?.detail || "Step-up failed");
    state.adminToken = r.admin_access_token;
    setAuthUI();
    scheduleAdminRefresh();
  }

  function lockAdmin() {
    state.adminToken = null;
    clearTimeout(state.adminRefreshTimer);
    setAuthUI();
  }

  function logout() {
    state.userToken = null;
    state.adminToken = null;
    state.password = null;
    clearTimeout(state.adminRefreshTimer);
    setAuthUI();
    dom.usersBody.innerHTML = "";
    dom.figuresBody.innerHTML = "";
    dom.usersStatus.textContent = "Waiting…";
    dom.figuresStatus.textContent = "Waiting…";
    dom.loginStatus.textContent = "Waiting…";
  }

  async function hydrate() {
    try { await loadUsers(); } catch {}
    try { await loadFigures(); } catch {}
  }

  async function loadUsers() {
    dom.usersStatus.textContent = "Loading…";
    dom.usersBody.innerHTML = "";
    const rows = await API.listUsers();
    dom.usersStatus.textContent = `${rows.length} users`;
    for (const u of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${u.id}</td>
        <td>${escapeHTML(u.username || "")}</td>
        <td>${escapeHTML(u.role || "user")}</td>
        <td>
          <div class="row-actions">
            <button class="btn" data-act="promote" data-id="${u.id}">Make Admin</button>
            <button class="btn" data-act="demote" data-id="${u.id}">Make User</button>
          </div>
        </td>
      `;
      dom.usersBody.appendChild(tr);
    }
    dom.usersBody.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const act = btn.getAttribute("data-act");
        try {
          await API.setUserRole(id, act === "promote" ? "admin" : "user");
          await loadUsers();
        } catch (e) { alert(e.message); }
      });
    });
  }

  async function loadFigures() {
    dom.figuresStatus.textContent = "Loading…";
    dom.figuresBody.innerHTML = "";
    const rows = await API.listFigures();
    dom.figuresStatus.textContent = `${rows.length} figures`;
    for (const f of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${f.id}</td>
        <td>${escapeHTML(f.name || "")}</td>
        <td>${escapeHTML(f.slug || "")}</td>
        <td>${escapeHTML(f.era || "")}</td>
        <td class="muted">${escapeHTML(f.short_summary || "")}</td>
        <td>
          <div class="row-actions">
            <button class="btn" data-act="fill" data-slug="${f.slug}">Fill form</button>
            <button class="btn danger" data-act="del" data-slug="${f.slug}">Delete</button>
          </div>
        </td>
      `;
      dom.figuresBody.appendChild(tr);
    }
    dom.figuresBody.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const act = btn.getAttribute("data-act");
        const slug = btn.getAttribute("data-slug");
        if (act === "fill") {
          const row = btn.closest("tr").children;
          dom.figName.value = row[1].textContent;
          dom.figSlug.value = row[2].textContent;
          dom.figEra.value = row[3].textContent;
          dom.figShort.value = row[4].textContent;
          window.scrollTo({ top: 0, behavior: "smooth" });
        } else if (act === "del") {
          if (!confirm(`Delete figure "${slug}"?`)) return;
          try { await API.deleteFigure(slug); await loadFigures(); } catch (e) { alert(e.message); }
        }
      });
    });
  }

  function escapeHTML(s) {
    return (s || "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // Tabs
  dom.tabs.forEach((el) => {
    el.addEventListener("click", () => {
      if (el.classList.contains("disabled")) return;
      dom.tabs.forEach((t) => t.classList.remove("active"));
      el.classList.add("active");
      const tab = el.getAttribute("data-tab");
      dom.panelUsers.style.display = tab === "users" ? "block" : "none";
      dom.panelFigures.style.display = tab === "figures" ? "block" : "none";
    });
  });

  // Events
  dom.loginBtn.addEventListener("click", loginAndStepUp);
  dom.autoRefresh.addEventListener("change", () => {
    state.autoRefresh = dom.autoRefresh.checked;
    scheduleAdminRefresh();
  });
  dom.lockAdminBtn.addEventListener("click", lockAdmin);
  dom.logoutBtn.addEventListener("click", logout);
  dom.checkHealthBtn.addEventListener("click", async () => {
    dom.healthStatus.textContent = "Checking…";
    try {
      const r = await API.health();
      dom.healthStatus.innerHTML = `<span class="good">OK</span> scope=${r.scope}`;
    } catch (e) {
      dom.healthStatus.innerHTML = `<span class="bad">${e.message}</span>`;
    }
  });
  dom.refreshUsers.addEventListener("click", loadUsers);
  dom.refreshFigures.addEventListener("click", loadFigures);
  dom.createFigureBtn.addEventListener("click", async () => {
    dom.figuresStatus.textContent = "Creating…";
    try {
      const payload = {
        id: 0,
        name: dom.figName.value.trim(),
        slug: dom.figSlug.value.trim(),
        short_summary: dom.figShort.value.trim() || null,
        long_bio: dom.figLong.value.trim() || null,
        era: dom.figEra.value.trim() || null,
        image_url: dom.figImage.value.trim() || null,
        quote: dom.figQuote.value.trim() || null,
      };
      if (!payload.name || !payload.slug) {
        dom.figuresStatus.innerHTML = `<span class="bad">Name and Slug are required</span>`;
        return;
      }
      await API.createFigure(payload);
      dom.figuresStatus.innerHTML = `<span class="good">Created</span>`;
      await loadFigures();
    } catch (e) { dom.figuresStatus.innerHTML = `<span class="bad">${e.message}</span>`; }
  });
  dom.updateFigureBtn.addEventListener("click", async () => {
    dom.figuresStatus.textContent = "Updating…";
    try {
      const slug = dom.figSlug.value.trim();
      if (!slug) {
        dom.figuresStatus.innerHTML = `<span class="bad">Slug is required to update</span>`;
        return;
      }
      const payload = {};
      if (dom.figName.value.trim()) payload["name"] = dom.figName.value.trim();
      if (dom.figShort.value.trim()) payload["short_summary"] = dom.figShort.value.trim();
      if (dom.figLong.value.trim()) payload["long_bio"] = dom.figLong.value.trim();
      if (dom.figEra.value.trim()) payload["era"] = dom.figEra.value.trim();
      if (dom.figImage.value.trim()) payload["image_url"] = dom.figImage.value.trim();
      if (dom.figQuote.value.trim()) payload["quote"] = dom.figQuote.value.trim();
      await API.updateFigure(slug, payload);
      dom.figuresStatus.innerHTML = `<span class="good">Updated</span>`;
      await loadFigures();
    } catch (e) { dom.figuresStatus.innerHTML = `<span class="bad">${e.message}</span>`; }
  });

  setAuthUI();
})();
