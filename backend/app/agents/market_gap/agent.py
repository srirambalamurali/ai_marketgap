from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.utils.logging import get_logger

logger = get_logger("agents.market_gap")

SYSTEM_PROMPT = """You are a market gap analyst. Identify underserved market opportunities by analyzing signals, trends, and pain points.

For each gap found:
- title: gap name
- description: what market need is unmet
- opportunity_score: 0-100
- supporting_evidence: list of evidence items
- affected_sources: which data sources confirmed this
- market_size: "small", "medium", "large", or "unknown"

Return a JSON array of gaps. Only return the JSON array, no other text."""


class MarketGapAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="market_gap")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        pain_points = state.get("pain_points", [])
        trends = state.get("trends", [])
        documents = state.get("documents", [])

        if not pain_points and not trends:
            return {"gaps": []}

        context_parts = []
        if pain_points:
            context_parts.append("Pain Points:\n" + "\n".join(
                f"- {p.get('title','')}: {p.get('description','')[:100]} (severity={p.get('severity_score',0)}, freq={p.get('frequency',0)})"
                for p in pain_points[:15]
            ))
        if trends:
            context_parts.append("Trends:\n" + "\n".join(
                f"- {t.get('title','')}: strength={t.get('strength',5)} direction={t.get('growth_direction','stable')}"
                for t in trends[:15]
            ))

        user_prompt = f"""Analyze the following market intelligence to identify gaps:

{chr(10).join(context_parts)}

Total signals: {len(documents)}
Identify underserved market gaps where demand exceeds supply."""

        result = await invoke_llm_json(SYSTEM_PROMPT, user_prompt)

        if not isinstance(result, list):
            return {"gaps": []}

        gaps = []
        for item in result:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            gaps.append({
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "opportunity_score": item.get("opportunity_score", 50),
                "supporting_evidence": item.get("supporting_evidence", []),
                "affected_sources": item.get("affected_sources", []),
                "market_size": item.get("market_size", "unknown"),
                "id": f"gap_{len(gaps)}",
            })

        gaps.sort(key=lambda x: x["opportunity_score"], reverse=True)
        self.logger.info("Identified %d market gaps", len(gaps))
        return {"gaps": gaps}
