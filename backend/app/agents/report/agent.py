import uuid
from typing import Any
from app.agents.base import BaseAgent
from app.llm.helpers import invoke_llm_json
from app.llm.prompts.report_prompt import REPORT_SYSTEM, build_report_prompt
from app.schemas.analysis import Report, PainPoint, TrendSignal, MarketGap, ValidatedOpportunity
from app.services.query_guardrails import calculate_query_relevance_score, has_negative_domain_terms, infer_query_domain


class ReportAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="report")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.logger.info("Generating final report")

        query = state.get("query", "")
        query_domain = state.get("query_domain") or infer_query_domain(query)
        pain_points = state.get("pain_points", [])
        trends = state.get("trends", [])
        gaps = state.get("gaps", [])
        validated = state.get("validation", [])
        documents = state.get("documents", [])

        user_prompt = build_report_prompt(query, pain_points, trends, gaps, validated)
        try:
            llm_result = await invoke_llm_json(REPORT_SYSTEM, user_prompt)
        except Exception as exc:
            self.logger.error("Report LLM call failed: %s", exc)
            llm_result = None

        exec_summary = ""
        recommendation = ""
        if isinstance(llm_result, dict):
            exec_summary = llm_result.get("executive_summary", "")
            recommendation = llm_result.get("recommendation", "")

        if not exec_summary:
            exec_summary = self._build_fallback_summary(state)

        top_pp = [PainPoint(**p) for p in pain_points[:5] if self._safe_pain_point(p) and self._matches_domain(query, query_domain, p)]
        top_trends = [TrendSignal(**t) for t in trends[:5] if self._safe_trend(t) and self._matches_domain(query, query_domain, t)]
        top_gaps = [MarketGap(**g) for g in gaps[:5] if self._safe_gap(g) and self._matches_domain(query, query_domain, g)]
        top_opps = []
        for v in validated[:5]:
            if isinstance(v, dict) and "opportunity" in v:
                opp = v["opportunity"]
                if not self._matches_domain(query, query_domain, opp, strict=True):
                    continue
                top_opps.append(ValidatedOpportunity(
                    opportunity=opp,
                    overall_score=v.get("overall_score", 0),
                    checks=v.get("checks", []),
                    validated=v.get("validated", False),
                ))

        report = Report(
            query=query,
            executive_summary=exec_summary,
            top_pain_points=top_pp,
            top_trends=top_trends,
            top_market_gaps=top_gaps,
            top_opportunities=top_opps,
            recommendation=recommendation,
            metadata={
                "total_signals": len(documents),
                "total_trends": len(trends),
                "total_pain_points": len(pain_points),
                "total_gaps": len(gaps),
                "total_validated": len([v for v in validated if isinstance(v, dict) and v.get("validated")]),
                "query_domain": query_domain,
            },
        )

        self.logger.info("Report generated with %d validated opportunities", len(top_opps))
        return {"report": report.model_dump()}

    def _build_fallback_summary(self, state: dict[str, Any]) -> str:
        docs = len(state.get("documents", []))
        trends = len(state.get("trends", []))
        pp = len(state.get("pain_points", []))
        gaps = len(state.get("gaps", []))
        opps = len(state.get("opportunities", []))
        validated = len([v for v in state.get("validation", []) if isinstance(v, dict) and v.get("validated")])

        return (
            f"Market analysis for \"{state.get('query', '')}\". "
            f"Analyzed {docs} signals across multiple sources. "
            f"Detected {trends} trends, identified {pp} pain points, "
            f"found {gaps} market gaps, generated {opps} opportunities, "
            f"and validated {validated} of them."
        )

    def _safe_pain_point(self, d: dict) -> bool:
        return isinstance(d, dict) and d.get("title") and d.get("description")

    def _safe_trend(self, d: dict) -> bool:
        return isinstance(d, dict) and d.get("title") and d.get("description")

    def _safe_gap(self, d: dict) -> bool:
        return isinstance(d, dict) and d.get("title") and d.get("description")

    def _matches_domain(self, query: str, query_domain: str, item: dict, strict: bool = False) -> bool:
        if query_domain == "general":
            return True
        combined_text = " ".join(
            str(item.get(key, ""))
            for key in ("title", "description", "problem", "solution", "summary", "target_user")
        )
        if has_negative_domain_terms(combined_text, domain=query_domain):
            return False
        if strict:
            return calculate_query_relevance_score(query, combined_text, domain=query_domain) >= 80.0
        return True
