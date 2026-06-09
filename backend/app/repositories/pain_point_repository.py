import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pain_point import PainPoint
from app.utils.logging import get_logger

logger = get_logger("repositories.pain_point")


async def create(session: AsyncSession, **kwargs) -> PainPoint:
    pp = PainPoint(**kwargs)
    session.add(pp)
    await session.flush()
    return pp


async def bulk_create(session: AsyncSession, points: list[dict]) -> list[PainPoint]:
    objects = [PainPoint(**p) for p in points]
    session.add_all(objects)
    await session.flush()
    logger.info("Bulk created %d pain points", len(objects))
    return objects


async def get_by_id(session: AsyncSession, pp_id: uuid.UUID) -> PainPoint | None:
    result = await session.execute(
        select(PainPoint).where(PainPoint.id == pp_id)
    )
    return result.scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[PainPoint]:
    result = await session.execute(
        select(PainPoint).order_by(PainPoint.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, pp: PainPoint, **kwargs) -> PainPoint:
    for key, value in kwargs.items():
        setattr(pp, key, value)
    await session.flush()
    return pp


async def delete(session: AsyncSession, pp: PainPoint) -> None:
    await session.delete(pp)
    await session.flush()


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(PainPoint.id)))
    return result.scalar_one()
