> **Copyright © 2025 Nexedi SA.** Developed by Boxiang Sun at Nexedi and published with Nexedi's permission.
> Originally hosted on Nexedi's GitLab; full commit history preserved.

# rag-vue-ui

The first version of a ChatGPT-style documentation assistant: a **Vue 3 + TypeScript** front end on top of a **RAG backend** (FastAPI, Chroma, self-hosted llama.cpp models).

The same backend later got a RenderJS front end: see [rjs-chat-ui](https://github.com/Daetalus/rjs-chat-ui), which is the more complete version.

<!-- TODO: add a screenshot of the chat UI here -->

## What's inside

- **Front end** (`src/`): Vue 3 + Vite + TypeScript. Chat container with auto-scroll, prompt input, Markdown and code-block rendering, collapsible sidebar with chat history, login screen.
- **Backend** (`backend/`): FastAPI with JWT auth and SQLite chat history; answers streamed over Server-Sent Events.
- **Retrieval experiments**: the backend contains three RAG implementations that were compared during development:
  - `rag_langchain.py`: hybrid retrieval (dense + BM25 + title index), the version carried over to rjs-chat-ui
  - `rag_haystack.py`: the same idea built with Haystack (pipeline diagram in `backend/haystack_pipeline.png`)
  - `rag_system.py`: an early LlamaIndex prototype

## Getting started

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # set LLM_BASE_URL, EMBED_BASE_URL, SECRET_KEY
python add_nexedi_docs.py         # build the document vector store
python add_nexedi_docs_title.py   # build the title index
uvicorn main:app --reload
```

### Front end

```bash
npm install
npm run dev
```

<!-- TODO: check the commands and the backend URL used by the front end -->
