async function slugFromPath() {
  // tries to read slug from query or heuristic
  const params = new URLSearchParams(window.location.search);
  if (params.get('slug')) return params.get('slug');
  const parts = window.location.pathname.split('/');
  return parts[parts.length-1] || parts[parts.length-2];
}

async function loadContexts(slug) {
  const res = await fetch(`/admin/rag/contexts?figure_slug=${encodeURIComponent(slug)}`);
  if (!res.ok) return [];
  return await res.json();
}

function renderContexts(rows) {
  const tbody = document.querySelector('#contexts tbody');
  tbody.innerHTML = '';
  rows.forEach(r => {
    const tr = document.createElement('tr');
    const tdId = document.createElement('td'); tdId.textContent = r.id;
    const tdText = document.createElement('td'); tdText.textContent = (r.content || r.text || '').slice(0,200);
    const tdActions = document.createElement('td');
    const embedBtn = document.createElement('button'); embedBtn.textContent = 'Embed';
    embedBtn.onclick = async ()=>{
      await fetch(`/admin/rag/contexts/${r.id}/embed`, {method:'POST'});
      loadAndRender();
    };
    tdActions.appendChild(embedBtn);
    tr.appendChild(tdId); tr.appendChild(tdText); tr.appendChild(tdActions);
    tbody.appendChild(tr);
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
  const res = await fetch(`/admin/rag/figure/${slug}/upload${q}`, {method:'POST', body: fd});
  if (!res.ok) return alert('Upload failed');
  const data = await res.json();
  if (data.job_id){
    pollJob(data.job_id);
  } else {
    await loadAndRender();
  }
});

// Wire buttons
document.getElementById('refresh').addEventListener('click', loadAndRender);

window.addEventListener('load', loadAndRender);
