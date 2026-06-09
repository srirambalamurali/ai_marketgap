from __future__ import annotations

from typing import Any

from app.services.chromadb_service import get_chroma_service


def get_vector_store(collection_name: str | None = None) -> Any:
    return get_chroma_service()


def get_retriever(
    collection_name: str | None = None,
    search_type: str = "similarity",
    top_k: int = 10,
) -> Any:
    return {
        "collection_name": collection_name,
        "search_type": search_type,
        "top_k": top_k,
        "vector_store": get_vector_store(collection_name),
    }
