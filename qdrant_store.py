import os, uuid
from pathlib import Path
from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient, models

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "aws_finops_knowledge")

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
dense_model = TextEmbedding(model_name=os.getenv("DENSE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
sparse_model = SparseTextEmbedding(model_name=os.getenv("SPARSE_EMBEDDING_MODEL", "Qdrant/bm25"))


def init_collection():
    """Sets up Qdrant collection for dual dense (384-dim) and sparse BM25 indexing."""
    if COLLECTION not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )


def index_documents(docs_dir: str = "data/aws_guidance") -> int:
    """Reads Markdown docs, generates dense + BM25 embeddings, and upserts to Qdrant."""
    init_collection()
    texts, payloads = [], []

    for file in Path(docs_dir).glob("*.md"):
        for chunk in file.read_text(encoding="utf-8").split("\n\n"):
            text = chunk.strip()
            if len(text) > 40:
                texts.append(text)
                payloads.append({"text": text, "source": file.name})

    if not texts:
        return 0

    dense_vecs = list(dense_model.embed(texts))
    sparse_vecs = list(sparse_model.embed(texts))

    points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": dense_vecs[i].tolist(),
                "sparse": models.SparseVector(indices=sparse_vecs[i].indices.tolist(), values=sparse_vecs[i].values.tolist()),
            },
            payload=payloads[i],
        )
        for i in range(len(texts))
    ]
    client.upsert(collection_name=COLLECTION, points=points, wait=True)
    return len(points)


def hybrid_search(query: str, limit: int = 3) -> list[dict]:
    """Runs dual-vector hybrid search combining dense semantic and sparse BM25 via RRF."""
    dense_vec = list(dense_model.embed([query]))[0].tolist()
    sparse_vec = list(sparse_model.embed([query]))[0]

    response = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(query=dense_vec, using="dense", limit=limit * 2),
            models.Prefetch(
                query=models.SparseVector(indices=sparse_vec.indices.tolist(), values=sparse_vec.values.tolist()),
                using="sparse",
                limit=limit * 2,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
    )
    return [p.payload for p in response.points if p.payload]
