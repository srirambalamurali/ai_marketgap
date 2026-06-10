from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

from app.collectors.github_collector import GitHubIntelligenceCollector
from app.collectors.google_trends_collector import GoogleTrendsCollector
from app.collectors.hackernews_collector import HackerNewsCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.stackexchange_collector import StackExchangeCollector
from app.services.query_guardrails import build_domain_profile


def _query_terms(query: str) -> list[str]:
    profile = build_domain_profile(query)
    related = [term.strip() for term in profile.get("related_terms", []) if str(term).strip()]
    keywords = [query.strip(), *related[:5]]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in keywords:
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


async def run_collector_probe(source: str, query: str) -> dict[str, Any]:
    profile = build_domain_profile(query)
    domain = profile["query_domain"]
    related_terms = _query_terms(query)
    started = time.perf_counter()

    try:
        if source == "github":
            batch = await GitHubIntelligenceCollector().collect_all(" || ".join(related_terms[:4]) or query)
        elif source == "rss":
            batch = await RSSCollector().collect_all(query=query, limit_per_feed=5)
        elif source == "hackernews":
            batch = await HackerNewsCollector().collect_all(limit_per_type=2, query=query)
        elif source == "stackexchange":
            batch = await StackExchangeCollector().collect_all(
                keywords=related_terms[:4] or [query],
                domain=domain,
                limit_per_site=4,
            )
        elif source == "google-trends":
            batch = await GoogleTrendsCollector().collect_all(related_terms[:3] or [query])
        else:
            raise ValueError(f"Unsupported source: {source}")

        signals = batch.signals or []
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": len(signals) > 0,
            "signals_collected": len(signals),
            "latency_ms": latency_ms,
            "error": None if signals else "No live signals collected from source",
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "signals_collected": 0,
            "latency_ms": latency_ms,
            "error": str(exc),
        }
