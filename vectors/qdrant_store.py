from __future__ import annotations

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION", "ttu_kb")
VECTOR_DIM = 384


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, check_compatibility=False)


def reset_collection(client: QdrantClient) -> None:
    """Drop and recreate collection with named dense + sparse vectors."""
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    print(f"Reset collection: {COLLECTION} (dense + sparse)")


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        reset_collection(client)


def upsert_points(
    client: QdrantClient,
    dense_vectors: list[list[float]],
    sparse_vectors: list[tuple[list[int], list[float]]],
    payloads: list[dict],
) -> None:
    points = [
        PointStruct(
            id=i,
            vector={
                "dense": dense_vectors[i],
                "sparse": SparseVector(
                    indices=sparse_vectors[i][0],
                    values=sparse_vectors[i][1],
                ),
            },
            payload=payloads[i],
        )
        for i in range(len(dense_vectors))
    ]
    client.upsert(collection_name=COLLECTION, points=points, wait=True)


def search(
    client: QdrantClient,
    dense_vector: list[float],
    sparse_vector: tuple[list[int], list[float]],
    top_k: int = 5,
) -> list[dict]:
    """Hybrid search: dense semantic + sparse BM25, fused with RRF."""
    response = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=dense_vector, using="dense", limit=top_k * 2),
            Prefetch(
                query=SparseVector(
                    indices=sparse_vector[0],
                    values=sparse_vector[1],
                ),
                using="sparse",
                limit=top_k * 2,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "text": r.payload.get("text", ""),
            "source": r.payload.get("source", ""),
            "chunk_index": r.payload.get("chunk_index", 0),
            "score": r.score,
        }
        for r in response.points
    ]
