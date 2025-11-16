(function () {
  const $ = (sel) => document.querySelector(sel);

  const state = {
    userToken: null,      // JWT scope=user
    adminToken: null,     // JWT scope=admin
    password: null,       // in-memory only
    adminRefreshTimer: null,
    autoRefresh: true,
  };

  // DOM (works whether login section exists or not)
  const dom = {
    // header controls
    authStatus: $("#authStatus"),
    adminStatus: $("#adminStatus"),
    lockAdminBtn: $("#lockAdminBtn"),
    logoutBtn: $("#logoutBtn"),

    // tabs & panels
    tabs: document.querySelectorAll(".tab"),
    panelUsers: $("#panel-users"),
    panelFigures: $("#panel-figures"),
  panelRag: $("#panel-rag"),
  panelLlm: $("#panel-llm"),

    // USERS
    refreshUsers: $("#refreshUsers"),
    usersStatus: $("#usersStatus"),
    usersBody: $("#usersBody"),

    // FIGURES
    refreshFigures: $("#refreshFigures"),
    figuresStatus: $("#figuresStatus"),
    figuresBody: $("#figuresBody"),
    figName: $("#figName"),
    figSlug: $("#figSlug"),
    figShort: $("#figShort"),
    figLong: $("#figLong"),
    figEra: $("#figEra"),
    figImage: $("#figImage"),
    figQuote: $("#figQuote"),
    createFigureBtn: $("#createFigureBtn"),
    updateFigureBtn: $("#updateFigureBtn"),

    // RAG
    refreshRag: $("#refreshRag"),
    ragStatus: $("#ragStatus"),
    ragBody: $("#ragBody"),
    ragName: $("#ragName"),
    ragType: $("#ragType"),
    ragUrl: $("#ragUrl"),

  // LLM
  llmProfileSelect: $("#llm-profile-select"),
  llmProfileActivate: $("#llm-profile-activate"),
  llmProfileName: $("#llm-profile-name"),
  llmProvider: $("#llm-provider"),
  llmModel: $("#llm-model"),
  llmApiBase: $("#llm-api-base"),
  llmTemp: $("#llm-temp"),
  llmTopP: $("#llm-topp"),
  llmMax: $("#llm-max"),
  llmProfileSave: $("#llm-profile-save"),
  llmProviderDirect: $("#llm-provider-direct"),
  llmModelDirect: $("#llm-model-direct"),
  llmApiBaseDirect: $("#llm-api-base-direct"),
  llmTempDirect: $("#llm-temp-direct"),
  llmTopPDirect: $("#llm-topp-direct"),
  llmMaxDirect: $("#llm-max-direct"),
  llmDirectSave: $("#llm-direct-save"),
  llmHealth: $("#llm-health"),

    // optional login form (older HTML)
    email: $("#email"),
    password: $("#password"),
    loginBtn: $("#loginBtn"),
    loginStatus: $("#loginStatus"),
    autoRefreshChk: $("#autoRefresh"),
    checkHealthBtn: $("#checkHealthBtn"),
    healthStatus: $("#healthStatus"),
  };

  // --------------- Auth helpers ---------------
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
    const ready = !!state.adminToken;
    dom.tabs.forEach((t) => t.classList.toggle("disabled", !ready));
    // Toggle inline login panel visibility
    const loginPanel = document.getElementById("login-panel");
    if (loginPanel) loginPanel.style.display = ready ? "none" : "block";
  }

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

  function saveTokens() {
    if (state.userToken) sessionStorage.setItem("user_token", state.userToken);
    else sessionStorage.removeItem("user_token");
    if (state.adminToken) sessionStorage.setItem("admin_token", state.adminToken);
    else sessionStorage.removeItem("admin_token");
  }
  function loadTokens() {
    const ut = sessionStorage.getItem("user_token");
    const at = sessionStorage.getItem("admin_token");
    if (ut && validToken(ut, "user")) state.userToken = ut;
    if (at && validToken(at, "admin")) state.adminToken = at;
  }

  function scheduleAdminRefresh() {
    clearTimeout(state.adminRefreshTimer);
    if (!state.autoRefresh || !state.adminToken || !state.password || !state.userToken) return;
    const p = parseJwt(state.adminToken);
    if (!p?.exp) return;
    const msLeft = p.exp * 1000 - Date.now();
    const wait = Math.max(5000, msLeft - 60_000); // refresh 60s early
    state.adminRefreshTimer = setTimeout(() => { stepUp().catch(()=>{}); }, wait);
  }

  async function fetchJSON(path, opts = {}, requireAdmin = false) {
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const tok = requireAdmin ? state.adminToken : state.userToken;
    if (tok) headers["Authorization"] = `Bearer ${tok}`;
    let res = await fetch(path, { ...opts, headers });

    if ((res.status === 401 || res.status === 403) && requireAdmin) {
      // try auto step-up using stored password
      if (state.userToken && state.password) {
        try {
          await stepUp();
          const headers2 = { ...headers, Authorization: `Bearer ${state.adminToken}` };
          res = await fetch(path, { ...opts, headers: headers2 });
        } catch {}
      }
      // interactive fallback if still unauthorized
      if (res.status === 401 || res.status === 403) {
        const ok = await interactiveLoginAndStepUp();
        if (ok) {
          const headers3 = { ...headers, Authorization: `Bearer ${state.adminToken}` };
          res = await fetch(path, { ...opts, headers: headers3 });
        }
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
    adminLogin: (username, password) =>
      fetchJSON("/auth/admin/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    stepUp: (password) =>
      fetch("/auth/admin/stepup", {
        method: "POST",
        headers: { Authorization: `Bearer ${state.userToken}`, "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      }).then((r) => r.json()),
    health: () => fetchJSON("/admin/health", {}, true),

    // users
    listUsers: () => fetchJSON("/admin/users", {}, true),
  setUserRole: (id, role) => fetchJSON(`/admin/users/${id}/role`, { method: "PATCH", body: JSON.stringify({ role }) }, true),
  deleteUser: (id) => fetchJSON(`/admin/users/${id}`, { method: "DELETE" }, true),

    // figures
    listFigures: () => fetchJSON("/admin/figures", {}, true),
    createFigure: (payload) => fetchJSON("/admin/figures", { method: "POST", body: JSON.stringify(payload) }, true),
    updateFigure: (slug, payload) => fetchJSON(`/admin/figures/${encodeURIComponent(slug)}`, { method: "PATCH", body: JSON.stringify(payload) }, true),
    deleteFigure: (slug) => fetchJSON(`/admin/figures/${encodeURIComponent(slug)}`, { method: "DELETE" }, true),

  // rag (summary + create-manual)
  ragSummary: () => fetchJSON("/admin/rag/sources", {}, true),
  ragCreate: (payload) => fetchJSON("/admin/rag/sources", { method: "POST", body: JSON.stringify(payload) }, true),

  // llm
  llmProfiles: () => fetchJSON("/admin/llm/profiles", {}, true),
  llmProfileSave: (name, config) => fetchJSON("/admin/llm/profiles", { method: "POST", body: JSON.stringify({ name, config }) }, true),
  llmActivate: (name) => fetchJSON("/admin/llm/profile/activate", { method: "PATCH", body: JSON.stringify({ name }) }, true),
  llmHealth: () => fetchJSON("/admin/llm/health", {}, true),
  llmPatch: (cfg) => fetchJSON("/admin/llm", { method: "PATCH", body: JSON.stringify(cfg) }, true),
  };

  // --------------- Auth flows ---------------
  async function interactiveLoginAndStepUp() {
    let username = dom.email?.value?.trim();
    let pw = dom.password?.value || "";
    if (!username) username = prompt("Admin email:") || "";
    if (!pw) pw = prompt("Password:") || "";
    if (!username || !pw) return false;

    try {
      if (dom.loginStatus) dom.loginStatus.textContent = "Signing in (admin)…";
      const login = await API.adminLogin(username, pw);
      if (!login?.admin_access_token || !login?.access_token) throw new Error("Admin login failed");
      state.userToken = login.access_token; // kept to allow step-up refresh flow
      state.adminToken = login.admin_access_token;
      state.password = pw;
      saveTokens();
      setAuthUI();
      scheduleAdminRefresh();
      if (dom.loginStatus) dom.loginStatus.innerHTML = `<span class="good">Admin active</span>`;
      await hydrate();
      return true;
    } catch (e) {
      alert(e.message || String(e));
      state.userToken = null;
      state.adminToken = null;
      state.password = null;
      saveTokens();
      setAuthUI();
      if (dom.loginStatus) dom.loginStatus.innerHTML = `<span class="bad">${e.message || e}</span>`;
      return false;
    }
  }

  async function stepUp() {
    const r = await API.stepUp(state.password || "");
    if (!r?.admin_access_token) throw new Error(r?.detail || "Step-up failed");
    state.adminToken = r.admin_access_token;
    saveTokens();
    setAuthUI();
    scheduleAdminRefresh();
  }

  function lockAdmin() {
    state.adminToken = null;
    clearTimeout(state.adminRefreshTimer);
    saveTokens();
    setAuthUI();
  }

  function logout() {
    state.userToken = null;
    state.adminToken = null;
    state.password = null;
    clearTimeout(state.adminRefreshTimer);
    saveTokens();
    setAuthUI();
    if (dom.usersBody) dom.usersBody.innerHTML = "";
    if (dom.figuresBody) dom.figuresBody.innerHTML = "";
    if (dom.ragBody) dom.ragBody.innerHTML = "";
    if (dom.usersStatus) dom.usersStatus.textContent = "Waiting…";
    if (dom.figuresStatus) dom.figuresStatus.textContent = "Waiting…";
    if (dom.ragStatus) dom.ragStatus.textContent = "Waiting…";
    if (dom.loginStatus) dom.loginStatus.textContent = "Waiting…";
  }

  // --------------- Loaders ---------------
  async function hydrate() {
    try { await loadUsers(); } catch {}
    try { await loadFigures(); } catch {}
    try { await loadRagSummary(); } catch {}
    // LLM health/profiles are loaded lazily when LLM tab is opened
  }

  // USERS
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
            <button class="btn sm" data-act="promote" data-id="${u.id}">Make Admin</button>
            <button class="btn sm" data-act="demote" data-id="${u.id}">Make User</button>
            <button class="btn success sm" data-act="contact" data-id="${u.id}" data-email="${escapeAttr(u.username || '')}">Contact</button>
            <button class="btn danger sm" data-act="delete" data-id="${u.id}">Delete</button>
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
          if (act === "contact") {
            const email = btn.getAttribute('data-email') || '';
            if (!email) return alert('No email available for this user.');
            // Open mail client; wiring to backend can be added later
            window.location.href = `mailto:${email}?subject=Support`;
          } else if (act === "delete") {
            if (!confirm(`Delete user ${id}? This cannot be undone.`)) return;
            await API.deleteUser(id);
          } else {
            await API.setUserRole(id, act === "promote" ? "admin" : "user");
          }
          await loadUsers();
        } catch (e) { alert(e.message); }
      });
    });

    // Update top scroll width to match table content and sync scroll positions
    updateUsersScrollSync();
  }

  function updateUsersScrollSync() {
    const table = document.getElementById('usersTable');
    const top = document.getElementById('usersScrollTop');
    const topInner = document.getElementById('usersScrollTopInner');
    if (!table || !top || !topInner) return;
    // Set spacer width to allow top scrollbar
    topInner.style.width = `${table.scrollWidth}px`;
    // Sync listeners (one-time; harmless to rebind)
    let syncing = false;
    const bottomContainer = table.parentElement; // panel acts as scroll container too, but table is not block-level; rely on parent
    const onTopScroll = () => {
      if (syncing) return; syncing = true;
      bottomContainer.scrollLeft = top.scrollLeft; syncing = false;
    };
    const onBottomScroll = () => {
      if (syncing) return; syncing = true;
      top.scrollLeft = bottomContainer.scrollLeft; syncing = false;
    };
    top.removeEventListener('scroll', onTopScroll);
    bottomContainer.removeEventListener('scroll', onBottomScroll);
    top.addEventListener('scroll', onTopScroll);
    bottomContainer.addEventListener('scroll', onBottomScroll);
  }

  // FIGURES
  async function loadFigures() {
    dom.figuresStatus.textContent = "Loading…";
    dom.figuresBody.innerHTML = "";
    const rows = await API.listFigures();
    dom.figuresStatus.textContent = `${rows.length} figures`;
    for (const f of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${f.id}</td>
        <td><a href="/admin/figure-ui/${escapeAttr(f.slug || '')}">${escapeHTML(f.name || "")}</a></td>
        <td><a href="/admin/figure_rag.html?slug=${escapeAttr(f.slug || '')}">${escapeHTML(f.slug || "")}</a></td>
        <td>${escapeHTML(f.era || "")}</td>
        <td class="muted summary-cell" title="${escapeAttr(f.short_summary || '')}">${escapeHTML(f.short_summary || "")}</td>
        <td>
          <div class="row-actions">
            <button class="btn sm" data-act="fill" data-slug="${f.slug}">Fill form</button>
            <button class="btn danger sm" data-act="del" data-slug="${f.slug}">Delete</button>
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
    // Sync top/bottom scrollbars
    updateFiguresScrollSync();
  }

  function updateFiguresScrollSync() {
    const table = document.getElementById('figuresTable');
    const top = document.getElementById('figuresScrollTop');
    const topInner = document.getElementById('figuresScrollTopInner');
    if (!table || !top || !topInner) return;
    topInner.style.width = `${table.scrollWidth}px`;
    let syncing = false;
    const bottomContainer = table.parentElement;
    const onTopScroll = () => { if (syncing) return; syncing = true; bottomContainer.scrollLeft = top.scrollLeft; syncing = false; };
    const onBottomScroll = () => { if (syncing) return; syncing = true; top.scrollLeft = bottomContainer.scrollLeft; syncing = false; };
    top.removeEventListener('scroll', onTopScroll);
    bottomContainer.removeEventListener('scroll', onBottomScroll);
    top.addEventListener('scroll', onTopScroll);
    bottomContainer.addEventListener('scroll', onBottomScroll);
  }

  // RAG summary (matches your /admin/rag/sources body)
  async function loadRagSummary() {
    dom.ragStatus.textContent = "Loading…";
    dom.ragBody.innerHTML = "";

    const data = await API.ragSummary();
    // Expect: { collection: {...}, figures: [...] }
    const figures = Array.isArray(data?.figures) ? data.figures : [];
    dom.ragStatus.textContent = `${figures.length} figures`;

    for (const f of figures) {
      const counts = f.context_counts || {};
      const countStr = Object.keys(counts).length
        ? Object.entries(counts).map(([k, v]) => `${k}:${v}`).join(" · ")
        : "—";
      const src = f.sources_meta || {};
      const links = [
        src.wikipedia ? `<a href="${escapeAttr(src.wikipedia)}" target="_blank" rel="noopener">wikipedia</a>` : "",
        src.wikidata ? `<a href="${escapeAttr(src.wikidata)}" target="_blank" rel="noopener">wikidata</a>` : "",
        src.dbpedia ? `<a href="${escapeAttr(src.dbpedia)}" target="_blank" rel="noopener">dbpedia</a>` : "",
      ].filter(Boolean).join(" | ");

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><a href="/admin/figure_rag.html?slug=${escapeAttr(f.slug || '')}">${escapeHTML(f.slug)}</a></td>
        <td><a href="/admin/figure-ui/${escapeAttr(f.slug || '')}">${escapeHTML(f.name || "")}</a></td>
        <td>${escapeHTML(String(f.total_contexts ?? 0))}${f.has_manual_context ? ' <span class="muted">(manual)</span>' : ''}<br/><span class="muted">${countStr}</span></td>
        <td>${links || ""}</td>
        <td>
          <div class="row-actions">
            <button class="btn sm" data-act="add-manual" data-slug="${f.slug}">Add manual</button>
          </div>
        </td>
      `;
      dom.ragBody.appendChild(tr);
    }

    dom.ragBody.querySelectorAll('button[data-act="add-manual"]').forEach((btn) => {
      btn.addEventListener("click", async () => {
        const figure_slug = btn.getAttribute("data-slug");
        try {
          await addManualSourceFlow(figure_slug);
          await loadRagSummary();
        } catch (e) {
          if (e?.message) alert(e.message);
        }
      });
    });
    // Sync top/bottom scrollbars
    updateRagScrollSync();
  }

  function updateRagScrollSync() {
    const table = document.getElementById('ragTable');
    const top = document.getElementById('ragScrollTop');
    const topInner = document.getElementById('ragScrollTopInner');
    if (!table || !top || !topInner) return;
    topInner.style.width = `${table.scrollWidth}px`;
    let syncing = false;
    const bottomContainer = table.parentElement;
    const onTopScroll = () => { if (syncing) return; syncing = true; bottomContainer.scrollLeft = top.scrollLeft; syncing = false; };
    const onBottomScroll = () => { if (syncing) return; syncing = true; top.scrollLeft = bottomContainer.scrollLeft; syncing = false; };
    top.removeEventListener('scroll', onTopScroll);
    bottomContainer.removeEventListener('scroll', onBottomScroll);
    top.addEventListener('scroll', onTopScroll);
    bottomContainer.addEventListener('scroll', onBottomScroll);
  }

  async function addManualSourceFlow(defaultSlug) {
    const figure_slug = defaultSlug || prompt("Figure slug for this source:") || "";
    if (!figure_slug) throw new Error("No figure slug provided");

    // Use the small form inputs if present; otherwise prompt.
    let source_name = dom.ragName?.value?.trim() || "";
    let content_type = dom.ragType?.value?.trim() || "";
    let source_url = dom.ragUrl?.value?.trim() || "";

    if (!source_name) source_name = prompt("Source name (e.g., persona, instruction, note):", "manual") || "";
    if (!content_type) content_type = prompt("Content type (persona, instruction, bio, note, quote, context):", "note") || "";
    // If content_type is a manual text-bearing type, ask for content.
    let content = "";
    if (["persona","instruction","bio","note","quote","context"].includes(content_type)) {
      content = prompt("Content (plain text):", "") || "";
    }
    // If not text type, content may be omitted; backend should tolerate empty.

    if (!source_name || !content_type) throw new Error("Name and Type are required");
    const payload = { figure_slug, source_name, content_type, source_url: source_url || null, content };
    dom.ragStatus.textContent = "Adding…";
    await API.ragCreate(payload);
    dom.ragStatus.innerHTML = `<span class="good">Added</span>`;
    if (dom.ragName) dom.ragName.value = "";
    if (dom.ragType) dom.ragType.value = "";
    if (dom.ragUrl) dom.ragUrl.value = "";
  }

  // --------------- Utils ---------------
  function escapeHTML(s) {
    return (s || "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
  function escapeAttr(s) {
    return String(s || "").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  }

  // --------------- Tabs & events ---------------
  dom.tabs.forEach((el) => {
    el.addEventListener("click", () => {
      if (el.classList.contains("disabled")) {
        interactiveLoginAndStepUp().then((ok) => { if (ok) el.click(); });
        return;
      }
      dom.tabs.forEach((t) => t.classList.remove("active"));
      el.classList.add("active");
      const tab = el.getAttribute("data-tab");
      dom.panelUsers.style.display = tab === "users" ? "block" : "none";
      dom.panelFigures.style.display = tab === "figures" ? "block" : "none";
      dom.panelRag.style.display = tab === "rag" ? "block" : "none";
      dom.panelLlm.style.display = tab === "llm" ? "block" : "none";
      if (tab === "users") loadUsers().catch(()=>{});
      if (tab === "figures") loadFigures().catch(()=>{});
      if (tab === "rag") loadRagSummary().catch(()=>{});
      if (tab === "llm") { loadLLMProfiles().catch(()=>{}); loadLLMHealth().catch(()=>{}); }
    });
  });

  dom.lockAdminBtn?.addEventListener("click", lockAdmin);
  dom.logoutBtn?.addEventListener("click", logout);
  dom.refreshUsers?.addEventListener("click", () => loadUsers().catch(e => alert(e.message)));
  dom.refreshFigures?.addEventListener("click", () => loadFigures().catch(e => alert(e.message)));

  // LLM events
  dom.llmProfileActivate?.addEventListener("click", async () => {
    try {
      const name = dom.llmProfileSelect.value;
      if (!name) return alert("Select a profile to activate.");
      await API.llmActivate(name);
      await Promise.all([loadLLMProfiles(), loadLLMHealth()]);
    } catch (e) { alert(e.message); }
  });

  dom.llmProfileSave?.addEventListener("click", async () => {
    try {
      const name = (dom.llmProfileName.value || "").trim();
      if (!name) return alert("Profile name is required.");
      const config = {
        provider: (dom.llmProvider.value || "").trim(),
        model: (dom.llmModel.value || "").trim(),
        api_base: (dom.llmApiBase.value || "").trim() || null,
        temperature: dom.llmTemp.value ? Number(dom.llmTemp.value) : null,
        top_p: dom.llmTopP.value ? Number(dom.llmTopP.value) : null,
        max_tokens: dom.llmMax.value ? Number(dom.llmMax.value) : null,
      };
      await API.llmProfileSave(name, config);
      await loadLLMProfiles();
    } catch (e) { alert(e.message); }
  });

  dom.llmDirectSave?.addEventListener("click", async () => {
    try {
      const cfg = {};
      const pv = (dom.llmProviderDirect.value || "").trim(); if (pv) cfg.provider = pv;
      const mv = (dom.llmModelDirect.value || "").trim(); if (mv) cfg.model = mv;
      const ab = (dom.llmApiBaseDirect.value || "").trim(); if (ab) cfg.api_base = ab;
      if (dom.llmTempDirect.value !== "") cfg.temperature = Number(dom.llmTempDirect.value);
      if (dom.llmTopPDirect.value !== "") cfg.top_p = Number(dom.llmTopPDirect.value);
      if (dom.llmMaxDirect.value !== "") cfg.max_tokens = Number(dom.llmMaxDirect.value);
      await API.llmPatch(cfg);
      await loadLLMHealth();
      alert("Runtime updated.");
    } catch (e) { alert(e.message); }
  });

  if (dom.createFigureBtn) dom.createFigureBtn.addEventListener("click", async () => {
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

  if (dom.updateFigureBtn) dom.updateFigureBtn.addEventListener("click", async () => {
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

  // Optional health button in older HTML
  dom.checkHealthBtn?.addEventListener("click", async () => {
    dom.healthStatus.textContent = "Checking…";
    try {
      const r = await API.health();
      dom.healthStatus.innerHTML = `<span class="good">OK</span> scope=${r.scope}`;
    } catch (e) {
      dom.healthStatus.innerHTML = `<span class="bad">${e.message}</span>`;
    }
  });

  dom.autoRefreshChk?.addEventListener("change", () => {
    state.autoRefresh = !!dom.autoRefreshChk.checked;
    scheduleAdminRefresh();
  });

  if (dom.loginBtn) {
    dom.loginBtn.addEventListener("click", (e) => {
      e.preventDefault();
      interactiveLoginAndStepUp().catch(()=>{});
    });
  }

  // --------------- Boot ---------------
  (function boot() {
    loadTokens();
    setAuthUI();

    // If admin token valid, hydrate silently; otherwise prompt.
    if (state.adminToken && validToken(state.adminToken, "admin")) {
      scheduleAdminRefresh();
      hydrate().catch(()=>{});
    } else {
      // If the page has a login form, wait for user click; else prompt immediately.
      if (!dom.loginBtn) interactiveLoginAndStepUp().catch(()=>{});
    }
  })();

  // Never persist password; clear in-memory on unload.
  window.addEventListener("beforeunload", () => { state.password = null; });

  // --------------- LLM helpers ---------------
  async function loadLLMProfiles() {
    const data = await API.llmProfiles();
    // populate select
    if (dom.llmProfileSelect) {
      dom.llmProfileSelect.innerHTML = "";
      (data.profiles || []).forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.name;
        opt.textContent = p.is_active ? `${p.name} (active)` : p.name;
        dom.llmProfileSelect.appendChild(opt);
      });
      if (data.active) dom.llmProfileSelect.value = data.active;
    }
  }

  async function loadLLMHealth() {
    const h = await API.llmHealth();
    if (dom.llmHealth) dom.llmHealth.textContent = JSON.stringify(h, null, 2);
    // prefill direct-edit fields as a convenience
    if (dom.llmProviderDirect) dom.llmProviderDirect.value = h.provider || "";
    if (dom.llmModelDirect) dom.llmModelDirect.value = h.model || "";
    if (dom.llmApiBaseDirect) dom.llmApiBaseDirect.value = h.api_base || "";
    if (dom.llmTempDirect) dom.llmTempDirect.value = h.temperature ?? "";
    if (dom.llmTopPDirect) dom.llmTopPDirect.value = h.top_p ?? "";
    if (dom.llmMaxDirect) dom.llmMaxDirect.value = h.max_tokens ?? "";
  }
})();
