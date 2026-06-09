# AI Market Gap Discovery Engine

## Architecture

```
ai_marketgap/
├── frontend/                # Next.js 15 (TypeScript)
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI entrypoint + startup validation
│       ├── config.py            # Pydantic Settings (all env vars)
│       │
│       ├── api/
│       │   ├── health.py        # GET  /api/v1/health
│       │   ├── collect.py       # POST /api/v1/collect
│       │   ├── rag.py           # POST /api/v1/rag/query, POST /api/v1/rag/ingest
│       │   └── workflow.py      # POST /api/v1/workflow/run
│       │
│       ├── agents/
│       │   ├── base.py              # BaseAgent ABC
│       │   ├── data_collector/      # Phase 1 skeleton
│       │   ├── trend_detector/
│       │   ├── pain_point/
│       │   ├── gap_analysis/
│       │   ├── opportunity/
│       │   ├── validation/
│       │   └── report/
│       │
│       ├── workflows/
│       │   └── market_gap_graph.py  # LangGraph StateGraph pipeline
│       │
│       ├── models/
│       │   └── state.py             # MarketGapState TypedDict
│       │
│       ├── database/
│       │   ├── postgres.py          # Async SQLAlchemy engine
│       │   └── validation.py        # Startup health checks
│       │
│       ├── rag/
│       │   └── chroma.py            # ChromaDB client
│       │
│       ├── services/
│       │   └── gemini.py            # Gemini 2.5 Flash via LangChain
│       │
│       └── utils/
│           └── logging.py           # Structured logging
│
└── docs/
    └── README.md
```

## Tech Stack

| Layer          | Technology                |
|----------------|---------------------------|
| Frontend       | Next.js 15, TypeScript    |
| Backend        | FastAPI, Python 3.11+     |
| Database       | PostgreSQL (asyncpg)      |
| Vector DB      | ChromaDB                  |
| LLM            | Gemini 2.5 Flash          |
| Orchestration  | LangGraph + LangChain     |

## Pipeline (LangGraph)

```
DataCollector → TrendDetector → PainPoint → GapAnalysis → Opportunity → Validation → Report
```

Each node is an agent that extends `BaseAgent` and implements `run(state) -> dict`.

## Developer Setup

### Prerequisites

- Python 3.11+
- PostgreSQL running and accessible
- ChromaDB server running (default `http://localhost:8000`)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in real values:
#   GEMINI_API_KEY     - your Google AI key
#   POSTGRES_PASSWORD  - your PostgreSQL password
#   POSTGRES_DB        - database name (create it first)
#   CHROMA_HOST/PORT   - if not on localhost:8000
```

### Database Setup

```bash
# Create the database
createdb marketgap

# Tables are created automatically via SQLAlchemy on first write.
# For manual init you can run:
#   python -c "from app.database.postgres import engine, Base; ..."
```

### Running

```bash
cd backend
uvicorn app.main:app --reload --port 8080
```

On startup the app validates PostgreSQL, ChromaDB, and the Gemini API key. If any check fails the server exits immediately with a clear error.

### Verify

```bash
# Health check
curl http://localhost:8080/api/v1/health
# → {"status":"healthy"}

# Data collection placeholder
curl -X POST http://localhost:8080/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"query":"AI coding assistants"}'

# RAG query placeholder
curl -X POST http://localhost:8080/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"AI coding assistants"}'

# Full workflow placeholder
curl -X POST http://localhost:8080/api/v1/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"query":"AI coding assistants"}'
```

### API Endpoints

| Method | Endpoint                      | Description                    |
|--------|-------------------------------|--------------------------------|
| GET    | `/api/v1/health`              | Health check                   |
| POST   | `/api/v1/collect`             | Collect market data            |
| POST   | `/api/v1/rag/query`           | Query vector store             |
| POST   | `/api/v1/rag/ingest`          | Ingest documents into RAG      |
| POST   | `/api/v1/workflow/run`        | Run full analysis pipeline     |

### Project Structure Conventions

- **Agents** live in `app/agents/<name>/agent.py` and extend `BaseAgent`
- **Workflows** wire agents together via LangGraph `StateGraph` in `app/workflows/`
- **Shared state** is typed via `MarketGapState` in `app/models/state.py`
- **Services** (LLM wrappers, external APIs) live in `app/services/`
- **RAG** helpers (ChromaDB, embeddings) live in `app/rag/`
- **Routers** map HTTP endpoints to logic in `app/api/`
