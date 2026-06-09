import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.schemas.signals import Signal, SignalBatch
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.reddit")

SUBREDDITS = [
    "startups",
    "entrepreneur",
    "SaaS",
    "artificial",
    "SideProject",
    "smallbusiness",
]


class RedditOAuthToken:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at: datetime = datetime.min
        self._token_type: str = "bearer"

    @property
    def is_valid(self) -> bool:
        return self._access_token is not None and datetime.utcnow() < self._expires_at

    @property
    def header_value(self) -> str:
        return f"{self._token_type} {self._access_token}"

    def update(self, token: str, expires_in: int, token_type: str = "bearer") -> None:
        expires_in = max(60, int(expires_in))
        self._access_token = token
        self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
        self._token_type = token_type
        logger.info("Reddit OAuth token refreshed, expires in %ds", expires_in)

    def invalidate(self) -> None:
        self._access_token = None
        self._expires_at = datetime.min


class RedditCollector:
    def __init__(self) -> None:
        settings = get_settings()
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self.user_agent = settings.reddit_user_agent
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        self._token = RedditOAuthToken()
        missing = []
        if not self.client_id:
            missing.append("REDDIT_CLIENT_ID")
        if not self.client_secret:
            missing.append("REDDIT_CLIENT_SECRET")
        if not self.user_agent:
            missing.append("REDDIT_USER_AGENT")
        if missing:
            raise RuntimeError(
                "Missing Reddit OAuth configuration: " + ", ".join(missing)
            )
        logger.info("Reddit OAuth2 enabled (client_id=%s...)", self.client_id[:8])

    async def _ensure_token(self) -> None:
        if self._token.is_valid:
            return

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"User-Agent": self.user_agent},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token.update(
                token=data["access_token"],
                expires_in=data.get("expires_in", 3600),
                token_type=data.get("token_type", "bearer"),
            )

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self._token.is_valid:
            headers["Authorization"] = self._token.header_value
        return headers

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=False,
    )
    async def _fetch_subreddit(self, subreddit: str, sort: str = "hot", limit: int = 25) -> SignalBatch:
        try:
            await self._ensure_token()

            url = f"https://oauth.reddit.com/r/{subreddit}/{sort}.json"
            params = {"limit": min(limit, 100), "t": "week", "raw_json": 1}

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._get_headers(), params=params)

                if resp.status_code == 401:
                    logger.warning("Reddit 401 for r/%s, refreshing token", subreddit)
                    self._token.invalidate()
                    await self._ensure_token()
                    resp = await client.get(url, headers=self._get_headers(), params=params)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    logger.warning("Reddit rate limited for r/%s, waiting %ds", subreddit, retry_after)
                    await asyncio.sleep(retry_after)
                    resp = await client.get(url, headers=self._get_headers(), params=params)

                resp.raise_for_status()
                data = resp.json()

            return self._parse_children(data, subreddit, limit)
        except Exception as exc:
            logger.error("Reddit fetch failed for r/%s: %s", subreddit, exc)
            raise

    def _parse_children(self, data: dict, subreddit: str, limit: int) -> SignalBatch:
        signals = []
        children = data.get("data", {}).get("children", [])
        for child in children[:limit]:
            d = child.get("data", {})
            if not d.get("title"):
                continue
            signals.append(
                Signal(
                    source="reddit",
                    source_id=d.get("id", ""),
                    source_type="post",
                    title=d.get("title", ""),
                    content=(d.get("selftext") or "")[:2000],
                    url=f"https://reddit.com{d.get('permalink', '')}",
                    author=d.get("author", ""),
                    score=d.get("score", 0),
                    comments_count=d.get("num_comments", 0),
                    collected_at=datetime.utcnow(),
                    created_at=datetime.utcfromtimestamp(d.get("created_utc", 0)),
                    metadata={
                        "subreddit": subreddit,
                        "upvote_ratio": d.get("upvote_ratio", 0),
                        "over_18": d.get("over_18", False),
                        "is_self": d.get("is_self", False),
                        "link_url": d.get("url", ""),
                        "oauth_used": True,
                        "credibility_score": score_source("reddit", "post"),
                    },
                )
            )
        logger.info("Collected %d posts from r/%s", len(signals), subreddit)
        return SignalBatch(source="reddit", signals=signals)

    async def collect_all(self, limit_per_sub: int = 15, fast_mode: bool = False) -> SignalBatch:
        all_signals = []
        for sub in SUBREDDITS:
            try:
                batch = await self._fetch_subreddit(sub, sort="hot", limit=limit_per_sub)
                all_signals.extend(batch.signals)
            except Exception as exc:
                logger.warning("Failed to collect r/%s: %s", sub, exc)
            if not fast_mode:
                await asyncio.sleep(2)
        logger.info("Reddit total: %d signals (oauth=%s)", len(all_signals), True)
        return SignalBatch(source="reddit", signals=all_signals)
