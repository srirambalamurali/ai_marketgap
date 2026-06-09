from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
import uuid


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    source_id: str = ""
    source_type: str = "unknown"
    query_id: str | None = None
    query_domain: str = "general"
    query_relevance_score: float = 0.0
    title: str
    content: str = ""
    url: str = ""
    author: str = ""
    score: int = 0
    comments_count: int = 0
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalBatch(BaseModel):
    source: str
    signals: list[Signal]

    @property
    def count(self) -> int:
        return len(self.signals)
