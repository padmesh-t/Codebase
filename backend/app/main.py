import time
import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import IntelligenceException
from app.logging_config import get_logger
from app.models import (
    AnalyzeResponse, ProjectStatusResponse,
    HealthResponse, ProjectStatus
)
from app.database import init_db, save_project, load_project, load_all_projects, delete_project as db_delete_project

logger = get_logger("main")

executor = ThreadPoolExecutor(max_workers=2)

_rate_limits: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    if not settings.ENABLE_RATE_LIMITING:
        return True
    now = time.time()
    window = settings.RATE_LIMIT_WINDOW
    _rate_limits[client_ip] = [t for t in _rate_limits[client_ip] if now - t < window]
    if len(_rate_limits[client_ip]) >= settings.RATE_LIMIT_REQUESTS:
        return False
    _rate_limits[client_ip].append(now)
    return True


def _validate_git_url(url: str) -> bool:
    return url.startswith("https://") and not any(
        scheme in url for scheme in ["file://", "ssh://", "git://", "http://"]
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Codebase Intelligence API v1.0.0")
    init_db()
    from app.services.llm_service import llm_service
    health = await llm_service.check_health()
    if health["connected"]:
        logger.info("LLM connection OK")
    else:
        logger.warning(f"LLM not connected: {health.get('error', 'unknown')}")
    yield
    executor.shutdown(wait=False)
    logger.info("Shutting down...")


app = FastAPI(
    title="Codebase Intelligence API",
    version="1.0.0",
    description="Multi-agent code review with debate-based consensus",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:8501",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8501",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:8])
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def request_timing(request: Request, call_next):
    if request.url.path in ("/health", "/health/llm", "/docs", "/openapi.json"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})

    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.1f}ms")
    return response


@app.exception_handler(IntelligenceException)
async def intelligence_exception_handler(request: Request, exc: IntelligenceException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    from app.services.llm_service import llm_service
    llm_health = await llm_service.check_health()
    all_projects = load_all_projects()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        ollama_connected=llm_health["connected"],
        vector_store_loaded=True,
        active_projects=len(all_projects),
    )


@app.get("/health/llm")
async def llm_health_check():
    from app.services.llm_service import llm_service
    return await llm_service.check_health()


def _run_analysis(project_id: str, project_dir, project_name: str):
    import asyncio
    from app.services.code_ingestion import code_ingestion_service
    from app.services.vector_store import vector_store_service
    from app.chains.debate_engine import debate_engine

    project_data = load_project(project_id) or {
        "project_id": project_id,
        "name": project_name,
        "status": ProjectStatus.INGESTING,
        "file_count": 0,
        "chunk_count": 0,
        "findings": [],
        "debate_messages": [],
        "report": {},
    }

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        project_data["status"] = ProjectStatus.INGESTING
        save_project(project_id, project_data)

        chunks = loop.run_until_complete(
            code_ingestion_service.ingest_project(project_dir, project_id)
        )
        project_data["file_count"] = len(set(c.metadata.get("file_path", "") for c in chunks))
        project_data["chunk_count"] = len(chunks)
        save_project(project_id, project_data)

        loop.run_until_complete(vector_store_service.add_documents(chunks, project_id))

        project_data["status"] = ProjectStatus.DEBATING
        save_project(project_id, project_data)

        result = loop.run_until_complete(
            debate_engine.run(project_id, chunks, project_data)
        )

        project_data["findings"] = result["findings"]
        project_data["debate_messages"] = result["debate_messages"]
        project_data["report"] = result["report"]
        project_data["status"] = ProjectStatus.COMPLETED
        save_project(project_id, project_data)
        logger.info(f"Analysis completed for {project_id}: {len(result['findings'])} findings")

    except Exception as e:
        logger.error(f"Analysis failed for {project_id}: {e}", exc_info=True)
        project_data["status"] = ProjectStatus.FAILED
        project_data["error"] = str(e)
        save_project(project_id, project_data)
    finally:
        loop.close()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_project(
    git_url: str | None = None,
    project_name: str | None = None,
    file: UploadFile | None = File(None),
):
    from app.services.code_ingestion import code_ingestion_service

    all_projects = load_all_projects()
    if len(all_projects) >= settings.MAX_PROJECT_COUNT:
        raise HTTPException(status_code=429, detail="Too many projects. Delete some first.")

    if not git_url and not file:
        raise HTTPException(status_code=400, detail="Provide git_url or file upload")

    if git_url and not _validate_git_url(git_url):
        raise HTTPException(status_code=400, detail="Only HTTPS git URLs are allowed")

    project_id = uuid.uuid4().hex[:12]

    if not project_name:
        if git_url:
            project_name = git_url.rstrip("/").split("/")[-1].replace(".git", "")
        else:
            project_name = file.filename if file else "uploaded_project"

    project_data = {
        "project_id": project_id,
        "name": project_name,
        "source": "git_url" if git_url else "upload",
        "status": ProjectStatus.INGESTING,
        "file_count": 0,
        "chunk_count": 0,
        "findings": [],
        "debate_messages": [],
        "report": {},
    }
    save_project(project_id, project_data)

    try:
        if git_url:
            project_dir = await code_ingestion_service.clone_repo(git_url, project_id)
        else:
            project_dir = await code_ingestion_service.upload_project(file, project_id)
    except Exception as e:
        db_delete_project(project_id)
        raise HTTPException(status_code=400, detail=str(e))

    executor.submit(_run_analysis, project_id, project_dir, project_name)

    return AnalyzeResponse(
        project_id=project_id,
        status=ProjectStatus.INGESTING,
        message=f"Analysis started for '{project_name}'.",
    )


@app.get("/projects/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(project_id: str):
    p = load_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    status_map = {
        ProjectStatus.PENDING: 0,
        ProjectStatus.INGESTING: 25,
        ProjectStatus.ANALYZING: 50,
        ProjectStatus.DEBATING: 75,
        ProjectStatus.COMPLETED: 100,
        ProjectStatus.FAILED: 100,
    }
    return ProjectStatusResponse(
        project_id=project_id,
        status=p["status"],
        file_count=p["file_count"],
        chunk_count=p["chunk_count"],
        progress_percent=status_map.get(p["status"], 0),
        error=p.get("error"),
    )


@app.get("/projects/{project_id}/report")
async def get_report(project_id: str):
    p = load_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if p["status"] != ProjectStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Project status is {p['status']}")
    return p["report"]


@app.get("/projects/{project_id}/debate")
async def get_debate(project_id: str):
    p = load_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": project_id,
        "messages": p["debate_messages"],
        "total_messages": len(p["debate_messages"]),
    }


@app.get("/projects")
async def list_projects():
    return load_all_projects()


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    if not db_delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": f"Project {project_id} deleted"}


@app.get("/models")
async def list_models():
    from app.services.llm_service import llm_service
    models = await llm_service.get_available_models()
    return {"models": models}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
