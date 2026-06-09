import httpx
from datetime import datetime
import asyncio
from xml.etree import ElementTree
from app.schemas.signals import Signal, SignalBatch
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("collectors.rss")

RSS_FEEDS = {
    "techcrunch": "https://techcrunch.com/feed/",
    "venturebeat": "https://venturebeat.com/feed/",
    "ycombinator": "https://news.ycombinator.com/rss",
    "hackernews": "https://hnrss.org/frontpage",
}


class RSSCollector:
    def __init__(self) -> None:
        self.timeout = httpx.Timeout(6.0, connect=2.5)

    async def _fetch_feed(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                return resp.text
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

    async def collect_all(self, limit_per_feed: int = 20) -> SignalBatch:
        all_signals = []
        fast_feed_names = ["techcrunch", "venturebeat"]
        tasks = [
            asyncio.create_task(self.collect_feed(name, RSS_FEEDS[name], limit=limit_per_feed))
            for name in fast_feed_names
        ]
        for batch in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(batch, Exception):
                logger.warning("RSS feed batch failed: %s", batch)
                continue
            all_signals.extend(batch.signals)
        logger.info("RSS total: %d signals", len(all_signals))
        return SignalBatch(source="rss", signals=all_signals)
