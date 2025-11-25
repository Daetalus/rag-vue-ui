# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Vue 3 + Vite frontend for the Nexedi RAG experience (see `README.md` for UI architecture).
- `backend/`: Python RAG backend built with FastAPI, LangChain, and Chroma.
  - `backend/main.py`: FastAPI app and Typer CLI (`serve` entrypoint).
  - `backend/auth.py`, `backend/crud.py`, `backend/database.py`, `backend/schemas.py`: JWT auth helpers, SQLAlchemy models, and Pydantic schemas.
  - RAG implementation: `backend/rag_langchain.py` (active) plus `backend/rag_haystack.py` (reference) and helpers like `backend/custom_embeddings.py`.
  - Utilities: ingestion scripts (`backend/add_document.py`, `backend/vectorize_html.py`), assets (`backend/haystack_pipeline.png`).
  - Data: SQLite DB (`backend/chat.db`) and vector stores (`backend/nexedi_doc_vec_*`).

## Build, Test, and Development Commands
- Frontend
  - Install: `npm install`
  - Run dev server: `npm run dev`
  - Build: `npm run build`
- Backend
  - Create venv: `python -m venv .venv && source .venv/bin/activate`
  - Install deps: `pip install -r backend/requirements.txt`
  - Run API (CLI): `python backend/main.py serve`
  - Run API (dev): `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
  - Smoke test: `curl http://localhost:8000/docs`

## Coding Style & Naming Conventions
- Frontend: Vue 3 composition API with TypeScript; keep components focused and leverage composables/stores under `src/stores/`.
- Backend: Python 3.10+, PEP 8, 4-space indentation. Snake_case for functions/modules, PascalCase for Pydantic & ORM models, type hints everywhere.
- Group imports (stdlib, third-party, local) and keep modules cohesive (e.g., DB logic in `database.py`, HTTP handlers in `main.py`).

## Testing Guidelines
- Frontend: prefer component/unit tests with Vitest; add e2e coverage as needed.
- Backend: `pytest` with `httpx.AsyncClient` for FastAPI routes. Place tests in `backend/tests/` (`test_*.py`).
- Run backend tests: `pytest -q backend/tests`
- Suggested coverage: `/token` success/401 paths, session CRUD, RAG streaming happy-path (mock external calls).

## Commit & Pull Request Guidelines
- Write imperative commit titles (≤72 chars) with optional explanatory body.
- Reference scope/intent, linked issues, testing steps, and any indexing/config impacts.
- Keep frontend/backend changes scoped; document migrations (DB/index) in PR description.

## Security & Configuration Tips
- Backend secrets (`SECRET_KEY`, token TTL, model endpoints) should come from environment variables—never commit them.
- Configure CORS appropriately for deployment (currently permissive for local dev).
- SQLite (`backend/chat.db`) is fine locally; plan to move to a multi-user database in production.
- Review vector store paths before committing large artefacts; use `.gitignore` where needed.
