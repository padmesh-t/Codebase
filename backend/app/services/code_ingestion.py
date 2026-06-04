import os
import io
import zipfile
import tarfile
from pathlib import Path

import git
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.exceptions import (
    IngestionException, GitCloneException, InvalidInputException
)
from app.logging_config import get_logger

logger = get_logger("code_ingestion")


class CodeIngestionService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        self._ast_chunker = None

    def _get_ast_chunker(self):
        if self._ast_chunker is None:
            try:
                from app.services.ast_chunker import ASTChunker
                self._ast_chunker = ASTChunker()
            except Exception as e:
                logger.warning(f"AST chunker unavailable: {e}")
                self._ast_chunker = None
        return self._ast_chunker

    async def clone_repo(self, git_url: str, project_id: str) -> Path:
        if not git_url.startswith("https://"):
            raise GitCloneException("Only HTTPS URLs are allowed")
        if any(scheme in git_url for scheme in ["file://", "ssh://", "git://"]):
            raise GitCloneException("Unsupported URL scheme")

        project_dir = settings.REPO_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            logger.info(f"Cloning {git_url}")
            git.Repo.clone_from(git_url, str(project_dir), depth=1)
            return project_dir
        except git.GitCommandError as e:
            raise GitCloneException(f"Failed to clone: {e}")

    async def upload_project(self, file, project_id: str) -> Path:
        project_dir = settings.UPLOAD_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        content = await file.read()
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise IngestionException(f"File too large: {len(content)} bytes")

        filename = file.filename or "upload.zip"
        if filename.endswith(".zip"):
            self._safe_extract_zip(io.BytesIO(content), project_dir)
        elif filename.endswith((".tar.gz", ".tgz")):
            self._safe_extract_tar(io.BytesIO(content), project_dir)
        else:
            raise InvalidInputException(f"Unsupported format: {filename}")

        logger.info(f"Uploaded {filename} to {project_dir}")
        return project_dir

    def _safe_extract_zip(self, data: io.BytesIO, target_dir: Path):
        with zipfile.ZipFile(data) as zf:
            for info in zf.infolist():
                if info.filename.startswith("/") or ".." in info.filename:
                    raise IngestionException(f"Unsafe path in zip: {info.filename}")
                target = target_dir / info.filename
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        dst.write(src.read())

    def _safe_extract_tar(self, data: io.BytesIO, target_dir: Path):
        with tarfile.open(fileobj=data, mode="r:*") as tf:
            for member in tf.getmembers():
                member_path = os.path.join(target_dir, member.name)
                abs_target = os.path.realpath(member_path)
                abs_base = os.path.realpath(str(target_dir))
                if not abs_target.startswith(abs_base):
                    raise IngestionException(f"Unsafe path in tar: {member.name}")
                if member.issym() or member.islnk():
                    link_target = os.path.join(target_dir, member.linkname)
                    if not os.path.realpath(link_target).startswith(abs_base):
                        raise IngestionException(f"Unsafe symlink in tar: {member.name}")
            tf.extractall(target_dir)

    def discover_files(self, project_dir: Path) -> list[Path]:
        files = []
        for root, dirs, filenames in os.walk(project_dir):
            dirs[:] = [
                d for d in dirs
                if d not in settings.SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                fpath = Path(root) / fname
                ext = fpath.suffix.lower()
                if ext in settings.SKIP_FILES:
                    continue
                if ext in settings.SUPPORTED_EXTENSIONS or not ext:
                    files.append(fpath)

        if len(files) > settings.MAX_FILE_COUNT:
            logger.warning(f"File count {len(files)} exceeds limit, truncating")
            files = files[:settings.MAX_FILE_COUNT]

        logger.info(f"Discovered {len(files)} files")
        return files

    def _detect_language(self, file_path: Path) -> str:
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript",
            ".java": "java", ".go": "go", ".rs": "rust",
            ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
            ".cs": "csharp", ".rb": "ruby", ".php": "php",
        }
        return ext_map.get(file_path.suffix.lower(), "unknown")

    def _chunk_python_ast(self, file_path: Path, content: str, project_dir: Path) -> list[Document]:
        ast_chunker = self._get_ast_chunker()
        if ast_chunker is None:
            return self._chunk_as_text(file_path, content, project_dir)

        try:
            chunks = ast_chunker.chunk_code(content, language="python")
            rel_path = str(file_path.relative_to(project_dir))
            return [
                Document(
                    page_content=chunk["code"],
                    metadata={
                        "file_path": rel_path,
                        "language": "python",
                        "chunk_type": chunk.get("type", "unknown"),
                        "name": chunk.get("name", ""),
                        "start_line": chunk.get("start_line", 0),
                        "end_line": chunk.get("end_line", 0),
                        "line_range": f"{chunk.get('start_line', 0)}-{chunk.get('end_line', 0)}",
                    },
                )
                for chunk in chunks
            ]
        except Exception as e:
            logger.warning(f"AST chunking failed for {file_path}: {e}")
            return self._chunk_as_text(file_path, content, project_dir)

    def _chunk_as_text(self, file_path: Path, content: str, project_dir: Path) -> list[Document]:
        rel_path = str(file_path.relative_to(project_dir))
        chunks = self.text_splitter.split_text(content)
        return [
            Document(
                page_content=chunk_text,
                metadata={
                    "file_path": rel_path,
                    "language": self._detect_language(file_path),
                    "chunk_type": "text",
                    "name": file_path.stem,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )
            for i, chunk_text in enumerate(chunks)
        ]

    async def ingest_project(self, project_dir: Path, project_id: str) -> list[Document]:
        files = self.discover_files(project_dir)
        if not files:
            raise IngestionException("No supported files found")

        all_documents = []
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue

                if file_path.suffix.lower() == ".py" and settings.USE_AST_CHUNKING:
                    docs = self._chunk_python_ast(file_path, content, project_dir)
                else:
                    docs = self._chunk_as_text(file_path, content, project_dir)

                all_documents.extend(docs)
            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")
                continue

        logger.info(f"Ingested {len(all_documents)} chunks from {len(files)} files")
        return all_documents


code_ingestion_service = CodeIngestionService()
