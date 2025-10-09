(function () {
  const $ = (s) => document.querySelector(s);
  const qs = new URLSearchParams(location.search);
  const slugFromPath = decodeURIComponent(location.pathname.split("/").pop() || "");
  const isCreate = slugFromPath === "new";

  const dom = {
    pageTitle: $("#pageTitle"),
    figStatus: $("#figStatus"),
    name: $("#name"),
    slug: $("#slug"),
    era: $("#era"),
    image_url: $("#image_url"),
    short_summary: $("#short_summary"),
    long_bio: $("#long_bio"),
    quote: $("#quote"),
    previewImg: $("#previewImg"),
    previewSummary: $("#previewSummary"),
    saveBtn: $("#saveBtn"),
    deleteBtn: $("#deleteBtn"),

    ragBody: $("#ragBody"),
    ragStatus: $("#ragStatus"),
    ragRefresh: $("#ragRefresh"),
    ragAdd: $("#ragAdd"),
  };

  const state = {
    userToken: sessionStorage.getItem("user_token") || null,
    adminToken: sessionStorage.getItem("admin_token") || null,
    password: null,
    currentSlug: isCreate ? "" : slugFromPath,
    figure: null,
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
    createFigure: (payload) => fetchJSON("/admin/figures", { method: "POST", body: JSON.stringify(payload) }),
    updateFigure: (slug, payload) => fetchJSON(`/admin/figures/${encodeURIComponent(slug)}`, { method: "PATCH", body: JSON.stringify(payload) }),
    deleteFigure: (slug) => fetchJSON(`/admin/figures/${encodeURIComponent(slug)}`, { method: "DELETE" }),

    // RAG: keep create at existing POST /admin/rag/sources
    ragCreate: (payload) => fetchJSON("/admin/rag/sources", { method: "POST", body: JSON.stringify(payload) }),
    ragListByFigure: (slug) => fetchJSON(`/admin/rag/contexts?figure_slug=${encodeURIComponent(slug)}`),
    ragUpdate: (id, patch) => fetchJSON(`/admin/rag/contexts/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    ragDelete: (id) => fetchJSON(`/admin/rag/contexts/${id}`, { method: "DELETE" }),
  };

  async function interactiveLoginAndStepUp() {
    const email = prompt("Admin email:") || "";
    const pw = prompt("Password:") || "";
    if (!email || !pw) return false;
    const login = await fetchJSON("/auth/login", {
      method: "POST", body: JSON.stringify({ username: email, password: pw })
    }, /*requireAdmin*/ false);
    if (!login?.access_token) return false;
    state.userToken = login.access_token;
    sessionStorage.setItem("user_token", state.userToken);
    state.password = pw;
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

  function escapeHTML(s) {
    return (s || "")
      .replaceAll("&","&amp;").replaceAll("<","&lt;")
      .replaceAll(">","&gt;").replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }

  function fillForm(fig) {
    dom.name.value = fig?.name || "";
    dom.slug.value = fig?.slug || "";
    dom.era.value = fig?.era || "";
    dom.image_url.value = fig?.image_url || "";
    dom.short_summary.value = fig?.short_summary || "";
    dom.long_bio.value = fig?.long_bio || "";
    dom.quote.value = fig?.quote || "";
    dom.previewImg.style.display = fig?.image_url ? "block" : "none";
    if (fig?.image_url) dom.previewImg.src = fig.image_url;
    dom.previewSummary.textContent = fig?.short_summary || "";
    dom.pageTitle.textContent = fig?.slug ? `Editing: ${fig.slug}` : "Create new figure";
  }

  async function loadFigure() {
    if (isCreate) {
      state.figure = null;
      fillForm(null);
      dom.deleteBtn.style.display = "none";
      dom.figStatus.textContent = "Create mode";
      return;
    }
    dom.figStatus.textContent = "Loading…";
    const rows = await API.listFigures();
    const match = rows.find(r => r.slug === state.currentSlug);
    if (!match) throw new Error("Figure not found");
    state.figure = match;
    fillForm(match);
    dom.figStatus.textContent = "Loaded";
  }

  async function saveFigure() {
    dom.figStatus.textContent = "Saving…";
    const payload = {
      name: dom.name.value.trim() || null,
      slug: dom.slug.value.trim(),
      era: dom.era.value.trim() || null,
      image_url: dom.image_url.value.trim() || null,
      short_summary: dom.short_summary.value.trim() || null,
      long_bio: dom.long_bio.value.trim() || null,
      quote: dom.quote.value.trim() || null,
    };
    if (isCreate) {
      if (!payload.name || !payload.slug) {
        dom.figStatus.textContent = "Name and Slug are required";
        return;
      }
      await API.createFigure(payload);
      dom.figStatus.textContent = "Created";
      location.href = `/admin/figure-ui/${encodeURIComponent(payload.slug)}`;
    } else {
      if (!state.currentSlug) throw new Error("Missing slug");
      await API.updateFigure(state.currentSlug, payload);
      dom.figStatus.textContent = "Saved";
      await loadFigure();
    }
  }

  async function deleteFigure() {
    if (!state.currentSlug) return;
    if (!confirm(`Delete figure "${state.currentSlug}"?`)) return;
    dom.figStatus.textContent = "Deleting…";
    await API.deleteFigure(state.currentSlug);
    location.href = "/admin/figures-ui";
  }

  // ---------- RAG ----------
  async function loadRag() {
    if (!state.currentSlug) {
      dom.ragStatus.textContent = "No slug (create mode)";
      dom.ragBody.innerHTML = "";
      return;
    }
    dom.ragStatus.textContent = "Loading…";
    dom.ragBody.innerHTML = "";
    const rows = await API.ragListByFigure(state.currentSlug);
    dom.ragStatus.textContent = `${rows.length} sources`;
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.id}</td>
        <td><input data-id="${r.id}" data-field="source_name" class="rag-input" value="${escapeHTML(r.source_name || "")}"/></td>
        <td><input data-id="${r.id}" data-field="content_type" class="rag-input" value="${escapeHTML(r.content_type || "")}"/></td>
        <td><input data-id="${r.id}" data-field="source_url" class="rag-input" value="${escapeHTML(r.source_url || "")}"/></td>
        <td>
          <div class="actions" style="display:flex;gap:8px;">
            <button class="btn" data-act="edit-content" data-id="${r.id}">Edit Content</button>
            <button class="btn danger" data-act="del" data-id="${r.id}">Delete</button>
          </div>
        </td>
      `;
      dom.ragBody.appendChild(tr);
    }

    // inline save on blur
    dom.ragBody.querySelectorAll(".rag-input").forEach((inp) => {
      inp.addEventListener("change", async () => {
        const id = inp.getAttribute("data-id");
        const field = inp.getAttribute("data-field");
        const patch = { [field]: inp.value.trim() || null };
        try { await API.ragUpdate(id, patch); }
        catch (e) { alert(e.message); }
      });
    });

    dom.ragBody.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const act = btn.getAttribute("data-act");
        if (act === "edit-content") {
          const current = prompt("Edit content (plain text). Leave empty to clear:", "");
          if (current === null) return;
          try { await API.ragUpdate(id, { content: current }); await loadRag(); }
          catch (e) { alert(e.message); }
        } else if (act === "del") {
          if (!confirm(`Delete source id=${id}?`)) return;
          try { await API.ragDelete(id); await loadRag(); }
          catch (e) { alert(e.message); }
        }
      });
    });
  }

  async function addRag() {
    if (!state.currentSlug) {
      alert("Save the figure first (needs slug).");
      return;
    }
    const source_name = prompt("Source name:", "manual") || "";
    const content_type = prompt("Content type (persona, instruction, bio, note, quote, context):", "note") || "";
    const source_url = prompt("Source URL (optional):", "") || "";
    let content = "";
    if (["persona","instruction","bio","note","quote","context"].includes((content_type || "").toLowerCase())) {
      content = prompt("Content (plain text):", "") || "";
    }
    if (!source_name || !content_type) return;
    dom.ragStatus.textContent = "Adding…";
    try {
      await API.ragCreate({
        figure_slug: state.currentSlug,
        source_name,
        content_type,
        source_url: source_url || null,
        content,
      });
      await loadRag();
      dom.ragStatus.textContent = "Added";
    } catch (e) {
      alert(e.message);
      dom.ragStatus.textContent = "Error";
    }
  }

  // events
  dom.saveBtn.addEventListener("click", () => saveFigure().catch(e => alert(e.message)));
  dom.deleteBtn.addEventListener("click", () => deleteFigure().catch(e => alert(e.message)));
  dom.ragRefresh.addEventListener("click", () => loadRag().catch(e => alert(e.message)));
  dom.ragAdd.addEventListener("click", () => addRag().catch(e => alert(e.message)));

  // boot
  (async () => {
    if (!validToken(state.adminToken, "admin")) {
      await interactiveLoginAndStepUp();
    }
    try {
      await loadFigure();
      await loadRag();
    } catch (e) {
      alert(e.message);
    }
  })();
})();
