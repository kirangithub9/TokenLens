

# 🔍 TokenLens



**TokenLens** is a full-stack AI chat application powered by local Ollama models (Gemma / GPT).  
It features a **two-layer memory system**, **PDF RAG with semantic search**, **live token cost analytics**, and a clean React 19 + Vite 8 frontend.



## 🌟 Overview

TokenLens is a monorepo AI chat application built around local **Ollama** models. It gives you:

- A **Gemma 3:4B** (or OpenAI GPT) chat interface with multi-session support
- **Two-layer memory** — short-term turn buffer + LLM-summarised long-term memory per session
- **PDF upload + RAG** — upload a PDF, ask questions, get semantically grounded answers
- **Token & cost analytics** — live INR/USD cost tracking per message across models
- A **metrics dashboard** built with Recharts for visualising usage over time
- **SQLite** locally or **Supabase** (PostgreSQL) in production — zero config switch

---

## ✨ Features

| Feature | Details |
|---|---|
| 🧠 **Two-Layer Memory** | Short-term turn buffer + async LLM summary condensed into long-term memory per session |
| 📄 **PDF RAG** | Upload PDFs (≤ 3 MB); semantic search via `nomic-embed-text` embeddings, falls back to keyword search |
| 🖼️ **Multimodal Input** | Images (PNG, JPG, GIF, WebP, SVG) converted to text semantics before memory storage |
| 💬 **Multi-Session Chat** | Unlimited named conversations stored in `localStorage`; sessions pruned automatically on backend |
| 📊 **Token Cost Dashboard** | Live per-message token count + INR/USD cost for Gemma and GPT-5 Nano models |
| 🔀 **Model Switching** | Switch between `gemma3:4b` (local Ollama) and `gpt-5-nano` (OpenAI) mid-conversation |
| 🗄️ **Dual Database** | SQLite for local dev, Supabase/PostgreSQL for production — set `DATABASE_URL` to switch |
| 🔴 **Redis Cache** | Optional Redis session cache; defaults to in-memory |
| ⚡ **FastAPI + Uvicorn** | Async Python backend with CORS, background pruning, and lifespan management |
| 🌗 **Light / Dark Mode** | Theme toggle built into the UI |

---

## 🏗️ Architecture

```
TokenLens/
├── Frontend/          # React 19 + Vite 8
│   ├── src/
│   │   ├── App.jsx          # Main chat UI + model selector + file upload
│   │   ├── MetricsView.jsx  # Token cost analytics dashboard (Recharts)
│   │   ├── assets/
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
│
└── Backend/           # Python FastAPI  (v3.0.0 — Gemma4 Chat Service)
    ├── main.py              # App entry point + all route definitions
    ├── memory/              # Two-layer memory system
    │   ├── __init__.py
    │   ├── manager.py       # add_turn_and_get_prompt, record_assistant_reply
    │   └── store.py         # Session store + prune_stale_sessions
    ├── database.py          # SQLAlchemy models, SQLite/Postgres helpers
    ├── requirements.txt
    └── .env.example         # Copy → .env and fill in values
```

```
Browser  (localhost:5173)
       │
       │  REST / JSON
       ▼
FastAPI Backend  (localhost:8000)
       │
       ├── Two-Layer Memory  ← short-term buffer + LLM summary
       ├── PDF RAG           ← PyPDF2 + nomic-embed-text cosine search
       ├── Ollama Client     ← httpx → gemma3:4b (or nomic-embed-text)
       ├── OpenAI Client     ← optional, activated by model selector
       └── Database          ← SQLite (dev)  |  Supabase/Postgres (prod)
```

---

## 🔧 Prerequisites

| Tool | Min Version | Check | Install |
|---|---|---|---|
| **Git** | 2.x | `git --version` | [git-scm.com](https://git-scm.com) |
| **Node.js** | 18+ | `node --version` | [nodejs.org](https://nodejs.org) |
| **npm** | 9+ | `npm --version` | Bundled with Node.js |
| **Python** | 3.10+ | `python3 --version` | [python.org](https://python.org) |
| **pip** | 23+ | `pip --version` | Bundled with Python |
| **Ollama** | latest | `ollama --version` | [ollama.com](https://ollama.com) |

### Pull the required Ollama models

```bash
# Chat model (required)
ollama pull gemma3:4b

# Embedding model for semantic PDF search (optional, falls back to keyword)
ollama pull nomic-embed-text
```

---

## 🚀 Getting Started

### 1. Fork the Repository

Go to **[https://github.com/alumnx-ai-labs/TokenLens](https://github.com/alumnx-ai-labs/TokenLens)** and click **Fork** (top-right). This creates your personal copy on GitHub.

### 2. Clone the Repository


# Replace YOUR_USERNAME with your GitHub username
git clone https://github.com/YOUR_USERNAME/TokenLens.git
cd TokenLens

# Keep your fork in sync with the upstream repo
git remote add upstream https://github.com/alumnx-ai-labs/TokenLens.git

### 3. Backend Setup

#### Step 1 — Navigate to Backend


cd Backend


#### Step 2 — Create a virtual environment


# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate.bat

# Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1
```



#### Step 3 — Install dependencies

pip install -r requirements.txt


#### Step 4 — Configure environment variables

# Copy the provided example file
cp .env.example .env
```

Then open `.env` and fill in at minimum the **required** fields (see [Environment Variables](#-environment-variables) below).

#### Step 5 — Start the backend

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> ✅ Backend running at **[http://localhost:8000](http://localhost:8000)**  
> ✅ Swagger docs at **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

### 4. Frontend Setup

> Open a **new terminal** — keep the backend running.

#### Step 1 — Navigate to Frontend

```bash
cd Frontend
```

#### Step 2 — Install dependencies

```bash
npm install
```

#### Step 3 — Configure environment

Create a `.env` file in the `Frontend/` folder:

```bash
# Frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

> Note: The variable name is `VITE_API_BASE_URL` (not `VITE_API_URL`).

#### Step 4 — Start the dev server

```bash
npm run dev
```

> ✅ Frontend running at **[http://localhost:5173](http://localhost:5173)**

---

## ⚙️ Environment Variables

### Backend — `Backend/.env`

Copy `Backend/.env.example` to `Backend/.env` and fill in the values:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OLLAMA_HOST` | ✅ | — | Ollama server URL e.g. `http://localhost:11434` |
| `OLLAMA_MODEL` | ✅ | — | Model name e.g. `gemma3:4b` |
| `OLLAMA_API_KEY` | No | `""` | API key if your Ollama endpoint requires one |
| `ALLOWED_ORIGINS` | No | `http://localhost:5173` | Comma-separated CORS allowed origins |
| `OLLAMA_EMBED_MODEL` | No | `nomic-embed-text` | Embedding model for semantic PDF search |
| `OPENAI_API_KEY` | No | `""` | Required only if user selects GPT model in UI |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model to use |
| `DATABASE_URL` | No | SQLite `gemma_chat.db` | Supabase/Postgres URI for production |
| `PORT` | No | `8000` | Server port |
| `USD_TO_INR` | No | `85.0` | Exchange rate for cost display |
| `CACHE_TYPE` | No | `in_memory` | Session cache: `in_memory` or `redis` |


**Minimal `.env` for local development:**

```dotenv
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
```

### Frontend — `Frontend/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | No | `http://localhost:8000` | Backend API base URL |

---

## ▶️ Running the Project

Run both services in two separate terminals:

**Terminal 1 — Backend:**

```bash
cd Backend
source venv/bin/activate        # Windows: venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd Frontend
npm run dev
```

### Verify everything is running

| Service | URL | Expected |
|---|---|---|
| Backend health | http://localhost:8000/health | `{"status":"ok"}` |
| API docs | http://localhost:8000/docs | Swagger UI |
| Frontend UI | http://localhost:5173 | TokenLens chat app |

---

## 📁 Project Structure

```
TokenLens/
│
├── Backend/
│   ├── main.py              # FastAPI app — all routes defined here
│   ├── database.py          # SQLAlchemy models + SQLite/Postgres helpers
│   ├── memory/
│   │   ├── __init__.py      # Public API for memory system
│   │   ├── manager.py       # Turn buffer + LLM summarisation logic
│   │   └── store.py         # In-memory/Redis session store
│   ├── requirements.txt     # All Python dependencies (pinned)
│   ├── .env.example         # Environment variable template
│   └── .env                 # Your local config (never commit)
│
├── Frontend/
│   ├── src/
│   │   ├── App.jsx          # Chat UI, multi-session, model switcher, file upload
│   │   ├── MetricsView.jsx  # Token & cost analytics dashboard
│   │   ├── assets/          # Static assets (logo, etc.)
│   │   └── index.css
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── .env                 # Frontend env vars (never commit)
│
└── README.md
```

---

## 📖 API Reference

Full interactive docs available at **[http://localhost:8000/docs](http://localhost:8000/docs)** once the backend is running.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root — returns service info |
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Send a text message, get an AI response |
| `POST` | `/chat-file` | Send a message with an image attachment |
| `POST` | `/upload` | Upload a PDF for RAG (max 3 MB) |
| `POST` | `/tokenize/count` | Count tokens in a given text block |
| `GET` | `/session/{session_id}/stats` | Inspect memory state for a session |
| `DELETE` | `/session/{session_id}` | Clear memory for a session |

### Example — Chat request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain RAG in simple terms",
    "session_id": "my-session-001",
    "model": "gemma"
  }'
```

---

## 🔨 Available Scripts

### Backend

```bash
# Development (auto-reload)
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2

# Deactivate virtual environment when done
deactivate
```

### Frontend

```bash
npm run dev        # Start development server (localhost:5173)
npm run build      # Production build → dist/
npm run preview    # Preview production build locally
npm run lint       # ESLint check
```

---

## 🐛 Troubleshooting

**`RuntimeError: Missing OLLAMA_HOST or OLLAMA_MODEL`**

The backend exits immediately if these two `.env` values are absent. Set them in `Backend/.env`:
```dotenv
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
```

**Ollama connection refused**

Make sure Ollama is running before starting the backend:
```bash
ollama serve          # start Ollama in background
ollama list           # confirm gemma3:4b is pulled
```

**Port already in use**

```bash
# Kill process on port 8000 (Linux/macOS)
lsof -ti:8000 | xargs kill

# Kill process on port 5173
lsof -ti:5173 | xargs kill

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**`ModuleNotFoundError` (Python)**

Virtual environment may not be active or dependencies not installed:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**`npm ERR!` / missing `node_modules`**

```bash
rm -rf node_modules package-lock.json
npm install
```

**CORS error in browser**

- Confirm `VITE_API_BASE_URL` in `Frontend/.env` matches backend URL exactly.
- Confirm `ALLOWED_ORIGINS` in `Backend/.env` includes `http://localhost:5173`.
- Restart both servers after editing `.env` files.

**PDF upload fails or returns no results**

- PDFs must be ≤ 3 MB.
- For semantic search, ensure `nomic-embed-text` is pulled: `ollama pull nomic-embed-text`.
- If not pulled, the backend automatically falls back to keyword matching.

---

## 🤝 Contributing

Contributions are welcome!

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Commit**: `git commit -m "feat: describe your change"`
4. **Push**: `git push origin feature/your-feature-name`
5. **Open a Pull Request** against `main`

Please keep PRs focused on a single concern and follow conventional commit message format.

---


⭐ Star this repo if you find it useful!
