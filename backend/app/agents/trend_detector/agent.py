import uuid
from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.llm.prompts.trend_prompt import TREND_SYSTEM, build_trend_prompt
from app.schemas.analysis import TrendSignal


class TrendDetectionAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="trend_detector")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        documents = state.get("documents", [])
        if not documents:
            return {"trends": []}

        self.logger.info("Analyzing %d documents for trends", len(documents))

        rag_context = state.get("rag_context", [])
        user_prompt = build_trend_prompt(documents, rag_context or None)
        result = await invoke_llm_json(TREND_SYSTEM, user_prompt)

        if result is None:
            result = []

        trends = []
        items = result if isinstance(result, list) else [result]

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                trend = TrendSignal(
                    id=str(uuid.uuid4()),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    trend_score=float(item.get("trend_score", 50)),
                    confidence=float(item.get("confidence", 0.5)),
                )
                trends.append(trend.model_dump())
            except Exception as exc:
                self.logger.warning("Failed to parse trend: %s", exc)

        self.logger.info("Detected %d trends", len(trends))
        return {"trends": trends}
