import uuid
from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.schemas.analysis import Opportunity
from app.services.query_guardrails import calculate_query_relevance_score, infer_query_domain
from app.utils.logging import get_logger

logger = get_logger("agents.opportunity")


class OpportunityAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="opportunity")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        gaps = state.get("gaps", [])
        pain_points = state.get("pain_points", [])
        query = state.get("query", "")
        query_domain = state.get("query_domain") or infer_query_domain(query)

        if not gaps and not pain_points:
            return {"opportunities": []}

        self.logger.info("Generating opportunities from %d gaps", len(gaps))

        gap_text = "\n".join(
            f"- {g.get('title', 'Unknown')}: {g.get('description', '')[:200]} (score={g.get('opportunity_score', 0)})"
            for g in gaps[:10]
        )
        pp_text = "\n".join(
            f"- {p.get('title', 'Unknown')}: {p.get('description', '')[:200]} (severity={p.get('severity_score', 0)})"
            for p in pain_points[:10]
        )

        system = """You are a startup opportunity generator. Based on market gaps and pain points, generate viable startup ideas.

Return ONLY a JSON array. Each element:
{
  "title": "startup name or concept",
  "description": "what this startup does and why it matters",
  "market_size_estimate": "small/medium/large/unknown",
  "confidence_score": <float 0-100>,
  "implementation_difficulty": "easy/medium/hard"
}"""

        user = f"""Generate startup opportunities for these market gaps:

Market Gaps:
{gap_text or "None"}

Pain Points:
{pp_text or "None"}

Return a JSON array. Return ONLY the JSON array."""

        result = await invoke_llm_json(system, user)

        if result is None:
            result = []

        opportunities = []
        items = result if isinstance(result, list) else [result]

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                title = str(item.get("title", ""))
                description = str(item.get("description", ""))
                combined_text = f"{title} {description}".strip()
                relevance_score = calculate_query_relevance_score(query, combined_text, domain=query_domain)
                if query and relevance_score < 80.0:
                    continue
                opp = Opportunity(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description,
                    market_size_estimate=item.get("market_size_estimate", "unknown"),
                    confidence_score=float(item.get("confidence_score", 50)),
                    implementation_difficulty=item.get("implementation_difficulty", "medium"),
                )
                opportunities.append(opp.model_dump())
            except Exception as exc:
                self.logger.warning("Failed to parse opportunity: %s", exc)

        self.logger.info("Generated %d opportunities", len(opportunities))
        return {"opportunities": opportunities}
