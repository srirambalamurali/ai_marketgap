import pytest
from app.rag.chunking import DocumentChunker


def test_chunk_text_short():
    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
    result = chunker.chunk_text("Hello world")
    assert result == ["Hello world"]


def test_chunk_text_empty():
    chunker = DocumentChunker()
    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   ") == []


def test_chunk_text_exact_size():
    text = "a" * 1000
    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
    result = chunker.chunk_text(text)
    assert len(result) == 1
    assert result[0] == text


def test_chunk_text_multiple_chunks():
    text = "word " * 300
    chunker = DocumentChunker(chunk_size=200, chunk_overlap=50)
    result = chunker.chunk_text(text)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk) <= 200


def test_chunk_text_overlap():
    text = "abcdefghij " * 100
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    result = chunker.chunk_text(text)
    assert len(result) > 1


def test_chunk_document():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_document(
        doc_id="doc-1",
        content="This is test content for chunking. " * 20,
        metadata={"source": "github", "source_type": "issue"},
    )
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.chunk_id.startswith("doc-1_chunk_")
        assert chunk.metadata["document_id"] == "doc-1"
        assert chunk.metadata["source"] == "github"
        assert chunk.metadata["source_type"] == "issue"
        assert "chunk_index" in chunk.metadata
        assert "total_chunks" in chunk.metadata


def test_chunk_document_empty():
    chunker = DocumentChunker()
    assert chunker.chunk_document("doc-1", "", {}) == []
    assert chunker.chunk_document("doc-1", "   ", {}) == []


def test_chunk_document_metadata_preserved():
    chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
    metadata = {"source": "github", "url": "https://example.com", "custom": 42}
    chunks = chunker.chunk_document("d1", "A" * 200, metadata)
    for chunk in chunks:
        assert chunk.metadata["source"] == "github"
        assert chunk.metadata["url"] == "https://example.com"
        assert chunk.metadata["custom"] == 42
