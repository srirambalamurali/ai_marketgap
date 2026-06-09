from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.trend_detector.agent import TrendDetectionAgent
from app.utils.logging import get_logger

router = APIRouter(prefix="/trends", tags=["trends"])
logger = get_logger("api.trends")


class TrendRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    documents: list[dict] = []


class TrendResponse(BaseModel):
    success: bool
    trends: list[dict]
    errors: list[str] = []


@router.post("/run", response_model=TrendResponse)
async def run_trends(request: TrendRequest):
    agent = TrendDetectionAgent()
    errors = []
    try:
        result = await agent.run({
            "query": request.query,
            "documents": request.documents,
        })
        trends = result.get("trends", [])
    except Exception as exc:
        logger.error("Trend detection failed: %s", exc)
        errors.append(str(exc))
        trends = []

    return TrendResponse(
        success=len(errors) == 0,
        trends=trends,
        errors=errors,
    )
