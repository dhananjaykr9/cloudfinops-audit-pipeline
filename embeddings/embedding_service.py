"""
Embedding Service — Provides dense semantic and sparse keyword embeddings.

Dense:
    Model: BAAI/bge-small-en-v1.5 (384-dimensional vector)
    Provides semantic understanding of cost optimization concepts.

Sparse:
    Model: Qdrant/bm25 (sparse vector: indices and values)
    Provides exact-term matching for AWS terminology (gp2, gp3, EBS, RDS, t3.large).
"""

import os
from typing import Optional
from fastembed import TextEmbedding
from fastembed.sparse.sparse_text_embedding import SparseTextEmbedding


DENSE_MODEL_NAME: str = os.getenv("DENSE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
SPARSE_MODEL_NAME: str = os.getenv("SPARSE_EMBEDDING_MODEL", "Qdrant/bm25")


class EmbeddingService:
    """Singleton service for generating dense and sparse embeddings."""

    _instance: Optional["EmbeddingService"] = None

    def __init__(self):
        print(f"[EMBEDDING] Loading dense model: {DENSE_MODEL_NAME}")
        self._dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
        print(f"[EMBEDDING] Loading sparse model: {SPARSE_MODEL_NAME}")
        self._sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
        print("[EMBEDDING] Models loaded successfully.")

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed_dense(self, text: str) -> list[float]:
        """Generate a 384-dim dense embedding for a single text."""
        generator = self._dense_model.embed([text])
        return list(next(generator))

    def embed_dense_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for a list of texts."""
        if not texts:
            return []
        generator = self._dense_model.embed(texts)
        return [list(vec) for vec in generator]

    def embed_sparse(self, text: str) -> tuple[list[int], list[float]]:
        """
        Generate sparse BM25 representation for a single text.

        Returns:
            Tuple of (indices, values) as standard Python lists.
        """
        generator = self._sparse_model.embed([text])
        sparse_vec = next(generator)
        return sparse_vec.indices.tolist(), sparse_vec.values.tolist()

    def embed_sparse_batch(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        """
        Generate sparse BM25 representations for a list of texts.

        Returns:
            List of (indices, values) tuples.
        """
        if not texts:
            return []
        generator = self._sparse_model.embed(texts)
        results = []
        for sparse_vec in generator:
            results.append((sparse_vec.indices.tolist(), sparse_vec.values.tolist()))
        return results


_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService.get_instance()
    return _service
