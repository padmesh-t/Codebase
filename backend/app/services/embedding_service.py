import time
from app.config import settings
from app.logging_config import get_logger
from app.exceptions import EmbeddingException

logger = get_logger("embedding_service")


class EmbeddingService:
    def __init__(self):
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
                self._embeddings = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
                )
                logger.info(f"Loaded embedding model: {settings.EMBEDDING_MODEL}")
            except Exception as e:
                raise EmbeddingException(f"Failed to load embedding model: {e}")
        return self._embeddings

    def embed_query(self, query: str) -> list[float]:
        try:
            return self.embeddings.embed_query(query)
        except Exception as e:
            raise EmbeddingException(f"Failed to embed query: {e}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            start = time.time()
            result = self.embeddings.embed_documents(texts)
            elapsed = time.time() - start
            logger.info(f"Embedded {len(texts)} documents in {elapsed:.2f}s")
            return result
        except Exception as e:
            raise EmbeddingException(f"Failed to embed documents: {e}")


embedding_service = EmbeddingService()
