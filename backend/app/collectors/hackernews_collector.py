from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from app.config import get_settings
from app.schemas.signals import Signal, SignalBatch
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.hackernews")

HN_API = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))

    async def _fetch_json(self, url: str, *, retry_once: bool = True) -> dict | list | None:
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "AI Market Gap Debugger/1.0"}) as client:
                    resp = await client.get(url)
                    logger.info("HN request url=%s status=%s attempt=%s", resp.request.url, resp.status_code, attempt)
                    resp.raise_for_status()
                    return resp.json()
            except httpx.TimeoutException as exc:
                logger.warning("HN timeout url=%s attempt=%s reason=%s", url, attempt, exc)
                if retry_once and attempt == 1:
                    continue
                return None
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HN request failed url=%s status=%s body=%s",
                    getattr(exc.request, "url", url),
                    exc.response.status_code,
                    exc.response.text[:300],
                )
                return None
            except Exception as exc:
                logger.warning("HN request failed url=%s attempt=%s reason=%s", url, attempt, exc)
                return None

    async def _search_algolia(self, query: str, limit: int = 20) -> list[Signal]:
        query = query.strip()
        if not query:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "AI Market Gap Debugger/1.0"}) as client:
                resp = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={
                        "query": query,
                        "tags": "story",
                        "hitsPerPage": min(limit, 20),
                    },
                )
                logger.info("HN Algolia request url=%s status=%s query=%s", resp.request.url, resp.status_code, query)
                resp.raise_for_status()
                items = resp.json().get("hits", [])[:limit]
                if not isinstance(items, list):
                    logger.warning("HN Algolia parse failure query=%r payload_keys=%s", query, list(resp.json().keys())[:10])
                    return []
                if not items:
                    logger.info("HN Algolia returned no items for query=%r", query)
        except Exception as exc:
            logger.warning("HN Algolia search failed query=%r reason=%s", query, exc)
            return []

        signals: list[Signal] = []
        for item in items:
            title = item.get("title") or ""
            url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
            content = item.get("_highlightResult", {}).get("title", {}).get("value") or item.get("story_text") or item.get("comment_text") or ""
            if not title and not content:
                continue
            signals.append(
                Signal(
                    source="hackernews",
                    source_type="story",
                    title=title or query,
                    content=str(content)[:2000],
                    url=url,
                    author=item.get("author", ""),
                    score=int(item.get("points") or 0),
                    comments_count=int(item.get("num_comments") or 0),
                    collected_at=datetime.utcnow(),
                    metadata={
                        "provider": "algolia",
                        "algolia_id": item.get("objectID"),
                    },
                )
            )
        return signals

    async def _fetch_story_ids(self, list_type: str) -> list[int]:
        data = await self._fetch_json(f"{HN_API}/{list_type}.json")
        return list(data or [])

    def _item_to_signal(self, item: dict) -> Signal:
        return Signal(
            source="hackernews",
            source_type=item.get("type", "story"),
            title=item.get("title", ""),
            content=(item.get("text", "") or "")[:2000],
            url=item.get("url", f"https://news.ycombinator.com/item?id={item.get('id')}"),
            author=item.get("by", ""),
            score=item.get("score", 0),
            comments_count=item.get("descendants", 0),
            collected_at=datetime.utcnow(),
            metadata={
                "hn_id": item.get("id"),
                "type": item.get("type"),
                "kids": item.get("kids", [])[:10],
            },
        )

    async def _fetch_story_batch(self, list_type: str, limit: int, source_type: str | None = None) -> list[Signal]:
        ids = await self._fetch_story_ids(list_type)
        if not ids:
            return []

        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "AI Market Gap Debugger/1.0"}) as client:
            tasks = [client.get(f"{HN_API}/item/{sid}.json") for sid in ids[:limit]]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        signals: list[Signal] = []
        for sid, resp in zip(ids[:limit], responses):
            if isinstance(resp, Exception):
                logger.warning("HN item request failed item_id=%s reason=%s", sid, resp)
                continue
            try:
                logger.info("HN item request url=%s status=%s item_id=%s", resp.request.url, resp.status_code, sid)
                resp.raise_for_status()
                item = resp.json()
            except Exception:
                logger.warning("HN item parse failure item_id=%s", sid)
                continue
            if not item or item.get("type") != "story":
                continue
            sig = self._item_to_signal(item)
            if source_type:
                sig.source_type = source_type
            sig.metadata["credibility_score"] = score_source("hackernews", sig.source_type)
            signals.append(sig)
        return signals

    async def collect_top_stories(self, limit: int = 20) -> SignalBatch:
        signals = await self._fetch_story_batch("topstories", limit)
        logger.info("Collected %d top HN stories", len(signals))
        return SignalBatch(source="hackernews", signals=signals)

    async def collect_ask_hn(self, limit: int = 20) -> SignalBatch:
        signals = await self._fetch_story_batch("askstories", limit, source_type="ask_hn")
        logger.info("Collected %d Ask HN stories", len(signals))
        return SignalBatch(source="hackernews", signals=signals)

    async def collect_show_hn(self, limit: int = 20) -> SignalBatch:
        signals = await self._fetch_story_batch("showstories", limit, source_type="show_hn")
        logger.info("Collected %d Show HN stories", len(signals))
        return SignalBatch(source="hackernews", signals=signals)

    async def collect_new_stories(self, limit: int = 20) -> SignalBatch:
        signals = await self._fetch_story_batch("newstories", limit, source_type="new_story")
        logger.info("Collected %d new HN stories", len(signals))
        return SignalBatch(source="hackernews", signals=signals)

    async def collect_all(self, limit_per_type: int = 15, query: str | None = None) -> SignalBatch:
        batches = await asyncio.gather(
            self.collect_top_stories(limit_per_type),
            self.collect_ask_hn(limit_per_type),
            self.collect_show_hn(limit_per_type),
            self.collect_new_stories(limit_per_type),
            return_exceptions=True,
        )
        all_signals: list[Signal] = []
        for batch in batches:
            if isinstance(batch, Exception):
                logger.warning("HN batch failed: %s", batch)
                continue
            all_signals.extend(batch.signals)
        if query:
            query_variants = [part.strip() for part in query.split("||") if part.strip()] or [query]
            for variant in query_variants[:3]:
                all_signals.extend(await self._search_algolia(variant, limit=max(5, limit_per_type)))
        logger.info("HN total: %d signals", len(all_signals))
        return SignalBatch(source="hackernews", signals=all_signals)
