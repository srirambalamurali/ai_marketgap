from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.schemas.signals import Signal, SignalBatch
from app.database.postgres import async_session
from app.models.market_signal import MarketSignal
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.google_trends")

FOCUS_KEYWORDS = [
    "artificial intelligence",
    "SaaS startup",
    "productivity tools",
    "automation software",
    "AI agent",
]

REQUEST_DELAY_SECONDS = 6
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_TTL = 3600
_cache: dict[str, dict] = {}


def _cache_key(prefix: str, keyword: str) -> str:
    raw = f"{prefix}:{keyword}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{key}.json")


def _load_cached_signals(key: str) -> list[Signal] | None:
    if key in _cache:
        data = _cache[key]
        if time.time() - data.get("ts", 0) < CACHE_TTL:
            return [Signal.model_validate(item) for item in data.get("signals", [])]
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("ts", 0)
        if time.time() - ts >= CACHE_TTL:
            return None
        return [Signal.model_validate(item) for item in data.get("signals", [])]
    except Exception as exc:
        logger.debug("Cache read failed for %s: %s", key, exc)
        return None


def _store_cached_signals(key: str, signals: list[Signal]) -> None:
    try:
        payload = {"ts": time.time(), "signals": [s.model_dump(mode="json") for s in signals]}
        _cache[key] = payload
        path = _cache_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as exc:
        logger.debug("Cache write failed for %s: %s", key, exc)


class GoogleTrendsCollector:
    def __init__(self) -> None:
        self._trends = None
        self._last_request_time = 0.0

    def _get_client(self):
        if self._trends is None:
            from pytrends.request import TrendReq

            self._trends = TrendReq(hl="en-US", tz=360)
        return self._trends

    async def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.time()

    def _build_payload(self, keyword: str) -> None:
        client = self._get_client()
        client.build_payload([keyword], cat=0, timeframe="today 1-m")

    def _build_signals_for_keyword(self, keyword: str) -> list[Signal]:
        self._build_payload(keyword)
        client = self._get_client()
        signals: list[Signal] = []

        related = client.related_queries() or {}
        kw_data = related.get(keyword)
        rising = kw_data.get("rising") if kw_data else None
        if rising is not None and not rising.empty:
            for _, row in rising.head(10).iterrows():
                query = row.iloc[0] if len(row) > 0 else ""
                value = row.iloc[1] if len(row) > 1 else 0
                if not query:
                    continue
                signals.append(
                    Signal(
                        source="google_trends",
                        source_id=f"related:{keyword}:{query}",
                        source_type="rising_query",
                        title=f"Rising query: {query}",
                        content=f"Rising search query related to '{keyword}': {query}",
                        url=f"https://trends.google.com/trends/explore?q={query.replace(' ', '+')}",
                        author="google_trends",
                        score=int(value) if isinstance(value, (int, float)) else 50,
                        collected_at=datetime.utcnow(),
                        metadata={
                            "trend_keyword": keyword,
                            "growth_score": int(value) if isinstance(value, (int, float)) else 50,
                            "category": "rising_query",
                            "credibility_score": score_source("google_trends", "rising_query"),
                        },
                    )
                )

        iot = client.interest_over_time()
        if iot is not None and not iot.empty and keyword in iot.columns:
            latest = iot[keyword].iloc[-1]
            previous_avg = iot[keyword].iloc[:-1].mean()
            growth = ((latest - previous_avg) / previous_avg) * 100 if previous_avg > 0 else 0
            signals.append(
                Signal(
                    source="google_trends",
                    source_id=f"iot:{keyword}",
                    source_type="interest_trend",
                    title=f"Interest trend: {keyword}",
                    content=f"Search interest for '{keyword}': latest={int(latest)}, growth={growth:.1f}%",
                    url=f"https://trends.google.com/trends/explore?q={keyword.replace(' ', '+')}",
                    author="google_trends",
                    score=int(latest),
                    collected_at=datetime.utcnow(),
                    metadata={
                        "trend_keyword": keyword,
                        "growth_score": round(growth, 1),
                        "category": "interest_trend",
                        "latest_interest": int(latest),
                        "credibility_score": score_source("google_trends", "interest_trend"),
                    },
                )
            )

        ibr = client.interest_by_region(resolution="COUNTRY", inc_low_vol=True, inc_geo_code=False)
        if ibr is not None and not ibr.empty and keyword in ibr.columns:
            top_regions = ibr[keyword].nlargest(5)
            for region, value in top_regions.items():
                if value == 0:
                    continue
                signals.append(
                    Signal(
                        source="google_trends",
                        source_id=f"region:{keyword}:{region}",
                        source_type="regional_interest",
                        title=f"Regional interest: {keyword} in {region}",
                        content=f"'{keyword}' interest in {region}: score {int(value)}",
                        url=f"https://trends.google.com/trends/explore?q={keyword.replace(' ', '+')}&geo={region}",
                        author="google_trends",
                        score=int(value),
                        collected_at=datetime.utcnow(),
                        metadata={
                            "trend_keyword": keyword,
                            "region": region,
                            "growth_score": int(value),
                            "category": "regional_interest",
                            "credibility_score": score_source("google_trends", "interest_trend"),
                        },
                    )
                )

        return signals

    async def _collect_keyword(self, keyword: str) -> list[Signal]:
        key = _cache_key("keyword", keyword)
        cached = _load_cached_signals(key)
        if cached is not None:
            return cached
        try:
            await self._throttle()
            signals = await asyncio.to_thread(self._build_signals_for_keyword, keyword)
            _store_cached_signals(key, signals)
            return signals
        except Exception as exc:
            logger.warning("Google Trends collection failed for '%s': %s", keyword, exc)
            return []

    async def collect_all(self, keywords: list[str] | None = None) -> SignalBatch:
        all_keywords = list(dict.fromkeys((keywords or FOCUS_KEYWORDS)))[:3]
        all_signals = []
        for keyword in all_keywords:
            all_signals.extend(await self._collect_keyword(keyword))

        logger.info("Google Trends total: %d signals", len(all_signals))
        return SignalBatch(source="google_trends", signals=all_signals)
