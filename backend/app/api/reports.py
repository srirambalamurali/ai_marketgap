import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.models.generated_report import GeneratedReport
from app.utils.logging import get_logger

router = APIRouter(prefix="/reports", tags=["reports"])
legacy_router = APIRouter(prefix="/report", tags=["reports"])
logger = get_logger("api.reports")
_report_store: dict[str, dict] = {}


class ReportResponse(BaseModel):
    success: bool
    report: dict | None = None
    error: str = ""


class ReportListResponse(BaseModel):
    success: bool
    reports: list[dict]


def store_report(*args, **kwargs):
    if len(args) >= 2 and not hasattr(args[0], "execute"):
        report_id = str(args[0])
        report = dict(args[1] if len(args) > 1 else {})
        _report_store[report_id] = report
        return None

    session: AsyncSession = args[0]
    report_id: str = args[1]
    report: dict = args[2]
    query_id: uuid.UUID | None = kwargs.get("query_id")

    async def _store_async() -> None:
        report_uuid = uuid.UUID(report_id)
        existing = await session.get(GeneratedReport, report_uuid)
        if existing:
            existing.query = report.get("query", "")
            existing.report_payload = report
            existing.query_id = query_id
            existing.query_domain = report.get("query_domain", report.get("metadata", {}).get("query_domain", "general"))
        else:
            session.add(
                GeneratedReport(
                    id=report_uuid,
                    query_id=query_id,
                    query_domain=report.get("query_domain", report.get("metadata", {}).get("query_domain", "general")),
                    query=report.get("query", ""),
                    report_payload=report,
                )
            )
        await session.flush()

    return _store_async()


def _serialize_report(report: GeneratedReport) -> dict:
    payload = dict(report.report_payload or {})
    payload.setdefault("id", str(report.id))
    payload.setdefault("query", report.query)
    payload.setdefault("title", payload.get("title") or report.query)
    payload.setdefault("created_at", report.created_at.isoformat() if report.created_at else None)
    payload.setdefault("query_id", str(report.query_id) if report.query_id else payload.get("query_id"))
    payload.setdefault("query_domain", getattr(report, "query_domain", payload.get("query_domain", "general")))
    payload.setdefault(
        "market_confidence_score",
        payload.get("market_confidence_score")
        or payload.get("confidence_score")
        or payload.get("overall_score")
        or 0,
    )
    return payload


@router.get("/{report_id}", response_model=ReportResponse)
@legacy_router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    report_uuid = None
    try:
        report_uuid = uuid.UUID(report_id)
    except Exception:
        report_uuid = None

    if report_uuid is not None:
        report = await db.get(GeneratedReport, report_uuid)
        if report:
            return ReportResponse(success=True, report=_serialize_report(report))
    if report_id in _report_store:
        payload = dict(_report_store[report_id])
        payload.setdefault("id", report_id)
        payload.setdefault("created_at", None)
        payload.setdefault("title", payload.get("title") or payload.get("query") or "Report")
        payload.setdefault("market_confidence_score", payload.get("market_confidence_score") or payload.get("confidence_score") or payload.get("overall_score") or 0)
        return ReportResponse(success=True, report=payload)
    return ReportResponse(success=False, report=None, error="Report not found")


@router.get("", response_model=ReportListResponse)
@legacy_router.get("", response_model=ReportListResponse)
async def list_reports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GeneratedReport).order_by(desc(GeneratedReport.created_at), desc(GeneratedReport.id))
    )
    rows = result.scalars().all()
    reports = []
    seen: set[tuple[str, str]] = set()
    for report in rows:
        payload = report.report_payload if isinstance(report.report_payload, dict) else {}
        fingerprint = (report.query, str(payload.get("executive_summary", "")))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        reports.append(
            {
                "id": str(report.id),
                "title": payload.get("title") or report.query,
                "query": report.query,
                "query_id": str(report.query_id) if report.query_id else payload.get("query_id"),
                "query_domain": getattr(report, "query_domain", payload.get("query_domain", "general")),
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "market_confidence_score": payload.get("market_confidence_score")
                or payload.get("confidence_score")
                or payload.get("overall_score")
                or 0,
            }
        )
    for report_id, payload in _report_store.items():
        fingerprint = (payload.get("query", ""), str(payload.get("executive_summary", "")))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        reports.append(
            {
                "id": report_id,
                "title": payload.get("title") or payload.get("query") or "Report",
                "query": payload.get("query", ""),
                "query_id": payload.get("query_id"),
                "query_domain": payload.get("query_domain", "general"),
                "created_at": payload.get("created_at"),
                "market_confidence_score": payload.get("market_confidence_score")
                or payload.get("confidence_score")
                or payload.get("overall_score")
                or 0,
            }
        )
    return ReportListResponse(success=True, reports=reports)
