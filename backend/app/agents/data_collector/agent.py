from typing import Any
from app.agents.base import BaseAgent
from app.repositories.market_signal_repository import list_recent, list_by_source
from app.utils.logging import get_logger


class DataCollectorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="data_collector")

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        query = state.get("query", "")
        self.logger.info("Collecting data for query: %s", query)

        from app.database.postgres import async_session
        documents = []
        recent_signals = []
        signal_summary = ""

        try:
            async with async_session() as session:
                recent = await list_recent(session, limit=50)
                for s in recent:
                    doc = {
                        "id": str(s.id),
                        "source": s.source,
                        "source_type": s.source_type,
                        "title": s.title,
                        "content": s.content,
                        "url": s.url,
                        "author": s.author,
                        "score": s.score,
                        "credibility_score": s.credibility_score,
                        "collected_at": s.collected_at.isoformat() if s.collected_at else None,
                    }
                    documents.append(doc)
                    recent_signals.append(doc)

                source_counts = {}
                for src in ["github", "hackernews", "rss", "reddit", "google_trends"]:
                    sigs = await list_by_source(session, src, limit=5)
                    source_counts[src] = len(sigs)

                signal_summary = (
                    f"Total recent signals: {len(documents)}. "
                    f"By source: {source_counts}. "
                    f"Top sources by count: "
                    f"{', '.join(f'{k}({v})' for k, v in sorted(source_counts.items(), key=lambda x: -x[1]) if v > 0)}"
                )
        except Exception as exc:
            self.logger.error("Failed to fetch signals from database: %s", exc)

        self.logger.info("Collected %d documents from market_signals", len(documents))
        return {
            "documents": documents,
            "recent_signals": recent_signals,
            "signal_summary": signal_summary,
        }
