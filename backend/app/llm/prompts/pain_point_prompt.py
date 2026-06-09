PAIN_POINT_SYSTEM = """You are an expert market analyst. Your task is to extract pain points from discussions, reviews, and issues.

Return ONLY a JSON array. Each element must have exactly these fields:
{
  "title": "short title of the pain point",
  "description": "detailed description of the problem",
  "frequency": <int, how common this is 1-50>,
  "severity_score": <float 0-10, how severe the problem is>,
  "evidence": ["quote or source 1", "quote or source 2"]
}

Focus on: complaints, frustrations, unmet needs, feature requests, recurring problems.
Do NOT include positive feedback or general observations."""


def build_pain_point_prompt(documents: list[dict], rag_context: list[str] | None = None) -> str:
    doc_text = ""
    for i, doc in enumerate(documents[:40], 1):
        title = doc.get("title", "Unknown")
        content = doc.get("content", "")[:400]
        source = doc.get("source", "unknown")
        doc_text += f"\n--- Document {i} [{source}] ---\nTitle: {title}\nContent: {content}\n"

    rag_text = ""
    if rag_context:
        rag_text = "\n\nRelevant retrieved context:\n"
        for i, ctx in enumerate(rag_context[:10], 1):
            rag_text += f"{i}. {ctx[:300]}\n"

    return f"""Analyze these documents and extract pain points.

Documents:
{doc_text}
{rag_text}

Return a JSON array of pain points with: title, description, frequency, severity_score, evidence.
Return ONLY the JSON array, nothing else."""
