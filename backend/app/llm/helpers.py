import json
from typing import Any
from app.services.gemini import get_gemini_llm
from app.utils.logging import get_logger

logger = get_logger("llm.helpers")


async def invoke_llm_json(system_prompt: str, user_prompt: str) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Invoke Gemini with a prompt and parse JSON from the response."""
    llm = get_gemini_llm()
    try:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = await llm.ainvoke(full_prompt)
        content = response.content
        return _parse_json_response(content)
    except Exception as exc:
        logger.error("LLM invocation failed: %s", exc)
        return None


def _parse_json_response(content: str) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Extract and parse JSON from LLM response text."""
    if not content:
        return None

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Find JSON array
    start = content.find("[")
    end = content.rfind("]") + 1
    if start != -1 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

    # Find JSON object
    start = content.find("{")
    end = content.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse JSON from LLM response")
    return None
