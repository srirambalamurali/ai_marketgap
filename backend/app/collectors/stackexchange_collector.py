from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from app.config import get_settings
from app.schemas.signals import Signal, SignalBatch
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.stackexchange")

SO_API = "https://api.stackexchange.com/2.3"

SITE_MAP: dict[str, list[str]] = {
    "accounting": ["stackoverflow", "softwareengineering", "webmasters", "entrepreneurs"],
    "marketing": ["webmasters", "entrepreneurs", "softwareengineering", "stackoverflow"],
    "sales": ["entrepreneurs", "softwareengineering", "stackoverflow", "webmasters"],
    "restaurant": ["entrepreneurs", "softwareengineering", "stackoverflow"],
    "hr": ["entrepreneurs", "softwareengineering", "stackoverflow"],
    "legal": ["softwareengineering", "stackoverflow", "entrepreneurs"],
    "productivity": ["softwareengineering", "stackoverflow", "webmasters"],
    "education": ["softwareengineering", "stackoverflow", "webmasters"],
    "cybersecurity": ["stackoverflow", "softwareengineering", "webmasters"],
    "fitness": ["stackoverflow", "softwareengineering", "entrepreneurs"],
    "amazon": ["webmasters", "entrepreneurs", "stackoverflow"],
}


class StackExchangeCollector:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))

    def _sites_for_query(self, query: str, domain: str | None = None) -> list[str]:
        if domain and domain in SITE_MAP:
            return SITE_MAP[domain]
        query_lower = query.lower()
        for domain_name, sites in SITE_MAP.items():
            if domain_name in query_lower:
                return sites
        return ["stackoverflow", "softwareengineering", "webmasters", "entrepreneurs"]

    async def _search_site(self, site: str, query: str, limit: int = 5) -> list[Signal]:
        params = {
            "order": "desc",
            "sort": "relevance",
            "site": site,
            "q": query,
            "pagesize": min(limit, 20),
            "filter": "withbody",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "AI Market Gap Debugger/1.0"}) as client:
                resp = await client.get(f"{SO_API}/search/advanced", params=params)
                logger.info("StackExchange request url=%s status=%s", resp.request.url, resp.status_code)
                resp.raise_for_status()
                payload = resp.json()
                items = payload.get("items", [])[:limit]
                if payload.get("error_name"):
                    logger.warning(
                        "StackExchange API error site=%s query=%r code=%s error=%s",
                        site,
                        query,
                        payload.get("error_id"),
                        payload.get("error_message"),
                    )
                if payload.get("backoff"):
                    logger.warning("StackExchange backoff site=%s query=%r seconds=%s", site, query, payload.get("backoff"))
        except Exception as exc:
            logger.warning("StackExchange search failed for site=%s query=%r: %s", site, query, exc)
            return []

        signals: list[Signal] = []
        for item in items:
            title = (item.get("title") or "").strip()
            body = (item.get("body_markdown") or item.get("body") or "").strip()
            if not title and not body:
                continue
            signals.append(
                Signal(
                    source="stackexchange",
                    source_type=site,
                    source_id=str(item.get("question_id") or item.get("answer_id") or item.get("item_id") or title),
                    title=title or query,
                    content=body[:2000],
                    url=item.get("link", ""),
                    author=item.get("owner", {}).get("display_name", ""),
                    score=int(item.get("score") or 0),
                    comments_count=int(item.get("answer_count") or item.get("comment_count") or 0),
                    collected_at=datetime.utcnow(),
                    metadata={
                        "site": site,
                        "is_answered": item.get("is_answered", False),
                    },
                )
            )
        return signals

    async def collect_all(
        self,
        keywords: list[str] | None = None,
        *,
        domain: str | None = None,
        limit_per_site: int = 5,
    ) -> SignalBatch:
        queries = [kw.strip() for kw in (keywords or []) if kw and kw.strip()]
        if not queries:
            return SignalBatch(source="stackexchange", signals=[])
        queries = list(dict.fromkeys(queries[:4]))
        sites = self._sites_for_query(" ".join(queries), domain=domain)[:4]
        tasks = []
        for site in sites:
            for query in queries:
                tasks.append(self._search_site(site, query, limit=limit_per_site))

        all_signals: list[Signal] = []
        for batch in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(batch, Exception):
                continue
            all_signals.extend(batch)

        logger.info("StackExchange total: %d signals", len(all_signals))
        return SignalBatch(source="stackexchange", signals=all_signals)
