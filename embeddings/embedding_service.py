import os
from typing import Optional
from fastembed import TextEmbedding
from fastembed.sparse.sparse_text_embedding import SparseTextEmbedding


DENSE_MODEL_NAME = os.getenv("DENSE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
SPARSE_MODEL_NAME = os.getenv("SPARSE_EMBEDDING_MODEL", "Qdrant/bm25")


class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None

    def __init__(self):
        self._dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
        self._sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed_dense(self, text: str) -> list[float]:
        return list(next(self._dense_model.embed([text])))

    def embed_dense_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [list(vec) for vec in self._dense_model.embed(texts)]

    def embed_sparse(self, text: str) -> tuple[list[int], list[float]]:
        sparse_vec = next(self._sparse_model.embed([text]))
        return sparse_vec.indices.tolist(), sparse_vec.values.tolist()

    def embed_sparse_batch(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        if not texts:
            return []
        results = []
        for sparse_vec in self._sparse_model.embed(texts):
            results.append((sparse_vec.indices.tolist(), sparse_vec.values.tolist()))
        return results


_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService.get_instance()
    return _service
