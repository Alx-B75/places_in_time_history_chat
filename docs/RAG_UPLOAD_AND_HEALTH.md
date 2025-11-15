RAG Upload & Health / Environment Controls
=========================================

Overview
--------
Recent additions extend Retrieval-Augmented Generation (RAG) management and tighten operational hygiene:

1. Document upload (TXT / MD / PDF / HTML / DOCX) with automatic chunking, dedupe, and optional embedding.
2. Background embedding jobs with status polling.
3. Sanitized `/health` output (no raw DB URLs/paths).
4. Dev-only debug routes and user seeding.

Endpoints
---------
`POST /admin/rag/figure/{slug}/upload`
- Multipart field name: `files` (repeatable)
- Query / form flags:
  - `auto_embed` (bool, default true) – embed small uploads immediately.
  - `force_background` (bool, default false) – force queue even for small files (testing).
  - `max_chunks` (int, default 50) – cap chunk ingestion per file.
Response JSON:
```
{
  "total_created": <int>,
  "total_skipped": <int>,
  "total_embedded": <int>,
  "files": [
    {"name": "sample.txt", "size": 12345, "created": 10, "skipped": 0, "embedded": 10, "detail": null }
  ],
  "job_id": "<optional string if background queued>"
}
```

`GET /admin/rag/upload-jobs/{job_id}` (dev/admin)
```
{
  "job_id": "...",
  "status": "queued|running|done",
  "done": <int>,
  "total": <int>
}
```

Chunking & Dedupe
-----------------
Chunk size ~1600 chars with 200 char overlap. Dedupe key = normalized chunk text per figure (content-only), preventing redundant vector growth across repeated uploads.

Supported File Types
--------------------
| Type  | Parser            | Notes |
|-------|-------------------|-------|
| .txt/.md | UTF-8 decode        | Replace errors; trim whitespace |
| .html/.htm | Lightweight tag strip | Strips scripts/styles; collapses whitespace |
| .pdf   | PyMuPDF then pdfminer | Fallback sequence for robustness |
| .docx  | python-docx       | Paragraph aggregation; whitespace normalization |

Background Embedding Trigger
----------------------------
- Large single file (>5MB) OR cumulative request size (>10MB) OR `force_background=true`.
- Immediate response includes `job_id`; vectors added asynchronously.
- UI polls every ~1.2s until `status` becomes `done`.

Health Endpoint (Sanitized)
---------------------------
`GET /health` now returns:
```
{
  "status": "ok",
  "chat_db_ok": true,
  "figures_db_ok": true,
  "keys": {
    "openai_configured": true,
    "openrouter_configured": false
  },
  "rag": { "enabled": true, "ok": true, "detail": null },
  "guest_prompt_debug": false,
  "environment": "dev"
}
```
Sensitive connection details (paths, URLs) are intentionally omitted.

Environment Controls
--------------------
ENVIRONMENT variable (default `dev`) governs:
- Dev-only user seeding (`admin@example.com`, `sample@example.com`).
- Debug routes: `/_debug/routes` and `/debug/routes` only registered in dev.
- GET `/login` and `/register` redirect to Vite SPA in dev; serve static HTML otherwise.

Static Mount
------------
Single mount: `/static` → `static_frontend` (HTML-enable) to avoid double registrations.

Security & Operational Rationale
--------------------------------
- Removing DB URL leakage reduces accidental exposure of filesystem paths in logs / client tooling.
- Background jobs prevent request timeouts for large uploads while delivering progress feedback.
- Content-based dedupe prevents vector store bloat and redundant embeddings cost.
- Dev-only seeding avoids polluting production user tables.

Testing Notes
-------------
- Upload tests monkeypatch Chroma collection to avoid external dependencies and use `force_background=true` for deterministic `job_id` return.
- Health tests only assert non-empty JSON; shape preserved for backward compatibility with future additions.

Future Enhancements
-------------------
- Add DOCX table extraction & hyperlink metadata.
- Persist upload jobs (currently in-memory) and add cancellation endpoint.
- Per-file chunk stats in response (min/median/max chunk length).

Last Updated: 2025-11-15