Places in Time – History Chat
=============================

Version 0 (v0) – 2025-11-12
----------------------------
This milestone delivers an end-to-end user flow:
- Register/Login with consent checkboxes and policy links
- Browse figures (alphabetical), favorite them, and start a new thread from a figure
- Chat in a thread with a centered figure hero; rename or delete threads
- Dashboard shows a Quick Start section powered by your favorites

What’s included
---------------
- Backend: FastAPI, SQLAlchemy, JWT auth, `/user/favorites` endpoints, thread CRUD, health
- Frontend: React + Vite SPA, routes for Dashboard, Threads, ThreadView, Figures, Login/Register, Policy pages
- Policies: `/policy/gdpr` and `/policy/ai`
- Tests: favorites API flow, existing suite green

Dev quick start (local)
-----------------------
1) Backend
	- Install Python 3.12 and create a venv
	- pip install -r requirements.txt
	- uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

2) Frontend
	- cd admin_frontend
	- npm install
	- npm run dev -- --host 127.0.0.1

Open http://127.0.0.1:5173

Notes
-----
- Favorites are per-user and appear on the Dashboard.
- In development, the Vite proxy is configured for `/user` so favorites calls reach the backend.
- Thread IDs are internal and not shown in the UI.

Roadmap (post v0)
-----------------
- Expand moderation and RAG source transparency
- Surface citations and source cards where available
- Additional tests and accessibility polish

Recent RAG & Operational Additions (2025-11-15)
----------------------------------------------
- Admin per-figure RAG detail page with context listing, ingest & embed actions.
- Document upload endpoint (`/admin/rag/figure/{slug}/upload`) supporting TXT/MD/PDF/HTML/DOCX.
- Automatic chunking, dedupe, and background embedding jobs with progress polling.
- Sanitized `/health` output (no DB paths; boolean flags only).
- Dev-only user seeding & debug routes; single static mount.
- Per-message source citations (collapsed “View sources (n)” toggles in threads).

See `docs/RAG_UPLOAD_AND_HEALTH.md` for full specification.
