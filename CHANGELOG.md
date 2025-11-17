# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [v0] - 2025-11-12
### Added
- Figure selection flow with alphabetical listing and fallback logo.
- Favorites: persist per user with `/user/favorites` (GET/POST/DELETE), Dashboard “Quick Start” grid.
- Thread management: delete with confirm, rename, opening question preview in list.
- UI: wider banners/logo alignment, consistent thumbnails, textarea containment, better button contrast.
- Login/Registration pages with even banners and consent checkboxes.
- Policy pages: `/policy/gdpr` and `/policy/ai` with in-app links from Register.
- Dev proxy for `/user` to ensure favorites hit backend in dev.

### Changed
- Thread creation accepts and stores `figure_slug`; ThreadView centers figure hero and hides internal thread id.
- Consolidated favorites endpoints to stable `/user/favorites` to avoid slug route collisions.

### Tests
- Added `tests/test_favorites_api.py` covering add/list/remove with compatibility login/register.

### Notes
- This marks the “Version 0” milestone for the end-to-end user flow: register/login, figure browse, favorite, start thread, chat, and manage threads.

## [Unreleased]
### Added
- RAG admin per-figure detail view with context CRUD, ingest and embed endpoints.
- Document upload (`/admin/rag/figure/{slug}/upload`) for TXT/MD/PDF/HTML/DOCX with chunking & dedupe.
- Background embedding jobs + status polling endpoint (`/admin/rag/upload-jobs/{job_id}`).
- Per-chat message source citations (collapsed toggle in thread views).
### Changed
- `/health` sanitized (no raw DB URLs; boolean flags and status only).
- Single `/static` mount retained; duplicate removed.
- Dev-only seeding (admin@example.com, sample@example.com) gated by `ENVIRONMENT=dev`.
- Debug routes gated to dev only.
### Security
- Eliminated leakage of database file paths in health response.
### Docs
- Added `docs/RAG_UPLOAD_AND_HEALTH.md` describing upload workflow, background jobs, health output, environment gating.

## [0.1.0] - 2025-08-13
### Added
- Initial CHANGELOG tracking.
- Passing tests for:
  - `/register` and `/login` flow using typed credentials via dependency.
  - `/threads` creation returns `thread_id`, `user_id`, `title`.
  - `/download_db` streams figures database file as attachment.
- New `/threads` endpoint in `chat.py`.
- New `data.py` router exposing `/download_db`.

### Changed
- `auth.py` updated to accept JSON or form credentials with typed validation.
- `main.py` now includes only router-driven `/login` and `/register` (inlined duplicates removed).
- `chat.py` thread creation uses `schemas.ThreadCreate` to match `crud.create_thread` signature.
- Tests generate unique usernames to avoid collisions across runs.

### Fixed
- `TypeError` from calling `create_thread()` with wrong argument shape.
- 422 errors on JSON credentials by centralizing validation in dependency.
- `/download_db` 404 in tests by isolating `DATA_DIR` via a tempdir fixture.

---

## [0.0.1] - 2025-08-12
### Added
- Initial refactor scaffolding on branch `fix/refactor-recovery`.
- Routers package layout under `app/routers/` (`auth`, `chat`, `figures`, `ask` present/being wired).
- Database modules for chat DB and figures DB.
- Basic static frontend mounting and CORS settings.

### Known Issues
- Duplicate `/login` and `/register` definitions lived both in `main.py` and `auth.py`.
- Some endpoints expected form-only payloads leading to 422s for JSON bodies.
- Vector dependencies pulled during import, increasing test fragility.

---

## [0.0.0] - 2025-08-11
### Added
- Baseline import and parity target with Repo A: `places_in_time_chatbot` at `ef78dfc97d95bcef41955ec12a2348f0b4ea6423`.
- Core FastAPI app structure (`app/main.py`), models, schemas, CRUD, and routers.
- Health endpoint and static file serving.

### Notes
- This version is the refactor starting line intended to reproduce Repo A behavior with cleaner structure.
