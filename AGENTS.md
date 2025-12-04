# Agent Guidelines

## Commands
- **Single Test:** `pytest tests/test_filename.py::test_function_name` (or `-k "pattern"`)
- **Run All Tests:** `pytest -q`
- **Frontend Dev:** `cd frontend && npm run dev` (Port: 5173)
- **Frontend Check:** `cd frontend && tsc --noEmit` (Type check only)
- **Backend Dev:** `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- **Full Build:** `docker compose up -d --build` (API: 8000, UI: 5173)

## Code Standards
- **Python:** FastAPI, Pydantic v2, SQLAlchemy. Use `str | None` for optionals. `snake_case`.
- **React:** TypeScript, Vite, Tailwind. Use functional components & named exports. `camelCase`.
- **Imports:** Verify library availability in `backend/requirements.txt` or `package.json` before use.
- **Config:** Manage env vars via `backend/app/settings.py` (Pydantic BaseSettings with Field()).
- **Async:** Use `async def` and `httpx.AsyncClient` for I/O in backend. All endpoint handlers are async.
- **Error Handling:** Wrap risky operations in try/except. Log errors with `print()` (FastAPI logs to stdout).
- **Types:** Backend uses Pydantic `BaseModel` for request/response schemas. Frontend uses TypeScript interfaces.

## Protocols
- **Paths:** USE ABSOLUTE PATHS for all file operations (Root: `/home/bogus/Skrypty/kartoteka-2.0`).
- **Testing:** Verify changes with existing tests. Do not modify `tests/` unless necessary.
- **Safety:** Read files before editing. Check for side effects. Never break existing functionality.
- **DB:** SQLite via SQLAlchemy. Schema in `backend/app/db.py`. Use `session.commit()` after changes.

## Key Logic (Do Not Break)
- **Card Analysis:** Uses "Combined Intelligence" (OpenAI Vision + Symbol Matcher + OCR). See `backend/app/analysis/pipeline.py`.
- **Shoper Sync:** Category tree creation (`POST /shoper/create-category-tree`) uses `shoper_sync.py` with deduplication and rich content generation.
- **Batch Scanning:** Warehouse codes are allocated per-batch (`get_next_free_location_for_batch`).
- **Mobile:** Camera requires HTTPS context.
- **Pricing:** Uses EUR→PLN conversion (`eur_pln_rate`), multipliers, and variant detection. Min prices differ by rarity.
- **Furgonetka Integration:** Uses OAuth 2.0 with token persistence (`FurgonetkaToken`). Auto-syncs shipments in background via `_background_sync_furgonetka`. See `backend/app/furgonetka_client.py` and `FURGONETKA_SETUP.md`.
