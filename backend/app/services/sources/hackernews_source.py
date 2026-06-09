import httpx
from app.services.sources.base import Signal
from app.utils.logging import get_logger

logger = get_logger("sources.hackernews")

HN_API = "https://hacker-news.firebaseio.com/v0"


class HackerNewsSource:
    def __init__(self) -> None:
        self.timeout = httpx.Timeout(15.0, connect=5.0)

    async def search(self, query: str, limit: int = 30) -> list[Signal]:
        signals = []
        signals.extend(await self._get_stories("topstories", limit))
        signals.extend(await self._get_stories("newstories", limit))
        signals.extend(await self._get_stories("askstories", limit))
        return signals[:limit]

    async def _get_stories(self, list_type: str, limit: int) -> list[Signal]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{HN_API}/{list_type}.json")
                resp.raise_for_status()
                story_ids = resp.json()[:limit]
        except Exception as exc:
            logger.error("HN %s fetch failed: %s", list_type, exc)
            return []

        signals = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for sid in story_ids:
                try:
                    resp = await client.get(f"{HN_API}/item/{sid}.json")
                    resp.raise_for_status()
                    item = resp.json()
                    if item and item.get("type") == "story":
                        signals.append(
                            Signal(
                                source="hackernews",
                                source_id=str(sid),
                                title=item.get("title", ""),
                                content=item.get("text", "")[:2000],
                                url=item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                                author=item.get("by", ""),
                                score=item.get("score", 0),
                                comments_count=item.get("descendants", 0),
                            )
                        )
                except Exception:
                    continue
        return signals
