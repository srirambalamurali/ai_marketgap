import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_document import CollectedDocument
from app.models.source_document import SourceDocument
from app.utils.logging import get_logger

logger = get_logger("repositories.documents")


def _normalize_query_id(value):
    if value in (None, "", "null"):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


async def save_documents(
    session: AsyncSession, documents: list[SourceDocument]
) -> list[CollectedDocument]:
    records = []
    for doc in documents:
        query_id = _normalize_query_id(getattr(doc, "query_id", None) or doc.metadata.get("query_id"))
        query_domain = getattr(doc, "query_domain", None) or doc.metadata.get("query_domain", "general")
        record = CollectedDocument(
            source=doc.source,
            source_type=doc.source_type.value,
            query_id=query_id,
            query_domain=str(query_domain or "general"),
            title=doc.title,
            content=doc.content,
            url=doc.url,
            created_at=doc.created_at,
            metadata_json=doc.metadata,
        )
        session.add(record)
        records.append(record)
    await session.flush()
    logger.info("Saved %d documents", len(records))
    return records


async def bulk_insert_documents(
    session: AsyncSession, documents: list[SourceDocument]
) -> int:
    records = [
        CollectedDocument(
            source=doc.source,
            source_type=doc.source_type.value,
            query_id=_normalize_query_id(getattr(doc, "query_id", None) or doc.metadata.get("query_id")),
            query_domain=str(getattr(doc, "query_domain", None) or doc.metadata.get("query_domain", "general")),
            title=doc.title,
            content=doc.content,
            url=doc.url,
            created_at=doc.created_at,
            metadata_json=doc.metadata,
        )
        for doc in documents
    ]
    session.add_all(records)
    await session.flush()
    logger.info("Bulk inserted %d documents", len(records))
    return len(records)


async def get_document_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(CollectedDocument.id)))
    return result.scalar_one()


async def get_document_by_url(session: AsyncSession, url: str) -> CollectedDocument | None:
    result = await session.execute(
        select(CollectedDocument).where(CollectedDocument.url == url).limit(1)
    )
    return result.scalar_one_or_none()
