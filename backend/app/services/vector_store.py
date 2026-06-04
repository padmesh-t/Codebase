import json
import pickle
from pathlib import Path

import numpy as np
from langchain_core.documents import Document
from app.config import settings
from app.logging_config import get_logger
from app.exceptions import VectorStoreException

logger = get_logger("vector_store")


class NumpyVectorStore:
    def __init__(self):
        self.embeddings: np.ndarray | None = None
        self.documents: list[Document] = []

    def add_documents(self, chunks: list[Document], embeddings: list[list[float]]):
        self.documents = chunks
        self.embeddings = np.array(embeddings, dtype=np.float32)

    def similarity_search_with_score(self, query_embedding: list[float], top_k: int = 10) -> list:
        if self.embeddings is None or len(self.documents) == 0:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        similarities = np.dot(self.embeddings, query_vec)
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1.0
        similarities = similarities / norms

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = 1.0 - float(similarities[idx])
            results.append((self.documents[idx], score))

        return results

    def save(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        np.save(path / "embeddings.npy", self.embeddings)
        with open(path / "documents.pkl", "wb") as f:
            pickle.dump(self.documents, f)

    @classmethod
    def load(cls, path: Path) -> "NumpyVectorStore":
        store = cls()
        emb_path = path / "embeddings.npy"
        doc_path = path / "documents.pkl"

        if emb_path.exists() and doc_path.exists():
            store.embeddings = np.load(emb_path)
            with open(doc_path, "rb") as f:
                store.documents = pickle.load(f)

        return store


class VectorStoreService:
    def __init__(self):
        self._vector_stores: dict[str, NumpyVectorStore] = {}
        self._embedding_service = None

    @property
    def embedding_service(self):
        if self._embedding_service is None:
            from app.services.embedding_service import embedding_service
            self._embedding_service = embedding_service
        return self._embedding_service

    def _get_store_path(self, project_id: str) -> Path:
        return settings.VECTOR_STORE_DIR / project_id

    def _get_metadata_path(self, project_id: str) -> Path:
        return self._get_store_path(project_id) / "metadata.json"

    async def add_documents(self, chunks: list[Document], project_id: str):
        try:
            store_path = self._get_store_path(project_id)
            store_path.mkdir(parents=True, exist_ok=True)

            texts = [doc.page_content for doc in chunks]
            embeddings = self.embedding_service.embed_documents(texts)

            store = NumpyVectorStore()
            store.add_documents(chunks, embeddings)
            store.save(store_path)

            metadata = {
                "project_id": project_id,
                "chunk_count": len(chunks),
                "dimension": len(embeddings[0]) if embeddings else 0,
                "file_count": len(set(doc.metadata.get("file_path", "") for doc in chunks)),
            }
            self._get_metadata_path(project_id).write_text(json.dumps(metadata, indent=2))

            self._vector_stores[project_id] = store
            logger.info(f"Added {len(chunks)} chunks for {project_id}")

        except Exception as e:
            raise VectorStoreException(f"Failed to add documents: {e}")

    def get_store(self, project_id: str) -> NumpyVectorStore | None:
        if project_id in self._vector_stores:
            return self._vector_stores[project_id]

        try:
            store_path = self._get_store_path(project_id)
            if not store_path.exists():
                return None

            store = NumpyVectorStore.load(store_path)
            self._vector_stores[project_id] = store
            return store
        except Exception as e:
            logger.error(f"Failed to load vector store for {project_id}: {e}")
            return None

    def similarity_search(self, query: str, project_id: str, top_k: int = 10) -> list:
        store = self.get_store(project_id)
        if store is None:
            raise VectorStoreException(f"No vector store for {project_id}")
        try:
            query_embedding = self.embedding_service.embed_query(query)
            return store.similarity_search_with_score(query_embedding, top_k)
        except Exception as e:
            raise VectorStoreException(f"Search failed: {e}")

    def delete_project(self, project_id: str):
        store_path = self._get_store_path(project_id)
        if store_path.exists():
            import shutil
            shutil.rmtree(store_path, ignore_errors=True)
        self._vector_stores.pop(project_id, None)
        logger.info(f"Deleted vector store for {project_id}")


vector_store_service = VectorStoreService()
