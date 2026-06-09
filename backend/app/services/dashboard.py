from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_report import GeneratedReport
from app.services.chromadb_service import get_chroma_service
from app.utils.logging import get_logger

logger = get_logger("services.dashboard")

TECH_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "llm",
    "gpt",
    "claude",
    "gemini",
    "langchain",
    "rag",
    "vector",
    "embedding",
    "blockchain",
    "web3",
    "rust",
    "typescript",
    "python",
    "react",
    "nextjs",
    "svelte",
    "flutter",
    "kubernetes",
    "docker",
    "grpc",
    "graphql",
    "rest api",
    "saas",
    "paas",
    "iaas",
    "no-code",
    "low-code",
    "devtools",
    "developer experience",
    "observability",
    "monitoring",
]


def _derive_competition_level(score: float | int | None) -> str:
    try:
        value = float(score if score is not None else 0)
    except Exception:
        value = 0.0
    if value >= 75:
        return "High"
    if value >= 45:
        return "Medium"
    return "Low"


def _normalize_competition_label(level: str | None, score: float | int | None = None) -> str:
    if not level:
        return _derive_competition_level(score)
    normalized = str(level).strip().lower().replace("_", " ")
    if normalized in {"high", "medium", "low"}:
        return normalized.title()
    if normalized in {"high competition", "competition high"}:
        return "High"
    if normalized in {"medium competition", "competition medium"}:
        return "Medium"
    if normalized in {"low competition", "competition low"}:
        return "Low"
    return _derive_competition_level(score)


async def get_dashboard_metrics(
    session: AsyncSession,
    *,
    report_id: str | None = None,
    query_id: str | None = None,
    scope: str | None = None,
) -> dict:
    recent_reports = await _get_recent_reports(session, limit=8)
    rag_health = await _get_rag_health()
    scope_value = (scope or "").strip().lower()

    if scope_value == "all":
        payload = await _build_all_time_dashboard_payload(session, rag_health, recent_reports)
        payload["scope"] = "all"
        payload["selected_report_id"] = None
        payload["selected_query_id"] = None
        payload["selected_query"] = None
        payload["recent_reports"] = recent_reports
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    selected_report = await _resolve_selected_report(session, report_id=report_id, query_id=query_id)
    if report_id or query_id:
        if not selected_report:
            raise LookupError("Selected report not found")
        scope_label = "report" if report_id else "query"
    else:
        if not selected_report:
            return {
                "scope": "latest",
                "analysis_selected": False,
                "state": "empty",
                "message": "No analysis selected",
                "selected_report_id": None,
                "selected_query_id": None,
                "selected_query": None,
                "selected_analysis": None,
                "recent_reports": recent_reports,
                "summary": {
                    "total_signals": 0,
                    "total_documents": 0,
                    "total_opportunities": 0,
                    "total_evidence_links": 0,
                    "top_opportunity_score": 0,
                    "rag_status": rag_health["status"],
                    "active_sources": [],
                },
                "charts": {
                    "signals_over_time": [],
                    "signals_over_time_status": {"status": "empty", "message": "No analysis selected"},
                    "source_distribution": [],
                    "opportunity_score_distribution": [],
                    "competition_levels": [{"level": "Low", "count": 0}, {"level": "Medium", "count": 0}, {"level": "High", "count": 0}],
                },
                "top_opportunities": [],
                "total_signals": 0,
                "total_documents": 0,
                "total_opportunities": 0,
                "top_opportunity_score": 0,
                "last_collection_time": None,
                "rag_status": rag_health["status"],
                "by_source": {},
                "by_type": {},
                "recent_signals": [],
                "avg_credibility_score": 0.0,
                "trending_keywords": [],
                "top_subreddits": [],
                "top_signals": [],
                "source_distribution": {"labels": [], "values": []},
                "trending_technologies": [],
                "emerging_startups": [],
                "signal_velocity": {"last_hour": 0, "last_day": 0, "last_week": 0},
                "collection_health": {},
                "opportunity_summary": {
                    "total_opportunities": 0,
                    "top_opportunities": [],
                    "by_competition_level": {},
                },
                "embedded_documents": rag_health["embedded_documents"],
                "chromadb_connected": rag_health["chromadb_connected"],
                "collection_exists": rag_health["collection_exists"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        scope_label = "latest"

    payload = selected_report.report_payload if isinstance(selected_report.report_payload, dict) else {}
    dashboard = _build_dashboard_from_report(selected_report, payload, rag_health, recent_reports, scope_label)
    logger.info(
        "Dashboard metrics selected_report_id=%s selected_query_id=%s selected_query=%r opportunity_count=%d evidence_count=%d source_counts=%s",
        dashboard.get("selected_report_id"),
        dashboard.get("selected_query_id"),
        dashboard.get("selected_query"),
        dashboard.get("summary", {}).get("total_opportunities", 0),
        dashboard.get("summary", {}).get("total_evidence_links", 0),
        dashboard.get("summary", {}).get("active_sources", []),
    )
    return dashboard


async def get_opportunities_dashboard(session: AsyncSession) -> dict:
    recent_reports = await _get_recent_reports(session, limit=1)
    selected_report = await _resolve_selected_report(session, None, recent_reports)
    if not selected_report:
        return {
            "opportunities": [],
            "market_gaps": [],
            "trends": [],
            "pipeline_summary": {},
            "generated_at": datetime.utcnow().isoformat(),
        }

    payload = selected_report.report_payload if isinstance(selected_report.report_payload, dict) else {}
    opportunities = _flatten_report_opportunities(payload, str(selected_report.id))
    return {
        "opportunities": opportunities[:10],
        "market_gaps": payload.get("top_market_gaps", [])[:10] if isinstance(payload.get("top_market_gaps"), list) else [],
        "trends": payload.get("top_trends", [])[:10] if isinstance(payload.get("top_trends"), list) else [],
        "pipeline_summary": {
            "report_id": str(selected_report.id),
            "query": payload.get("query") or selected_report.query,
            "query_id": payload.get("query_id") or (str(selected_report.query_id) if selected_report.query_id else None),
            "opportunities": len(opportunities),
            "evidence_links": len(payload.get("evidence_links", []) or []),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _get_recent_reports(session: AsyncSession, limit: int = 8) -> list[dict]:
    result = await session.execute(
        select(GeneratedReport).order_by(desc(GeneratedReport.created_at), desc(GeneratedReport.id)).limit(limit)
    )
    reports = []
    seen: set[tuple[str, str]] = set()
    for report in result.scalars().all():
        payload = report.report_payload if isinstance(report.report_payload, dict) else {}
        fingerprint = (report.query, str(payload.get("executive_summary", "")))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        reports.append(
            {
                "id": str(report.id),
                "title": payload.get("title") or report.query or "Untitled Report",
                "query": report.query,
                "query_id": str(report.query_id) if report.query_id else payload.get("query_id"),
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "market_confidence_score": payload.get("market_confidence_score")
                or payload.get("confidence_score")
                or payload.get("overall_score")
                or 0,
            }
        )
    return reports


async def _resolve_selected_report(
    session: AsyncSession,
    *,
    report_id: str | None = None,
    query_id: str | None = None,
) -> GeneratedReport | None:
    if report_id:
        try:
            return await session.get(GeneratedReport, UUID(str(report_id)))
        except Exception:
            logger.warning("Invalid report_id supplied to dashboard metrics: %r", report_id)
            return None
    if query_id:
        try:
            query_uuid = UUID(str(query_id))
        except Exception:
            logger.warning("Invalid query_id supplied to dashboard metrics: %r", query_id)
            return None
        result = await session.execute(
            select(GeneratedReport)
            .where(GeneratedReport.query_id == query_uuid)
            .order_by(desc(GeneratedReport.created_at), desc(GeneratedReport.id))
        )
        return result.scalars().first()
    result = await session.execute(
        select(GeneratedReport).order_by(desc(GeneratedReport.created_at), desc(GeneratedReport.id)).limit(1)
    )
    return result.scalars().first()


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _normalize_source_name(value: object) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in {"github", "git_hub", "repo", "repository"}:
        return "github"
    if text in {"hackernews", "hacker_news", "hn", "hackernews_story"}:
        return "hackernews"
    if text in {"rss", "feed", "article"}:
        return "rss"
    if text in {"google_trends", "googletrends", "trends"}:
        return "google_trends"
    if text in {"reddit", "subreddit", "reddit_post", "reddit_comment"}:
        return "reddit"
    return text or "unknown"


def _extract_report_sources(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    sources: dict[str, dict] = {}

    def _ensure_source(source: object, *, count: int = 0, status: str | None = None) -> None:
        normalized = _normalize_source_name(source)
        if normalized == "unknown":
            return
        entry = sources.setdefault(
            normalized,
            {
                "source": normalized,
                "count": 0,
                "status": "SUCCESS",
            },
        )
        entry["count"] = int(entry.get("count", 0)) + int(count or 0)
        if status:
            current_status = str(entry.get("status", "SUCCESS")).upper()
            incoming_status = str(status).upper()
            priority = {
                "SUCCESS": 0,
                "CONFIG_BLOCKED": 1,
                "TIMEOUT": 2,
                "FAILED": 3,
                "ERROR": 4,
            }
            if priority.get(incoming_status, 99) >= priority.get(current_status, 99):
                entry["status"] = incoming_status

    for item in payload.get("evidence_links", []) or []:
        if not isinstance(item, dict):
            continue
        _ensure_source(item.get("source") or item.get("source_type"), count=1, status=item.get("status"))

    for raw in payload.get("top_opportunities", []) or []:
        if not isinstance(raw, dict):
            continue
        opportunity = raw.get("opportunity", raw)
        if not isinstance(opportunity, dict):
            opportunity = {}
        for source in opportunity.get("sources", []) or []:
            _ensure_source(source)
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            _ensure_source(signal.get("source") or signal.get("source_type"), count=1)

    metadata = payload.get("metadata", {})
    metadata_sources = metadata.get("sources", {}) if isinstance(metadata, dict) else {}
    if isinstance(metadata_sources, dict):
        for source, value in metadata_sources.items():
            if isinstance(value, dict):
                _ensure_source(source, count=int(value.get("count", 0) or 0), status=value.get("status"))
            else:
                _ensure_source(source, count=int(value or 0))
    elif isinstance(metadata_sources, list):
        for source in metadata_sources:
            _ensure_source(source)

    for status_item in payload.get("source_statuses", []) or []:
        if not isinstance(status_item, dict):
            continue
        _ensure_source(
            status_item.get("source"),
            count=int(status_item.get("signals_collected", 0) or 0),
            status=status_item.get("status"),
        )

    ordered = []
    for source in ["github", "hackernews", "rss", "google_trends", "reddit"]:
        if source in sources:
            ordered.append(sources[source])
    for source, value in sources.items():
        if source not in {"github", "hackernews", "rss", "google_trends", "reddit"}:
            ordered.append(value)
    return ordered


def _extract_report_timestamps(payload: dict, opportunities: list[dict], fallback: datetime | None = None) -> list[datetime]:
    timestamps: list[datetime] = []
    if not isinstance(payload, dict):
        payload = {}
    for item in payload.get("evidence_links", []) or []:
        if not isinstance(item, dict):
            continue
        for key in ("timestamp", "collected_at", "created_at"):
            parsed = _parse_timestamp(item.get(key))
            if parsed:
                timestamps.append(parsed)
                break
    for raw in payload.get("top_opportunities", []) or []:
        if not isinstance(raw, dict):
            continue
        opportunity = raw.get("opportunity", raw)
        if not isinstance(opportunity, dict):
            opportunity = {}
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            for key in ("timestamp", "collected_at", "created_at"):
                parsed = _parse_timestamp(signal.get(key))
                if parsed:
                    timestamps.append(parsed)
                    break
    for opportunity in opportunities or []:
        if not isinstance(opportunity, dict):
            continue
        for key in ("created_at", "last_signal_at", "emergence_date"):
            parsed = _parse_timestamp(opportunity.get(key))
            if parsed:
                timestamps.append(parsed)
                break
    for key in ("generated_at", "created_at"):
        parsed = _parse_timestamp(payload.get(key))
        if parsed:
            timestamps.append(parsed)
    if fallback:
        timestamps.append(_parse_timestamp(fallback) or fallback)
    return [ts for ts in timestamps if ts]


def _signals_over_time_from_evidence(payload: dict, evidence_links: list[dict], opportunities: list[dict], fallback: datetime | None = None) -> dict:
    timestamps = _extract_report_timestamps(payload, opportunities, fallback)
    evidence_count = len(evidence_links or []) or sum(int(o.get("evidence_count", 0) or 0) for o in opportunities or [])
    if evidence_count <= 0:
        return {
            "status": "low_activity",
            "message": "No evidence collected for this selected report.",
            "series": [
                {"label": "1h", "count": 0},
                {"label": "24h", "count": 0},
                {"label": "7d", "count": 0},
            ],
        }
    if len(timestamps) < 2 or len({ts.replace(minute=0, second=0, microsecond=0) for ts in timestamps}) < 2:
        return {
            "status": "single_batch",
            "message": "Evidence was collected in one analysis batch.",
            "series": [
                {"label": "Current report", "count": evidence_count},
                {"label": "Last 24h", "count": evidence_count},
                {"label": "Last 7d", "count": evidence_count},
            ],
        }
    now = datetime.now(timezone.utc)
    return {
        "status": "healthy",
        "message": "",
        "series": [
            {"label": "1h", "count": sum(1 for ts in timestamps if ts >= now - timedelta(hours=1))},
            {"label": "24h", "count": sum(1 for ts in timestamps if ts >= now - timedelta(days=1))},
            {"label": "7d", "count": sum(1 for ts in timestamps if ts >= now - timedelta(days=7))},
        ],
    }


def _serialize_selected_analysis(report: GeneratedReport, payload: dict) -> dict:
    return {
        "id": str(report.id),
        "report_id": str(report.id),
        "title": payload.get("title") or payload.get("query") or report.query or "Untitled Report",
        "query": payload.get("query") or report.query,
        "query_id": payload.get("query_id") or (str(report.query_id) if report.query_id else None),
        "created_at": payload.get("created_at") or (report.created_at.isoformat() if report.created_at else None),
        "market_confidence_score": payload.get("market_confidence_score")
        or payload.get("confidence_score")
        or payload.get("overall_score")
        or 0,
        "source_statuses": payload.get("source_statuses", []),
        "evidence_links": payload.get("evidence_links", []),
        "top_opportunities": payload.get("top_opportunities", []),
        "top_pain_points": payload.get("top_pain_points", []),
        "top_market_gaps": payload.get("top_market_gaps", []),
        "top_trends": payload.get("top_trends", []),
        "rag_status": payload.get("rag_status", {}),
        "metadata": payload.get("metadata", {}),
    }


def _source_counts_from_evidence(payload: dict, evidence_links: list[dict], opportunities: list[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in evidence_links or []:
        if not isinstance(item, dict):
            continue
        source = _normalize_source_name(item.get("source") or item.get("source_type") or "unknown")
        counts[source] += 1
    for opportunity in opportunities or []:
        if not isinstance(opportunity, dict):
            continue
        for source in opportunity.get("sources", []) or []:
            source_name = _normalize_source_name(source)
            if source_name not in counts:
                counts[source_name] += 0
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            source_name = _normalize_source_name(signal.get("source") or signal.get("source_type"))
            if source_name not in counts:
                counts[source_name] += 0
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    metadata_sources = metadata.get("sources", {}) if isinstance(metadata, dict) else {}
    if isinstance(metadata_sources, dict):
        for source, value in metadata_sources.items():
            counts[_normalize_source_name(source)] += int(value.get("count", 0) if isinstance(value, dict) else value or 0)
    elif isinstance(metadata_sources, list):
        for source in metadata_sources:
            counts[_normalize_source_name(source)] += 0
    for status_item in payload.get("source_statuses", []) or []:
        if not isinstance(status_item, dict):
            continue
        source_name = _normalize_source_name(status_item.get("source"))
        counts[source_name] += int(status_item.get("signals_collected", 0) or 0)
    return counts


def _source_distribution_from_counts(source_counts: Counter[str], payload: dict) -> list[dict]:
    source_statuses = {}
    for item in payload.get("source_statuses", []) or []:
        if not isinstance(item, dict):
            continue
        source_name = _normalize_source_name(item.get("source"))
        if source_name == "unknown":
            continue
        source_statuses[source_name] = {
            "status": str(item.get("status") or "SUCCESS").upper(),
            "signals_collected": int(item.get("signals_collected", 0) or 0),
        }
    ordered_sources = ["github", "hackernews", "rss", "google_trends", "reddit"]
    merged = []
    seen: set[str] = set()
    for source in ordered_sources:
        if source in source_counts or source in source_statuses:
            merged.append({
                "source": source,
                "count": int(source_counts.get(source, 0)),
                "status": source_statuses.get(source, {}).get("status", "SUCCESS"),
            })
            seen.add(source)
    for source in sorted(set(source_counts.keys()) | set(source_statuses.keys())):
        if source in seen:
            continue
        merged.append({
            "source": source,
            "count": int(source_counts.get(source, 0)),
            "status": source_statuses.get(source, {}).get("status", "SUCCESS"),
        })
    return merged


def _top_opportunities_from_report(opportunities: list[dict], limit: int = 10) -> list[dict]:
    ordered = sorted(
        [item for item in opportunities if isinstance(item, dict)],
        key=lambda item: (
            float(item.get("opportunity_score", item.get("market_score", 0)) or 0),
            float(item.get("confidence_score", 0) or 0),
            float(item.get("demand_score", 0) or 0),
        ),
        reverse=True,
    )
    top = []
    seen: set[str] = set()
    for item in ordered:
        key = str(item.get("id") or item.get("startup_name") or item.get("name") or item.get("problem") or "").strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        top.append(
            {
                "id": str(item.get("id") or ""),
                "name": item.get("startup_name") or item.get("name") or "Untitled Opportunity",
                "problem": item.get("problem") or "",
                "opportunity_score": float(item.get("opportunity_score", item.get("market_score", 0)) or 0),
                "demand_score": float(item.get("demand_score", 0) or 0),
                "competition_score": float(item.get("competition_score", 0) or 0),
                "competition_level": _normalize_competition_label(item.get("competition_level"), item.get("competition_score")),
                "query_relevance_score": float(item.get("query_relevance_score", 0) or 0),
                "evidence_count": int(item.get("evidence_count", len(item.get("evidence", {}).get("signals", [])) if isinstance(item.get("evidence"), dict) else 0)),
                "sources": item.get("sources", []),
                "evidence": item.get("evidence", {}),
                "score": float(item.get("opportunity_score", item.get("market_score", 0)) or 0),
            }
        )
        if len(top) >= limit:
            break
    return top


def _competition_levels_from_opportunities(opportunities: list[dict]) -> list[dict]:
    levels = Counter()
    for item in opportunities or []:
        if not isinstance(item, dict):
            continue
        levels[_normalize_competition_label(item.get("competition_level"), item.get("competition_score"))] += 1
    return [{"level": level, "count": int(levels.get(level, 0))} for level in ["Low", "Medium", "High"]]


def _collection_health_from_counts(source_counts: Counter[str]) -> dict:
    return {
        source: {
            "signals_7d": int(count),
            "avg_credibility": 1.0 if count else 0.0,
        }
        for source, count in source_counts.items()
    }


def _build_dashboard_from_report(
    report: GeneratedReport,
    payload: dict,
    rag_health: dict,
    recent_reports: list[dict],
    scope_label: str,
) -> dict:
    selected_analysis = _serialize_selected_analysis(report, payload)
    evidence_links = payload.get("evidence_links", []) if isinstance(payload, dict) else []
    opportunities = _flatten_report_opportunities(payload, str(report.id))
    source_counts = _source_counts_from_evidence(payload, evidence_links, opportunities)
    signal_over_time = _signals_over_time_from_evidence(payload, evidence_links, opportunities, report.created_at)
    top_opportunities = _top_opportunities_from_report(opportunities)
    competition_levels = _competition_levels_from_opportunities(opportunities)
    source_distribution = _source_distribution_from_counts(source_counts, payload)
    summary = {
        "total_signals": len(evidence_links),
        "total_documents": len(evidence_links),
        "total_opportunities": len(opportunities),
        "total_evidence_links": len(evidence_links),
        "top_opportunity_score": max((item.get("opportunity_score", item.get("market_score", 0)) for item in opportunities), default=0),
        "rag_status": rag_health["status"],
        "active_sources": list(source_counts.keys()),
    }
    selected_query = selected_analysis.get("query") or report.query
    return {
        "scope": scope_label,
        "analysis_selected": True,
        "state": "success",
        "message": selected_analysis["title"],
        "selected_report_id": str(report.id),
        "selected_query_id": selected_analysis.get("query_id"),
        "selected_query": selected_query,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recent_reports": recent_reports,
        "selected_analysis": selected_analysis,
        "summary": summary,
        "charts": {
            "signals_over_time": signal_over_time.get("series", []),
            "signals_over_time_status": {
                "status": signal_over_time.get("status", "healthy"),
                "message": signal_over_time.get("message", ""),
            },
            "source_distribution": source_distribution,
            "opportunity_score_distribution": [
                {
                    "name": item.get("name") or item.get("startup_name") or "Untitled Opportunity",
                    "score": item.get("score", 0),
                }
                for item in opportunities
            ],
            "competition_levels": competition_levels,
        },
        "top_opportunities": top_opportunities,
        "total_signals": summary["total_signals"],
        "total_documents": summary["total_documents"],
        "total_opportunities": summary["total_opportunities"],
        "top_opportunity_score": summary["top_opportunity_score"],
        "last_collection_time": _last_collection_time_from_report(payload, report.created_at),
        "rag_status": rag_health["status"],
        "by_source": {source: int(count) for source, count in source_counts.items()},
        "by_type": {},
        "recent_signals": top_opportunities,
        "avg_credibility_score": round(
            float(sum(item.get("confidence_score", 0) for item in opportunities) / max(len(opportunities), 1)),
            3,
        ),
        "trending_keywords": _trending_keywords_from_report(payload),
        "top_subreddits": [],
        "top_signals": top_opportunities,
        "source_distribution": source_distribution,
        "trending_technologies": _trending_technologies_from_report(payload),
        "emerging_startups": _emerging_startups_from_report(opportunities),
        "signal_velocity": {
            "last_hour": signal_over_time.get("series", [{}])[0].get("count", 0) if signal_over_time.get("series") else 0,
            "last_day": signal_over_time.get("series", [{}, {"count": 0}])[1].get("count", 0) if len(signal_over_time.get("series", [])) > 1 else 0,
            "last_week": signal_over_time.get("series", [{}, {}, {"count": 0}])[2].get("count", 0) if len(signal_over_time.get("series", [])) > 2 else 0,
        },
        "collection_health": _collection_health_from_counts(source_counts),
        "opportunity_summary": {
            "total_opportunities": len(opportunities),
            "top_opportunities": top_opportunities,
            "by_competition_level": {item["level"]: item["count"] for item in competition_levels},
        },
        "embedded_documents": rag_health["embedded_documents"],
        "chromadb_connected": rag_health["chromadb_connected"],
        "collection_exists": rag_health["collection_exists"],
    }


async def _build_all_time_dashboard_payload(
    session: AsyncSession,
    rag_health: dict,
    recent_reports: list[dict],
) -> dict:
    result = await session.execute(select(GeneratedReport).order_by(desc(GeneratedReport.created_at), desc(GeneratedReport.id)))
    reports = result.scalars().all()
    all_opportunities: list[dict] = []
    all_sources: Counter[str] = Counter()
    all_evidence_links: list[dict] = []
    for report in reports:
        payload = report.report_payload if isinstance(report.report_payload, dict) else {}
        all_evidence_links.extend(payload.get("evidence_links", []) if isinstance(payload.get("evidence_links"), list) else [])
        all_opportunities.extend(_flatten_report_opportunities(payload, str(report.id)))
        for source, count in _source_counts_from_evidence(payload, payload.get("evidence_links", []), []).items():
            all_sources[source] += count
    signal_over_time = _signals_over_time_from_evidence({}, all_evidence_links, all_opportunities, None)
    top_opportunities = _top_opportunities_from_report(all_opportunities)
    competition_levels = _competition_levels_from_opportunities(all_opportunities)
    summary = {
        "total_signals": len(all_evidence_links),
        "total_documents": len(all_evidence_links),
        "total_opportunities": len(all_opportunities),
        "total_evidence_links": len(all_evidence_links),
        "top_opportunity_score": max((item.get("opportunity_score", item.get("market_score", 0)) for item in all_opportunities), default=0),
        "rag_status": rag_health["status"],
        "active_sources": list(all_sources.keys()),
    }
    return {
        "scope": "all",
        "analysis_selected": False,
        "state": "success",
        "message": "All data",
        "selected_report_id": None,
        "selected_query_id": None,
        "selected_query": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recent_reports": recent_reports,
        "selected_analysis": None,
        "summary": summary,
        "charts": {
            "signals_over_time": signal_over_time.get("series", []),
            "signals_over_time_status": {
                "status": signal_over_time.get("status", "healthy"),
                "message": signal_over_time.get("message", ""),
            },
            "source_distribution": _source_distribution_from_counts(all_sources, {}),
            "opportunity_score_distribution": [
                {
                    "name": item.get("name") or item.get("startup_name") or "Untitled Opportunity",
                    "score": item.get("score", 0),
                }
                for item in all_opportunities
            ],
            "competition_levels": competition_levels,
        },
        "top_opportunities": top_opportunities,
        "total_signals": summary["total_signals"],
        "total_documents": summary["total_documents"],
        "total_opportunities": summary["total_opportunities"],
        "top_opportunity_score": summary["top_opportunity_score"],
        "last_collection_time": _last_collection_time_from_evidence(all_evidence_links, all_opportunities),
        "rag_status": rag_health["status"],
        "by_source": {source: int(count) for source, count in all_sources.items()},
        "by_type": {},
        "recent_signals": top_opportunities,
        "avg_credibility_score": round(
            float(sum(item.get("confidence_score", 0) for item in all_opportunities) / max(len(all_opportunities), 1)),
            3,
        ),
        "trending_keywords": [],
        "top_subreddits": [],
        "top_signals": top_opportunities,
        "source_distribution": _source_distribution_from_counts(all_sources, {}),
        "trending_technologies": [],
        "emerging_startups": _emerging_startups_from_report(all_opportunities),
        "signal_velocity": {
            "last_hour": signal_over_time.get("series", [{}])[0].get("count", 0) if signal_over_time.get("series") else 0,
            "last_day": signal_over_time.get("series", [{}, {"count": 0}])[1].get("count", 0) if len(signal_over_time.get("series", [])) > 1 else 0,
            "last_week": signal_over_time.get("series", [{}, {}, {"count": 0}])[2].get("count", 0) if len(signal_over_time.get("series", [])) > 2 else 0,
        },
        "collection_health": _collection_health_from_counts(all_sources),
        "opportunity_summary": {
            "total_opportunities": len(all_opportunities),
            "top_opportunities": top_opportunities,
            "by_competition_level": {item["level"]: item["count"] for item in competition_levels},
        },
        "embedded_documents": rag_health["embedded_documents"],
        "chromadb_connected": rag_health["chromadb_connected"],
        "collection_exists": rag_health["collection_exists"],
    }


def _extract_selected_sources(payload: dict) -> dict:
    metadata = payload.get("metadata") if isinstance(payload, dict) else {}
    sources = metadata.get("sources") if isinstance(metadata, dict) else {}
    return sources if isinstance(sources, dict) else {}


def _flatten_report_opportunities(payload: dict, report_id: str) -> list[dict]:
    flattened: list[dict] = []
    seen: set[str] = set()
    for raw in payload.get("top_opportunities", []) or []:
        if not isinstance(raw, dict):
            continue
        opportunity = raw.get("opportunity", raw)
        if not isinstance(opportunity, dict):
            opportunity = {}
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        signals = evidence.get("signals", []) if isinstance(evidence, dict) else []
        nested_sources = opportunity.get("sources", []) if isinstance(opportunity.get("sources"), list) else []
        key = (opportunity.get("id") or raw.get("id") or opportunity.get("title") or opportunity.get("startup_name") or raw.get("title") or raw.get("startup_name") or "").strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        opportunity_score = float(opportunity.get("opportunity_score") or raw.get("overall_score") or opportunity.get("market_score") or 0)
        evidence_count = int(opportunity.get("evidence_count") or raw.get("evidence_count") or len(signals))
        flattened.append(
            {
                "id": str(opportunity.get("id") or raw.get("id") or report_id),
                "report_id": report_id,
                "query_id": opportunity.get("query_id") or raw.get("query_id") or payload.get("query_id"),
                "startup_name": opportunity.get("title") or opportunity.get("startup_name") or raw.get("title") or raw.get("startup_name"),
                "name": opportunity.get("title") or opportunity.get("startup_name") or raw.get("name") or raw.get("title"),
                "problem": opportunity.get("description") or opportunity.get("problem") or raw.get("problem") or "",
                "market_gap": opportunity.get("description") or opportunity.get("market_gap") or raw.get("market_gap") or opportunity.get("problem") or "",
                "solution": opportunity.get("description") or opportunity.get("solution") or raw.get("description") or "",
                "market_score": opportunity_score,
                "opportunity_score": opportunity_score,
                "confidence_score": float(opportunity.get("confidence_score") or raw.get("confidence_score") or 0),
                "evidence_score": float(opportunity.get("evidence_score") or raw.get("evidence_score") or 0),
                "demand_score": float(opportunity.get("demand_score") or raw.get("demand_score") or 0),
                "competition_score": float(opportunity.get("competition_score") or raw.get("competition_score") or 0),
                "whitespace_score": float(opportunity.get("whitespace_score") or raw.get("whitespace_score") or max(0.0, 100.0 - float(opportunity.get("competition_score") or raw.get("competition_score") or 0))),
                "competition_level": _normalize_competition_label(
                    opportunity.get("competition_level") or raw.get("competition_level"),
                    opportunity.get("competition_score") or raw.get("competition_score"),
                ),
                "query_relevance_score": float(opportunity.get("query_relevance_score") or raw.get("query_relevance_score") or 0),
                "evidence_count": evidence_count,
                "sources": sorted({str(source) for source in nested_sources if source}) or sorted({item.get("source", "") for item in signals if item.get("source")}),
                "created_at": opportunity.get("created_at") or raw.get("created_at"),
                "evidence": evidence,
                "score": opportunity_score,
            }
        )
    return flattened


def _source_distribution(selected_sources: dict) -> dict:
    if not selected_sources:
        return {"labels": [], "values": []}
    labels = list(selected_sources.keys())
    values = [int(selected_sources[source].get("signals_collected", 0)) for source in labels]
    return {"labels": labels, "values": values}


def _signal_velocity_from_report(payload: dict) -> dict:
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(days=1)
    last_week = now - timedelta(days=7)
    timestamps: list[datetime] = []
    for item in payload.get("top_opportunities", []) or []:
        if not isinstance(item, dict):
            continue
        opportunity = item.get("opportunity", item)
        if not isinstance(opportunity, dict):
            continue
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            collected_at = signal.get("collected_at")
            if not collected_at:
                continue
            try:
                ts = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                timestamps.append(ts)
            except Exception:
                continue
    return {
        "last_hour": sum(1 for ts in timestamps if ts >= last_hour),
        "last_day": sum(1 for ts in timestamps if ts >= last_day),
        "last_week": sum(1 for ts in timestamps if ts >= last_week),
    }


def _top_signals_from_report(payload: dict) -> list[dict]:
    signals: list[dict] = []
    seen: set[str] = set()
    for item in payload.get("top_opportunities", []) or []:
        if not isinstance(item, dict):
            continue
        opportunity = item.get("opportunity", item)
        if not isinstance(opportunity, dict):
            continue
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            key = signal.get("url") or signal.get("signal_id") or signal.get("title")
            if not key or key in seen:
                continue
            seen.add(str(key))
            signals.append(
                {
                    "title": str(signal.get("title", ""))[:80],
                    "source": signal.get("source", "unknown"),
                    "source_type": signal.get("source_type", "unknown"),
                    "url": signal.get("url"),
                    "score": 1,
                    "credibility_score": 1,
                    "collected_at": signal.get("collected_at"),
                }
            )
            if len(signals) >= 10:
                return signals
    return signals


def _collection_health(selected_sources: dict) -> dict:
    health = {}
    for source, data in selected_sources.items():
        signals_collected = int(data.get("signals_collected", 0))
        filtered = int(data.get("quality_filtered", 0))
        health[source] = {
            "signals_7d": signals_collected,
            "avg_credibility": round(filtered / max(signals_collected, 1), 3),
        }
    return health


def _opportunity_summary_from_report(opportunities: list[dict]) -> dict:
    ordered = sorted(opportunities, key=lambda item: (item.get("market_score", 0), item.get("confidence_score", 0)), reverse=True)
    competition_levels = Counter()
    for item in opportunities:
        level = _normalize_competition_label(item.get("competition_level"), item.get("competition_score"))
        competition_levels[level] += 1
    return {
        "total_opportunities": len(opportunities),
        "top_opportunities": ordered[:10],
        "by_competition_level": dict(competition_levels),
    }


def _last_collection_time_from_report(payload: dict, fallback: datetime | None) -> str | None:
    timestamps: list[datetime] = []
    for item in payload.get("top_opportunities", []) or []:
        if not isinstance(item, dict):
            continue
        opportunity = item.get("opportunity", item)
        if not isinstance(opportunity, dict):
            continue
        evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
        for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
            if not isinstance(signal, dict):
                continue
            collected_at = signal.get("collected_at")
            if not collected_at:
                continue
            try:
                ts = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                timestamps.append(ts)
            except Exception:
                continue
    if timestamps:
        return max(timestamps).isoformat()
    return fallback.isoformat() if fallback else None


def _last_collection_time_from_evidence(evidence_links: list[dict], opportunities: list[dict]) -> str | None:
    timestamps: list[datetime] = []
    for item in evidence_links or []:
        if not isinstance(item, dict):
            continue
        for key in ("timestamp", "collected_at", "created_at"):
            parsed = _parse_timestamp(item.get(key))
            if parsed:
                timestamps.append(parsed)
                break
    if not timestamps:
        for opportunity in opportunities or []:
            if not isinstance(opportunity, dict):
                continue
            evidence = opportunity.get("evidence", {}) if isinstance(opportunity.get("evidence"), dict) else {}
            for signal in evidence.get("signals", []) if isinstance(evidence, dict) else []:
                if not isinstance(signal, dict):
                    continue
                parsed = _parse_timestamp(signal.get("collected_at"))
                if parsed:
                    timestamps.append(parsed)
    return max(timestamps).isoformat() if timestamps else None


def _trending_keywords_from_report(payload: dict) -> list[str]:
    keywords: list[str] = []
    for item in payload.get("top_pain_points", []) or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if title and title not in keywords:
            keywords.append(str(title))
    return keywords[:10]


def _trending_technologies_from_report(payload: dict) -> list[dict]:
    tech_counts: dict[str, int] = {}
    for item in payload.get("top_market_gaps", []) or []:
        if not isinstance(item, dict):
            continue
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        for keyword in TECH_KEYWORDS:
            if keyword in text:
                tech_counts[keyword] = tech_counts.get(keyword, 0) + 1
    return [{"technology": tech, "mentions": count} for tech, count in sorted(tech_counts.items(), key=lambda x: -x[1])[:10]]


def _emerging_startups_from_report(opportunities: list[dict]) -> list[dict]:
    return [
        {
            "name": item.get("startup_name"),
            "description": item.get("solution"),
            "stars": item.get("market_score", 0),
            "language": _normalize_competition_label(item.get("competition_level"), item.get("competition_score")),
            "url": item.get("sources", []),
            "credibility_score": item.get("confidence_score", 0),
        }
        for item in opportunities[:10]
    ]


async def _get_rag_health() -> dict:
    try:
        chroma = get_chroma_service()
        health = await chroma.health()
        if not health["chromadb_connected"]:
            return {
                "chromadb_connected": False,
                "collection_exists": False,
                "embedded_documents": 0,
                "status": "degraded",
            }
        if health["embedded_documents"] == 0:
            health["status"] = "empty"
        else:
            health["status"] = "healthy"
        return health
    except Exception as exc:
        logger.warning("RAG health check degraded: %s", exc)
        return {
            "chromadb_connected": False,
            "collection_exists": False,
            "embedded_documents": 0,
            "status": "degraded",
        }
