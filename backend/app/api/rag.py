from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.postgres import get_db
from app.models.collected_document import CollectedDocument
from app.models.embedding_status import DocumentEmbeddingStatus, EmbeddingStatus
from app.rag.chunking import DocumentChunker
from app.rag.schemas import (
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    ContextRequest,
    ContextResponse,
    SearchResult,
)
from app.services.chromadb_service import get_chroma_service
from app.utils.logging import get_logger

router = APIRouter(prefix="/rag", tags=["rag"])
logger = get_logger("api.rag")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CollectedDocument.id).where(
                ~CollectedDocument.id.in_(
                    select(DocumentEmbeddingStatus.document_id).where(
                        DocumentEmbeddingStatus.embedding_status == EmbeddingStatus.COMPLETED
                    )
                )
            ).limit(request.limit)
        )
        doc_ids = [row[0] for row in result.all()]
    except Exception as exc:
        logger.error("Failed to fetch unembedded documents: %s", exc)
        return IngestResponse(
            success=False,
            documents_processed=0,
            chunks_created=0,
            vectors_stored=0,
            errors=[f"Database query failed: {exc}"],
        )

    if not doc_ids:
        return IngestResponse(
            success=True,
            documents_processed=0,
            chunks_created=0,
            vectors_stored=0,
        )

    result = await db.execute(
        select(CollectedDocument).where(CollectedDocument.id.in_(doc_ids))
    )
    documents = result.scalars().all()

    chunker = DocumentChunker()
    all_chunks = []
    errors = []

    for doc in documents:
        try:
            metadata = {
                "source": doc.source,
                "source_type": doc.source_type,
                "url": doc.url,
                "query_id": str(doc.query_id) if doc.query_id else "",
                "query_domain": doc.metadata_json.get("query_domain", "general") if isinstance(doc.metadata_json, dict) else "general",
            }
            chunks = chunker.chunk_document(
                doc_id=str(doc.id),
                content=doc.content,
                metadata=metadata,
            )
            all_chunks.extend(chunks)

            status = DocumentEmbeddingStatus(
                document_id=doc.id,
                embedding_status=EmbeddingStatus.PROCESSING,
            )
            db.add(status)
        except Exception as exc:
            logger.error("Failed to chunk document %s: %s", doc.id, exc)
            errors.append(f"Chunk failed for {doc.id}: {exc}")

    await db.flush()

    vectors_stored = 0
    if all_chunks:
        try:
            from app.rag.ingestion import VectorIngestionService

            ingestion = VectorIngestionService()
            vectors_stored = await ingestion.ingest_documents(all_chunks)
        except Exception as exc:
            logger.error("Failed to ingest into ChromaDB: %s", exc)
            errors.append(f"ChromaDB ingestion failed: {exc}")

    processing_result = await db.execute(
        select(DocumentEmbeddingStatus).where(
            DocumentEmbeddingStatus.embedding_status == EmbeddingStatus.PROCESSING
        )
    )
    for status_row in processing_result.scalars().all():
        status_row.embedding_status = (
            EmbeddingStatus.COMPLETED if vectors_stored > 0 else EmbeddingStatus.FAILED
        )

    await db.commit()

    return IngestResponse(
        success=len(errors) == 0,
        documents_processed=len(documents),
        chunks_created=len(all_chunks),
        vectors_stored=vectors_stored,
        errors=errors,
    )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    source: str | None = Query(None, description="Filter by source: github, reddit, hackernews, rss, google_trends"),
    search_mode: str = Query("hybrid", description="Search mode: similarity, hybrid, time, opportunity"),
    hours_ago: int | None = Query(None, description="For time mode: only results from last N hours"),
    days_ago: int | None = Query(None, description="For time mode: only results from last N days"),
):
    try:
        from app.rag.retrieval import VectorSearchService

        search_service = VectorSearchService()
        query_domain = search_service.infer_query_domain(request.query)

        if search_mode == "time":
            results = await search_service.time_based_search(
                query=request.query,
                top_k=request.top_k,
                query_domain=query_domain,
                hours_ago=hours_ago,
                days_ago=days_ago,
            )
        elif search_mode == "opportunity":
            results = await search_service.opportunity_search(
                query=request.query,
                top_k=request.top_k,
            )
        elif search_mode == "similarity":
            if source:
                results = await search_service.filtered_search(
                    query=request.query,
                    top_k=request.top_k,
                    query_domain=query_domain,
                    source=source,
                )
            else:
                results = await search_service.similarity_search(
                    query=request.query,
                    top_k=request.top_k,
                    query_domain=query_domain,
                )
        else:
            results = await search_service.hybrid_search(
                query=request.query,
                top_k=request.top_k,
                query_domain=query_domain,
                source=source,
            )

        return SearchResponse(success=True, query=request.query, results=results)
    except RuntimeError as exc:
        message = str(exc)
        if "ChromaDB unavailable" in message or "Start ChromaDB" in message:
            return SearchResponse(
                success=False,
                query=request.query,
                results=[],
                error="Vector search unavailable. Start ChromaDB on port 8001.",
            )
        logger.error("Search failed: %s", exc)
        return SearchResponse(success=False, query=request.query, results=[], error=message)
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        return SearchResponse(success=False, query=request.query, results=[], error=str(exc))


@router.post("/context", response_model=ContextResponse)
async def get_context(request: ContextRequest):
    try:
        from app.rag.retrieval import VectorSearchService

        search_service = VectorSearchService()
        query_domain = search_service.infer_query_domain(request.query)
        results = await search_service.get_document_context(
            query=request.query,
            top_k=10,
        )
        return ContextResponse(success=True, query=request.query, context=results)
    except Exception as exc:
        logger.error("Context retrieval failed: %s", exc)
        return ContextResponse(success=False, query=request.query, context=[])


@router.get("/collection/stats")
async def get_collection_stats():
    try:
        chroma = get_chroma_service()
        health = await chroma.health(COLLECTION_NAME)
        return {
            "collection": COLLECTION_NAME,
            "chromadb_connected": health["chromadb_connected"],
            "collection_exists": health["collection_exists"],
            "vector_count": health["embedded_documents"],
            "status": health["status"],
        }
    except Exception as exc:
        logger.error("Collection stats failed: %s", exc)
        return {"error": str(exc)}


@router.get("/health")
async def rag_health():
    chroma = get_chroma_service()
    health = await chroma.health(COLLECTION_NAME)
    return health


COLLECTION_NAME = get_settings().chroma_collection
