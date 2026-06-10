from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.postgres import get_db
from app.collectors.github_collector import GitHubIntelligenceCollector
from app.collectors.hackernews_collector import HackerNewsCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.reddit_collector import RedditCollector
from app.collectors.google_trends_collector import GoogleTrendsCollector
from app.collectors.stackexchange_collector import StackExchangeCollector
from app.repositories.market_signal_repository import list_recent, count
from app.services.dashboard import get_dashboard_metrics
from app.scheduler.jobs import get_job_status
from app.utils.logging import get_logger

logger = get_logger("api.collect")
router = APIRouter(prefix="/collect", tags=["collection"])

@router.post("/run")
async def run_all_collectors(db: AsyncSession = Depends(get_db)):
    from app.services.signal_pipeline import SignalIngestionPipeline

    pipeline = SignalIngestionPipeline()
    results = {}
    collectors = [
        ("github", GitHubIntelligenceCollector()),
        ("hackernews", HackerNewsCollector()),
        ("rss", RSSCollector()),
        ("reddit", RedditCollector()),
        ("google_trends", GoogleTrendsCollector()),
        ("stackexchange", StackExchangeCollector()),
    ]
    for name, collector in collectors:
        try:
            if name == "github":
                batch = await collector.collect_all("AI startup")
            else:
                batch = await collector.collect_all()
            metrics = await pipeline.process_batch(batch, db)
            await db.commit()
            results[name] = {"success": True, "metrics": metrics}
        except Exception as exc:
            logger.error("Collector %s failed: %s", name, exc)
            results[name] = {"success": False, "error": str(exc)}
    return {"results": results}


@router.post("/signals/github")
async def collect_github_signals(query: str = "AI startup", db: AsyncSession = Depends(get_db)):
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = GitHubIntelligenceCollector()
        batch = await collector.collect_all(query)
        metrics = await pipeline.process_batch(batch, db)
        await db.commit()
        return {"success": True, "signals_collected": metrics.get("signals_collected", 0), "metrics": metrics}
    except Exception as exc:
        logger.error("GitHub collection failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/hackernews")
async def collect_hackernews(db: AsyncSession = Depends(get_db)):
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = HackerNewsCollector()
        batch = await collector.collect_all()
        metrics = await pipeline.process_batch(batch, db)
        await db.commit()
        return {"success": True, "signals_collected": metrics.get("signals_collected", 0), "metrics": metrics}
    except Exception as exc:
        logger.error("Hacker News collection failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/rss")
async def collect_rss(db: AsyncSession = Depends(get_db)):
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = RSSCollector()
        batch = await collector.collect_all()
        metrics = await pipeline.process_batch(batch, db)
        await db.commit()
        return {"success": True, "signals_collected": metrics.get("signals_collected", 0), "metrics": metrics}
    except Exception as exc:
        logger.error("RSS collection failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/reddit")
async def collect_reddit(db: AsyncSession = Depends(get_db)):
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = RedditCollector()
        batch = await collector.collect_all()
        metrics = await pipeline.process_batch(batch, db)
        await db.commit()
        return {"success": True, "signals_collected": metrics.get("signals_collected", 0), "metrics": metrics}
    except Exception as exc:
        logger.error("Reddit collection failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/google-trends")
async def collect_google_trends(db: AsyncSession = Depends(get_db)):
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = GoogleTrendsCollector()
        batch = await collector.collect_all()
        metrics = await pipeline.process_batch(batch, db)
        await db.commit()
        return {"success": True, "signals_collected": metrics.get("signals_collected", 0), "metrics": metrics}
    except Exception as exc:
        logger.error("Google Trends collection failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/stackexchange")
async def collect_stackexchange(db: AsyncSession = Depends(get_db)):
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = StackExchangeCollector()
        batch = await collector.collect_all(keywords=["workflow", "automation", "software"], domain="general")
        metrics = await pipeline.process_batch(batch, db)
        await db.commit()
        return {"success": True, "signals_collected": metrics.get("signals_collected", 0), "metrics": metrics}
    except Exception as exc:
        logger.error("StackExchange collection failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.get("/status")
async def get_collection_status():
    jobs = get_job_status()
    return {"scheduler_jobs": jobs, "status": "running" if jobs else "idle"}
