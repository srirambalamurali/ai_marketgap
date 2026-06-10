import httpx
from app.services.sources.base import Signal
from app.utils.logging import get_logger
from app.config import get_settings

logger = get_logger("sources.github")

GITHUB_API = "https://api.github.com"


class GitHubSource:
    def __init__(self) -> None:
        settings = get_settings()
        self.token = settings.github_token
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def search(self, query: str, limit: int = 20) -> list[Signal]:
        signals = []
        signals.extend(await self._search_repos(query, limit))
        signals.extend(await self._search_issues(query, limit))
        return signals

    async def _search_repos(self, query: str, limit: int) -> list[Signal]:
        params = {"q": query, "per_page": min(limit, 100), "sort": "stars", "order": "desc"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{GITHUB_API}/search/repositories",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])[:limit]
        except Exception as exc:
            logger.error("GitHub repo search failed: %s", exc)
            return []

        return [
            Signal(
                source="github",
                source_id=str(r["id"]),
                title=r.get("full_name", ""),
                content=r.get("description") or "",
                url=r.get("html_url", ""),
                author=r.get("owner", {}).get("login", ""),
                score=r.get("stargazers_count", 0),
                comments_count=r.get("open_issues_count", 0),
            )
            for r in items
        ]

    async def _search_issues(self, query: str, limit: int) -> list[Signal]:
        params = {"q": query, "per_page": min(limit, 100), "sort": "created", "order": "desc"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{GITHUB_API}/search/issues",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])[:limit]
        except Exception as exc:
            logger.error("GitHub issue search failed: %s", exc)
            return []

        return [
            Signal(
                source="github",
                source_id=str(i["id"]),
                title=i.get("title", ""),
                content=(i.get("body") or "")[:2000],
                url=i.get("html_url", ""),
                author=i.get("user", {}).get("login", ""),
                score=i.get("reactions", {}).get("+1", 0),
                comments_count=i.get("comments", 0),
            )
            for i in items
        ]
