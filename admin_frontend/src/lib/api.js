export async function apiFetch(path, opts = {}) {
  const base = (import.meta?.env?.VITE_API_BASE || "").replace(/\/+$/, "");
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = new Headers(opts.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
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
