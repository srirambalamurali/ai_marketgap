import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    REPOSITORY = "repository"
    ISSUE = "issue"


class SourceDocument(BaseModel):
    source: str = "github"
    source_type: SourceType
    query_id: uuid.UUID | str | None = None
    query_domain: str = "general"
    query_relevance_score: float = 0.0
    title: str
    content: str
    url: str
    created_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)
