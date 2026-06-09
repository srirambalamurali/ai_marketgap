from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.models.market_signal import MarketSignal
from app.utils.logging import get_logger

router = APIRouter(prefix="/signals", tags=["signals"])
logger = get_logger("api.signals")


def _serialize(signal: MarketSignal) -> dict:
    return {
        "id": str(signal.id),
        "source": signal.source,
        "source_type": signal.source_type,
        "source_id": signal.source_id,
        "title": signal.title,
        "content": signal.content,
        "url": signal.url,
        "author": signal.author,
        "score": signal.score,
        "comments_count": signal.comments_count,
        "credibility_score": signal.credibility_score,
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
        "collected_at": signal.collected_at.isoformat() if signal.collected_at else None,
        "extra_metadata": signal.extra_metadata or {},
    }


@router.get("/latest")
async def get_latest_signals(limit: int = Query(25, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MarketSignal).order_by(desc(MarketSignal.collected_at)).limit(limit)
    )
    signals = result.scalars().all()
    return {"success": True, "count": len(signals), "signals": [_serialize(s) for s in signals]}


@router.get("/stats")
async def get_signal_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MarketSignal))
    signals = result.scalars().all()
    by_source: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_day: dict[str, int] = {}
    top_score = 0
    for signal in signals:
        by_source[signal.source] = by_source.get(signal.source, 0) + 1
        by_type[signal.source_type] = by_type.get(signal.source_type, 0) + 1
        top_score = max(top_score, signal.score or 0)
        if signal.collected_at:
            by_day[signal.collected_at.date().isoformat()] = by_day.get(signal.collected_at.date().isoformat(), 0) + 1
    return {
        "success": True,
        "total": len(signals),
        "by_source": by_source,
        "by_type": by_type,
        "by_day": by_day,
        "top_score": top_score,
    }


@router.get("/source/{source}")
async def get_signals_by_source(source: str, limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MarketSignal)
        .where(MarketSignal.source == source)
        .order_by(desc(MarketSignal.collected_at))
        .limit(limit)
    )
    signals = result.scalars().all()
    return {"success": True, "source": source, "count": len(signals), "signals": [_serialize(s) for s in signals]}
