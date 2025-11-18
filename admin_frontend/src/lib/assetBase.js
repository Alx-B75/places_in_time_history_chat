export function asset(path) {
  const runtime = (typeof window !== 'undefined' && (window.__ASSET_BASE || window.ASSET_BASE)) || '';
  const env = (import.meta?.env?.VITE_ASSET_BASE || '');
  // Prefer explicit overrides; fallback to main backend host
  let base = (env || runtime || 'https://places-in-time-history-chat.onrender.com').replace(/\/+$/, '');
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}
