from typing import Any

from app.agents.base import BaseAgent
from app.services.opportunity_intelligence import opportunity_intelligence_service
from app.database.postgres import async_session


class OpportunityIntelligenceAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="opportunity_intelligence")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        query = state.get("query", "")
        limit = int(state.get("opportunity_limit", 10))
        opportunities = []
        try:
            async with async_session() as session:
                opportunities = await opportunity_intelligence_service.build_opportunities(session, limit=limit)
                await session.commit()
        except Exception as exc:
            self.logger.warning("Opportunity intelligence skipped: %s", exc)
        return {
            "opportunities": opportunities,
            "opportunity_scores": opportunities,
            "market_gaps": state.get("market_gaps", []),
            "opportunity_intelligence": {
                "query": query,
                "generated": len(opportunities),
            },
        }
