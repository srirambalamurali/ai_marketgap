from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from app.database.postgres import async_session
from app.collectors.github_collector import GitHubIntelligenceCollector
from app.collectors.hackernews_collector import HackerNewsCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.reddit_collector import RedditCollector
from app.collectors.google_trends_collector import GoogleTrendsCollector
from app.utils.logging import get_logger

logger = get_logger("scheduler")

scheduler = AsyncIOScheduler()


async def run_github_collection() -> None:
    logger.info("Starting GitHub collection job")
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = GitHubIntelligenceCollector()
        async with async_session() as session:
            batch = await collector.collect_all("AI startup")
            await pipeline.process_batch(batch, session)
            await session.commit()
        logger.info("GitHub collection job completed")
    except Exception as exc:
        logger.error("GitHub collection job failed: %s", exc)


async def run_hackernews_collection() -> None:
    logger.info("Starting Hacker News collection job")
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = HackerNewsCollector()
        async with async_session() as session:
            batch = await collector.collect_all()
            await pipeline.process_batch(batch, session)
            await session.commit()
        logger.info("Hacker News collection job completed")
    except Exception as exc:
        logger.error("Hacker News collection job failed: %s", exc)


async def run_rss_collection() -> None:
    logger.info("Starting RSS collection job")
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = RSSCollector()
        async with async_session() as session:
            batch = await collector.collect_all()
            await pipeline.process_batch(batch, session)
            await session.commit()
        logger.info("RSS collection job completed")
    except Exception as exc:
        logger.error("RSS collection job failed: %s", exc)


async def run_reddit_collection() -> None:
    logger.info("Starting Reddit collection job")
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = RedditCollector()
        async with async_session() as session:
            batch = await collector.collect_all()
            await pipeline.process_batch(batch, session)
            await session.commit()
        logger.info("Reddit collection job completed")
    except Exception as exc:
        logger.error("Reddit collection job failed: %s", exc)


async def run_google_trends_collection() -> None:
    logger.info("Starting Google Trends collection job")
    try:
        from app.services.signal_pipeline import SignalIngestionPipeline

        pipeline = SignalIngestionPipeline()
        collector = GoogleTrendsCollector()
        async with async_session() as session:
            batch = await collector.collect_all()
            await pipeline.process_batch(batch, session)
            await session.commit()
        logger.info("Google Trends collection job completed")
    except Exception as exc:
        logger.error("Google Trends collection job failed: %s", exc)


def _job_listener(event) -> None:
    if event.exception:
        logger.error("Job %s failed: %s", event.job_id, event.exception)
    else:
        logger.debug("Job %s completed successfully", event.job_id)


def register_jobs() -> None:
    existing_ids = {j.id for j in scheduler.get_jobs()}
    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    job_specs = [
        (run_github_collection, "interval", "github_collection", {"minutes": 30}),
        (run_hackernews_collection, "interval", "hackernews_collection", {"minutes": 15}),
        (run_rss_collection, "interval", "rss_collection", {"minutes": 60}),
        (run_reddit_collection, "interval", "reddit_collection", {"minutes": 20}),
        (run_google_trends_collection, "interval", "google_trends_collection", {"minutes": 60}),
    ]

    for func, trigger_type, job_id, trigger_kwargs in job_specs:
        if job_id not in existing_ids:
            scheduler.add_job(
                func,
                trigger_type,
                id=job_id,
                replace_existing=True,
                max_instances=1,
                **trigger_kwargs,
            )

    logger.info("Scheduler jobs registered: github(30m), hackernews(15m), rss(60m), reddit(20m), google_trends(60m)")


def start_scheduler() -> None:
    register_jobs()
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")


def get_job_status() -> dict[str, dict]:
    jobs = {}
    for job in scheduler.get_jobs():
        jobs[job.id] = {
            "id": job.id,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
    return jobs
