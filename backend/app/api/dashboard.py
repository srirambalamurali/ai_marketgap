from fastapi import APIRouter, Depends
from fastapi import Query
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.services.dashboard import get_dashboard_metrics
from app.utils.logging import get_logger

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = get_logger("api.dashboard")


@router.get("")
async def read_dashboard(
    report_id: str | None = Query(None, description="Optional report id to scope the dashboard to"),
    query_id: str | None = Query(None, description="Optional query id to scope the dashboard to"),
    scope: str | None = Query(None, description="Optional dashboard scope: latest|report|query|all"),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_dashboard_metrics(db, report_id=report_id, query_id=query_id, scope=scope)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
