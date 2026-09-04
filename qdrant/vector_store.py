"""
Qdrant Vector Store — Manages collection setup and document upsert.

Stores document embeddings (dense + sparse) and metadata:
    service: EBS | EC2 | RDS | AWS
    issue_type: LEGACY_STORAGE | ORPHANED_STORAGE | IDLE_RESOURCE | COST_OPTIMIZATION
    recommendation: Actionable recommendation summary
    source_document: Source filename
    text: Full chunk text
"""

import os
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from ingestion.document_parser import DocumentChunk
from embeddings.embedding_service import get_embedding_service


QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "aws_finops_knowledge")
DENSE_VECTOR_NAME: str = "dense"
SPARSE_VECTOR_NAME: str = "sparse"
DENSE_DIM: int = 384


class VectorStore:
    """Qdrant vector store adapter for AWS cost-optimization knowledge."""

    def __init__(self, host: str = QDRANT_HOST, port: int = QDRANT_PORT):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = COLLECTION_NAME

    def init_collection(self, recreate: bool = False) -> None:
        """
        Create the Qdrant collection with both dense and sparse vector configurations.

        Args:
            recreate: If True, delete the existing collection and create a fresh one.
        """
        collections = [c.name for c in self.client.get_collections().collections]

        if self.collection_name in collections:
            if recreate:
                print(f"[QDRANT] Recreating collection: {self.collection_name}")
                self.client.delete_collection(self.collection_name)
            else:
                print(f"[QDRANT] Collection already exists: {self.collection_name}")
                return

        print(f"[QDRANT] Creating collection '{self.collection_name}' with dense and sparse vectors...")
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
        print(f"[QDRANT] Collection '{self.collection_name}' created successfully.")

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        """
        Embed and upsert document chunks into Qdrant.

        Args:
            chunks: List of DocumentChunk objects from document_parser.

        Returns:
            Number of points successfully upserted.
        """
        if not chunks:
            print("[QDRANT] No chunks to upsert.")
            return 0

        self.init_collection(recreate=False)
        embedding_service = get_embedding_service()

        texts = [chunk.text for chunk in chunks]
        print(f"[QDRANT] Generating embeddings for {len(texts)} chunks...")
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
        print(f"[QDRANT] Successfully upserted {len(points)} chunks into '{self.collection_name}'.")
        return len(points)

    def count(self) -> int:
        """Return total number of points in the collection."""
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
