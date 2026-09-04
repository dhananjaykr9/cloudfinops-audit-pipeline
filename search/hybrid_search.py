"""
Hybrid Search — Combines dense semantic search with sparse exact-term matching.

Uses Qdrant's Reciprocal Rank Fusion (RRF) to combine:
    - Dense Search (Semantic Match via BAAI/bge-small-en-v1.5)
    - Sparse Search (Exact Match via Qdrant/bm25 for AWS terms like gp2, gp3, EBS, RDS)
"""

import os
from dataclasses import dataclass
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from embeddings.embedding_service import get_embedding_service


QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "aws_finops_knowledge")


@dataclass
class SearchResult:
    """A retrieved knowledge chunk with metadata and similarity score."""

    text: str
    service: str
    issue_type: str
    recommendation: str
    source_document: str
    score: float


class HybridSearcher:
    """Performs hybrid search on Qdrant using dense and sparse vectors."""

    def __init__(self, host: str = QDRANT_HOST, port: int = QDRANT_PORT):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = COLLECTION_NAME
        self.embedding_service = get_embedding_service()

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        """
        Execute hybrid search for the given query.

        Args:
            query: Search string (e.g. 'Large gp2 EBS volume')
            limit: Maximum number of results to return.

        Returns:
            List of SearchResult objects ordered by relevance.
        """
        print(f"[HYBRID-SEARCH] Query: '{query}'")

        # 1. Generate dense semantic embedding
        dense_vec = self.embedding_service.embed_dense(query)

        # 2. Generate sparse BM25 keyword representation
        sparse_indices, sparse_values = self.embedding_service.embed_sparse(query)

        # 3. Build Prefetch queries for both vectors
        prefetch = [
            models.Prefetch(
                query=dense_vec,
                using="dense",
                limit=limit * 2,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_indices,
                    values=sparse_values,
                ),
                using="sparse",
                limit=limit * 2,
            ),
        ]

        # 4. Execute hybrid search using Reciprocal Rank Fusion (RRF)
        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        )

        results = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                SearchResult(
                    text=payload.get("text", ""),
                    service=payload.get("service", ""),
                    issue_type=payload.get("issue_type", ""),
                    recommendation=payload.get("recommendation", ""),
                    source_document=payload.get("source_document", ""),
                    score=point.score if point.score is not None else 0.0,
                )
            )

        print(f"[HYBRID-SEARCH] Found {len(results)} results.")
        return results


_searcher: Optional[HybridSearcher] = None


def get_hybrid_searcher() -> HybridSearcher:
    global _searcher
    if _searcher is None:
        _searcher = HybridSearcher()
    return _searcher
