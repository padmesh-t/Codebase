import hashlib
import re
import time
import numpy as np
from app.config import settings
from app.logging_config import get_logger
from app.exceptions import EmbeddingException

logger = get_logger("embedding_service")


class EmbeddingService:
    def __init__(self):
        self._dimension = settings.EMBEDDING_DIMENSION

    def _text_to_features(self, text: str) -> list[float]:
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()

        bigrams = []
        for i in range(len(words) - 1):
            bigrams.append(f"{words[i]}_{words[i+1]}")

        all_tokens = words + bigrams

        hash_vector = np.zeros(self._dimension, dtype=np.float32)
        for token in all_tokens:
            hash_val = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = hash_val % self._dimension
            hash_vector[idx] += 1.0

        norms = np.linalg.norm(hash_vector)
        if norms > 0:
            hash_vector = hash_vector / norms

        return hash_vector.tolist()

    def embed_query(self, query: str) -> list[float]:
        try:
            return self._text_to_features(query)
        except Exception as e:
            raise EmbeddingException(f"Failed to embed query: {e}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            start = time.time()
            result = [self._text_to_features(text) for text in texts]
            elapsed = time.time() - start
            logger.info(f"Embedded {len(texts)} documents in {elapsed:.2f}s")
            return result
        except Exception as e:
            raise EmbeddingException(f"Failed to embed documents: {e}")


embedding_service = EmbeddingService()
