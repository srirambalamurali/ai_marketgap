from __future__ import annotations

from app.config import get_settings
from app.rag.chunking import DocumentChunker
from app.rag.schemas import DocumentChunk
from app.rag.embeddings import EmbeddingService
from app.services.chromadb_service import get_chroma_service
from app.utils.logging import get_logger

logger = get_logger("rag.ingestion")


class VectorIngestionService:
    def __init__(self, collection_name: str | None = None) -> None:
        settings = get_settings()
        self._collection_name = collection_name or settings.chroma_collection
        self._embedding_service = EmbeddingService()
        self._chroma = get_chroma_service()
        self._chunker = DocumentChunker()

    async def ingest_document(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        embeddings = await self._embedding_service.embed_batch(texts)

        ids = [c.chunk_id for c in chunks]
        contents = [c.content for c in chunks]
        metadatas = []
        for c in chunks:
            metadata = {k: str(v) for k, v in c.metadata.items()}
            if c.query_id:
                metadata["query_id"] = str(c.query_id)
            metadata["query_domain"] = c.query_domain
            metadata["query_relevance_score"] = str(c.query_relevance_score)
            metadatas.append(metadata)

        stored = await self._chroma.upsert_documents(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
            embeddings=embeddings,
            collection_name=self._collection_name,
        )

        logger.info("Ingested %d chunks into ChromaDB collection %s", stored, self._collection_name)
        return stored

    async def ingest_documents(self, chunks: list[DocumentChunk]) -> int:
        return await self.ingest_document(chunks)

    async def delete_document(self, document_id: str) -> int:
        return await self._chroma.delete_documents(
            where={"document_id": document_id},
            collection_name=self._collection_name,
        )

    async def update_document(self, document_id: str, chunks: list[DocumentChunk]) -> int:
        await self.delete_document(document_id)
        return await self.ingest_document(chunks)

    @property
    def collection(self):
        return self._chroma

    async def get_vector_count(self) -> int:
        return await self._chroma.count_documents(self._collection_name)
