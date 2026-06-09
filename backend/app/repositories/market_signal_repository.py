import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_signal import MarketSignal
from app.utils.logging import get_logger

logger = get_logger("repositories.market_signal")


async def create(session: AsyncSession, **kwargs) -> MarketSignal:
    signal = MarketSignal(**kwargs)
    session.add(signal)
    await session.flush()
    return signal


async def bulk_create(session: AsyncSession, signals: list[dict]) -> list[MarketSignal]:
    objects = [MarketSignal(**s) for s in signals]
    session.add_all(objects)
    await session.flush()
    logger.info("Bulk created %d market signals", len(objects))
    return objects


async def get_by_id(session: AsyncSession, signal_id: uuid.UUID) -> MarketSignal | None:
    result = await session.execute(
        select(MarketSignal).where(MarketSignal.id == signal_id)
    )
    return result.scalar_one_or_none()


async def get_by_source_id(session: AsyncSession, source: str, source_id: str) -> MarketSignal | None:
    result = await session.execute(
        select(MarketSignal).where(
            MarketSignal.source == source, MarketSignal.source_id == source_id
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[MarketSignal]:
    result = await session.execute(
        select(MarketSignal).order_by(MarketSignal.collected_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def list_by_source(session: AsyncSession, source: str, limit: int = 50) -> list[MarketSignal]:
    result = await session.execute(
        select(MarketSignal)
        .where(MarketSignal.source == source)
        .order_by(MarketSignal.collected_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, signal: MarketSignal, **kwargs) -> MarketSignal:
    for key, value in kwargs.items():
        setattr(signal, key, value)
    await session.flush()
    return signal


async def delete(session: AsyncSession, signal: MarketSignal) -> None:
    await session.delete(signal)
    await session.flush()


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(MarketSignal.id)))
    return result.scalar_one()
