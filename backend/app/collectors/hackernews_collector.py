from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from app.schemas.signals import Signal, SignalBatch
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.hackernews")

HN_API = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector:
    def __init__(self) -> None:
        self.timeout = httpx.Timeout(4.0, connect=1.5)

    async def _fetch_json(self, url: str) -> dict | list | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.debug("HN request failed for %s: %s", url, exc)
            return None

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

        async def _fetch_item(item_id: int) -> dict | None:
            return await self._fetch_json(f"{HN_API}/item/{item_id}.json")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [client.get(f"{HN_API}/item/{sid}.json") for sid in ids[:limit]]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        signals: list[Signal] = []
        for sid, resp in zip(ids[:limit], responses):
            if isinstance(resp, Exception):
                continue
            try:
                resp.raise_for_status()
                item = resp.json()
            except Exception:
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

    async def collect_all(self, limit_per_type: int = 15) -> SignalBatch:
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
        logger.info("HN total: %d signals", len(all_signals))
        return SignalBatch(source="hackernews", signals=all_signals)
