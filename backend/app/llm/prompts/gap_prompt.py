GAP_SYSTEM = """You are an expert market gap analyst. Your task is to find underserved market opportunities.

Return ONLY a JSON array. Each element must have exactly these fields:
{
  "title": "short title of the gap",
  "description": "what market gap exists and why it matters",
  "opportunity_score": <float 0-100, how promising this gap is>,
  "pain_points": ["related pain point titles"],
  "supporting_trends": ["related trend titles"]
}

Focus on: problems with high frequency but weak solutions, underserved audiences,
growing demand without adequate supply."""


def build_gap_prompt(
    pain_points: list[dict],
    trends: list[dict],
    rag_context: list[str] | None = None,
) -> str:
    pp_text = "\n".join(
        f"- [{p.get('title', 'Unknown')}] severity={p.get('severity_score', 0)}, "
        f"frequency={p.get('frequency', 0)}: {p.get('description', '')[:200]}"
        for p in pain_points[:15]
    )
    trend_text = "\n".join(
        f"- [{t.get('title', 'Unknown')}] score={t.get('trend_score', 0)}, "
        f"confidence={t.get('confidence', 0)}: {t.get('description', '')[:200]}"
        for t in trends[:15]
    )

    rag_text = ""
    if rag_context:
        rag_text = "\n\nRelevant retrieved context:\n"
        for i, ctx in enumerate(rag_context[:10], 1):
            rag_text += f"{i}. {ctx[:300]}\n"

    return f"""Identify market gaps where pain is high, solutions are weak, and demand is growing.

Pain Points:
{pp_text or "None identified"}

Trends:
{trend_text or "None identified"}
{rag_text}

Return a JSON array of market gaps with: title, description, opportunity_score, pain_points, supporting_trends.
Return ONLY the JSON array, nothing else."""
