from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.postgres import get_db
from app.repositories.market_signal_repository import list_recent, count
from app.services.dashboard import get_dashboard_metrics, get_opportunities_dashboard
from app.utils.logging import get_logger

logger = get_logger("api.signals")
router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/latest")
async def get_latest_signals(limit: int = 20, db: AsyncSession = Depends(get_db)):
    signals = await list_recent(db, limit=limit)
    return {
        "signals": [
            {
                "id": str(s.id),
                "source": s.source,
                "source_type": s.source_type,
                "title": s.title,
                "content": s.content[:200],
                "url": s.url,
                "author": s.author,
                "score": s.score,
                "credibility_score": s.credibility_score,
                "collected_at": s.collected_at.isoformat() if s.collected_at else None,
            }
            for s in signals
        ],
        "count": len(signals),
    }


@router.get("/stats")
async def get_signal_stats(db: AsyncSession = Depends(get_db)):
    return await get_dashboard_metrics(db)


@router.get("/dashboard")
async def get_full_dashboard(db: AsyncSession = Depends(get_db)):
    metrics = await get_dashboard_metrics(db)
    opps = await get_opportunities_dashboard(db)
    return {**metrics, **opps}
