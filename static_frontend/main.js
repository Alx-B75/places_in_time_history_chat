// Frontend glue for auth, navigation, figures UI, and figure deep-link support.

(function () {
  function base() {
    const { protocol, host } = window.location;
    return `${protocol}//${host}`;
  }

  function qs(sel) {
    return document.querySelector(sel);
  }

  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(props).forEach(([k, v]) => {
      if (k === 'class') node.className = v;
      else if (k === 'html') node.innerHTML = v;
      else node.setAttribute(k, v);
    });
    children.forEach((c) => node.appendChild(c));
    return node;
  }

  function showError(id, msg) {
    const box = qs(id);
    if (!box) return;
    box.textContent = msg;
    box.style.display = 'block';
  }

  // Parse URL query params once per page
  const URL_PARAMS = new URLSearchParams(window.location.search);
  const PARAM_FIGURE = URL_PARAMS.get('figure');

  // Persist an incoming figure slug for after-login use
  function stashPendingFigure(slug) {
    if (slug) localStorage.setItem('pending_figure_slug', slug);
  }
  function popPendingFigure() {
    const v = localStorage.getItem('pending_figure_slug');
    if (v) localStorage.removeItem('pending_figure_slug');
    return v;
  }

  async function postForm(url, fields) {
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    const res = await fetch(url, { method: 'POST', body: fd });
    let body = {};
    try {
      body = await res.json();
    } catch (_) {}
    if (!res.ok) {
      const detail = body && body.detail ? body.detail : res.statusText || 'Request failed';
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return body;
  }

  function storeAuth(payload) {
    if (payload && payload.access_token) localStorage.setItem('access_token', payload.access_token);
    if (payload && payload.user_id != null) localStorage.setItem('user_id', String(payload.user_id));
    if (payload && payload.username) localStorage.setItem('username', payload.username);
  }

  async function doLogin() {
    const username = qs('#username')?.value?.trim() || '';
    const password = qs('#password')?.value || '';

    // If the user arrived with ?figure=slug, remember it before login
    if (PARAM_FIGURE) stashPendingFigure(PARAM_FIGURE);

    const resp = await postForm(`${base()}/auth/login`, { username, password });
    storeAuth(resp);
    const userId = resp.user_id || resp.id;
    if (!userId) throw new Error('Missing user_id in response');

    // After login, forward to threads with figure if we have one
    const pending = popPendingFigure();
    const suffix = pending ? `?figure=${encodeURIComponent(pending)}` : '';
    window.location.href = `${base()}/user/${userId}/threads${suffix}`;
  }

  async function doRegister() {
    const username = qs('#username')?.value?.trim() || '';
    const password = qs('#password')?.value || '';

    if (PARAM_FIGURE) stashPendingFigure(PARAM_FIGURE);

    const reg = await postForm(`${base()}/auth/register`, { username, password });
    let userId = reg.user_id || reg.id;
    if (!userId) {
      const login = await postForm(`${base()}/auth/login`, { username, password });
      storeAuth(login);
      userId = login.user_id || login.id;
    } else {
      storeAuth(reg);
    }
    if (!userId) throw new Error('Missing user_id in response');

    const pending = popPendingFigure();
    const suffix = pending ? `?figure=${encodeURIComponent(pending)}` : '';
    window.location.href = `${base()}/user/${userId}/threads${suffix}`;
  }

  // Login/register form wiring
  document.addEventListener(
    'submit',
    function (e) {
      const t = e.target;
      if (!(t instanceof HTMLFormElement)) return;
      if (t.id === 'login-form' || t.id === 'register-form') {
        e.preventDefault();
        const fn = t.id === 'login-form' ? doLogin : doRegister;
        fn().catch((err) => showError('#message', err.message || 'Request failed'));
      }
    },
    true
  );

  // Figures list page population (unchanged)
  window.addEventListener('DOMContentLoaded', async function () {
    const list = qs('#figures-list');
    if (list) {
      try {
        const res = await fetch(`${base()}/figures/`);
        const data = await res.json();
        list.innerHTML = '';
        data.forEach((item) => {
          const card = el('div', { class: 'card' });
          const img = el('img', {
            src: item.image_url || '/static/logo.png',
            alt: item.name,
            class: 'card-img',
          });
          const title = el('h3', { class: 'card-title', html: item.name });
          const meta = el('p', {
            class: 'card-meta',
            html: [item.era, item.roles].filter(Boolean).join(' • '),
          });

          // Deep link hint: pass ?figure=slug to threads page; login page
          // will preserve it and forward after auth.
          const userId = localStorage.getItem('user_id');
          const target = userId
            ? `/user/${userId}/threads?figure=${encodeURIComponent(item.slug)}`
            : `/?figure=${encodeURIComponent(item.slug)}`;

          const link = el(
            'a',
            { class: 'button', href: target },
            document.createTextNode('Ask this figure')
          );
          card.appendChild(img);
          card.appendChild(title);
          card.appendChild(meta);
          card.appendChild(link);
          list.appendChild(card);
        });
      } catch (err) {
        showError('#figures-error', err.message || 'Failed to load figures.');
      }
    }
  });

  // Expose minimal helpers for threads page to read the pending figure param
  window.__pit_params__ = {
    figureFromQuery: PARAM_FIGURE || null,
    popPendingFigure,
  };
})();
