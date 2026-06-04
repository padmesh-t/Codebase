from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=True)

    BASE_DIR: Path = Path(__file__).parent.parent
    _DATA_ROOT: Path = Path.home() / ".codebase-intelligence"
    UPLOAD_DIR: Path = _DATA_ROOT / "uploads"
    REPO_DIR: Path = _DATA_ROOT / "repos"
    VECTOR_STORE_DIR: Path = _DATA_ROOT / "vector_store"

    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 60
    USE_AST_CHUNKING: bool = True

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    FAISS_INDEX_TYPE: str = "flat"
    TOP_K_RESULTS: int = 10

    # OpenRouter API
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4096

    DEBATE_ROUNDS: int = 3
    MAX_FINDINGS_PER_AGENT: int = 5

    ENABLE_API_KEY_AUTH: bool = False
    API_KEY: str = ""
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    ENABLE_INPUT_SANITIZATION: bool = True
    ENABLE_AUDIT_LOGGING: bool = True

    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_FILE_COUNT: int = 5000
    MAX_PROJECT_COUNT: int = 50

    SKIP_DIRS: list[str] = [
        ".git", "node_modules", "__pycache__", "venv", ".venv",
        "env", ".env", "dist", "build", ".next", ".nuxt",
        "target", "bin", "obj", ".idea", ".vscode",
    ]
    SKIP_FILES: list[str] = [
        ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
        ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg",
        ".mp3", ".mp4", ".wav", ".avi", ".mov",
        ".zip", ".tar", ".gz", ".rar", ".7z",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ]
    SUPPORTED_EXTENSIONS: list[str] = [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
        ".rs", ".c", ".cpp", ".h", ".hpp", ".cs",
        ".rb", ".php", ".swift", ".kt", ".scala",
        ".md", ".txt", ".yml", ".yaml", ".json", ".toml",
        ".html", ".css", ".scss", ".sql", ".sh", ".bat",
    ]

    LOG_LEVEL: str = "INFO"


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.REPO_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
