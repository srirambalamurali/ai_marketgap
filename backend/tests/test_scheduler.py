import pytest
from unittest.mock import patch, MagicMock
from app.scheduler.jobs import (
    get_job_status,
    register_jobs,
    scheduler,
)


@pytest.fixture(autouse=True)
def clean_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for job in list(scheduler.get_jobs()):
        try:
            scheduler.remove_job(job.id)
        except Exception:
            pass
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for job in list(scheduler.get_jobs()):
        try:
            scheduler.remove_job(job.id)
        except Exception:
            pass


def test_get_job_status_empty():
    status = get_job_status()
    assert isinstance(status, dict)
    assert len(status) == 0


def test_register_jobs():
    register_jobs()
    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}
    assert "github_collection" in job_ids
    assert "hackernews_collection" in job_ids
    assert "rss_collection" in job_ids
    assert "reddit_collection" in job_ids
    assert "google_trends_collection" in job_ids


def test_job_intervals():
    register_jobs()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    github_job = jobs["github_collection"]
    hn_job = jobs["hackernews_collection"]
    rss_job = jobs["rss_collection"]
    reddit_job = jobs["reddit_collection"]
    gt_job = jobs["google_trends_collection"]

    assert github_job.trigger is not None
    assert hn_job.trigger is not None
    assert rss_job.trigger is not None
    assert reddit_job.trigger is not None
    assert gt_job.trigger is not None


def test_register_jobs_idempotent():
    register_jobs()
    register_jobs()
    jobs = scheduler.get_jobs()
    job_ids = [j.id for j in jobs]
    assert job_ids.count("github_collection") == 1
    assert job_ids.count("hackernews_collection") == 1
    assert job_ids.count("rss_collection") == 1
    assert job_ids.count("reddit_collection") == 1
    assert job_ids.count("google_trends_collection") == 1


def test_job_count():
    register_jobs()
    jobs = scheduler.get_jobs()
    assert len(jobs) == 5
