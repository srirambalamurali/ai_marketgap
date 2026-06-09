from __future__ import annotations

from app.services.chromadb_service import get_chroma_service


def get_chroma_client():
    return get_chroma_service()


async def get_collection(name: str | None = None):
    service = get_chroma_service()
    return await service.get_collection(name)
