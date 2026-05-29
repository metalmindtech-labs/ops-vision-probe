"""Tests for the Leland scraper / ingestion endpoints + status."""
import os
import time
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

SAMPLE_HTML = (
    "Jun 1, 2026 at 9:00 PM 999 registered "
    "Test Event Title For Pytest Foo B. | 5.0 ( 10 ) Register"
)


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- /api/scraper/status ----
def test_scraper_status(session):
    r = session.get(f"{API}/scraper/status", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ["last_run", "next_run_at", "scheduler_running", "interval_hours"]:
        assert k in data, f"Missing key: {k}"
    assert data["scheduler_running"] is True
    assert data["interval_hours"] == 12
    # next_run_at must parse + be in the future, ~ <= 12h from now
    nxt = data.get("next_run_at")
    assert nxt, "next_run_at should be set when scheduler is running"
    parsed = datetime.fromisoformat(nxt.replace("Z", "+00:00"))
    delta_h = (parsed - datetime.now(timezone.utc)).total_seconds() / 3600
    assert -0.5 < delta_h <= 12.5, f"next_run_at delta out of range: {delta_h}h"


# ---- /api/scraper/ingest-html validations ----
def test_ingest_html_rejects_missing(session):
    r = session.post(f"{API}/scraper/ingest-html", json={}, timeout=30)
    assert r.status_code == 400


def test_ingest_html_rejects_too_small(session):
    r = session.post(f"{API}/scraper/ingest-html", json={"html": "tiny"}, timeout=30)
    assert r.status_code == 400


# ---- /api/scraper/ingest-html happy path (deterministic) ----
def test_ingest_html_parses_one_event(session):
    # Pre-count signals
    before = session.get(f"{API}/signals", timeout=30).json()
    before_count = len(before)

    # Pad payload to satisfy >=50 chars (already > 50). Send.
    assert len(SAMPLE_HTML) >= 50
    r = session.post(
        f"{API}/scraper/ingest-html",
        json={"html": SAMPLE_HTML},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    summary = r.json()
    for k in ["discovered", "created", "updated", "skipped", "errors", "trigger"]:
        assert k in summary, f"Missing key {k}"
    assert summary["trigger"] == "manual-paste"
    assert summary["discovered"] == 1, f"Expected 1 event parsed, got {summary}"
    assert summary["created"] + summary["updated"] == 1
    assert isinstance(summary["errors"], list)

    # If created, verify the signal exists with category + priority_score
    after = session.get(f"{API}/signals", timeout=30).json()
    matched = [s for s in after if s["event_title"] == "Test Event Title For Pytest"]
    assert matched, "Parsed event not persisted as a signal"
    sig = matched[0]
    assert isinstance(sig.get("category"), str) and sig["category"]
    assert isinstance(sig.get("priority_score"), int)
    assert 0 <= sig["priority_score"] <= 100
    assert sig["registration_count"] == 999

    # Either grew by 1 OR was an idempotent update (collision)
    assert len(after) - before_count in (0, 1)

    # Cleanup the created signal
    session.delete(f"{API}/signals/{sig['id']}", timeout=30)


# ---- /api/scraper/runs ----
def test_scraper_runs_returns_sorted(session):
    r = session.get(f"{API}/scraper/runs?limit=10", timeout=30)
    assert r.status_code == 200, r.text
    runs = r.json()
    assert isinstance(runs, list)
    # After the ingest-html test above ran, there should be >=1 run
    if runs:
        # Sorted desc by ran_at
        timestamps = [run["ran_at"] for run in runs]
        assert timestamps == sorted(timestamps, reverse=True), "runs not sorted desc"
        # No _id leakage
        for run in runs:
            assert "_id" not in run
            assert "discovered" in run
            assert "trigger" in run


# ---- /api/scraper/run live (best-effort) ----
def test_scraper_run_manual(session):
    """Live scrape — may return discovered=0 if network/anti-bot blocks. Still must 200."""
    r = session.post(f"{API}/scraper/run", timeout=180)
    assert r.status_code == 200, r.text
    summary = r.json()
    for k in ["discovered", "created", "updated", "skipped", "errors", "trigger"]:
        assert k in summary
    assert summary["trigger"] == "manual"
    assert isinstance(summary["discovered"], int)
    assert summary["discovered"] >= 0
    # If discovered > 0 and new signals created, verify enrichment populated
    if summary["created"] > 0:
        signals = session.get(f"{API}/signals", timeout=30).json()
        # Find any scraped (has 'ingested_by' = manual)
        scraped = [s for s in signals if s.get("priority_score") is not None]
        assert scraped, "No enriched signals after live scrape"
