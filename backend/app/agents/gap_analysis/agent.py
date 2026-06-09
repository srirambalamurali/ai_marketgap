import uuid
from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.llm.prompts.gap_prompt import GAP_SYSTEM, build_gap_prompt
from app.schemas.analysis import MarketGap
from app.services.opportunity_scoring import score_gap


class GapAnalysisAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="gap_analysis")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trends = state.get("trends", [])
        pain_points = state.get("pain_points", [])

        if not trends and not pain_points:
            return {"gaps": []}

        self.logger.info("Analyzing %d trends and %d pain points", len(trends), len(pain_points))

        rag_context = state.get("rag_context", [])
        user_prompt = build_gap_prompt(pain_points, trends, rag_context or None)
        result = await invoke_llm_json(GAP_SYSTEM, user_prompt)

        if result is None:
            result = []

        gaps = []
        items = result if isinstance(result, list) else [result]

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                gap = MarketGap(
                    id=str(uuid.uuid4()),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    opportunity_score=score_gap(
                        pain_points,
                        trends,
                        item.get("pain_points", []),
                        item.get("supporting_trends", []),
                    ),
                    pain_points=item.get("pain_points", []),
                    supporting_trends=item.get("supporting_trends", []),
                )
                gaps.append(gap.model_dump())
            except Exception as exc:
                self.logger.warning("Failed to parse gap: %s", exc)

        self.logger.info("Identified %d gaps", len(gaps))
        return {"gaps": gaps}
