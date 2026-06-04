from enum import Enum
from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    ANALYZING = "analyzing"
    DEBATING = "debating"
    COMPLETED = "completed"
    FAILED = "failed"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AnalysisSource(str, Enum):
    UPLOAD = "upload"
    GIT_URL = "git_url"


class Finding(BaseModel):
    agent: str
    category: str
    severity: Severity
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    file_path: str | None = None
    line_number: int | None = None


class DebateMessage(BaseModel):
    agent: str
    phase: str
    round_num: int
    content: str
    findings: list[Finding] = Field(default_factory=list)


class ProjectInfo(BaseModel):
    project_id: str
    name: str
    source: AnalysisSource
    source_url: str | None = None
    status: ProjectStatus
    file_count: int = 0
    chunk_count: int = 0
    created_at: str
    error: str | None = None


class AnalyzeRequest(BaseModel):
    git_url: str | None = None
    project_name: str | None = None


class AnalyzeResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    message: str


class ProjectStatusResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    file_count: int = 0
    chunk_count: int = 0
    current_phase: str | None = None
    progress_percent: int = 0
    error: str | None = None


class SourceChunk(BaseModel):
    content: str
    file_path: str
    line_range: str | None = None
    relevance_score: float


class ConsensusReport(BaseModel):
    project_id: str
    executive_summary: str
    overall_score: int = Field(ge=1, le=10)
    confidence: float = Field(ge=0.0, le=1.0)
    critical_issues: list[Finding] = Field(default_factory=list)
    high_issues: list[Finding] = Field(default_factory=list)
    medium_issues: list[Finding] = Field(default_factory=list)
    low_issues: list[Finding] = Field(default_factory=list)
    positive_observations: list[str] = Field(default_factory=list)
    agent_summary: dict[str, str] = Field(default_factory=dict)


class DebateTranscript(BaseModel):
    project_id: str
    rounds: list[dict] = Field(default_factory=list)
    total_messages: int = 0


class HealthResponse(BaseModel):
    status: str
    version: str
    ollama_connected: bool
    vector_store_loaded: bool
    active_projects: int = 0
