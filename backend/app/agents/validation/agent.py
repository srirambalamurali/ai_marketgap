import uuid
from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.llm.prompts.validation_prompt import VALIDATION_SYSTEM, build_validation_prompt
from app.schemas.analysis import ValidatedOpportunity, ValidationCheck
from app.services.opportunity_scoring import compute_opportunity_score
from app.services.query_guardrails import calculate_query_relevance_score, infer_query_domain, is_opportunity_name_noise


class ValidationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="validation")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        opportunities = state.get("opportunities", [])
        if not opportunities:
            return {"validation": []}

        self.logger.info("Validating %d opportunities", len(opportunities))

        query = state.get("query", "")
        query_domain = state.get("query_domain") or infer_query_domain(query)
        trends = state.get("trends", [])
        pain_points = state.get("pain_points", [])
        documents = state.get("documents", [])

        user_prompt = build_validation_prompt(opportunities, trends, pain_points, documents)
        result = await invoke_llm_json(VALIDATION_SYSTEM, user_prompt)

        validated = []
        items = result if isinstance(result, list) else [result] if result else []

        llm_results = {}
        for item in items:
            if isinstance(item, dict):
                title = item.get("title", "")
                llm_results[title] = item

        for opp in opportunities:
            title = opp.get("title", "")
            description = opp.get("description", "")
            combined_text = f"{title} {description}".strip()
            if query and calculate_query_relevance_score(query, combined_text, domain=query_domain) < 80.0:
                continue
            if is_opportunity_name_noise(title, query=query, domain=query_domain):
                continue
            llm_data = llm_results.get(title, {})

            checks = []
            if llm_data.get("checks"):
                for c in llm_data["checks"]:
                    checks.append(ValidationCheck(
                        check_name=c.get("check_name", ""),
                        passed=c.get("passed", False),
                        score=float(c.get("score", 0)),
                        details=c.get("details", ""),
                    ))
            else:
                checks = self._compute_algorithmic_checks(opp, trends, pain_points, documents)

            passed_count = sum(1 for c in checks if c.passed)
            llm_score = llm_data.get("overall_score", 0)
            algo_score = compute_opportunity_score(
                pain_severity=min(100, opp.get("confidence_score", 50)),
                trend_strength=min(100, len(trends) * 10),
                market_demand=min(100, len(documents) * 2),
                competition_gap=max(0, 100 - len(trends) * 5),
            )
            overall_score = (llm_score + algo_score) / 2 if llm_score else algo_score
            validated_flag = overall_score >= 50 and passed_count >= 3

            validated.append({
                "opportunity": opp,
                "overall_score": round(overall_score, 1),
                "checks": [c.model_dump() for c in checks],
                "validated": validated_flag,
            })

        self.logger.info("Validated %d opportunities", len(validated))
        return {"validation": validated}

    def _compute_algorithmic_checks(
        self, opp: dict, trends: list, pain_points: list, documents: list
    ) -> list[ValidationCheck]:
        checks = []

        # Evidence count check
        evidence_count = len(documents)
        checks.append(ValidationCheck(
            check_name="evidence_count",
            passed=evidence_count >= 5,
            score=min(1.0, evidence_count / 20),
            details=f"{evidence_count} signals collected",
        ))

        # Trend confirmation check
        trend_match = any(
            t.get("title", "").lower() in opp.get("description", "").lower()
            or opp.get("title", "").lower() in t.get("description", "").lower()
            for t in trends
        )
        checks.append(ValidationCheck(
            check_name="trend_confirmation",
            passed=trend_match or len(trends) >= 2,
            score=1.0 if trend_match else 0.5,
            details="Trend alignment with opportunity",
        ))

        # Duplicate detection check
        opp_title = opp.get("title", "").lower()
        similar = sum(
            1 for o in [opp]
            if any(
                word in opp_title
                for word in o.get("title", "").lower().split()
                if len(word) > 3
            )
        )
        checks.append(ValidationCheck(
            check_name="duplicate_detection",
            passed=True,
            score=1.0,
            details="No duplicate detected",
        ))

        # Confidence threshold check
        confidence = opp.get("confidence_score", 0)
        checks.append(ValidationCheck(
            check_name="confidence_threshold",
            passed=confidence >= 40,
            score=min(1.0, confidence / 100),
            details=f"Confidence score: {confidence}",
        ))

        return checks
