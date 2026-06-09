from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.utils.logging import get_logger

logger = get_logger("agents.opportunity_scoring")

SCORING_PROMPT = """You are a startup opportunity evaluator. Score market opportunities on 5 dimensions.

For each opportunity, evaluate:
1. demand (0-25): How strong is the market demand?
2. competition (0-25): How underserved is the market? (higher = less competition = better)
3. growth (0-25): What is the growth potential?
4. pain_intensity (0-25): How painful is the problem for users?
5. technical_feasibility (0-25): How feasible is building a solution?

Return a JSON array of scored opportunities, each with:
- title: opportunity name
- description: what the opportunity is
- demand_score: 0-25
- competition_score: 0-25
- growth_score: 0-25
- pain_intensity_score: 0-25
- technical_feasibility_score: 0-25
- total_score: sum of all 5 (0-100)
- recommendation: "strong_opportunity", "moderate_opportunity", or "weak_opportunity"

Only return the JSON array, no other text."""


class OpportunityScoringAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="opportunity_scoring")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        gaps = state.get("gaps", [])
        trends = state.get("trends", [])
        pain_points = state.get("pain_points", [])
        documents = state.get("documents", [])

        if not gaps and not pain_points:
            return {"opportunities": []}

        context_parts = []
        if gaps:
            context_parts.append("Market Gaps:\n" + "\n".join(
                f"- {g.get('title','')}: {g.get('description','')[:100]}" for g in gaps[:10]
            ))
        if trends:
            context_parts.append("Trends:\n" + "\n".join(
                f"- {t.get('title','')}: {t.get('description','')[:100]}" for t in trends[:10]
            ))
        if pain_points:
            context_parts.append("Pain Points:\n" + "\n".join(
                f"- {p.get('title','')}: severity={p.get('severity_score',0)}" for p in pain_points[:10]
            ))

        user_prompt = f"""Based on the following market intelligence:

{chr(10).join(context_parts)}

Total signals analyzed: {len(documents)}

Score each viable opportunity on the 5 dimensions. Be specific and data-driven."""

        result = await invoke_llm_json(SCORING_PROMPT, user_prompt)

        if not isinstance(result, list):
            return {"opportunities": []}

        opportunities = []
        for item in result:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            total = sum(item.get(dim, 0) for dim in [
                "demand_score", "competition_score", "growth_score",
                "pain_intensity_score", "technical_feasibility_score"
            ])
            opportunities.append({
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "demand_score": item.get("demand_score", 0),
                "competition_score": item.get("competition_score", 0),
                "growth_score": item.get("growth_score", 0),
                "pain_intensity_score": item.get("pain_intensity_score", 0),
                "technical_feasibility_score": item.get("technical_feasibility_score", 0),
                "total_score": total,
                "recommendation": item.get("recommendation", "moderate_opportunity"),
                "confidence_score": min(100, total),
                "id": f"opp_{len(opportunities)}",
            })

        opportunities.sort(key=lambda x: x["total_score"], reverse=True)
        self.logger.info("Scored %d opportunities", len(opportunities))
        return {"opportunities": opportunities}
