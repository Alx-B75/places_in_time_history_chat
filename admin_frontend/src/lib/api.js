export async function apiFetch(path, opts = {}) {
  const runtimeBase = (typeof window !== 'undefined' && (window.__API_BASE || window.API_BASE)) || "";
  const envBase = (import.meta?.env?.VITE_API_BASE || "");
  // Final fallback: known backend host (kept minimal to unblock prod)
  const fallbackBase = "https://places-backend-o8ym.onrender.com";

  const base = (envBase || runtimeBase || fallbackBase).replace(/\/+$/, "");

  const token = typeof window !== "undefined" ? (localStorage.getItem("token") || localStorage.getItem("access_token")) : null;
  const headers = new Headers(opts.headers || {});
  if (token && !headers.has('Authorization')) headers.set("Authorization", `Bearer ${token}`);
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  return fetch(url, { ...opts, headers });
}

export async function patchLLMConfig(payload) {
  const res = await apiFetch('/admin/llm', {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
