class IntelligenceException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ProjectNotFoundException(IntelligenceException):
    def __init__(self, project_id: str):
        super().__init__(f"Project not found: {project_id}", 404)


class InvalidInputException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(message, 400)


class FileTooLargeException(IntelligenceException):
    def __init__(self, size: int, max_size: int):
        super().__init__(f"File size {size} exceeds maximum {max_size} bytes", 400)


class IngestionException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"Ingestion error: {message}", 422)


class GitCloneException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"Git clone failed: {message}", 422)


class VectorStoreException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"Vector store error: {message}", 500)


class EmbeddingException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"Embedding error: {message}", 500)


class LLMServiceException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"LLM service error: {message}", 503)


class DebateEngineException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"Debate engine error: {message}", 500)


class ChunkingException(IntelligenceException):
    def __init__(self, message: str):
        super().__init__(f"Chunking error: {message}", 500)
