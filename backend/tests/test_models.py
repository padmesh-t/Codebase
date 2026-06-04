import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models import (
    Finding, Severity, ProjectStatus, AnalyzeRequest,
    HealthResponse, ProjectStatusResponse
)
from app.exceptions import (
    IntelligenceException, ProjectNotFoundException,
    InvalidInputException, FileTooLargeException
)


def test_config_defaults():
    assert settings.CHUNK_SIZE == 400
    assert settings.CHUNK_OVERLAP == 60
    assert settings.TOP_K_RESULTS == 10
    assert settings.OPENROUTER_MODEL is not None
    assert settings.DEBATE_ROUNDS == 3
    assert settings.MAX_FINDINGS_PER_AGENT == 5
    assert ".git" in settings.SKIP_DIRS
    assert "node_modules" in settings.SKIP_DIRS
    assert ".py" in settings.SUPPORTED_EXTENSIONS


def test_finding_model():
    finding = Finding(
        agent="Security Analyst",
        category="security",
        severity=Severity.CRITICAL,
        title="SQL Injection",
        description="User input used in SQL query",
        evidence=["app.py:42"],
        confidence=0.9,
        file_path="app.py",
        line_number=42,
    )
    assert finding.severity == Severity.CRITICAL
    assert finding.confidence == 0.9
    assert len(finding.evidence) == 1


def test_finding_defaults():
    finding = Finding(
        agent="test",
        category="test",
        severity=Severity.LOW,
        title="test",
        description="test",
    )
    assert finding.evidence == []
    assert finding.confidence == 0.5
    assert finding.file_path is None


def test_project_status_enum():
    assert ProjectStatus.PENDING == "pending"
    assert ProjectStatus.COMPLETED == "completed"
    assert ProjectStatus.FAILED == "failed"


def test_severity_enum():
    assert Severity.CRITICAL == "critical"
    assert Severity.HIGH == "high"
    assert Severity.MEDIUM == "medium"
    assert Severity.LOW == "low"


def test_exceptions():
    exc = IntelligenceException("test error", 500)
    assert exc.message == "test error"
    assert exc.status_code == 500

    exc = ProjectNotFoundException("abc123")
    assert exc.status_code == 404
    assert "abc123" in exc.message

    exc = InvalidInputException("bad input")
    assert exc.status_code == 400

    exc = FileTooLargeException(1000, 500)
    assert exc.status_code == 400


def test_health_response():
    resp = HealthResponse(
        status="healthy",
        version="1.0.0",
        ollama_connected=True,
        vector_store_loaded=False,
        active_projects=5,
    )
    assert resp.status == "healthy"
    assert resp.active_projects == 5


def test_analyze_request():
    req = AnalyzeRequest(git_url="https://github.com/test/repo.git")
    assert req.git_url is not None
    assert req.local_path is None

    req = AnalyzeRequest(local_path="/tmp/project")
    assert req.local_path == "/tmp/project"
    assert req.git_url is None
