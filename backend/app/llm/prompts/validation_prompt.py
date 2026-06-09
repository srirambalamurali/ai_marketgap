VALIDATION_SYSTEM = """You are an expert opportunity validator. Your task is to assess startup opportunities for viability.

For each opportunity, return a JSON object with these exact fields:
{
  "title": "the opportunity title",
  "overall_score": <float 0-100>,
  "checks": [
    {"check_name": "evidence_count", "passed": true/false, "score": 0-1, "details": "explanation"},
    {"check_name": "trend_confirmation", "passed": true/false, "score": 0-1, "details": "explanation"},
    {"check_name": "duplicate_detection", "passed": true/false, "score": 0-1, "details": "explanation"},
    {"check_name": "confidence_threshold", "passed": true/false, "score": 0-1, "details": "explanation"}
  ],
  "validated": true/false
}

An opportunity is validated if overall_score >= 50 AND at least 3 checks passed."""


def build_validation_prompt(
    opportunities: list[dict],
    trends: list[dict],
    pain_points: list[dict],
    documents: list[dict],
) -> str:
    opp_text = "\n".join(
        f"- [{o.get('title', 'Unknown')}] score={o.get('confidence_score', 0)}: {o.get('description', '')[:200]}"
        for o in opportunities[:10]
    )
    pp_text = "\n".join(
        f"- [{p.get('title', 'Unknown')}] severity={p.get('severity_score', 0)}: {p.get('description', '')[:150]}"
        for p in pain_points[:10]
    )
    trend_text = "\n".join(
        f"- [{t.get('title', 'Unknown')}] score={t.get('trend_score', 0)}: {t.get('description', '')[:150]}"
        for t in trends[:10]
    )

    return f"""Validate these startup opportunities based on available evidence.

Opportunities:
{opp_text or "None to validate"}

Supporting Pain Points:
{pp_text or "None"}

Supporting Trends:
{trend_text or "None"}

Total signals collected: {len(documents)}

Return a JSON array of validation results.
Return ONLY the JSON array, nothing else."""
