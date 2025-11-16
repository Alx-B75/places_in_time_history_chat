async function slugFromPath() {
  // tries to read slug from query or heuristic
  const params = new URLSearchParams(window.location.search);
  if (params.get('slug')) return params.get('slug');
  const parts = window.location.pathname.split('/');
  return parts[parts.length-1] || parts[parts.length-2];
}

function authFetch(url, opts={}) {
  const tok = sessionStorage.getItem('admin_token');
  const headers = { ...(opts.headers||{}) };
  if (tok) headers['Authorization'] = `Bearer ${tok}`;
  return fetch(url, { ...opts, headers });
}

async function loadContexts(slug) {
  const res = await authFetch(`/admin/rag/contexts?figure_slug=${encodeURIComponent(slug)}`);
  if (res.status === 401 || res.status === 403) {
    showAuthWarning();
    return [];
  }
  if (!res.ok) return [];
  return await res.json();
}

function renderContexts(rows) {
  const tbody = document.querySelector('#contexts tbody');
  tbody.innerHTML = '';
  if(!rows.length){
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="3" class="muted">No contexts yet.</td>';
    tbody.appendChild(tr);
    return;
  }
  rows.forEach(r => {
    const tr = document.createElement('tr');
    const preview = (r.content || '').replace(/\s+/g,' ').slice(0,160);
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>
        <div class="ctx-preview" title="${escapeAttr(r.content||'')}">${escapeHTML(preview)}</div>
        <div class="ctx-meta muted">${escapeHTML(r.source_name||'')} · ${escapeHTML(r.content_type||'')}</div>
      </td>
      <td>
        <button class="btn sm" data-act="embed" data-id="${r.id}">Embed</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll('button[data-act="embed"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      btn.disabled = true; btn.textContent='Embedding…';
      try { 
        const r = await authFetch(`/admin/rag/contexts/${id}/embed`, {method:'POST'}); 
        if(!r.ok) throw new Error(await r.text());
      } catch(e){ alert(e.message||e); }
      btn.textContent='Embed'; btn.disabled=false; loadAndRender();
    });
  });
}

async function loadAndRender(){
  const slug = await slugFromPath();
  document.getElementById('title').textContent = 'Figure: ' + slug;
  const rows = await loadContexts(slug);
  renderContexts(rows);
}

// Upload flow
let filesToUpload = [];
const drop = document.getElementById('dropzone');
const filePicker = document.getElementById('filePicker');

drop.addEventListener('click', ()=> filePicker.click());
filePicker.addEventListener('change', (e)=>{ filesToUpload = Array.from(e.target.files); });

['dragenter','dragover'].forEach(evt=> drop.addEventListener(evt, (e)=>{ e.preventDefault(); e.stopPropagation(); drop.style.background='#eef'; }));
['dragleave','drop'].forEach(evt=> drop.addEventListener(evt, (e)=>{ e.preventDefault(); e.stopPropagation(); drop.style.background=''; }));

drop.addEventListener('drop', (e)=>{
  filesToUpload = Array.from(e.dataTransfer.files || []);
});

async function pollJob(job_id){
  const wrap = document.getElementById('progressWrap');
  wrap.classList.remove('hidden');
  const prog = document.getElementById('progress');
  const txt = document.getElementById('progressText');
  while(true){
    const r = await fetch(`/admin/rag/upload-jobs/${job_id}`);
    if (!r.ok) break;
    const j = await r.json();
    const total = j.total || 0; const done = j.done || 0;
    if (total) prog.max = total; prog.value = done; txt.textContent = `${done}/${total} ${j.status||''}`;
    if (j.status === 'done') break;
    await new Promise(res=>setTimeout(res, 1000));
  }
  await loadAndRender();
}

document.getElementById('uploadBtn').addEventListener('click', async ()=>{
  const slug = await slugFromPath();
  if (!filesToUpload.length) return alert('No files selected');
  const fd = new FormData();
  filesToUpload.forEach(f=> fd.append('files', f));
  const auto = document.getElementById('autoEmbed').checked;
  const q = `?auto_embed=${auto?1:0}`;
  const res = await authFetch(`/admin/rag/figure/${slug}/upload${q}`, {method:'POST', body: fd});
  if (!res.ok) return alert('Upload failed');
  const data = await res.json();
  if (data.job_id){
    pollJob(data.job_id);
  } else {
    await loadAndRender();
  }
});

// Embed All
document.getElementById('embedAll').addEventListener('click', async ()=>{
  const slug = await slugFromPath();
  if(!confirm('Embed all contexts for this figure?')) return;
  try{ 
    const r = await authFetch(`/admin/rag/figure/${slug}/embed-all`, {method:'POST'}); 
    if(!r.ok) throw new Error(await r.text());
    loadAndRender(); 
  }catch(e){ alert(e.message||e); }
});

// Ingest All (wikipedia only for now)
document.getElementById('ingestAll').addEventListener('click', async ()=>{
  const slug = await slugFromPath();
  if(!confirm('Ingest primary source (Wikipedia) for this figure?')) return;
  try{
    const r = await authFetch(`/admin/rag/figure/${slug}/ingest-source`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ source:'wikipedia', auto_embed:false })
    });
    if(!r.ok){ throw new Error(await r.text()); }
    await loadAndRender();
  }catch(e){ alert(e.message||e); }
});

// Wire buttons
document.getElementById('refresh').addEventListener('click', loadAndRender);

window.addEventListener('load', loadAndRender);

function escapeHTML(s){
  return (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
}
function escapeAttr(s){ return escapeHTML(s); }

function showAuthWarning(){
  const tbody = document.querySelector('#contexts tbody');
  if (!tbody) return;
  if (tbody.dataset.authWarn) return;
  tbody.dataset.authWarn = '1';
  const tr = document.createElement('tr');
  tr.innerHTML = '<td colspan="3" style="color:#b00;font-weight:600">Admin token missing or expired. Open /admin/ui and sign in, then reload this page.</td>';
  tbody.innerHTML='';
  tbody.appendChild(tr);
}
