Running the manual smoke test (smoke-admin)

This folder contains a manual smoke test script: `scripts/smoke.py`.
It is intended to be run locally or in a pre-production environment using real provider API keys.

What it validates
- PATCH /admin/llm to switch LLM runtime configuration.
- GET /admin/llm/health to verify the runtime provider and model respond.
- POST /guest/start and POST /guest/ask to validate guest flows.
- POST /auth/register and POST /guest/upgrade to validate guest→user migration and thread/message migration.

IMPORTANT: This script contacts live LLM providers (OpenAI/OpenRouter) and requires real API keys. Do NOT run it on CI or in environments without proper secrets.

Quick usage (Unix / macOS / WSL / CI)

- Put environment variables in a file named `.env` at the repo root (optional). Example variables used by the script:
  - OPENAI_API_KEY
  - OPENROUTER_API_KEY
  - ADMIN_TOKEN       # admin bearer token for PATCH /admin/llm
  - VITE_API_BASE     # e.g. http://127.0.0.1:8000
  - Any other auth vars your local server expects

- From the repository root run:

  make smoke-admin

This Makefile target will source `.env` if present and run the smoke script with the system `python`.

Quick usage (Windows PowerShell)

- Create a PowerShell-style environment or use a `.env` parser. One quick way to run with `.env` in PowerShell:

  Get-Content .env | ForEach-Object { if ($_ -match "^\s*#") { return } ; $parts = $_ -split "=",2 ; if ($parts.Count -eq 2) { $name = $parts[0].Trim(); $val = $parts[1].Trim(); Set-Item -Path Env:\$name -Value $val } }
  python scripts/smoke.py

- Or set required variables manually in PowerShell before running:

  $env:ADMIN_TOKEN = "your_admin_token_here"
  $env:OPENAI_API_KEY = "sk-..."
  python scripts/smoke.py

Notes
- The script is intentionally manual and uses real provider keys. Do not check in secrets.
- If you want a CI-safe version, convert the script into a pytest test that mocks the LLM client responses instead of calling real providers.

Contact
- If you hit problems, run the admin LLM health endpoint manually first to ensure the runtime is responsive:
  curl -H "Authorization: Bearer <ADMIN_TOKEN>" http://127.0.0.1:8000/admin/llm/health

