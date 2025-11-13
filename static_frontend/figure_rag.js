(function(){
  const $ = (s)=>document.querySelector(s);
  const state = { userToken: sessionStorage.getItem('user_token'), adminToken: sessionStorage.getItem('admin_token') };
  function authHeader() {
    const h = { 'Content-Type': 'application/json' };
    if (state.adminToken) h['Authorization'] = `Bearer ${state.adminToken}`;
    else if (state.userToken) h['Authorization'] = `Bearer ${state.userToken}`;
    return h;
  }
  async function fetchJSON(path, opts={}){
    const res = await fetch(path, { ...opts, headers: { ...(opts.headers||{}), ...authHeader() } });
    if (res.status === 204) return { ok:true };
    const data = await res.json().catch(()=>({}));
    if (!res.ok) throw new Error(data?.detail || res.statusText);
    return data;
  }
  const dom = {
    hdrSlug: $('#hdrSlug'), hdrStatus: $('#hdrStatus'),
    figureMeta: $('#figureMeta'), sourcesMeta: $('#sourcesMeta'), embeddingsMeta: $('#embeddingsMeta'),
    ragName: $('#ragName'), ragType: $('#ragType'), ragUrl: $('#ragUrl'), addRagBtn: $('#addRagBtn'), addStatus: $('#addStatus'),
    ctxStatus: $('#ctxStatus'), ctxBody: $('#ctxBody')
  };
  function slugFromPath(){
    const m = location.pathname.match(/\/admin\/figure-rag\/([^/?#]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  function esc(s){ return String(s||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;'); }
  function escAttr(s){ return String(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

  async function loadDetail(){
    const slug = slugFromPath();
    if (!slug){ dom.hdrStatus.textContent = 'Missing slug'; return; }
    dom.hdrSlug.textContent = slug;
    dom.hdrStatus.textContent = 'Loading…';
    const d = await fetchJSON(`/admin/rag/figure/${encodeURIComponent(slug)}/detail`);
    // figure meta
    const f = d.figure || {};
    const lines = [];
    if (f.name) lines.push(`<b>Name:</b> ${esc(f.name)}`);
    if (f.era) lines.push(`<b>Era:</b> ${esc(f.era)}`);
    if (f.short_summary) lines.push(`<b>Summary:</b> ${esc(f.short_summary)}`);
    dom.figureMeta.innerHTML = lines.join(' · ') || '<span class="muted">No metadata</span>';
    // sources
    const s = d.sources_meta || {};
    const links = [
      s.wikipedia ? `<a href="${escAttr(s.wikipedia)}" target="_blank" rel="noopener">wikipedia</a>` : '',
      s.wikidata ? `<a href="${escAttr(s.wikidata)}" target="_blank" rel="noopener">wikidata</a>` : '',
      s.dbpedia ? `<a href="${escAttr(s.dbpedia)}" target="_blank" rel="noopener">dbpedia</a>` : ''
    ].filter(Boolean).join(' | ');
    dom.sourcesMeta.innerHTML = links || '<span class="muted">No known links</span>';
    // embeddings
    const e = d.embeddings || {};
    const ids = Array.isArray(e.ids) ? e.ids : [];
    const idsPreview = ids.slice(0, 50).map(esc).join(', ');
    dom.embeddingsMeta.innerHTML = `<b>Vectors:</b> ${Number(e.count||ids.length)} ${e.has_more? '(showing first 1000)' : ''}<br/><span class="muted">IDs:</span> ${idsPreview || '—'}`;
    // contexts
    renderContexts(d.contexts||[], slug);
    dom.hdrStatus.textContent = 'Ready';
  }

  async function addManual(slug){
    const source_name = (dom.ragName.value||'').trim() || prompt('Source name:','manual') || '';
    const content_type = (dom.ragType.value||'').trim() || prompt('Content type:','note') || '';
    let source_url = (dom.ragUrl.value||'').trim();
    let content = '';
    if (['persona','instruction','bio','note','quote','context'].includes(content_type)) {
      content = prompt('Content (plain text):','') || '';
    }
    if (!source_name || !content_type) return alert('Name and Type are required');
    dom.addStatus.textContent = 'Adding…';
    await fetchJSON('/admin/rag/sources', { method:'POST', body: JSON.stringify({ figure_slug: slug, source_name, content_type, source_url: source_url||null, content })});
    dom.addStatus.textContent = 'Added';
    dom.ragName.value = ''; dom.ragType.value = ''; dom.ragUrl.value = '';
    await loadDetail();
  }

  function renderContexts(rows, slug){
    dom.ctxStatus.textContent = `${rows.length} contexts`;
    dom.ctxBody.innerHTML = '';
    for (const c of rows){
      const url = c.source_url ? `<a href="${escAttr(c.source_url)}" target="_blank" rel="noopener">${esc(c.source_url)}</a>` : '';
      const contentPreview = c.content ? esc(String(c.content).slice(0,160)) + (String(c.content).length>160?'…':'') : '';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${c.id}</td>
        <td>${esc(c.source_name || '')}</td>
        <td>${esc(c.content_type || '')}${c.is_manual? ' <span class="muted">(manual)</span>' : ''}</td>
        <td class="summary-cell">${url}${url && contentPreview? ' · ' : ''}<span class="muted">${contentPreview}</span></td>
        <td>
          <div class="row-actions">
            <button class="btn sm" data-act="toggle" data-id="${c.id}" data-val="${c.is_manual?0:1}">${c.is_manual? 'Unset Manual' : 'Set Manual'}</button>
            <button class="btn sm" data-act="edit" data-id="${c.id}">Edit</button>
            <button class="btn danger sm" data-act="delete" data-id="${c.id}">Delete</button>
          </div>
        </td>`;
      dom.ctxBody.appendChild(tr);
    }
    dom.ctxBody.querySelectorAll('button').forEach((btn)=>{
      btn.addEventListener('click', async ()=>{
        const id = btn.getAttribute('data-id');
        const act = btn.getAttribute('data-act');
        try{
          if (act==='toggle'){
            const val = Number(btn.getAttribute('data-val'))||0;
            await fetchJSON(`/admin/rag/contexts/${id}`, { method:'PATCH', body: JSON.stringify({ is_manual: val }) });
          } else if (act==='delete'){
            if (!confirm(`Delete context ${id}?`)) return;
            await fetchJSON(`/admin/rag/contexts/${id}`, { method:'DELETE' });
          } else if (act==='edit'){
            const name = prompt('Source name (blank=skip):','')||'';
            const type = prompt('Content type (blank=skip):','')||'';
            const url = prompt('Source URL (blank=skip):','')||'';
            const content = prompt('Content (blank=skip):','')||'';
            const patch = {};
            if (name) patch.source_name = name;
            if (type) patch.content_type = type;
            if (url) patch.source_url = url;
            if (content) patch.content = content;
            if (Object.keys(patch).length) await fetchJSON(`/admin/rag/contexts/${id}`, { method:'PATCH', body: JSON.stringify(patch) });
          }
          await loadDetail();
        }catch(e){ alert(e.message); }
      });
    });
    updateScrollSync();
  }

  function updateScrollSync(){
    const table = document.getElementById('ctxTable');
    const top = document.getElementById('ctxScrollTop');
    const topInner = document.getElementById('ctxScrollTopInner');
    if (!table || !top || !topInner) return;
    topInner.style.width = `${table.scrollWidth}px`;
    let syncing=false; const bottom=table.parentElement;
    const onTop=()=>{ if(syncing) return; syncing=true; bottom.scrollLeft=top.scrollLeft; syncing=false; };
    const onBottom=()=>{ if(syncing) return; syncing=true; top.scrollLeft=bottom.scrollLeft; syncing=false; };
    top.removeEventListener('scroll', onTop); bottom.removeEventListener('scroll', onBottom);
    top.addEventListener('scroll', onTop); bottom.addEventListener('scroll', onBottom);
  }

  // events
  dom.addRagBtn?.addEventListener('click', ()=>{
    const slug = slugFromPath(); if (!slug) return alert('Missing slug');
    addManual(slug).catch(e=>alert(e.message));
  });

  // boot
  loadDetail().catch(e=>{ dom.hdrStatus.textContent = e.message; });
})();
