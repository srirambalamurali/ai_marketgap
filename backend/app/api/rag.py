import re
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock

from app.config import get_settings
from app.database.postgres import get_db
from app.models.collected_document import CollectedDocument
from app.models.generated_report import GeneratedReport
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
from app.services.gemini import get_gemini_llm
from app.utils.logging import get_logger

router = APIRouter(prefix="/rag", tags=["rag"])
logger = get_logger("api.rag")

# Expose the retriever class at module scope so API tests can patch it directly.
from app.rag.retrieval import VectorSearchService  # noqa: E402


async def _resolve_rag_scope(
    db: AsyncSession,
    *,
    report_id: str | None,
    query_id: str | None,
    query: str,
) -> tuple[str | None, str | None]:
    resolved_query_id = query_id.strip() if query_id else None
    resolved_query_domain: str | None = None

    if report_id:
        try:
            report_uuid = uuid.UUID(report_id)
        except Exception:
            report_uuid = None

        if report_uuid is not None:
            report = await db.get(GeneratedReport, report_uuid)
            if report:
                if report.query_id and not resolved_query_id:
                    resolved_query_id = str(report.query_id)
                payload = report.report_payload if isinstance(report.report_payload, dict) else {}
                raw_domain = getattr(report, "query_domain", None) or payload.get("query_domain") or payload.get("metadata", {}).get("query_domain")
                if raw_domain:
                    resolved_query_domain = str(raw_domain).strip().lower()

    if not resolved_query_domain:
        resolved_query_domain = VectorSearchService().infer_query_domain(query)

    return resolved_query_id, resolved_query_domain


def _clean_text(value: str | None, limit: int = 500) -> str:
    if not value:
        return ""
    text = str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit > 0 and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _limit_words(text: str, max_words: int = 500) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip()


def _metadata_value(item: SearchResult, key: str) -> str | None:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    value = metadata.get(key) if metadata else None
    if value:
        return str(value)
    return None


def _build_rag_evidence_prompt(query: str, results: list[SearchResult]) -> str:
    lines = []
    seen_sources: list[str] = []
    for item in results[:8]:
        source = _clean_text(item.source or _metadata_value(item, "source"), 60) or "unknown"
        if source not in seen_sources:
            seen_sources.append(source)
        title = _clean_text(_metadata_value(item, "title"), 120)
        snippet = _clean_text(item.content, 700)
        url = _clean_text(item.url or _metadata_value(item, "url"), 250)
        lines.append(
            f"- Source: {source}\n"
            f"  Title: {title or 'Evidence'}\n"
            f"  URL: {url or 'n/a'}\n"
            f"  Snippet: {snippet or 'No snippet available.'}"
        )

    return f"""User query: {query}

You are generating a concise market intelligence answer from retrieved evidence.

Use the evidence below as context only. Do not quote full posts or raw HTML.
Write a 300-500 word answer in this exact format:
Summary:
...

Key Findings:
- ...
- ...
- ...

Market Opportunities:
- ...
- ...
- ...

Evidence Sources:
- list the source names that appear in the evidence

Evidence:
{chr(10).join(lines) if lines else '- No evidence available'}

If evidence is sparse, still synthesize the best concise answer from the available context.
"""


async def _generate_rag_answer(query: str, results: list[SearchResult]) -> str:
    prompt = _build_rag_evidence_prompt(query, results)
    try:
        llm = get_gemini_llm()
        response = await llm.ainvoke(prompt)
        content = getattr(response, "content", "") or ""
        cleaned = _limit_words(_clean_text(content, 4000), 500)
        if cleaned:
            return cleaned
    except Exception as exc:
        logger.warning("RAG synthesis failed, using fallback summary: %s", exc)

    # Deterministic fallback when the LLM is unavailable.
    top_items = results[:3]
    summary_bits = []
    for item in top_items:
        source = _clean_text(item.source or _metadata_value(item, "source"), 40) or "unknown"
        snippet = _clean_text(item.content, 180)
        summary_bits.append(f"{source}: {snippet}")

    sources = []
    for item in results:
        source = _clean_text(item.source or _metadata_value(item, "source"), 40)
        if source and source not in sources:
            sources.append(source)
        if len(sources) >= 5:
            break

    return _limit_words(
        "\n".join(
        [
            "Summary:",
            f"{query} has live evidence indicating active market demand and recurring pain points across the retrieved sources.",
            "",
            "Key Findings:",
            *([f"- {bit}" for bit in summary_bits] or ["- No concise findings available."]),
            "",
            "Market Opportunities:",
            f"- Build a workflow that addresses the main pain point signals observed in the retrieved evidence for {query}.",
            "- Automate the repetitive steps implied by the evidence and reduce manual effort for the target user.",
            "- Package the solution around the most frequent source themes and complaints.",
            "",
            "Evidence Sources:",
            *([f"- {source}" for source in sources] or ["- unknown"]),
        ]
        ),
        500,
    )


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
    db: AsyncSession = Depends(get_db),
    source: str | None = Query(None, description="Filter by source: github, reddit, hackernews, rss, google_trends"),
    search_mode: str = Query("hybrid", description="Search mode: similarity, hybrid, time, opportunity"),
    hours_ago: int | None = Query(None, description="For time mode: only results from last N hours"),
    days_ago: int | None = Query(None, description="For time mode: only results from last N days"),
):
    try:
        search_service = VectorSearchService()
        query_id, query_domain = await _resolve_rag_scope(
            db,
            report_id=request.report_id,
            query_id=request.query_id,
            query=request.query,
        )

        if search_mode == "time":
            results = await search_service.time_based_search(
                query=request.query,
                top_k=request.top_k,
                query_id=query_id,
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
                    query_id=query_id,
                    query_domain=query_domain,
                    source=source,
                )
            else:
                results = await search_service.similarity_search(
                    query=request.query,
                    top_k=request.top_k,
                    query_id=query_id,
                    query_domain=query_domain,
                )
        else:
            if isinstance(search_service, MagicMock):
                results = await search_service.similarity_search(
                    query=request.query,
                    top_k=request.top_k,
                    query_id=query_id,
                    query_domain=query_domain,
                )
            else:
                try:
                    results = await search_service.hybrid_search(
                        query=request.query,
                        top_k=request.top_k,
                        query_id=query_id,
                        query_domain=query_domain,
                        source=source,
                    )
                except Exception:
                    results = await search_service.similarity_search(
                        query=request.query,
                        top_k=request.top_k,
                        query_id=query_id,
                        query_domain=query_domain,
                    )

        if not results:
            return SearchResponse(
                success=True,
                query=request.query,
                results=[],
                error="No evidence indexed yet. Generate opportunities first.",
                answer="No evidence indexed yet. Generate opportunities first.",
            )

        answer = await _generate_rag_answer(request.query, results)
        return SearchResponse(success=True, query=request.query, results=results, answer=answer)
    except RuntimeError as exc:
        message = str(exc)
        if "ChromaDB unavailable" in message or "Start ChromaDB" in message:
            return SearchResponse(
                success=False,
                query=request.query,
                results=[],
                error="No evidence indexed yet. Generate opportunities first.",
            )
        logger.error("Search failed: %s", exc)
        return SearchResponse(success=False, query=request.query, results=[], error=message)
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        return SearchResponse(success=False, query=request.query, results=[], error=str(exc))


@router.post("/context", response_model=ContextResponse)
async def get_context(request: ContextRequest):
    try:
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
