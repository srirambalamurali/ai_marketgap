import httpx
from datetime import datetime
import asyncio
from urllib.parse import quote_plus
from xml.etree import ElementTree
from app.config import get_settings
from app.schemas.signals import Signal, SignalBatch
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.rss")

RSS_FEEDS = {
    "techcrunch": "https://techcrunch.com/feed/",
    "venturebeat": "https://venturebeat.com/feed/",
    "producthunt": "https://www.producthunt.com/feed",
    "indiehackers": "https://www.indiehackers.com/feed",
    "hackernoon": "https://hackernoon.com/feed",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "zdnet": "https://www.zdnet.com/news/rss.xml",
    "mit_technology_review": "https://www.technologyreview.com/feed/",
    "saastr": "https://www.saastr.com/feed/",
    "ycombinator": "https://news.ycombinator.com/rss",
    "hackernews": "https://hnrss.org/frontpage",
}


class RSSCollector:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = httpx.Timeout(float(settings.request_timeout_seconds))

    async def _fetch_feed(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, follow_redirects=True)
                logger.info("RSS request url=%s status=%s", resp.request.url, resp.status_code)
                resp.raise_for_status()
                return resp.text
        except httpx.TimeoutException as exc:
            logger.warning("RSS timeout url=%s reason=%s", url, exc)
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "RSS request failed url=%s status=%s body=%s",
                getattr(exc.request, "url", url),
                exc.response.status_code,
                exc.response.text[:300],
            )
            return None
        except Exception as exc:
            logger.error("Failed to fetch RSS feed %s: %s", url, exc)
            return None

    def _parse_feed(self, xml_text: str, source_name: str) -> list[Signal]:
        signals = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            logger.error("Failed to parse RSS XML from %s: %s", source_name, exc)
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}

        items = root.findall(".//item")
        if not items:
            items = root.findall(".//atom:entry", ns)

        for item in items:
            title = ""
            link = ""
            description = ""
            pub_date = None
            author = ""

            title_el = item.find("title")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()

            link_el = item.find("link")
            if link_el is not None:
                link = link_el.text.strip() if link_el.text else (link_el.get("href", ""))

            desc_el = item.find("description")
            if desc_el is None:
                desc_el = item.find("atom:summary", ns)
            if desc_el is None:
                desc_el = item.find("atom:content", ns)
            if desc_el is not None:
                import re
                raw = desc_el.text or ""
                if not raw:
                    raw = ElementTree.tostring(desc_el, encoding="unicode")
                    raw = re.sub(r"<[^>]+>", "", raw)
                description = re.sub(r"<[^>]+>", "", raw).strip()[:2000]

            pub_el = item.find("pubDate") or item.find("atom:updated", ns)
            if pub_el is not None and pub_el.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pub_el.text)
                except Exception:
                    try:
                        pub_date = datetime.fromisoformat(pub_el.text.replace("Z", "+00:00"))
                    except Exception:
                        pub_date = datetime.utcnow()

            author_el = item.find("author") or item.find("atom:author/atom:name", ns)
            if author_el is not None and author_el.text:
                author = author_el.text.strip()

            if title:
                source = "hackernews" if source_name in {"hackernews", "ycombinator"} else "rss"
                signals.append(Signal(
                    source=source,
                    source_type=source_name,
                    title=title,
                    content=description,
                    url=link,
                    author=author or source_name,
                    score=0,
                    collected_at=datetime.utcnow(),
                    created_at=pub_date or datetime.utcnow(),
                    metadata={
                        "credibility_score": score_source(source, source_name),
                        "feed": source_name,
                    },
                ))

        return signals

    async def collect_feed(self, name: str, url: str, limit: int = 20) -> SignalBatch:
        xml_text = await self._fetch_feed(url)
        if not xml_text:
            source = "hackernews" if name in {"hackernews", "ycombinator"} else "rss"
            return SignalBatch(source=source, signals=[])
        signals = self._parse_feed(xml_text, name)[:limit]
        logger.info("Collected %d items from RSS feed '%s'", len(signals), name)
        source = "hackernews" if name in {"hackernews", "ycombinator"} else "rss"
        return SignalBatch(source=source, signals=signals)

    async def _collect_google_news(self, query: str, limit: int = 10) -> SignalBatch:
        if not query.strip():
            return SignalBatch(source="rss", signals=[])
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        batch = await self.collect_feed(f"google_news:{query}", url, limit=limit)
        for signal in batch.signals:
            signal.source_type = "google_news"
        return batch

    async def collect_all(self, query: str | None = None, limit_per_feed: int = 20) -> SignalBatch:
        all_signals = []
        prioritized_signals = []
        fast_feed_names = ["techcrunch", "venturebeat"]
        secondary_feed_names = [
            "producthunt",
            "indiehackers",
            "hackernoon",
            "theverge",
            "arstechnica",
            "zdnet",
            "mit_technology_review",
            "saastr",
            "ycombinator",
            "hackernews",
        ]
        tasks = [
            asyncio.create_task(self.collect_feed(name, RSS_FEEDS[name], limit=limit_per_feed))
            for name in fast_feed_names
        ]
        for batch in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(batch, Exception):
                logger.warning("RSS feed batch failed: %s", batch)
                continue
            all_signals.extend(batch.signals)
        secondary_tasks = [
            asyncio.create_task(self.collect_feed(name, RSS_FEEDS[name], limit=max(4, limit_per_feed // 2)))
            for name in secondary_feed_names
        ]
        for batch in await asyncio.gather(*secondary_tasks, return_exceptions=True):
            if isinstance(batch, Exception):
                logger.warning("RSS secondary feed batch failed: %s", batch)
                continue
            all_signals.extend(batch.signals)
        if query:
            try:
                query_variants = [part.strip() for part in query.split("||") if part.strip()] or [query]
                for variant in query_variants[:3]:
                    google_news_batch = await self._collect_google_news(variant, limit=max(5, limit_per_feed // 2))
                    prioritized_signals.extend(google_news_batch.signals)
            except Exception as exc:
                logger.warning("Google News RSS collection failed for %r: %s", query, exc)
        all_signals = prioritized_signals + all_signals
        logger.info("RSS total: %d signals", len(all_signals))
        return SignalBatch(source="rss", signals=all_signals)
