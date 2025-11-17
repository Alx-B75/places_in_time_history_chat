// Global fetch base prefixer for relative API paths
// Ensures calls like fetch('/auth/login') hit the backend when deployed separately
(function(){
  if (typeof window === 'undefined' || typeof window.fetch !== 'function') return;
  const BASE = (import.meta?.env?.VITE_API_BASE_URL || import.meta?.env?.VITE_API_BASE || '').replace(/\/+$/, '');
  if (!BASE) return; // nothing to do
  const origFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    try {
      // If input is Request, derive url
      let url = typeof input === 'string' ? input : (input && input.url);
      if (typeof url === 'string' && url.startsWith('/')) {
        const prefixed = `${BASE}${url}`;
        if (typeof input === 'string') {
          input = prefixed;
        } else {
          // new Request with same init
          input = new Request(prefixed, input);
        }
      }
    } catch (_) { /* ignore */ }
    return origFetch(input, init);
  };
})();
