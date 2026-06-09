import time
import threading
from datetime import datetime, timedelta
from typing import Any
from app.utils.logging import get_logger

logger = get_logger("services.monitoring")

ALERT_THRESHOLD_FAILURES = 3
ALERT_THRESHOLD_LATENCY_MS = 30000


class CollectorMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}

    def record_collection(self, source: str, signals_collected: int, latency_ms: float, success: bool) -> None:
        with self._lock:
            if source not in self._data:
                self._data[source] = {
                    "total_runs": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "total_signals": 0,
                    "total_latency_ms": 0,
                    "last_run_at": None,
                    "last_success_at": None,
                    "last_failure_at": None,
                    "last_error": None,
                    "recent_latency": [],
                }
            metrics = self._data[source]
            metrics["total_runs"] += 1
            metrics["total_signals"] += signals_collected
            metrics["total_latency_ms"] += latency_ms
            metrics["last_run_at"] = datetime.utcnow().isoformat()
            metrics["recent_latency"].append(latency_ms)
            if len(metrics["recent_latency"]) > 20:
                metrics["recent_latency"] = metrics["recent_latency"][-20:]

            if success:
                metrics["successful_runs"] += 1
                metrics["last_success_at"] = datetime.utcnow().isoformat()
            else:
                metrics["failed_runs"] += 1
                metrics["last_failure_at"] = datetime.utcnow().isoformat()

            if not success:
                consecutive_failures = self._get_consecutive_failures(source)
                if consecutive_failures >= ALERT_THRESHOLD_FAILURES:
                    logger.error(
                        "ALERT: %s collector failed %d consecutive times",
                        source, consecutive_failures,
                    )

            if latency_ms > ALERT_THRESHOLD_LATENCY_MS:
                logger.warning(
                    "ALERT: %s collector latency %.0fms exceeds threshold %dms",
                    source, latency_ms, ALERT_THRESHOLD_LATENCY_MS,
                )

    def record_error(self, source: str, error: str) -> None:
        with self._lock:
            if source not in self._data:
                self._data[source] = {
                    "total_runs": 0, "successful_runs": 0, "failed_runs": 0,
                    "total_signals": 0, "total_latency_ms": 0,
                    "last_run_at": None, "last_success_at": None,
                    "last_failure_at": None, "last_error": None, "recent_latency": [],
                }
            self._data[source]["last_error"] = error
            self._data[source]["last_failure_at"] = datetime.utcnow().isoformat()

    def _get_consecutive_failures(self, source: str) -> int:
        data = self._data.get(source, {})
        total = data.get("total_runs", 0)
        success = data.get("successful_runs", 0)
        failed = total - success
        if failed >= ALERT_THRESHOLD_FAILURES and success == 0:
            return failed
        return 0

    def get_source_metrics(self, source: str) -> dict:
        with self._lock:
            data = self._data.get(source, {})
            total = data.get("total_runs", 0)
            success = data.get("successful_runs", 0)
            recent_latency = data.get("recent_latency", [])
            avg_recent = sum(recent_latency) / len(recent_latency) if recent_latency else 0
            return {
                **data,
                "success_rate": round(success / total, 3) if total > 0 else 0,
                "avg_latency_ms": round(data.get("total_latency_ms", 0) / total, 2) if total > 0 else 0,
                "avg_recent_latency_ms": round(avg_recent, 2),
                "avg_signals_per_run": round(data.get("total_signals", 0) / total, 1) if total > 0 else 0,
                "recent_failure_count": data.get("failed_runs", 0),
            }

    def get_all_metrics(self) -> dict:
        with self._lock:
            return {source: self.get_source_metrics(source) for source in self._data}

    def get_overall_metrics(self) -> dict:
        with self._lock:
            total_runs = sum(m.get("total_runs", 0) for m in self._data.values())
            total_success = sum(m.get("successful_runs", 0) for m in self._data.values())
            total_signals = sum(m.get("total_signals", 0) for m in self._data.values())
            total_latency = sum(m.get("total_latency_ms", 0) for m in self._data.values())
            return {
                "total_runs": total_runs,
                "overall_success_rate": round(total_success / total_runs, 3) if total_runs > 0 else 0,
                "total_signals_collected": total_signals,
                "avg_latency_ms": round(total_latency / total_runs, 2) if total_runs > 0 else 0,
                "sources_monitored": len(self._data),
            }


collector_metrics = CollectorMetrics()


class APILatencyTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._endpoints: dict[str, dict[str, Any]] = {}

    def record(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        key = f"{method} {path}"
        with self._lock:
            if key not in self._endpoints:
                self._endpoints[key] = {
                    "total_calls": 0,
                    "error_count": 0,
                    "total_latency_ms": 0,
                    "recent_latency": [],
                    "last_called": None,
                }
            ep = self._endpoints[key]
            ep["total_calls"] += 1
            ep["total_latency_ms"] += latency_ms
            ep["last_called"] = datetime.utcnow().isoformat()
            ep["recent_latency"].append(latency_ms)
            if len(ep["recent_latency"]) > 50:
                ep["recent_latency"] = ep["recent_latency"][-50:]
            if status_code >= 400:
                ep["error_count"] += 1

    def get_endpoint_metrics(self) -> dict:
        with self._lock:
            result = {}
            for key, ep in self._endpoints.items():
                total = ep["total_calls"]
                recent = ep["recent_latency"]
                result[key] = {
                    "total_calls": total,
                    "error_count": ep["error_count"],
                    "error_rate": round(ep["error_count"] / total, 3) if total > 0 else 0,
                    "avg_latency_ms": round(ep["total_latency_ms"] / total, 2) if total > 0 else 0,
                    "p95_latency_ms": round(sorted(recent)[int(len(recent) * 0.95)] if recent else 0, 2),
                    "last_called": ep["last_called"],
                }
            return result

    def get_overall_stats(self) -> dict:
        with self._lock:
            total_calls = sum(ep["total_calls"] for ep in self._endpoints.values())
            total_errors = sum(ep["error_count"] for ep in self._endpoints.values())
            all_latency = []
            for ep in self._endpoints.values():
                all_latency.extend(ep["recent_latency"])
            all_latency.sort()
            return {
                "total_endpoints": len(self._endpoints),
                "total_calls": total_calls,
                "total_errors": total_errors,
                "overall_error_rate": round(total_errors / total_calls, 3) if total_calls > 0 else 0,
                "p50_latency_ms": round(all_latency[len(all_latency) // 2] if all_latency else 0, 2),
                "p95_latency_ms": round(all_latency[int(len(all_latency) * 0.95)] if all_latency else 0, 2),
                "p99_latency_ms": round(all_latency[int(len(all_latency) * 0.99)] if all_latency else 0, 2),
            }


api_tracker = APILatencyTracker()


class SignalIngestionRate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: list[tuple[datetime, int, int]] = []

    def record(self, ingested: int, quality_filtered: int) -> None:
        with self._lock:
            self._buckets.append((datetime.utcnow(), ingested, quality_filtered))
            cutoff = datetime.utcnow() - timedelta(hours=24)
            self._buckets = [(t, i, q) for t, i, q in self._buckets if t >= cutoff]

    def get_rate(self, minutes: int = 60) -> dict:
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            recent = [(t, i, q) for t, i, q in self._buckets if t >= cutoff]
            total_ingested = sum(i for _, i, _ in recent)
            total_filtered = sum(q for _, _, q in recent)
            rate_per_min = total_ingested / max(minutes, 1)
            return {
                "window_minutes": minutes,
                "total_ingested": total_ingested,
                "total_filtered": total_filtered,
                "rate_per_minute": round(rate_per_min, 2),
                "data_points": len(recent),
            }

    def get_24h_summary(self) -> dict:
        with self._lock:
            total_ingested = sum(i for _, i, _ in self._buckets)
            total_filtered = sum(q for _, _, q in self._buckets)
            return {
                "total_ingested_24h": total_ingested,
                "total_filtered_24h": total_filtered,
                "rate_per_hour": round(total_ingested / 24, 2),
            }


ingestion_rate = SignalIngestionRate()


class FailedCollectionAlerts:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alerts: list[dict] = []
        self._max_alerts = 100

    def record_failure(self, source: str, error: str, details: str = "") -> None:
        with self._lock:
            alert = {
                "source": source,
                "error": error,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "critical" if "auth" in error.lower() or "403" in error else "warning",
            }
            self._alerts.append(alert)
            if len(self._alerts) > self._max_alerts:
                self._alerts = self._alerts[-self._max_alerts:]
            logger.warning("Collection alert: [%s] %s — %s", alert["severity"], source, error)

    def get_recent_alerts(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return list(reversed(self._alerts[-limit:]))

    def get_alert_summary(self) -> dict:
        with self._lock:
            severity_counts = {}
            source_counts = {}
            for alert in self._alerts:
                sev = alert.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
                src = alert.get("source", "unknown")
                source_counts[src] = source_counts.get(src, 0) + 1
            return {
                "total_alerts": len(self._alerts),
                "by_severity": severity_counts,
                "by_source": source_counts,
            }


collection_alerts = FailedCollectionAlerts()


class PipelineMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: list[dict] = []
        self._max_history = 100

    def record_pipeline_run(self, source: str, metrics: dict, success: bool) -> None:
        with self._lock:
            run = {
                "source": source,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "signals_collected": metrics.get("signals_collected", 0),
                "signals_ingested": metrics.get("signals_ingested", 0),
                "duplicates_removed": metrics.get("duplicates_removed", 0),
                "quality_filtered": metrics.get("quality_filtered", 0),
                "vectors_created": metrics.get("vectors_created", 0),
                "collection_latency_ms": metrics.get("collection_latency_ms", 0),
                "ingestion_latency_ms": metrics.get("ingestion_latency_ms", 0),
            }
            self._runs.append(run)
            if len(self._runs) > self._max_history:
                self._runs = self._runs[-self._max_history:]

            collector_metrics.record_collection(
                source,
                metrics.get("signals_collected", 0),
                metrics.get("collection_latency_ms", 0) + metrics.get("ingestion_latency_ms", 0),
                success,
            )
            ingestion_rate.record(
                metrics.get("signals_ingested", 0),
                metrics.get("quality_filtered", 0),
            )

            if not success:
                collection_alerts.record_failure(source, "Pipeline run failed")

    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return list(reversed(self._runs[-limit:]))

    def get_pipeline_summary(self) -> dict:
        with self._lock:
            if not self._runs:
                return {"total_runs": 0, "success_rate": 0}
            total = len(self._runs)
            success = sum(1 for r in self._runs if r["success"])
            return {
                "total_runs": total,
                "success_rate": round(success / total, 3),
                "total_signals_collected": sum(r["signals_collected"] for r in self._runs),
                "total_signals_ingested": sum(r["signals_ingested"] for r in self._runs),
                "total_duplicates_removed": sum(r["duplicates_removed"] for r in self._runs),
                "total_quality_filtered": sum(r.get("quality_filtered", 0) for r in self._runs),
                "total_vectors_created": sum(r["vectors_created"] for r in self._runs),
            }


pipeline_monitor = PipelineMonitor()
