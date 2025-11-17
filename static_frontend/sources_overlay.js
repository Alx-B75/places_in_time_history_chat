(function(){
  if (!window || window.__pitSourcesOverlay) return; window.__pitSourcesOverlay = true;

  function isThreadView(){ return location.pathname.startsWith('/thread/') || /\/threads?$/.test(location.pathname); }

  // UI helpers
  function ensureUI(){
    if (!isThreadView()) return null;
    const chatCard = document.querySelector('.chat-card');
    const messages = document.querySelector('.messages');
    if (!chatCard || !messages) return null;
    let wrap = document.getElementById('pit-sources-wrap');
    if (wrap) return wrap;
    wrap = document.createElement('div');
    wrap.id = 'pit-sources-wrap';
    wrap.style.margin = '4px 0 10px';
    const btn = document.createElement('button');
    btn.id = 'pit-sources-toggle';
    btn.className = 'btn';
    btn.type = 'button';
    btn.textContent = 'Show sources';
    btn.style.margin = '0 16px 8px';
    const panel = document.createElement('div');
    panel.id = 'pit-sources-panel';
    panel.style.display = 'none';
    panel.style.margin = '0 16px 12px';
    panel.style.padding = '10px';
    panel.style.border = '1px solid var(--border)';
    panel.style.borderRadius = '10px';
    panel.style.background = 'rgba(148,163,184,.08)';
    const list = document.createElement('div');
    list.id = 'pit-sources-list';
    list.style.display = 'grid';
    list.style.gridTemplateColumns = '1fr';
    list.style.gap = '6px';
    panel.appendChild(list);
    wrap.appendChild(btn);
    wrap.appendChild(panel);
    chatCard.insertBefore(wrap, chatCard.querySelector('.compose'));
    btn.addEventListener('click', () => {
      const open = panel.style.display !== 'none';
      panel.style.display = open ? 'none' : '';
      btn.textContent = open ? 'Show sources' : 'Hide sources';
    });
    return wrap;
  }

  function safeHtml(s){
    return String(s||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  }

  function updateUI(sources){
    const wrap = ensureUI();
    if (!wrap) return;
    const panel = document.getElementById('pit-sources-panel');
    const list = document.getElementById('pit-sources-list');
    const toggle = document.getElementById('pit-sources-toggle');
    if (!sources || !Array.isArray(sources) || sources.length === 0){
      wrap.style.display = 'none';
      panel.style.display = 'none';
      if (toggle) toggle.textContent = 'Show sources';
      return;
    }
    wrap.style.display = '';
    list.innerHTML = '';
    sources.forEach((s, i) => {
      const name = s && s.source_name ? s.source_name : `Source ${i+1}`;
      const url = s && s.source_url ? s.source_url : null;
      const div = document.createElement('div');
      div.className = 'pit-source-item';
      if (url) div.innerHTML = `<a href="${safeHtml(url)}" target="_blank" rel="noopener noreferrer">${safeHtml(name)}</a>`;
      else div.textContent = name;
      list.appendChild(div);
    });
    panel.style.display = 'none';
    if (toggle) toggle.textContent = 'Show sources';
  }

  // Observe route/content changes to place UI when chat renders
  const mo = new MutationObserver(() => { if (isThreadView()) ensureUI(); });
  mo.observe(document.documentElement, { childList:true, subtree:true });
  window.addEventListener('popstate', () => setTimeout(ensureUI, 50));
  window.addEventListener('DOMContentLoaded', () => setTimeout(ensureUI, 50));

  // Intercept /ask to capture sources and update the UI
  const origFetch = window.fetch;
  window.fetch = async function(input, init){
    const res = await origFetch(input, init);
    try{
      const url = typeof input === 'string' ? input : (input && input.url);
      const method = (init && init.method) || (input && input.method) || 'GET';
      if (url && url.endsWith('/ask') && method.toUpperCase() === 'POST'){
        res.clone().json().then(data => {
          if (data && Array.isArray(data.sources)){
            try { sessionStorage.setItem('pit_last_sources', JSON.stringify(data.sources)); } catch {}
            updateUI(data.sources);
          }
        }).catch(()=>{});
      }
    }catch(_){ /* ignore */ }
    return res;
  };

  // As a fallback, on load attempt to display any stored sources (e.g., after refresh)
  try {
    const cached = sessionStorage.getItem('pit_last_sources');
    if (cached) updateUI(JSON.parse(cached));
  } catch {}
})();
