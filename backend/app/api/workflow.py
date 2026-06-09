from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.workflows.market_gap_graph import build_graph
from app.services.dashboard import get_dashboard_metrics
from app.services.monitoring import collector_metrics, collection_alerts, ingestion_rate
from app.utils.logging import get_logger

router = APIRouter(prefix="/workflow", tags=["workflow"])
logger = get_logger("api.workflow")


class WorkflowRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class WorkflowResponse(BaseModel):
    success: bool
    query: str
    report: dict | None = None
    errors: list[str] = []


@router.get("")
async def get_workflow_status(db: AsyncSession = Depends(get_db)):
    metrics = await get_dashboard_metrics(db)
    overall = collector_metrics.get_overall_metrics()
    alerts = collection_alerts.get_alert_summary()
    rate = ingestion_rate.get_rate(60)
    return {
        "status": "healthy" if overall.get("overall_success_rate", 0) >= 0.5 else "degraded",
        "success_rate": overall.get("overall_success_rate", 0),
        "total_signals": metrics.get("total_signals", 0),
        "ingestion_rate_per_min": rate.get("rate_per_minute", 0),
        "active_alerts": alerts.get("total_alerts", 0),
        "pipeline_summary": overall,
        "generated_at": metrics.get("generated_at"),
    }


@router.post("/run", response_model=WorkflowResponse)
async def run_workflow(request: WorkflowRequest):
    initial_state = {
        "query": request.query,
        "documents": [],
        "rag_context": [],
        "trends": [],
        "pain_points": [],
        "gaps": [],
        "opportunities": [],
        "validation": [],
        "report": None,
        "market_gaps": [],
        "trend_analysis": [],
        "opportunity_scores": [],
        "recent_signals": [],
    }

    try:
        graph = build_graph()
        result = await graph.ainvoke(initial_state)
        return WorkflowResponse(
            success=True,
            query=request.query,
            report=result.get("report"),
        )
    except Exception as exc:
        logger.error("Workflow failed: %s", exc)
        return WorkflowResponse(
            success=False,
            query=request.query,
            report=None,
            errors=[str(exc)],
        )
