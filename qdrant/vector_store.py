import os
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from ingestion.document_parser import DocumentChunk
from embeddings.embedding_service import get_embedding_service


QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "aws_finops_knowledge")
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_DIM = 384


class VectorStore:
    def __init__(self, host: str = QDRANT_HOST, port: int = QDRANT_PORT):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = COLLECTION_NAME

    def init_collection(self, recreate: bool = False) -> None:
        collections = [c.name for c in self.client.get_collections().collections]

        if self.collection_name in collections:
            if recreate:
                self.client.delete_collection(self.collection_name)
            else:
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=DENSE_DIM,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams()
            },
        )

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        self.init_collection(recreate=False)
        embedding_service = get_embedding_service()

        texts = [chunk.text for chunk in chunks]
        dense_vectors = embedding_service.embed_dense_batch(texts)
        sparse_vectors = embedding_service.embed_sparse_batch(texts)

        points = []
        for idx, chunk in enumerate(chunks):
            indices, values = sparse_vectors[idx]
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))

            point = models.PointStruct(
                id=point_id,
                vector={
                    DENSE_VECTOR_NAME: dense_vectors[idx],
                    SPARSE_VECTOR_NAME: models.SparseVector(
                        indices=indices,
                        values=values,
                    ),
                },
                payload={
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "source_document": chunk.source_document,
                    "service": chunk.service,
                    "issue_type": chunk.issue_type,
                    "recommendation": chunk.recommendation,
                },
            )
            points.append(point)

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )
        return len(points)

    def count(self) -> int:
        try:
            res = self.client.count(collection_name=self.collection_name)
            return res.count
        except Exception:
            return 0


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
