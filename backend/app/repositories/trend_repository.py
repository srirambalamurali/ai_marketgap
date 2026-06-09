import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_trend import DetectedTrend
from app.utils.logging import get_logger

logger = get_logger("repositories.trend")


async def create(session: AsyncSession, **kwargs) -> DetectedTrend:
    trend = DetectedTrend(**kwargs)
    session.add(trend)
    await session.flush()
    return trend


async def bulk_create(session: AsyncSession, trends: list[dict]) -> list[DetectedTrend]:
    objects = [DetectedTrend(**t) for t in trends]
    session.add_all(objects)
    await session.flush()
    logger.info("Bulk created %d trends", len(objects))
    return objects


async def get_by_id(session: AsyncSession, trend_id: uuid.UUID) -> DetectedTrend | None:
    result = await session.execute(
        select(DetectedTrend).where(DetectedTrend.id == trend_id)
    )
    return result.scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[DetectedTrend]:
    result = await session.execute(
        select(DetectedTrend).order_by(DetectedTrend.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, trend: DetectedTrend, **kwargs) -> DetectedTrend:
    for key, value in kwargs.items():
        setattr(trend, key, value)
    await session.flush()
    return trend


async def delete(session: AsyncSession, trend: DetectedTrend) -> None:
    await session.delete(trend)
    await session.flush()


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(DetectedTrend.id)))
    return result.scalar_one()
