TREND_SYSTEM = """You are an expert market trend analyst. Your task is to identify emerging trends from market signals.

Return ONLY a JSON array. Each element must have exactly these fields:
{
  "title": "short title of the trend",
  "description": "what this trend means for the market",
  "trend_score": <float 0-100, strength of the trend>,
  "confidence": <float 0-1, how confident you are>
}

Focus on: emerging technologies, growing niches, adoption signals, technology shifts.
Look for patterns across multiple sources."""


def build_trend_prompt(documents: list[dict], rag_context: list[str] | None = None) -> str:
    doc_text = ""
    for i, doc in enumerate(documents[:40], 1):
        title = doc.get("title", "Unknown")
        content = doc.get("content", "")[:300]
        source = doc.get("source", "unknown")
        score = doc.get("score", 0)
        doc_text += f"\n--- Signal {i} [{source}, score={score}] ---\nTitle: {title}\nContent: {content}\n"

    rag_text = ""
    if rag_context:
        rag_text = "\n\nRelevant retrieved context:\n"
        for i, ctx in enumerate(rag_context[:10], 1):
            rag_text += f"{i}. {ctx[:300]}\n"

    return f"""Analyze these market signals and identify emerging trends.

Signals:
{doc_text}
{rag_text}

Return a JSON array of trends with: title, description, trend_score, confidence.
Return ONLY the JSON array, nothing else."""
