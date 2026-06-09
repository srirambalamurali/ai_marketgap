import uuid
from app.rag.schemas import DocumentChunk
from app.utils.logging import get_logger

logger = get_logger("rag.chunking")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


class DocumentChunker:
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict,
    ) -> list[DocumentChunk]:
        if not content or not content.strip():
            return []

        chunks = self.chunk_text(content)
        result = []
        for i, chunk_text in enumerate(chunks):
            query_id = str(metadata.get("query_id")) if metadata.get("query_id") else None
            query_domain = str(metadata.get("query_domain") or "general")
            chunk_metadata = {
                **metadata,
                "document_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            result.append(
                DocumentChunk(
                    chunk_id=f"{doc_id}_chunk_{i}",
                    content=chunk_text,
                    metadata=chunk_metadata,
                    query_id=query_id,
                    query_domain=query_domain,
                    query_relevance_score=float(metadata.get("query_relevance_score", 0.0) or 0.0),
                )
            )

        logger.info("Chunked document %s into %d chunks", doc_id, len(result))
        return result

    def chunk_text(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size

            if end < len(text):
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space

            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap

        return [c for c in chunks if c]
