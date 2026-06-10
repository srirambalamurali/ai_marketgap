import httpx
from app.config import get_settings
from app.services.sources.base import Signal
from app.utils.logging import get_logger

logger = get_logger("sources.reddit")

REDDIT_SEARCH = "https://www.reddit.com/search.json"
REDDIT_COMMENTS = "https://www.reddit.com/comments/{id}.json"


class RedditSource:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))
        self.headers = {"User-Agent": "MarketGapEngine/1.0"}

    async def search(self, query: str, limit: int = 25) -> list[Signal]:
        params = {"q": query, "limit": min(limit, 100), "sort": "relevance", "t": "month"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    REDDIT_SEARCH, headers=self.headers, params=params
                )
                resp.raise_for_status()
                children = resp.json().get("data", {}).get("children", [])[:limit]
        except Exception as exc:
            logger.error("Reddit search failed: %s", exc)
            return []

        signals = []
        for child in children:
            d = child.get("data", {})
            signals.append(
                Signal(
                    source="reddit",
                    source_id=d.get("id", ""),
                    title=d.get("title", ""),
                    content=d.get("selftext", "")[:2000],
                    url=f"https://reddit.com{d.get('permalink', '')}",
                    author=d.get("author", ""),
                    score=d.get("score", 0),
                    comments_count=d.get("num_comments", 0),
                )
            )
        return signals

    async def get_comments(self, post_id: str, limit: int = 20) -> list[Signal]:
        url = REDDIT_COMMENTS.format(id=post_id)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("Reddit comments fetch failed: %s", exc)
            return []

        if len(data) < 2:
            return []

        comments = data[1].get("data", {}).get("children", [])[:limit]
        return [
            Signal(
                source="reddit",
                source_id=c.get("data", {}).get("id", ""),
                title=f"Comment on {post_id}",
                content=c.get("data", {}).get("body", "")[:2000],
                url=f"https://reddit.com{c.get('data', {}).get('permalink', '')}",
                author=c.get("data", {}).get("author", ""),
                score=c.get("data", {}).get("score", 0),
                comments_count=0,
            )
            for c in comments
            if c.get("kind") == "t1"
        ]
