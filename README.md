# Codebase Intelligence

Multi-agent code review system with debate-based consensus. Four specialized AI analysts independently review a codebase, engage in structured debate, and produce a consensus report.

## Agents

| Agent | Focus |
|-------|-------|
| Security Analyst | Vulnerabilities, OWASP, secrets, injection |
| Performance Analyst | Bottlenecks, memory, N+1, algorithm complexity |
| Architecture Agent | SOLID, coupling, cohesion, design patterns |
| Testing Agent | Coverage, edge cases, test quality |
| Debate Moderator | Synthesizes consensus from all agents |

## Quick Start

### Docker (Recommended)

```bash
docker-compose up
```

- Backend API: http://localhost:8000
- Frontend UI: http://localhost:8501
- Ollama: http://localhost:11434

### Manual Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Usage

### API

```bash
# Analyze a Git repo
curl -X POST "http://localhost:8000/analyze?git_url=https://github.com/user/repo.git"

# Analyze uploaded archive
curl -X POST "http://localhost:8000/analyze" -F "file=@project.zip"

# Check status
curl http://localhost:8000/projects/{project_id}/status

# Get report
curl http://localhost:8000/projects/{project_id}/report

# Get debate transcript
curl http://localhost:8000/projects/{project_id}/debate
```

### Frontend

Open http://localhost:8501 and:
1. Enter a Git URL, local path, or upload an archive
2. Click "Start Analysis"
3. View the consensus report, debate transcript, or individual agent perspectives

## Architecture

```
User Input (Git URL / Upload / Local Path)
  ↓
Code Ingestion (file discovery + AST chunking)
  ↓
FAISS Vector Store (code embeddings)
  ↓
LangGraph Debate Engine
  ├── Security Agent (opening → challenge → revision)
  ├── Performance Agent (opening → challenge → revision)
  ├── Architecture Agent (opening → challenge → revision)
  ├── Testing Agent (opening → challenge → revision)
  └── Moderator (consensus synthesis)
  ↓
Consensus Report
```

## Tech Stack

- **Backend**: FastAPI, LangGraph, LangChain
- **Vector Store**: FAISS
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: Ollama (llama3)
- **Code Chunking**: tree-sitter (AST-aware)
- **Frontend**: Streamlit
- **Deployment**: Docker Compose

## Configuration

Copy `backend/.env.example` to `backend/.env` and adjust settings.

Key environment variables:
- `OLLAMA_BASE_URL` - Ollama server URL
- `OLLAMA_MODEL` - LLM model to use
- `EMBEDDING_MODEL` - Embedding model
- `TOP_K_RESULTS` - Number of context chunks to retrieve
- `DEBATE_ROUNDS` - Number of debate rounds
