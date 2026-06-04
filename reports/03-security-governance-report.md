# Security & Governance Report

**Project:** Codebase Intelligence  
**Date:** 2026-06-03  

---

## Security Fixes Applied

### 1. Path Traversal Protection (CRITICAL)

**Before:**
```python
# Any path was accepted
project_dir = code_ingestion_service.validate_local_path(local_path)
```

**After:**
```python
# Only paths under allowed directories
def _validate_local_path(path: str) -> bool:
    resolved = os.path.realpath(path)
    allowed_roots = [
        os.path.realpath(settings.UPLOAD_DIR.parent),
        os.path.realpath(settings.REPO_DIR.parent),
    ]
    return any(resolved.startswith(root) for root in allowed_roots)
```

### 2. Zip Slip Prevention (CRITICAL)

**Before:**
```python
with zipfile.ZipFile(io.BytesIO(content)) as zf:
    zf.extractall(project_dir)  # VULNERABLE
```

**After:**
```python
def _safe_extract_zip(self, data: io.BytesIO, target_dir: Path):
    with zipfile.ZipFile(data) as zf:
        for info in zf.infolist():
            if info.filename.startswith("/") or ".." in info.filename:
                raise IngestionException(f"Unsafe path in zip: {info.filename}")
            target = target_dir / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
```

### 3. Tar Symlink Protection (CRITICAL)

**Before:**
```python
with tarfile.open(fileobj=io.BytesIO(content)) as tf:
    tf.extractall(project_dir)  # VULNERABLE
```

**After:**
```python
def _safe_extract_tar(self, data: io.BytesIO, target_dir: Path):
    with tarfile.open(fileobj=data, mode="r:*") as tf:
        for member in tf.getmembers():
            abs_target = os.path.realpath(os.path.join(target_dir, member.name))
            abs_base = os.path.realpath(str(target_dir))
            if not abs_target.startswith(abs_base):
                raise IngestionException(f"Unsafe path in tar: {member.name}")
            if member.issym() or member.islnk():
                link_target = os.path.join(target_dir, member.linkname)
                if not os.path.realpath(link_target).startswith(abs_base):
                    raise IngestionException(f"Unsafe symlink in tar: {member.name}")
        tf.extractall(target_dir)
```

### 4. CORS Restriction (CRITICAL)

**Before:**
```python
allow_origins=["*"],  # VULNERABLE
```

**After:**
```python
ALLOWED_ORIGINS = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
]
```

### 5. SSRF Prevention (HIGH)

**Before:**
```python
# Any URL scheme accepted
git.Repo.clone_from(git_url, ...)
```

**After:**
```python
def _validate_git_url(url: str) -> bool:
    return url.startswith("https://") and not any(
        scheme in url for scheme in ["file://", "ssh://", "git://", "http://"]
    )
```

### 6. Rate Limiting (HIGH)

Added in-memory rate limiting:
- Default: 100 requests per 60-second window
- Returns HTTP 429 with Retry-After header
- Configurable via `ENABLE_RATE_LIMITING`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`

### 7. Project Count Limit (HIGH)

Added `MAX_PROJECT_COUNT = 50` to prevent memory exhaustion.

### 8. Removed trust_remote_code (HIGH)

Removed `trust_remote_code=True` from HuggingFace embeddings to prevent code execution.

---

## Governance Controls

| Control | Status | Implementation |
|---------|--------|----------------|
| API Authentication | Optional | `ENABLE_API_KEY_AUTH` config |
| Rate Limiting | Active | In-memory sliding window |
| Input Validation | Active | URL scheme, path traversal, file size |
| Audit Logging | Active | Request timing, errors, analysis progress |
| Data Retention | Not implemented | Would need persistent storage |
| GDPR Compliance | Not implemented | Would need database |
| CORS Policy | Active | Restricted to localhost |
| Security Headers | Active | X-Content-Type, X-Frame, etc. |

---

## Remaining Security Recommendations

1. **Add persistent storage** — in-memory projects dict loses data on restart
2. **Add API key authentication** — currently optional, should be enforced
3. **Add request ID middleware** — for traceability
4. **Add file count limits during extraction** — prevent zip bomb
5. **Add LLM output sanitization** — prevent XSS in frontend
6. **Add .dockerignore** — prevent copying secrets to Docker image
7. **Run Docker as non-root** — add USER directive to Dockerfiles
