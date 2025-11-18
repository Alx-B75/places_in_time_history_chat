const API_BASE = (import.meta?.env?.VITE_API_BASE_URL || import.meta?.env?.VITE_API_BASE || "").replace(/\/+$/, "");

export async function apiFetch(path, opts = {}) {
  const isAbsolute = typeof path === 'string' && /^(https?:)?\/\//i.test(path);
  const url = isAbsolute
    ? path
    : `${API_BASE}${(typeof path === 'string' && path.startsWith('/')) ? path : `/${path}`}`;

  const headers = new Headers(opts.headers || {});

  // Attach bearer if present (support both keys)
  try {
    const token = localStorage.getItem('access_token') || localStorage.getItem('token') || sessionStorage.getItem('userToken');
    if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
  } catch (_) { /* ignore */ }

  // Default JSON content-type if body is a string and no content-type yet
  if (opts.body && typeof opts.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) {
    let msg = '';
    try { msg = await res.text(); } catch (_) { /* ignore */ }
    throw new Error(msg || `Request failed: ${res.status} ${res.statusText}`);
  }
  return res;
}

export { API_BASE };
