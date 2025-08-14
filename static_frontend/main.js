// Frontend glue for auth, navigation, and figures UI.

(function () {
  function base() {
    const { protocol, host } = window.location;
    return `${protocol}//${host}`;
  }

  function qs(sel) { return document.querySelector(sel); }
  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(props).forEach(([k, v]) => {
      if (k === 'class') node.className = v;
      else if (k === 'html') node.innerHTML = v;
      else node.setAttribute(k, v);
    });
    children.forEach(c => node.appendChild(c));
    return node;
  }

  function showError(id, msg) {
    const box = qs(id);
    if (!box) return;
    box.textContent = msg;
    box.style.display = 'block';
  }

  async function postForm(url, fields) {
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    const res = await fetch(url, { method: 'POST', body: fd });
    let body = {};
    try { body = await res.json(); } catch (_) {}
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
    const resp = await postForm(`${base()}/login`, { username, password });
    storeAuth(resp);
    const userId = resp.user_id || resp.id;
    if (!userId) throw new Error('Missing user_id in response');
    window.location.href = `${base()}/user/${userId}/threads`;
  }

  async function doRegister() {
    const username = qs('#username')?.value?.trim() || '';
    const password = qs('#password')?.value || '';
    const reg = await postForm(`${base()}/register`, { username, password });
    let userId = reg.user_id || reg.id;
    if (!userId) {
      const login = await postForm(`${base()}/login`, { username, password });
      storeAuth(login);
      userId = login.user_id || login.id;
    } else {
      storeAuth(reg);
    }
    if (!userId) throw new Error('Missing user_id in response');
    window.location.href = `${base()}/user/${userId}/threads`;
  }

  document.addEventListener('submit', function (e) {
    const t = e.target;
    if (!(t instanceof HTMLFormElement)) return;
    if (t.id === 'login-form' || t.id === 'register-form') {
      e.preventDefault();
      const fn = t.id === 'login-form' ? doLogin : doRegister;
      fn().catch(err => showError('#message', err.message || 'Request failed'));
    }
  }, true);

  window.addEventListener('DOMContentLoaded', async function () {
    // If we're on figures page, fetch and render
    const list = qs('#figures-list');
    if (list) {
      try {
        const res = await fetch(`${base()}/figures/`);
        const data = await res.json();
        list.innerHTML = '';
        data.forEach(item => {
          const card = el('div', { class: 'card' });
          const img = el('img', { src: item.image_url || '/static/logo.png', alt: item.name, class: 'card-img' });
          const title = el('h3', { class: 'card-title', html: item.name });
          const meta = el('p', { class: 'card-meta', html: [item.era, item.roles].filter(Boolean).join(' • ') });
          const link = el('a', { class: 'button', href: `/figures/${item.slug}` }, document.createTextNode('Ask this figure'));
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
})();
