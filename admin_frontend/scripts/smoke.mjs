import fetch from 'node-fetch';
const token = process.env.ADMIN_TOKEN;
const base = process.env.VITE_API_BASE || process.env.BACKEND_BASE || "";
if (!token) { console.error('Missing ADMIN_TOKEN'); process.exit(2); }
async function main() {
  try {
  const res = await fetch(base + '/admin/llm/health', {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error(await res.text());
    const json = await res.json();
    console.log('LLM Health:', json);
    if (!json.ok) process.exit(1);
  } catch (e) {
    console.error('Smoke test failed:', e);
    process.exit(1);
  }
}
main();
