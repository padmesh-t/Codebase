import json
from pathlib import Path

from langchain_core.documents import Document
from app.config import settings
from app.logging_config import get_logger
from app.exceptions import VectorStoreException

logger = get_logger("vector_store")


class VectorStoreService:
    def __init__(self):
        self._vector_stores: dict[str, object] = {}
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
            from langchain_community.vectorstores import FAISS
            import faiss
            import numpy as np

            store_path = self._get_store_path(project_id)
            store_path.mkdir(parents=True, exist_ok=True)

            texts = [doc.page_content for doc in chunks]
            embeddings = self.embedding_service.embed_documents(texts)
            embeddings_array = np.array(embeddings, dtype=np.float32)
            dimension = embeddings_array.shape[1]

            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings_array)

            vector_store = FAISS(
                embedding_function=self.embedding_service.embeddings,
                index=index,
                docstore=self._create_docstore(chunks),
                index_to_docstore_id={i: i for i in range(len(chunks))},
            )

            vector_store.save_local(str(store_path))

            metadata = {
                "project_id": project_id,
                "chunk_count": len(chunks),
                "dimension": dimension,
                "file_count": len(set(doc.metadata.get("file_path", "") for doc in chunks)),
            }
            self._get_metadata_path(project_id).write_text(json.dumps(metadata, indent=2))

            self._vector_stores[project_id] = vector_store
            logger.info(f"Added {len(chunks)} chunks for {project_id}")

        except Exception as e:
            raise VectorStoreException(f"Failed to add documents: {e}")

    def _create_docstore(self, chunks: list[Document]):
        from langchain_community.docstore.in_memory import InMemoryDocstore
        return InMemoryDocstore({i: doc for i, doc in enumerate(chunks)})

    def get_store(self, project_id: str):
        if project_id in self._vector_stores:
            return self._vector_stores[project_id]

        try:
            from langchain_community.vectorstores import FAISS
            store_path = self._get_store_path(project_id)
            if not store_path.exists():
                return None

            vector_store = FAISS.load_local(
                str(store_path),
                self.embedding_service.embeddings,
                allow_dangerous_deserialization=True,
            )
            self._vector_stores[project_id] = vector_store
            return vector_store
        except Exception as e:
            logger.error(f"Failed to load vector store for {project_id}: {e}")
            return None

    def similarity_search(self, query: str, project_id: str, top_k: int = 10) -> list:
        store = self.get_store(project_id)
        if store is None:
            raise VectorStoreException(f"No vector store for {project_id}")
        try:
            return store.similarity_search_with_score(query, k=top_k)
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
