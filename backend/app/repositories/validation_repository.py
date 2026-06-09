import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_result import ValidationResult
from app.utils.logging import get_logger

logger = get_logger("repositories.validation")


async def create(session: AsyncSession, **kwargs) -> ValidationResult:
    vr = ValidationResult(**kwargs)
    session.add(vr)
    await session.flush()
    return vr


async def bulk_create(session: AsyncSession, results: list[dict]) -> list[ValidationResult]:
    objects = [ValidationResult(**r) for r in results]
    session.add_all(objects)
    await session.flush()
    logger.info("Bulk created %d validation results", len(objects))
    return objects


async def get_by_id(session: AsyncSession, vr_id: uuid.UUID) -> ValidationResult | None:
    result = await session.execute(
        select(ValidationResult).where(ValidationResult.id == vr_id)
    )
    return result.scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[ValidationResult]:
    result = await session.execute(
        select(ValidationResult).order_by(ValidationResult.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, vr: ValidationResult, **kwargs) -> ValidationResult:
    for key, value in kwargs.items():
        setattr(vr, key, value)
    await session.flush()
    return vr


async def delete(session: AsyncSession, vr: ValidationResult) -> None:
    await session.delete(vr)
    await session.flush()


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(ValidationResult.id)))
    return result.scalar_one()
