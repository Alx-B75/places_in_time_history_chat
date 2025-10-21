export async function apiFetch(path, opts = {}) {
  const base = (import.meta.env.VITE_API_BASE || "").replace(/\/+$/, "");
  const token = localStorage.getItem("token");
  const headers = new Headers(opts.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${base}${path.startsWith("/") ? path : `/${path}`}`,
    { ...opts, headers });
}
