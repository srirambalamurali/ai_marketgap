import logging

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from app.config import get_settings
from app.models.source_document import SourceDocument, SourceType
from app.utils.logging import get_logger

logger = get_logger("services.github")

GITHUB_API_BASE = "https://api.github.com"


class GitHubRateLimitError(Exception):
    def __init__(self, reset_at: int, remaining: int) -> None:
        self.reset_at = reset_at
        self.remaining = remaining
        super().__init__(
            f"GitHub rate limit exceeded. Remaining: {remaining}, resets at: {reset_at}"
        )


class GitHubCollector:
    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.github_token
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _check_rate_limit(self, response: httpx.Response) -> None:
        remaining = int(response.headers.get("x-ratelimit-remaining", 1))
        reset_at = int(response.headers.get("x-ratelimit-reset", 0))
        if remaining == 0:
            logger.warning("GitHub rate limit hit, resets at %d", reset_at)
            raise GitHubRateLimitError(reset_at, remaining)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method, url, headers=self._headers(), **kwargs
            )
            self._check_rate_limit(response)
            response.raise_for_status()
            return response

    async def search_repositories(
        self, query: str, limit: int = 20
    ) -> list[SourceDocument]:
        logger.info("Searching repos for '%s' (limit=%d)", query, limit)
        per_page = min(limit, 100)
        params = {"q": query, "per_page": per_page, "sort": "stars", "order": "desc"}

        try:
            response = await self._request(
                "GET", f"{GITHUB_API_BASE}/search/repositories", params=params
            )
        except GitHubRateLimitError:
            logger.warning("Rate limited during repo search, returning empty")
            return []
        except httpx.HTTPStatusError as exc:
            logger.error("GitHub repo search failed: %s", exc.response.status_code)
            return []
        except httpx.RequestError as exc:
            logger.error("GitHub repo search network error: %s", exc)
            return []

        data = response.json()
        items = data.get("items", [])[:limit]
        return [self.normalize_repository(repo) for repo in items]

    async def search_issues(self, query: str, limit: int = 50) -> list[SourceDocument]:
        logger.info("Searching issues for '%s' (limit=%d)", query, limit)
        per_page = min(limit, 100)
        params = {"q": query, "per_page": per_page, "sort": "created", "order": "desc"}

        try:
            response = await self._request(
                "GET", f"{GITHUB_API_BASE}/search/issues", params=params
            )
        except GitHubRateLimitError:
            logger.warning("Rate limited during issue search, returning empty")
            return []
        except httpx.HTTPStatusError as exc:
            logger.error("GitHub issue search failed: %s", exc.response.status_code)
            return []
        except httpx.RequestError as exc:
            logger.error("GitHub issue search network error: %s", exc)
            return []

        data = response.json()
        items = data.get("items", [])[:limit]
        return [self.normalize_issue(issue) for issue in items]

    async def get_repository(self, owner: str, repo: str) -> SourceDocument | None:
        logger.info("Fetching repo %s/%s", owner, repo)
        try:
            response = await self._request(
                "GET", f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
            )
        except (GitHubRateLimitError, httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("Failed to fetch repo %s/%s: %s", owner, repo, exc)
            return None
        return self.normalize_repository(response.json())

    @staticmethod
    def normalize_repository(repo: dict) -> SourceDocument:
        name = repo.get("full_name", repo.get("name", ""))
        description = repo.get("description") or ""
        content = f"{name}: {description}" if description else name

        return SourceDocument(
            source="github",
            source_type=SourceType.REPOSITORY,
            title=name,
            content=content,
            url=repo.get("html_url", ""),
            created_at=repo.get("created_at"),
            metadata={
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language"),
                "topics": repo.get("topics", []),
                "open_issues": repo.get("open_issues_count", 0),
            },
        )

    @staticmethod
    def normalize_issue(issue: dict) -> SourceDocument:
        title = issue.get("title", "")
        body = issue.get("body") or ""
        labels = [label["name"] for label in issue.get("labels", [])]

        return SourceDocument(
            source="github",
            source_type=SourceType.ISSUE,
            title=title,
            content=body,
            url=issue.get("html_url", ""),
            created_at=issue.get("created_at"),
            metadata={
                "labels": labels,
                "comments": issue.get("comments", 0),
                "state": issue.get("state", "open"),
            },
        )
