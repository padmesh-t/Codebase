import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
from app.logging_config import get_logger

logger = get_logger("database")

DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
Base = declarative_base()


class ProjectDB(Base):
    __tablename__ = "projects"

    project_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    status = Column(String, default="pending")
    file_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    findings = Column(Text, default="[]")
    debate_messages = Column(Text, default="[]")
    report = Column(Text, default="{}")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    if engine:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized")


def get_db():
    if SessionLocal:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        yield None


def save_project(project_id: str, data: dict):
    if not SessionLocal:
        return
    db = SessionLocal()
    try:
        existing = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
        if existing:
            existing.name = data.get("name", existing.name)
            existing.source = data.get("source", existing.source)
            existing.status = data.get("status", existing.status)
            existing.file_count = data.get("file_count", existing.file_count)
            existing.chunk_count = data.get("chunk_count", existing.chunk_count)
            existing.findings = json.dumps(data.get("findings", []), default=str)
            existing.debate_messages = json.dumps(data.get("debate_messages", []), default=str)
            existing.report = json.dumps(data.get("report", {}), default=str)
            existing.error = data.get("error", existing.error)
        else:
            project = ProjectDB(
                project_id=project_id,
                name=data.get("name", ""),
                source=data.get("source", ""),
                status=data.get("status", "pending"),
                file_count=data.get("file_count", 0),
                chunk_count=data.get("chunk_count", 0),
                findings=json.dumps(data.get("findings", []), default=str),
                debate_messages=json.dumps(data.get("debate_messages", []), default=str),
                report=json.dumps(data.get("report", {}), default=str),
                error=data.get("error"),
            )
            db.add(project)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save project {project_id}: {e}")
    finally:
        db.close()


def load_project(project_id: str) -> dict | None:
    if not SessionLocal:
        return None
    db = SessionLocal()
    try:
        project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
        if not project:
            return None
        return {
            "project_id": project.project_id,
            "name": project.name,
            "source": project.source,
            "status": project.status,
            "file_count": project.file_count,
            "chunk_count": project.chunk_count,
            "findings": json.loads(project.findings) if project.findings else [],
            "debate_messages": json.loads(project.debate_messages) if project.debate_messages else [],
            "report": json.loads(project.report) if project.report else {},
            "error": project.error,
        }
    except Exception as e:
        logger.error(f"Failed to load project {project_id}: {e}")
        return None
    finally:
        db.close()


def load_all_projects() -> list[dict]:
    if not SessionLocal:
        return []
    db = SessionLocal()
    try:
        projects = db.query(ProjectDB).all()
        return [
            {
                "project_id": p.project_id,
                "name": p.name,
                "source": p.source,
                "status": p.status,
                "file_count": p.file_count,
                "chunk_count": p.chunk_count,
            }
            for p in projects
        ]
    except Exception as e:
        logger.error(f"Failed to load projects: {e}")
        return []
    finally:
        db.close()


def delete_project(project_id: str) -> bool:
    if not SessionLocal:
        return False
    db = SessionLocal()
    try:
        project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
        if project:
            db.delete(project)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete project {project_id}: {e}")
        return False
    finally:
        db.close()
