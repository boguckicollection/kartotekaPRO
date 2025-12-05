# Agent Guidelines

## Commands
- **Test:** `pytest -q` (All) | `pytest tests/test_file.py::test_func` (Single) | `pytest -m integration` (Integration)
- **Dev:** Backend: `cd backend && uvicorn app.main:app --reload` | Frontend: `cd frontend && npm run dev`
- **Build:** `docker compose up -d --build` (Ports: 5173/8000/8001) | Type Check: `cd frontend && tsc --noEmit`

## Code Style
- **Python:** `snake_case`, type hints, Pydantic BaseModel, async/await with httpx, try/except logging via print()
- **TypeScript:** `camelCase`, strict mode, React functional components, Tailwind CSS
- **Imports:** Verify dependencies in requirements.txt/package.json before use
- **Paths:** Always use absolute paths. Root: `/home/gumcia/kartotekaPRO`
- **Error Handling:** Wrap risky operations in try/except blocks, log errors to stdout

## Application Modules
- **Scanner App:** React/Vite frontend (5173) + FastAPI backend (8000) for card scanning/analysis
- **Collector App:** Standalone Python server (8001) for data collection and legacy operations

## Critical Logic (DO NOT BREAK)
- **Analysis Pipeline:** Combined AI (OpenAI+Symbol+OCR) in `backend/app/analysis/pipeline.py`
- **Shoper Integration:** Category trees and deduplication in `shoper_sync.py`
- **Pricing:** EUR→PLN conversion with rarity-based minimums
- **Furgonetka:** OAuth 2.0 token persistence and background sync
