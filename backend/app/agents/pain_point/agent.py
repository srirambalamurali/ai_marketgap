import uuid
from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.llm.prompts.pain_point_prompt import PAIN_POINT_SYSTEM, build_pain_point_prompt
from app.schemas.analysis import PainPoint


class PainPointAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="pain_point")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        documents = state.get("documents", [])
        if not documents:
            return {"pain_points": []}

        self.logger.info("Extracting pain points from %d documents", len(documents))

        rag_context = state.get("rag_context", [])
        user_prompt = build_pain_point_prompt(documents, rag_context or None)
        result = await invoke_llm_json(PAIN_POINT_SYSTEM, user_prompt)

        if result is None:
            result = []

        pain_points = []
        items = result if isinstance(result, list) else [result]

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                pp = PainPoint(
                    id=str(uuid.uuid4()),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    frequency=int(item.get("frequency", 1)),
                    severity_score=float(item.get("severity_score", 5)),
                    evidence=item.get("evidence", []),
                )
                pain_points.append(pp.model_dump())
            except Exception as exc:
                self.logger.warning("Failed to parse pain point: %s", exc)

        self.logger.info("Extracted %d pain points", len(pain_points))
        return {"pain_points": pain_points}
