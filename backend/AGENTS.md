# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: FastAPI app and `typer` CLI (`serve`).
- `auth.py`, `crud.py`, `database.py`, `schemas.py`: Auth, data access, SQLite models, and Pydantic schemas.
- RAG engines: `rag_langchain.py`, `rag_haystack.py` and helpers like `custom_embeddings.py`.
- Scripts/assets: `add_document.py`, `vectorize_html.py`, `haystack_pipeline.png`.
- Data: `chat.db` (SQLite), and vector stores under `nexedi_doc_vec_haystack_v3/`.

## Build, Test, and Development Commands
- Create venv: `python -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run API (CLI): `python main.py serve`
- Run API (dev): `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Quick smoke: `curl http://localhost:8000/docs` to open Swagger UI.

## Coding Style & Naming Conventions
- Python 3.10+; follow PEP 8 with 4‑space indentation.
- Names: snake_case for functions/modules, PascalCase for Pydantic/SQLAlchemy models.
- Use type hints and concise docstrings; group imports (stdlib, third‑party, local).
- Keep modules focused (e.g., DB in `database.py`, HTTP in `main.py`).

## Testing Guidelines
- Framework: `pytest` with `httpx` `AsyncClient` for FastAPI endpoints.
- Location: `tests/` with files named `test_*.py` (add if missing).
- Run tests: `pytest -q`; target core coverage for `auth.py`, `crud.py`, and API routes.
- Example: test `/token` happy/invalid paths; seed with a user via CRUD.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise summary (≤72 chars), details in body.
- Style mirrors existing history (e.g., “Add langchain RAG backend”, “Improve prompts”).
- PRs include: scope/intent, linked issues, testing steps, breaking changes, and any config/indexing impacts.

## Security & Configuration Tips
- Secrets: set `SECRET_KEY` via env; do not commit secrets. Consider `ALGORITHM`, token TTL as envs.
- Models/LLM: make `LLM_URL`, `LLM_MODEL`, `EMBED_MODEL` configurable via env for deployments.
- CORS: currently wide‑open for dev; restrict origins/methods in prod.
- Data: SQLite at `sqlite:///./chat.db` is fine for local; upgrade to a server DB for concurrency.

