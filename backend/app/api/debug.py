from fastapi import APIRouter, Query

from app.services.collector_debug import run_collector_probe

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/github")
async def debug_github(query: str = Query("fitness")):
    return await run_collector_probe("github", query)


@router.get("/rss")
async def debug_rss(query: str = Query("fitness")):
    return await run_collector_probe("rss", query)


@router.get("/hackernews")
async def debug_hackernews(query: str = Query("fitness")):
    return await run_collector_probe("hackernews", query)


@router.get("/stackexchange")
async def debug_stackexchange(query: str = Query("fitness")):
    return await run_collector_probe("stackexchange", query)


@router.get("/google-trends")
async def debug_google_trends(query: str = Query("fitness")):
    return await run_collector_probe("google-trends", query)
