import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, func, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.postgres import Base


class StartupOpportunity(Base):
    __tablename__ = "startup_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    market_gap_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    query_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    query_domain: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    startup_name: Mapped[str] = mapped_column(String(200), nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    market_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    demand_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pain_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    growth_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    competition_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    whitespace_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    feasibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    query_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    competition_level: Mapped[str] = mapped_column(String(20), nullable=False, default="Unknown")
    emergence_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signal_growth_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trend_acceleration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_momentum: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    target_customers: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revenue_model: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mvp_features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    go_to_market: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
