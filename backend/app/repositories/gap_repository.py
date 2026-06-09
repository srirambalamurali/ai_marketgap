import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_gap import MarketGap
from app.utils.logging import get_logger

logger = get_logger("repositories.gap")


async def create(session: AsyncSession, **kwargs) -> MarketGap:
    gap = MarketGap(**kwargs)
    session.add(gap)
    await session.flush()
    return gap


async def bulk_create(session: AsyncSession, gaps: list[dict]) -> list[MarketGap]:
    objects = [MarketGap(**g) for g in gaps]
    session.add_all(objects)
    await session.flush()
    logger.info("Bulk created %d market gaps", len(objects))
    return objects


async def get_by_id(session: AsyncSession, gap_id: uuid.UUID) -> MarketGap | None:
    result = await session.execute(
        select(MarketGap).where(MarketGap.id == gap_id)
    )
    return result.scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[MarketGap]:
    result = await session.execute(
        select(MarketGap).order_by(MarketGap.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, gap: MarketGap, **kwargs) -> MarketGap:
    for key, value in kwargs.items():
        setattr(gap, key, value)
    await session.flush()
    return gap


async def delete(session: AsyncSession, gap: MarketGap) -> None:
    await session.delete(gap)
    await session.flush()


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(MarketGap.id)))
    return result.scalar_one()
