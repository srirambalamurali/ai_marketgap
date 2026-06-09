REPORT_SYSTEM = """You are an expert market analyst generating a final report.

Return ONLY a JSON object with these exact fields:
{
  "executive_summary": "2-3 paragraph executive summary of findings",
  "recommendation": "top 1-3 actionable recommendations for entering this market"
}"""


def build_report_prompt(
    query: str,
    pain_points: list[dict],
    trends: list[dict],
    gaps: list[dict],
    validated_opportunities: list[dict],
) -> str:
    pp_text = "\n".join(
        f"- {p.get('title', 'Unknown')}: {p.get('description', '')[:150]} (severity={p.get('severity_score', 0)})"
        for p in pain_points[:5]
    )
    trend_text = "\n".join(
        f"- {t.get('title', 'Unknown')}: {t.get('description', '')[:150]} (score={t.get('trend_score', 0)})"
        for t in trends[:5]
    )
    gap_text = "\n".join(
        f"- {g.get('title', 'Unknown')}: {g.get('description', '')[:150]} (score={g.get('opportunity_score', 0)})"
        for g in gaps[:5]
    )
    opp_text = "\n".join(
        f"- {o.get('title', 'Unknown')}: {o.get('description', '')[:150]} (score={o.get('overall_score', 0)})"
        for o in validated_opportunities[:5]
    )

    return f"""Generate a final market analysis report for query: "{query}"

Top Pain Points:
{pp_text or "None"}

Top Trends:
{trend_text or "None"}

Top Market Gaps:
{gap_text or "None"}

Validated Opportunities:
{opp_text or "None"}

Return a JSON object with: executive_summary, recommendation.
Return ONLY the JSON object, nothing else."""
