from __future__ import annotations

from fastembed import SparseTextEmbedding
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DIM = 384
SPARSE_MODEL_NAME = "Qdrant/bm25"

_model: SentenceTransformer | None = None
_sparse_model: SparseTextEmbedding | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading {MODEL_NAME} (first run downloads ~90 MB)...")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_sparse_model() -> SparseTextEmbedding:
    global _sparse_model
    if _sparse_model is None:
        print(f"Loading {SPARSE_MODEL_NAME} sparse encoder...")
        _sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    return _sparse_model


# ── Dense ──────────────────────────────────────────────────────────────────────

def embed(text: str) -> list[float]:
    return get_model().encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts, normalize_embeddings=True).tolist()


# ── Sparse (BM25) ──────────────────────────────────────────────────────────────

def sparse_embed(text: str) -> tuple[list[int], list[float]]:
    result = next(get_sparse_model().embed([text]))
    return result.indices.tolist(), result.values.tolist()


def sparse_embed_batch(texts: list[str]) -> list[tuple[list[int], list[float]]]:
    results = list(get_sparse_model().embed(texts))
    return [(r.indices.tolist(), r.values.tolist()) for r in results]
