from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.opportunity_scoring import rank_opportunities
from app.utils.logging import get_logger

router = APIRouter(prefix="/opportunities", tags=["opportunities"])
logger = get_logger("api.top_opportunities")


class TopOpportunitiesRequest(BaseModel):
    opportunities: list[dict] = []
    validation: list[dict] = []
    top_n: int = Field(default=5, ge=1, le=50)


class TopOpportunitiesResponse(BaseModel):
    success: bool
    opportunities: list[dict]


@router.post("/top", response_model=TopOpportunitiesResponse)
async def get_top_opportunities(request: TopOpportunitiesRequest):
    validated_opps = []
    for v in request.validation:
        if isinstance(v, dict) and v.get("validated"):
            opp = v.get("opportunity", {})
            opp["overall_score"] = v.get("overall_score", 0)
            validated_opps.append(opp)

    if not validated_opps:
        validated_opps = request.opportunities

    ranked = rank_opportunities(validated_opps)
    return TopOpportunitiesResponse(
        success=True,
        opportunities=ranked[: request.top_n],
    )
