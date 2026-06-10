import uuid
import inspect

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.models.generated_report import GeneratedReport
from app.models.market_signal import MarketSignal
from app.models.startup_opportunity import StartupOpportunity
from app.utils.logging import get_logger

try:
    from app.api.reports import _report_store
except Exception:  # pragma: no cover - legacy in-memory store may not exist in every environment
    _report_store = {}

router = APIRouter(prefix="/signals", tags=["signals"])
logger = get_logger("api.signals")

QUERY_RELEVANCE_ACCEPT_THRESHOLD = 80.0
DOMAIN_RELEVANCE_ACCEPT_THRESHOLD = 80.0


def _serialize(signal: MarketSignal) -> dict:
    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    query_relevance = _safe_float(getattr(signal, "query_relevance_score", 0.0))
    domain_relevance = _safe_float(getattr(signal, "domain_relevance_score", 0.0))
    accepted = query_relevance >= QUERY_RELEVANCE_ACCEPT_THRESHOLD and domain_relevance >= DOMAIN_RELEVANCE_ACCEPT_THRESHOLD
    status = "accepted" if accepted else "rejected"
    rejection_reason = None if accepted else (
        "query_relevance_below_threshold"
        if query_relevance < QUERY_RELEVANCE_ACCEPT_THRESHOLD
        else "domain_relevance_below_threshold"
    )
    return {
        "id": str(getattr(signal, "id", "")),
        "query_id": str(getattr(signal, "query_id", "")) if getattr(signal, "query_id", None) else None,
        "query_domain": getattr(signal, "query_domain", None),
        "source": getattr(signal, "source", None),
        "source_type": getattr(signal, "source_type", None),
        "source_id": getattr(signal, "source_id", None),
        "title": getattr(signal, "title", None),
        "content": getattr(signal, "content", None),
        "url": getattr(signal, "url", None),
        "author": getattr(signal, "author", None),
        "score": getattr(signal, "score", None),
        "comments_count": getattr(signal, "comments_count", None),
        "credibility_score": getattr(signal, "credibility_score", None),
        "query_relevance_score": query_relevance,
        "domain_relevance_score": domain_relevance,
        "status": status,
        "accepted_status": status,
        "rejection_reason": rejection_reason,
        "created_at": getattr(signal, "created_at", None).isoformat() if getattr(signal, "created_at", None) else None,
        "collected_at": getattr(signal, "collected_at", None).isoformat() if getattr(signal, "collected_at", None) else None,
        "extra_metadata": getattr(signal, "extra_metadata", None) or {},
    }


def _serialize_evidence_signal(
    *,
    source: str,
    source_type: str,
    source_id: str,
    title: str,
    content: str,
    url: str,
    query_id: str | None,
    query_domain: str | None,
    query_relevance_score: float,
    domain_relevance_score: float,
    collected_at: str | None = None,
) -> dict:
    accepted = query_relevance_score >= QUERY_RELEVANCE_ACCEPT_THRESHOLD and domain_relevance_score >= DOMAIN_RELEVANCE_ACCEPT_THRESHOLD
    status = "accepted" if accepted else "rejected"
    rejection_reason = None if accepted else (
        "query_relevance_below_threshold"
        if query_relevance_score < QUERY_RELEVANCE_ACCEPT_THRESHOLD
        else "domain_relevance_below_threshold"
    )
    return {
        "id": source_id,
        "query_id": query_id,
        "query_domain": query_domain,
        "source": source,
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "content": content,
        "url": url,
        "author": "",
        "score": 0,
        "comments_count": 0,
        "credibility_score": 0.0,
        "query_relevance_score": query_relevance_score,
        "domain_relevance_score": domain_relevance_score,
        "status": status,
        "accepted_status": status,
        "rejection_reason": rejection_reason,
        "created_at": collected_at,
        "collected_at": collected_at,
        "extra_metadata": {"evidence_fallback": True},
    }


def _payload_scope(payload: dict | None) -> dict[str, str | None]:
    if not isinstance(payload, dict):
        return {"query_id": None, "query_domain": None}
    query_id = payload.get("query_id")
    query_domain = payload.get("query_domain") or payload.get("metadata", {}).get("query_domain")
    return {
        "query_id": str(query_id).strip() if query_id else None,
        "query_domain": str(query_domain).strip().lower() if query_domain else None,
    }


def _extract_report_evidence_records(payload: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    if not isinstance(payload, dict):
        return records

    def _add_record(*, source: str, source_type: str, source_id: str, title: str, content: str, url: str, collected_at: str | None, query_id: str | None, query_domain: str | None, query_relevance_score: float, domain_relevance_score: float) -> None:
        fingerprint = url or source_id or f"{source}:{title}"
        if not fingerprint or fingerprint in seen:
            return
        seen.add(fingerprint)
        records.append(
            _serialize_evidence_signal(
                source=source,
                source_type=source_type,
                source_id=source_id or fingerprint,
                title=title or "Evidence",
                content=content or title or "",
                url=url or fingerprint,
                query_id=query_id,
                query_domain=query_domain,
                query_relevance_score=query_relevance_score,
                domain_relevance_score=domain_relevance_score,
                collected_at=collected_at,
            )
        )

    report_query_id = str(payload.get("query_id") or "").strip() or None
    report_query_domain = str(payload.get("query_domain") or payload.get("metadata", {}).get("query_domain") or "").strip().lower() or None
    top_opportunities = payload.get("top_opportunities", []) if isinstance(payload.get("top_opportunities"), list) else []

    for item in payload.get("evidence_links", []) or []:
        if not isinstance(item, dict):
            continue
        _add_record(
            source=str(item.get("source") or item.get("source_type") or "unknown"),
            source_type=str(item.get("source_type") or "evidence"),
            source_id=str(item.get("signal_id") or item.get("id") or item.get("url") or item.get("title") or ""),
            title=str(item.get("title") or "Evidence"),
            content=str(item.get("snippet") or item.get("content") or item.get("title") or ""),
            url=str(item.get("url") or ""),
            collected_at=str(item.get("collected_at") or item.get("timestamp") or item.get("created_at") or "") or None,
            query_id=report_query_id,
            query_domain=report_query_domain,
            query_relevance_score=float(item.get("query_relevance_score") or 100.0),
            domain_relevance_score=float(item.get("domain_relevance_score") or 100.0),
        )

    for raw in top_opportunities:
        if not isinstance(raw, dict):
            continue
        opportunity = raw.get("opportunity", raw)
        if not isinstance(opportunity, dict):
            continue
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            _add_record(
                source=str(signal.get("source") or "unknown"),
                source_type=str(signal.get("source_type") or "evidence"),
                source_id=str(signal.get("signal_id") or signal.get("id") or signal.get("url") or signal.get("title") or ""),
                title=str(signal.get("title") or "Evidence"),
                content=str(signal.get("snippet") or signal.get("content") or signal.get("title") or ""),
                url=str(signal.get("url") or ""),
                collected_at=str(signal.get("collected_at") or signal.get("timestamp") or signal.get("created_at") or "") or None,
                query_id=str(signal.get("query_id") or report_query_id or ""),
                query_domain=str(signal.get("query_domain") or report_query_domain or "").strip().lower() or None,
                query_relevance_score=float(signal.get("query_relevance_score") or opportunity.get("query_relevance_score") or 100.0),
                domain_relevance_score=float(signal.get("domain_relevance_score") or opportunity.get("domain_relevance_score") or 100.0),
            )
    return records


async def _resolve_report_scope(report_id: str | None, db: AsyncSession) -> dict[str, str | None]:
    scope = {"query_id": None, "query_domain": None}
    if not report_id:
        return scope

    report_id = report_id.strip()

    try:
        report_uuid = uuid.UUID(report_id)
    except Exception:
        report_uuid = None

    if report_uuid is not None:
        report = await db.get(GeneratedReport, report_uuid)
        if report:
            scope.update(_payload_scope(getattr(report, "report_payload", None)))
            if report.query_id:
                scope["query_id"] = str(report.query_id).strip()
            if getattr(report, "query_domain", None):
                scope["query_domain"] = str(report.query_domain).strip().lower()
            return scope

    legacy_report = _report_store.get(report_id) if isinstance(_report_store, dict) else None
    if isinstance(legacy_report, dict):
        scope.update(_payload_scope(legacy_report))
    return scope


def _apply_scope(query, *, query_id: str | None = None, query_domain: str | None = None):
    if query_id:
        try:
            query_uuid = uuid.UUID(query_id)
            query = query.where(MarketSignal.query_id == query_uuid)
        except Exception:
            logger.warning("Invalid query_id provided to signals API: %s", query_id)
    if query_domain:
        query = query.where(MarketSignal.query_domain == query_domain.strip().lower())
    return query


async def _fetch_scoped_evidence_signals(
    db: AsyncSession,
    *,
    query_id: str | None = None,
    query_domain: str | None = None,
    source: str | None = None,
    include_rejected: bool = False,
) -> list[dict]:
    market_statement = select(MarketSignal)
    market_statement = _apply_scope(market_statement, query_id=query_id, query_domain=query_domain)
    if source and source != "all":
        market_statement = market_statement.where(MarketSignal.source == source)
    market_statement = market_statement.order_by(desc(MarketSignal.collected_at))
    market_result = await db.execute(market_statement)
    market_signals = [_serialize(item) for item in market_result.scalars().all()]
    if not include_rejected:
        market_signals = [item for item in market_signals if item["status"] == "accepted"]
    if market_signals:
        return market_signals

    opportunity_statement = select(StartupOpportunity)
    if query_id:
        try:
            opportunity_statement = opportunity_statement.where(StartupOpportunity.query_id == uuid.UUID(query_id))
        except Exception:
            logger.warning("Invalid query_id provided to evidence fallback: %s", query_id)
    if query_domain:
        opportunity_statement = opportunity_statement.where(StartupOpportunity.query_domain == query_domain.strip().lower())
    opportunity_statement = opportunity_statement.order_by(desc(StartupOpportunity.created_at))
    opportunity_result = await db.execute(opportunity_statement)
    opportunities = opportunity_result.scalars().all()

    fallback_signals: list[dict] = []
    seen: set[str] = set()
    for opportunity in opportunities:
        evidence = opportunity.evidence if isinstance(opportunity.evidence, dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            url = str(signal.get("url") or "").strip()
            title = str(signal.get("title") or "").strip()
            source_name = str(signal.get("source") or "").strip() or "unknown"
            source_id = str(signal.get("signal_id") or url or title).strip()
            if source and source != "all" and source_name != source:
                continue
            fingerprint = url or source_id or f"{source_name}:{title}"
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            fallback_signals.append(
                _serialize_evidence_signal(
                    source=source_name,
                    source_type=str(signal.get("source_type") or "evidence"),
                    source_id=source_id or fingerprint,
                    title=title or "Evidence",
                    content=str(signal.get("snippet") or signal.get("content") or title or "").strip(),
                    url=url or fingerprint,
                    query_id=str(opportunity.query_id) if opportunity.query_id else query_id,
                    query_domain=str(opportunity.query_domain).strip().lower() if opportunity.query_domain else query_domain,
                    query_relevance_score=float(getattr(opportunity, "query_relevance_score", 0.0) or 0.0),
                    domain_relevance_score=float(getattr(opportunity, "domain_relevance_score", 0.0) or 0.0),
                    collected_at=signal.get("collected_at"),
                )
            )

    fallback_signals.sort(key=lambda item: item.get("collected_at") or "", reverse=True)
    if not include_rejected:
        fallback_signals = [item for item in fallback_signals if item["status"] == "accepted"]
    return fallback_signals


async def _fetch_report_scoped_signals(
    db: AsyncSession,
    *,
    report_id: str,
    source: str | None = None,
    include_rejected: bool = False,
) -> list[dict]:
    resolved = await _resolve_report_scope(report_id, db)
    try:
        report_uuid = uuid.UUID(str(report_id))
    except Exception:
        report_uuid = None

    report = await db.get(GeneratedReport, report_uuid) if report_uuid is not None else None
    payload = report.report_payload if report and isinstance(report.report_payload, dict) else {}
    report_query_id = resolved["query_id"] or (str(report.query_id) if report and report.query_id else None)
    report_query_domain = resolved["query_domain"] or (str(report.query_domain).strip().lower() if report and getattr(report, "query_domain", None) else None)
    report_evidence_urls = {
        str(item.get("url") or "").strip()
        for item in _extract_report_evidence_records(payload)
        if str(item.get("url") or "").strip()
    }

    evidence: list[dict] = []
    seen: set[str] = set()

    def _append(item: dict) -> None:
        if not isinstance(item, dict):
            return
        url = str(item.get("url") or "").strip()
        signal_id = str(item.get("id") or item.get("source_id") or url or item.get("title") or "").strip()
        key = url or signal_id or f"{item.get('source', 'unknown')}:{item.get('title', '')}"
        if not key or key in seen:
            return
        seen.add(key)
        evidence.append(item)

    market_statement = select(MarketSignal)
    market_statement = _apply_scope(market_statement, query_id=report_query_id, query_domain=report_query_domain)
    if source and source != "all":
        market_statement = market_statement.where(MarketSignal.source == source)
    market_statement = market_statement.order_by(desc(MarketSignal.collected_at))
    market_result = await db.execute(market_statement)
    market_signals = [_serialize(item) for item in market_result.scalars().all()]
    if report_evidence_urls:
        market_signals = [item for item in market_signals if not item.get("url") or str(item.get("url")) in report_evidence_urls]
    for item in market_signals:
        _append(item)

    opportunity_statement = select(StartupOpportunity)
    if report_query_id:
        try:
            opportunity_statement = opportunity_statement.where(StartupOpportunity.query_id == uuid.UUID(report_query_id))
        except Exception:
            logger.warning("Invalid report query_id while loading report-scoped signals: %s", report_query_id)
    if report_query_domain:
        opportunity_statement = opportunity_statement.where(StartupOpportunity.query_domain == report_query_domain)
    opportunity_statement = opportunity_statement.order_by(desc(StartupOpportunity.created_at))
    opportunity_result = await db.execute(opportunity_statement)
    for opportunity in opportunity_result.scalars().all():
        evidence_data = opportunity.evidence if isinstance(opportunity.evidence, dict) else {}
        for signal in evidence_data.get("signals", []) if isinstance(evidence_data, dict) else []:
            if not isinstance(signal, dict):
                continue
            if source and source != "all" and str(signal.get("source") or "unknown") != source:
                continue
            _append(
                _serialize_evidence_signal(
                    source=str(signal.get("source") or "unknown"),
                    source_type=str(signal.get("source_type") or "evidence"),
                    source_id=str(signal.get("signal_id") or signal.get("id") or signal.get("url") or signal.get("title") or ""),
                    title=str(signal.get("title") or "Evidence"),
                    content=str(signal.get("snippet") or signal.get("content") or signal.get("title") or ""),
                    url=str(signal.get("url") or ""),
                    query_id=str(opportunity.query_id) if opportunity.query_id else report_query_id,
                    query_domain=str(opportunity.query_domain).strip().lower() if opportunity.query_domain else report_query_domain,
                    query_relevance_score=float(getattr(opportunity, "query_relevance_score", 100.0) or 100.0),
                    domain_relevance_score=float(getattr(opportunity, "domain_relevance_score", 100.0) or 100.0),
                    collected_at=signal.get("collected_at"),
                )
            )

    scoped_records = _extract_report_evidence_records(payload)
    if source and source != "all":
        scoped_records = [item for item in scoped_records if item.get("source") == source]
    for item in scoped_records:
        _append(item)

    if not include_rejected:
        evidence = [item for item in evidence if item["status"] == "accepted"]
    return evidence


@router.get("/latest")
async def get_latest_signals(
    limit: int = Query(25, ge=1, le=200),
    query_id: str | None = Query(default=None),
    report_id: str | None = Query(default=None),
    query_domain: str | None = Query(default=None),
    include_rejected: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    resolved = await _resolve_report_scope(report_id, db)
    query_id = query_id or resolved["query_id"]
    query_domain = query_domain or resolved["query_domain"]

    if report_id:
        serialized = await _fetch_report_scoped_signals(
            db,
            report_id=report_id,
            source=None,
            include_rejected=include_rejected,
        )
        serialized = serialized[:limit]
        return {
            "success": True,
            "count": len(serialized),
            "query_id": query_id,
            "report_id": report_id,
            "query_domain": query_domain,
            "signals": serialized,
        }

    if not query_id and not query_domain:
        try:
            from app.api.signal_stats import list_recent as list_recent_signals

            recent = await list_recent_signals(db, limit=limit)
            return {
                "success": True,
                "count": len(recent),
                "query_id": query_id,
                "report_id": report_id,
                "query_domain": query_domain,
                "signals": [_serialize(item) for item in recent],
            }
        except Exception:
            pass

    serialized = await _fetch_scoped_evidence_signals(
        db,
        query_id=query_id,
        query_domain=query_domain,
        source=None,
        include_rejected=include_rejected,
    )
    serialized = serialized[:limit]
    return {
        "success": True,
        "count": len(serialized),
        "query_id": query_id,
        "report_id": report_id,
        "query_domain": query_domain,
        "signals": serialized,
    }


@router.get("/stats")
async def get_signal_stats(
    query_id: str | None = Query(default=None),
    report_id: str | None = Query(default=None),
    query_domain: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    resolved = await _resolve_report_scope(report_id, db)
    query_id = query_id or resolved["query_id"]
    query_domain = query_domain or resolved["query_domain"]

    if report_id:
        signals = await _fetch_report_scoped_signals(
            db,
            report_id=report_id,
            source=None,
            include_rejected=True,
        )
        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_day: dict[str, int] = {}
        top_score = 0
        for signal in signals:
            by_source[signal["source"]] = by_source.get(signal["source"], 0) + 1
            by_type[signal["source_type"]] = by_type.get(signal["source_type"], 0) + 1
            top_score = max(top_score, int(signal.get("score", 0) or 0))
            if signal.get("collected_at"):
                day = str(signal["collected_at"])[:10]
                by_day[day] = by_day.get(day, 0) + 1
        return {
            "success": True,
            "total": len(signals),
            "query_id": query_id,
            "report_id": report_id,
            "query_domain": query_domain,
            "by_source": by_source,
            "by_type": by_type,
            "by_day": by_day,
            "top_score": top_score,
        }

    if not query_id and not report_id and not query_domain:
        try:
            from app.api.signal_stats import get_dashboard_metrics as get_signal_dashboard_metrics

            return await get_signal_dashboard_metrics(db)
        except Exception:
            pass

    signals = await _fetch_scoped_evidence_signals(
        db,
        query_id=query_id,
        query_domain=query_domain,
        source=None,
        include_rejected=True,
    )
    by_source: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_day: dict[str, int] = {}
    top_score = 0
    for signal in signals:
        by_source[signal["source"]] = by_source.get(signal["source"], 0) + 1
        by_type[signal["source_type"]] = by_type.get(signal["source_type"], 0) + 1
        top_score = max(top_score, int(signal.get("score", 0) or 0))
        if signal.get("collected_at"):
            day = str(signal["collected_at"])[:10]
            by_day[day] = by_day.get(day, 0) + 1
    return {
        "success": True,
        "total": len(signals),
        "query_id": query_id,
        "report_id": report_id,
        "query_domain": query_domain,
        "by_source": by_source,
        "by_type": by_type,
        "by_day": by_day,
        "top_score": top_score,
    }


@router.get("/source/{source}")
async def get_signals_by_source(
    source: str,
    limit: int = Query(50, ge=1, le=200),
    query_id: str | None = Query(default=None),
    report_id: str | None = Query(default=None),
    query_domain: str | None = Query(default=None),
    include_rejected: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    resolved = await _resolve_report_scope(report_id, db)
    query_id = query_id or resolved["query_id"]
    query_domain = query_domain or resolved["query_domain"]

    serialized = await _fetch_scoped_evidence_signals(
        db,
        query_id=query_id,
        query_domain=query_domain,
        source=source,
        include_rejected=include_rejected,
    )
    serialized = serialized[:limit]
    return {
        "success": True,
        "source": source,
        "count": len(serialized),
        "query_id": query_id,
        "report_id": report_id,
        "query_domain": query_domain,
        "signals": serialized,
    }
