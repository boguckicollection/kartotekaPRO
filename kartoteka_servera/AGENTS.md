# Kartoteka Development Guidelines

## Workflows
- **Run Server**: `uvicorn server:app --reload` or `python server.py`
- **Test All**: `pytest`
- **Test Single**: `pytest tests/api/test_cards.py::test_collection_crud_lifecycle`
- **Sync Catalog**: `python sync_catalog.py --limit 25` (Requires RAPIDAPI_KEY)

## Code Standards
- **Stack**: Python 3.10+, FastAPI, SQLModel (SQLite), Jinja2 templates.
- **Imports**: `from __future__ import annotations` first. Group: stdlib, 3rd-party, local.
- **Typing**: Strict hints (`str | None`, `list[int]`). SQLModel: `Field(default=None)` for optional cols.
- **Naming**: `snake_case` for functions/vars, `PascalCase` for Classes/Models.
- **Database**: Always use context manager: `with session_scope() as session:`.
- **Error Handling**: Raise `fastapi.HTTPException` for API errors. Log warnings via `logger`.
- **Structure**: Routes in `kartoteka_web/routes/`. Logic in `kartoteka_web/services/`.
- **Auth**: Use `_resolve_request_user(request)` for templates, `get_current_user` for API.
