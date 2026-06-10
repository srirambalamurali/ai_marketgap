import asyncio
import httpx
from datetime import datetime
from app.schemas.signals import Signal, SignalBatch
from app.config import get_settings
from app.services.source_scoring import score_source
from app.services.query_guardrails import build_domain_profile
from app.utils.logging import get_logger

logger = get_logger("collectors.github")

GITHUB_API = "https://api.github.com"


class GitHubIntelligenceCollector:
    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.github_token
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get(self, url: str, params: dict | None = None) -> dict | list | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self._headers(), params=params)
                logger.info("GitHub request url=%s status=%s params=%s", resp.request.url, resp.status_code, params or {})
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "GitHub request failed url=%s status=%s body=%s",
                getattr(exc.request, "url", url),
                exc.response.status_code,
                exc.response.text[:300],
            )
            if exc.response.status_code == 403:
                logger.warning("GitHub rate limit hit")
            else:
                logger.error("GitHub API error %s: %s", exc.response.status_code, exc)
            return None
        except httpx.TimeoutException as exc:
            logger.warning("GitHub timeout url=%s reason=%s", url, exc)
            return None
        except Exception as exc:
            logger.error("GitHub request failed url=%s reason=%s", url, exc)
            return None

    def _expand_query_variants(self, query: str) -> list[str]:
        query_lower = query.strip().lower()
        if not query_lower:
            return []
        if query_lower == "fitness":
            return ["fitness", "workout", "gym", "exercise"]

        profile = build_domain_profile(query)
        related_terms = [term.strip() for term in profile.get("related_terms", []) if str(term).strip()]
        variants = [part.strip() for part in query.split("||") if part.strip()] or [query.strip()]
        if not variants:
            variants = [query.strip()]
        variants.extend(related_terms[:4])

        deduped: list[str] = []
        seen: set[str] = set()
        for variant in variants:
            normalized = variant.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(variant)
        return deduped[:6]

    async def collect_trending_repos(self, query: str, limit: int = 30) -> SignalBatch:
        signals = []
        data = await self._get(f"{GITHUB_API}/search/repositories", {
            "q": f"{query} created:>{self._days_ago(30)}",
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100),
        })
        if data:
            for repo in data.get("items", [])[:limit]:
                signals.append(Signal(
                    source="github",
                    source_type="repository",
                    title=repo.get("full_name", ""),
                    content=repo.get("description") or "",
                    url=repo.get("html_url", ""),
                    author=repo.get("owner", {}).get("login", ""),
                    score=repo.get("stargazers_count", 0),
                    collected_at=datetime.utcnow(),
                    metadata={
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "language": repo.get("language"),
                        "topics": repo.get("topics", []),
                        "open_issues": repo.get("open_issues_count", 0),
                    },
                ))
        logger.info("Collected %d trending repos for '%s'", len(signals), query)
        return SignalBatch(source="github", signals=signals)

    async def collect_issues(self, query: str, limit: int = 30) -> SignalBatch:
        signals = []
        data = await self._get(f"{GITHUB_API}/search/issues", {
            "q": f"{query} is:issue is:open",
            "sort": "created",
            "order": "desc",
            "per_page": min(limit, 100),
        })
        if data:
            for issue in data.get("items", [])[:limit]:
                labels = [l.get("name", "") for l in issue.get("labels", [])]
                signals.append(Signal(
                    source="github",
                    source_type="issue",
                    title=issue.get("title", ""),
                    content=(issue.get("body") or "")[:2000],
                    url=issue.get("html_url", ""),
                    author=issue.get("user", {}).get("login", ""),
                    score=issue.get("reactions", {}).get("+1", 0),
                    comments_count=issue.get("comments", 0),
                    collected_at=datetime.utcnow(),
                    metadata={
                        "labels": labels,
                        "state": issue.get("state"),
                        "repo": issue.get("repository_url", "").split("/")[-2:] if issue.get("repository_url") else [],
                    },
                ))
        logger.info("Collected %d issues for '%s'", len(signals), query)
        return SignalBatch(source="github", signals=signals)

    async def collect_feature_requests(self, query: str, limit: int = 20) -> SignalBatch:
        signals = []
        data = await self._get(f"{GITHUB_API}/search/issues", {
            "q": f'{query} is:issue label:"feature request" is:open',
            "sort": "reactions",
            "order": "desc",
            "per_page": min(limit, 100),
        })
        if data:
            for issue in data.get("items", [])[:limit]:
                signals.append(Signal(
                    source="github",
                    source_type="feature_request",
                    title=issue.get("title", ""),
                    content=(issue.get("body") or "")[:2000],
                    url=issue.get("html_url", ""),
                    author=issue.get("user", {}).get("login", ""),
                    score=issue.get("reactions", {}).get("+1", 0),
                    comments_count=issue.get("comments", 0),
                    collected_at=datetime.utcnow(),
                    metadata={
                        "reactions": issue.get("reactions", {}),
                        "labels": [l.get("name", "") for l in issue.get("labels", [])],
                    },
                ))
        logger.info("Collected %d feature requests for '%s'", len(signals), query)
        return SignalBatch(source="github", signals=signals)

    async def collect_all(self, query: str) -> SignalBatch:
        query_variants = self._expand_query_variants(query)
        if not query_variants:
            query_variants = [query]
        query_variants = query_variants[:5]

        per_query_limit = max(2, 10 // max(len(query_variants), 1))
        all_signals = []

        async def _collect_variant(variant: str, include_feature_requests: bool) -> list[Signal]:
            feature_request_task = (
                self.collect_feature_requests(variant, limit=max(2, per_query_limit // 2))
                if include_feature_requests
                else asyncio.sleep(0, result=SignalBatch(source="github", signals=[]))
            )
            batches = await asyncio.gather(
                self.collect_trending_repos(variant, limit=per_query_limit),
                self.collect_issues(variant, limit=per_query_limit),
                feature_request_task,
                return_exceptions=True,
            )
            variant_signals: list[Signal] = []
            for batch in batches:
                if isinstance(batch, Exception):
                    logger.warning("GitHub variant batch failed for '%s': %s", variant, batch)
                    continue
                variant_signals.extend(batch.signals)
            return variant_signals

        variant_batches = await asyncio.gather(
            *[_collect_variant(variant, index == 0) for index, variant in enumerate(query_variants)],
            return_exceptions=True,
        )
        for batch in variant_batches:
            if isinstance(batch, Exception):
                logger.warning("GitHub query variant failed: %s", batch)
                continue
            all_signals.extend(batch)

        deduped: list[Signal] = []
        seen_keys: set[str] = set()
        for signal in all_signals:
            key = signal.url or signal.source_id or f"{signal.title}:{signal.content[:80]}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(signal)

        scored = []
        for s in deduped:
            s.metadata["credibility_score"] = score_source(s.source, s.source_type)
            scored.append(s)

        logger.info("GitHub total: %d signals for '%s'", len(scored), query)
        return SignalBatch(source="github", signals=scored)

    @staticmethod
    def _days_ago(n: int) -> str:
        from datetime import timedelta
        return (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")
