from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.utils.logging import get_logger

logger = get_logger("agents.trend_analysis")

SYSTEM_PROMPT = """You are a trend analysis expert. Analyze market signals and identify key trends.

Given signals and their metadata, identify:
1. Emerging technologies and topics
2. Growth patterns across sources
3. Sentiment shifts
4. Market momentum indicators

Return a JSON array of trends, each with:
- title: short trend name
- description: what this trend means
- strength: 1-10 strength score
- sources: which sources confirmed this
- growth_direction: "rising", "stable", or "declining"

Only return the JSON array, no other text."""


class TrendAnalysisAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="trend_analysis")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        documents = state.get("documents", [])
        if not documents:
            return {"trends": []}

        source_summary = {}
        for doc in documents:
            src = doc.get("source", "unknown")
            source_summary[src] = source_summary.get(src, 0) + 1

        signal_text = "\n".join(
            f"- [{d.get('source','?')}] {d.get('title','')[:80]} (score={d.get('score',0)}, credibility={d.get('credibility_score',0.5)})"
            for d in documents[:30]
        )

        user_prompt = f"""Source distribution: {source_summary}
Total signals: {len(documents)}

Top signals:
{signal_text}

Identify the key market trends from these signals."""

        result = await invoke_llm_json(SYSTEM_PROMPT, user_prompt)

        if not isinstance(result, list):
            return {"trends": []}

        trends = []
        for item in result:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            trends.append({
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "strength": item.get("strength", 5),
                "sources": item.get("sources", []),
                "growth_direction": item.get("growth_direction", "stable"),
                "trend_score": item.get("strength", 5) * 10,
                "confidence": min(1.0, item.get("strength", 5) / 10),
            })

        self.logger.info("Identified %d trends", len(trends))
        return {"trends": trends}
