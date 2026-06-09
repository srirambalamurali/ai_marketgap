import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.models.source_document import SourceDocument, SourceType
from app.repositories.documents import save_documents, bulk_insert_documents, get_document_count


def _make_doc(i: int = 0) -> SourceDocument:
    return SourceDocument(
        source="github",
        source_type=SourceType.REPOSITORY,
        title=f"test/repo{i}",
        content=f"test/repo{i}: description",
        url=f"https://github.com/test/repo{i}",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        metadata={"stars": i * 10},
    )


def _make_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


@pytest.mark.asyncio
async def test_save_documents():
    session = _make_session()
    docs = [_make_doc(0), _make_doc(1)]

    records = await save_documents(session, docs)

    assert len(records) == 2
    assert session.add.call_count == 2
    session.flush.assert_awaited_once()

    r0 = records[0]
    assert r0.source == "github"
    assert r0.source_type == "repository"
    assert r0.title == "test/repo0"
    assert r0.metadata_json == {"stars": 0}


@pytest.mark.asyncio
async def test_bulk_insert_documents():
    session = _make_session()
    docs = [_make_doc(0), _make_doc(1), _make_doc(2)]

    count = await bulk_insert_documents(session, docs)

    assert count == 3
    session.add_all.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_count():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    session.execute = AsyncMock(return_value=mock_result)

    count = await get_document_count(session)

    assert count == 42
    session.execute.assert_awaited_once()
