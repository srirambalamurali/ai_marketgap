from typing import TypedDict, Annotated
from operator import add


class MarketGapState(TypedDict):
    query: str
    documents: Annotated[list[dict], add]
    rag_context: Annotated[list[str], add]
    recent_signals: Annotated[list[dict], add]
    signal_summary: str
    trends: Annotated[list[dict], add]
    pain_points: Annotated[list[dict], add]
    gaps: Annotated[list[dict], add]
    opportunities: Annotated[list[dict], add]
    validation: Annotated[list[dict], add]
    report: dict | None
    opportunity_scores: Annotated[list[dict], add]
    market_gaps: Annotated[list[dict], add]
    trend_analysis: Annotated[list[dict], add]
