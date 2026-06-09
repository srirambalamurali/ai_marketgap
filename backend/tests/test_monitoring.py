import pytest
from app.services.monitoring import CollectorMetrics, PipelineMonitor, collector_metrics, pipeline_monitor


def test_record_collection():
    cm = CollectorMetrics()
    cm.record_collection("github", signals_collected=10, latency_ms=500, success=True)
    metrics = cm.get_source_metrics("github")
    assert metrics["total_runs"] == 1
    assert metrics["successful_runs"] == 1
    assert metrics["total_signals"] == 10
    assert metrics["success_rate"] == 1.0


def test_record_failure():
    cm = CollectorMetrics()
    cm.record_collection("reddit", signals_collected=0, latency_ms=100, success=False)
    cm.record_error("reddit", "403 Blocked")
    metrics = cm.get_source_metrics("reddit")
    assert metrics["failed_runs"] == 1
    assert metrics["success_rate"] == 0.0
    assert metrics["last_error"] == "403 Blocked"


def test_multiple_sources():
    cm = CollectorMetrics()
    cm.record_collection("github", 10, 500, True)
    cm.record_collection("hackernews", 5, 200, True)
    cm.record_collection("reddit", 0, 100, False)
    all_m = cm.get_all_metrics()
    assert len(all_m) == 3
    assert "github" in all_m
    assert "hackernews" in all_m
    assert "reddit" in all_m


def test_overall_metrics():
    cm = CollectorMetrics()
    cm.record_collection("github", 10, 500, True)
    cm.record_collection("rss", 20, 300, True)
    overall = cm.get_overall_metrics()
    assert overall["total_runs"] == 2
    assert overall["overall_success_rate"] == 1.0
    assert overall["total_signals_collected"] == 30


def test_pipeline_monitor_record():
    pm = PipelineMonitor()
    pm.record_pipeline_run("github", {
        "signals_collected": 10, "signals_ingested": 8,
        "duplicates_removed": 2, "quality_filtered": 0,
        "vectors_created": 8, "collection_latency_ms": 500,
        "ingestion_latency_ms": 300,
    }, success=True)
    recent = pm.get_recent_runs()
    assert len(recent) == 1
    assert recent[0]["source"] == "github"
    assert recent[0]["success"] is True


def test_pipeline_summary():
    pm = PipelineMonitor()
    pm.record_pipeline_run("github", {"signals_collected": 10, "signals_ingested": 8, "duplicates_removed": 2, "quality_filtered": 0, "vectors_created": 8, "collection_latency_ms": 0, "ingestion_latency_ms": 0}, True)
    pm.record_pipeline_run("rss", {"signals_collected": 20, "signals_ingested": 18, "duplicates_removed": 2, "quality_filtered": 0, "vectors_created": 18, "collection_latency_ms": 0, "ingestion_latency_ms": 0}, True)
    summary = pm.get_pipeline_summary()
    assert summary["total_runs"] == 2
    assert summary["success_rate"] == 1.0
    assert summary["total_signals_collected"] == 30


def test_global_instances_exist():
    assert collector_metrics is not None
    assert pipeline_monitor is not None
