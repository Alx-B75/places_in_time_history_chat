// admin_frontend/src/lib/apiFetch.js

function resolveApiBase() {
  const runtime = (typeof window !== 'undefined' && (window.__API_BASE || window.API_BASE)) || "";
  const env = (import.meta?.env?.VITE_API_BASE || import.meta?.env?.VITE_API_BASE_URL || "");
  const fallback = "https://places-in-time-history-chat.onrender.com";
  return (env || runtime || fallback).replace(/\/+$/, "");
}

export async function apiFetch(path, opts = {}) {
  const base = resolveApiBase();
  const isAbsolute = typeof path === "string" && /^(https?:)?\/\//i.test(path);
  const url = isAbsolute ? path : `${base}${typeof path === "string" && path.startsWith("/") ? path : `/${path}`}`;

  const headers = new Headers(opts.headers || {});
  try {
    const token = localStorage.getItem("access_token") || localStorage.getItem("token") || sessionStorage.getItem("userToken");
    if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  } catch (_) {}

  if (opts.body && typeof opts.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) {
    let msg = "";
    try { msg = await res.text(); } catch (_) {}
    throw new Error(msg || `Request failed: ${res.status} ${res.statusText}`);
  }
  return res;
}

export const API_BASE = resolveApiBase();
