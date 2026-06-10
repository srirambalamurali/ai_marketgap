import httpx
from app.config import get_settings
from app.services.sources.base import Signal
from app.utils.logging import get_logger

logger = get_logger("sources.stackoverflow")

SO_API = "https://api.stackexchange.com/2.3"


class StackOverflowSource:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))

    async def search(self, query: str, limit: int = 30) -> list[Signal]:
        params = {
            "order": "desc",
            "sort": "relevance",
            "intitle": query,
            "site": "stackoverflow",
            "pagesize": min(limit, 100),
            "filter": "withbody",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{SO_API}/search/advanced", params=params
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])[:limit]
        except Exception as exc:
            logger.error("SO search failed: %s", exc)
            return []

        return [
            Signal(
                source="stackoverflow",
                source_id=str(q["question_id"]),
                title=q.get("title", ""),
                content=q.get("body_markdown", q.get("body", ""))[:2000],
                url=q.get("link", ""),
                author=q.get("owner", {}).get("display_name", ""),
                score=q.get("score", 0),
                comments_count=q.get("answer_count", 0),
            )
            for q in items
        ]
