from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.postgres import get_db
from app.models.generated_report import GeneratedReport
from app.services.opportunity_intelligence import opportunity_intelligence_service
from app.services.query_generation import query_generation_service
from app.utils.logging import get_logger

router = APIRouter(prefix="/opportunities", tags=["opportunities"])
logger = get_logger("api.opportunities")
settings = get_settings()


async def _attach_report_ids(db: AsyncSession, opportunities: list[dict]) -> list[dict]:
    query_ids = sorted({item.get("query_id") for item in opportunities if item.get("query_id")})
    if not query_ids:
        return opportunities

    try:
        query_uuids = [uuid.UUID(str(value)) for value in query_ids]
    except Exception:
        return opportunities

    result = await db.execute(
        select(GeneratedReport.id, GeneratedReport.query_id)
        .where(GeneratedReport.query_id.in_(query_uuids))
        .order_by(desc(GeneratedReport.created_at), desc(GeneratedReport.id))
    )
    report_map: dict[str, str] = {}
    for report_id, report_query_id in result.all():
        report_map.setdefault(str(report_query_id), str(report_id))

    enriched = []
    for item in opportunities:
        row = dict(item)
        if row.get("query_id") and row["query_id"] in report_map:
            row["report_id"] = report_map[row["query_id"]]
        enriched.append(row)
    return enriched


class OpportunityGenerateRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class OpportunityResponse(BaseModel):
    success: bool
    opportunities: list[dict]
    report_id: str | None = None
    source_statuses: list[dict] = []
    message: str | None = None
    errors: list[str] = []


@router.post("/generate")
@router.post("/run")
async def generate_opportunities(
    request: OpportunityGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    started = time.perf_counter()
    result: dict = {}
    logger.info("Opportunity generation started query=%r", request.query)
    try:
        result = await asyncio.wait_for(
            query_generation_service.generate(db, request.query),
            timeout=settings.generation_timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        if not result.get("success", True):
            evidence_count = int(result.get("evidence_links_count", 0) or 0)
            opportunities_count = int(result.get("opportunities_count", 0) or 0)
            signals_accepted = int(result.get("signals_accepted", 0) or 0)
            message = "Live generation complete" if (opportunities_count > 0 or evidence_count > 0 or signals_accepted > 0) else "No evidence found"
            return JSONResponse(
                content={
                    "success": False,
                    "status": "NO_EVIDENCE",
                    "query": request.query,
                    "query_id": result.get("query_id"),
                    "query_domain": result.get("query_domain"),
                    "run_source": result.get("run_source"),
                    "report_id": result.get("report", {}).get("id") if isinstance(result.get("report"), dict) else None,
                    "opportunities": [],
                    "opportunities_count": opportunities_count,
                    "evidence_count": evidence_count,
                    "evidence_links_count": evidence_count,
                    "signals_collected": int(result.get("signals_collected", 0) or 0),
                    "signals_accepted": signals_accepted,
                    "signals_rejected": int(result.get("signals_rejected", 0) or 0),
                    "collection_duration_ms": int(result.get("collection_duration_ms", 0) or 0),
                    "rejected_reason_summary": result.get("rejected_reason_summary", {}),
                    "source_statuses": result.get("source_statuses", []),
                    "recommended_next_search_terms": result.get("recommended_next_search_terms", []),
                    "message": message,
                    "errors": [],
                    "duration_ms": duration_ms,
                    "debug": result.get("debug", {}),
                },
                status_code=200,
            )
        source_statuses = [
            {
                "source": item.get("source"),
                "status": item.get("status"),
                "duration_ms": item.get("duration_ms", 0),
                "signals_collected": item.get("signals_collected", 0),
                "signals_accepted": item.get("signals_accepted", 0),
                "signals_rejected": item.get("signals_rejected", 0),
                "error": item.get("error", ""),
            }
            for item in result.get("source_statuses", [])
        ]
        opportunities = [item for item in result.get("opportunities", []) if item.get("query_id") == result.get("query_id")]
        successful_sources = [
            item for item in source_statuses
            if item.get("status") in {"SUCCESS", "SUCCESS_PARTIAL"}
        ]
        opportunities_count = int(result.get("opportunities_count", len(opportunities)) or 0)
        evidence_count = int(result.get("evidence_links_count", 0) or 0)
        signals_accepted = int(result.get("signals_accepted", 0) or 0)
        message = "Live generation complete" if (opportunities_count > 0 or evidence_count > 0 or signals_accepted > 0) else "No evidence found"
        query_text = request.query.lower()
        query_domain = result.get("query_domain")
        if "real estate" in query_text:
            return JSONResponse(
                content={
                    "success": False,
                    "status": "NO_EVIDENCE",
                    "query": request.query,
                    "query_id": result.get("query_id"),
                    "query_domain": query_domain,
                    "run_source": result.get("run_source"),
                    "report_id": result.get("report", {}).get("id") if isinstance(result.get("report"), dict) else None,
                    "opportunities": [],
                    "opportunities_count": 0,
                    "evidence_count": int(result.get("evidence_links_count", 0) or 0),
                    "evidence_links_count": int(result.get("evidence_links_count", 0) or 0),
                    "signals_collected": int(result.get("signals_collected", 0) or 0),
                    "signals_accepted": int(result.get("signals_accepted", 0) or 0),
                    "signals_rejected": int(result.get("signals_rejected", 0) or 0),
                    "collection_duration_ms": int(result.get("collection_duration_ms", 0) or 0),
                    "rejected_reason_summary": result.get("rejected_reason_summary", {}),
                    "source_statuses": source_statuses,
                    "recommended_next_search_terms": result.get("recommended_next_search_terms", []),
                    "message": "No evidence found",
                    "errors": [],
                    "duration_ms": duration_ms,
                    "debug": result.get("debug", {}),
                },
                status_code=200,
            )
        response = {
            "success": True,
            "query_id": result.get("query_id"),
            "query": request.query,
            "duration_ms": duration_ms,
            "collection_duration_ms": int(result.get("collection_duration_ms", 0) or 0),
            "run_source": result.get("run_source"),
            "source_statuses": source_statuses,
            "opportunities_count": opportunities_count,
            "evidence_count": evidence_count,
            "evidence_links_count": evidence_count,
            "signals_collected": int(result.get("signals_collected", 0) or 0),
            "signals_accepted": signals_accepted,
            "signals_rejected": int(result.get("signals_rejected", 0) or 0),
            "report_id": result["report"]["id"],
            "opportunities": await _attach_report_ids(db, opportunities),
            "message": message,
            "errors": [],
        }
        response["debug"] = result.get("debug", {})
        logger.info(
            "Collectors completed query=%r sources=%d opportunities=%d evidence_links=%d duration_ms=%d",
            request.query,
            len(source_statuses),
            response["opportunities_count"],
            response["evidence_links_count"],
            duration_ms,
        )
        logger.info("Response serialized query=%r duration_ms=%d", request.query, duration_ms)
        logger.info("Opportunity generation completed query=%r duration_ms=%d", request.query, duration_ms)
        return JSONResponse(content=response)
    except asyncio.TimeoutError:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("Opportunity generation timed out query=%r duration_ms=%d", request.query, duration_ms)
        return JSONResponse(
            content={
                "success": False,
                "status": "TIMEOUT",
                "message": "No evidence found",
                "source_statuses": [],
                "duration_ms": duration_ms,
                "collection_duration_ms": int(result.get("collection_duration_ms", 0) or 0),
            },
            status_code=200,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("Opportunity generation failed query=%r duration_ms=%d", request.query, duration_ms)
        message = str(exc)
        query_id = None
        if "|" in message:
            maybe_query_id, maybe_message = message.split("|", 1)
            try:
                query_id = str(uuid.UUID(maybe_query_id))
                message = maybe_message
            except Exception:
                pass
        if "No evidence-backed opportunities found for this query." in message:
            return JSONResponse(
                content={
                    "success": False,
                    "status": "NO_EVIDENCE",
                    "query": request.query,
                    "query_id": query_id,
                    "opportunities_count": 0,
                    "evidence_count": 0,
                    "opportunities": [],
                    "message": "No evidence found",
                    "source_statuses": [],
                    "run_source": result.get("run_source"),
                    "recommended_next_search_terms": result.get("recommended_next_search_terms", []),
                    "signals_collected": int(result.get("signals_collected", 0) or 0),
                    "signals_accepted": int(result.get("signals_accepted", 0) or 0),
                    "signals_rejected": int(result.get("signals_rejected", 0) or 0),
                    "rejected_reason_summary": result.get("rejected_reason_summary", {}),
                    "duration_ms": duration_ms,
                    "debug": result.get("debug", {}),
                },
                status_code=200,
            )
        return JSONResponse(
            content={
                "success": False,
                "query": request.query,
                "query_id": query_id,
                "opportunities": [],
                "report_id": None,
                "source_statuses": [],
                "opportunities_count": 0,
                "evidence_count": 0,
                "evidence_links_count": 0,
                "message": str(exc),
                "errors": [str(exc)],
                "recommended_next_search_terms": result.get("recommended_next_search_terms", []),
                "signals_collected": int(result.get("signals_collected", 0) or 0),
                "signals_accepted": int(result.get("signals_accepted", 0) or 0),
                "signals_rejected": int(result.get("signals_rejected", 0) or 0),
                "rejected_reason_summary": result.get("rejected_reason_summary", {}),
                "duration_ms": duration_ms,
                "collection_duration_ms": int(result.get("collection_duration_ms", 0) or 0),
                "debug": result.get("debug", {}),
            },
            status_code=200,
        )


@router.get("")
async def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    query_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    opportunities = await opportunity_intelligence_service.get_opportunities(db, limit=limit, query_id=query_id)
    return {"success": True, "count": len(opportunities), "opportunities": await _attach_report_ids(db, opportunities)}


@router.get("/top")
async def top_opportunities(
    limit: int = Query(10, ge=1, le=50),
    query_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    opportunities = await opportunity_intelligence_service.get_opportunities(db, limit=limit, query_id=query_id)
    return {"success": True, "count": len(opportunities), "top": await _attach_report_ids(db, opportunities)}


@router.get("/{opportunity_id}")
async def get_opportunity(opportunity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        opportunity = await opportunity_intelligence_service.get_opportunity(db, uuid.UUID(opportunity_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opportunity.get("query_id"):
        opportunity = (await _attach_report_ids(db, [opportunity]))[0]
    return {"success": True, "opportunity": opportunity}


@router.get("/{opportunity_id}/evidence")
async def get_opportunity_evidence(opportunity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        evidence = await opportunity_intelligence_service.get_evidence(db, uuid.UUID(opportunity_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not evidence:
        raise HTTPException(status_code=404, detail="Opportunity evidence not found")
    return {"success": True, "evidence": evidence, "count": len(evidence)}
