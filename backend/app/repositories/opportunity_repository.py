import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.startup_opportunity import StartupOpportunity
from app.utils.logging import get_logger

logger = get_logger("repositories.opportunity")


async def create(session: AsyncSession, **kwargs) -> StartupOpportunity:
    opp = StartupOpportunity(**kwargs)
    session.add(opp)
    await session.flush()
    return opp


async def bulk_create(session: AsyncSession, opportunities: list[dict]) -> list[StartupOpportunity]:
    objects = [StartupOpportunity(**o) for o in opportunities]
    session.add_all(objects)
    await session.flush()
    logger.info("Bulk created %d opportunities", len(objects))
    return objects


async def get_by_id(session: AsyncSession, opp_id: uuid.UUID) -> StartupOpportunity | None:
    result = await session.execute(
        select(StartupOpportunity).where(StartupOpportunity.id == opp_id)
    )
    return result.scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[StartupOpportunity]:
    result = await session.execute(
        select(StartupOpportunity).order_by(StartupOpportunity.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, opp: StartupOpportunity, **kwargs) -> StartupOpportunity:
    for key, value in kwargs.items():
        setattr(opp, key, value)
    await session.flush()
    return opp


async def delete(session: AsyncSession, opp: StartupOpportunity) -> None:
    await session.delete(opp)
    await session.flush()


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(StartupOpportunity.id)))
    return result.scalar_one()
