from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    query_id: str | None = None
    query_domain: str = "general"
    query_relevance_score: float = 0.0


class SearchResult(BaseModel):
    content: str
    source: str | None = None
    url: str | None = None
    score: float
    query_id: str | None = None
    query_domain: str = "general"
    query_relevance_score: float = 0.0
    timestamp: str | None = None
    collected_at: str | None = None
    metadata: dict = Field(default_factory=dict)


class IngestRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class IngestResponse(BaseModel):
    success: bool
    documents_processed: int
    chunks_created: int
    vectors_stored: int
    errors: list[str] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    query_id: str | None = None
    report_id: str | None = None


class SearchResponse(BaseModel):
    success: bool
    query: str | None = None
    results: list[SearchResult]
    error: str | None = None
    answer: str | None = None


class ContextRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class ContextResponse(BaseModel):
    success: bool
    query: str | None = None
    context: list[SearchResult]
