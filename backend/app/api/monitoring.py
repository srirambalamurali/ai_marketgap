from fastapi import APIRouter
from app.services.monitoring import (
    collector_metrics,
    pipeline_monitor,
    api_tracker,
    ingestion_rate,
    collection_alerts,
)
from app.utils.logging import get_logger

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
logger = get_logger("api.monitoring")


@router.get("/metrics")
async def get_monitoring_metrics():
    return {
        "collector_metrics": collector_metrics.get_all_metrics(),
        "overall": collector_metrics.get_overall_metrics(),
        "pipeline_summary": pipeline_monitor.get_pipeline_summary(),
    }


@router.get("/metrics/{source}")
async def get_source_metrics(source: str):
    metrics = collector_metrics.get_source_metrics(source)
    return {"source": source, "metrics": metrics}


@router.get("/pipeline/recent")
async def get_recent_pipeline_runs(limit: int = 20):
    runs = pipeline_monitor.get_recent_runs(limit=limit)
    return {"runs": runs, "count": len(runs)}


@router.get("/api-latency")
async def get_api_latency():
    return {
        "endpoints": api_tracker.get_endpoint_metrics(),
        "overall": api_tracker.get_overall_stats(),
    }


@router.get("/ingestion-rate")
async def get_ingestion_rate(minutes: int = 60):
    return {
        "current_rate": ingestion_rate.get_rate(minutes),
        "summary_24h": ingestion_rate.get_24h_summary(),
    }


@router.get("/alerts")
async def get_alerts(limit: int = 20):
    return {
        "alerts": collection_alerts.get_recent_alerts(limit),
        "summary": collection_alerts.get_alert_summary(),
    }


@router.get("/health")
async def get_health_summary():
    overall = collector_metrics.get_overall_metrics()
    alerts = collection_alerts.get_alert_summary()
    rate = ingestion_rate.get_rate(60)
    return {
        "status": "healthy" if overall.get("overall_success_rate", 0) >= 0.5 else "degraded",
        "success_rate": overall.get("overall_success_rate", 0),
        "total_signals": overall.get("total_signals_collected", 0),
        "ingestion_rate_per_min": rate.get("rate_per_minute", 0),
        "active_alerts": alerts.get("total_alerts", 0),
    }
