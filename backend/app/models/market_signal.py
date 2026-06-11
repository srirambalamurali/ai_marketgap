import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, Float, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.postgres import Base


class MarketSignal(Base):
    __tablename__ = "market_signals"
    __table_args__ = (
        Index("ix_market_signals_source_collected", "source", "collected_at"),
        Index("ix_market_signals_source_type", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    query_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    query_domain: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    domain_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    query_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
