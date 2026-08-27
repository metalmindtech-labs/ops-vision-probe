"""Iteration 15 — Radar -> LearnForge STAGING live dispatch gate.

Covers:
- Idempotent re-dispatch of an already-accepted signal (no second job)
- job-status
- course-jobs/{id}/refresh against the LIVE staging GET endpoint
- CourseBriefV2 preview shape + forbidden-field guard
- legacy publish 410
- fresh 202 dispatch for exactly ONE extra signal, then dedup repeat
"""

import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get(
    "REACT_APP_BACKEND_URL"
)
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

TARGET = "06981200-86b3-412e-9fa6-1578665160f5"
FRESH = "f7f1253a-2b8c-45c1-bc83-32803107710a"
FORBIDDEN = ("modules", "lessons", "quizzes", "syllabus")
LONG = 90


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _post_retry(client, url, timeout=LONG):
    """Retry once on transient transport error (Vercel cold start)."""
    try:
        return client.post(url, timeout=timeout)
    except requests.RequestException:
        return client.post(url, timeout=timeout)


# ---------------- Idempotent re-dispatch of already-accepted signal ----------
class TestIdempotentDispatch:
    def test_dispatch_target_is_deduplicated(self, api_client):
        r = _post_retry(api_client, f"{API}/signals/{TARGET}/dispatch")
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["ok"] is True
        assert d["deduplicated"] is True
        job = d["job"]
        assert job["status"] == "accepted"
        assert job["http_status"] == 202
        assert job["remote_job_id"]
        assert job["status_url"]

    def test_no_duplicate_job_created(self, api_client):
        r = api_client.get(f"{API}/signals/{TARGET}/job-status", timeout=30)
        assert r.status_code == 200
        job = r.json()["job"]
        assert job["status"] == "accepted"
        assert job["job_id"]

    def test_refresh_hits_live_staging(self, api_client):
        js = api_client.get(f"{API}/signals/{TARGET}/job-status", timeout=30).json()
        job_id = js["job"]["job_id"]
        r = _post_retry(api_client, f"{API}/course-jobs/{job_id}/refresh")
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["ok"] is True, d
        assert d["status_code"] == 200
        assert d["job"]["status"] == "accepted"


# ---------------- CourseBriefV2 preview -------------------------------------
class TestBriefPreview:
    def test_preview_shape_and_no_forbidden_fields(self, api_client):
        r = api_client.get(f"{API}/signals/{TARGET}/brief/preview", timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        brief = body.get("brief", body)
        for key in (
            "source",
            "demand_evidence",
            "audience",
            "commercial_hypothesis",
            "generation_constraints",
        ):
            assert key in brief, f"missing {key}"
        assert brief["generation_constraints"].get("target_duration_min") is not None
        flat = str(brief).lower()
        for bad in FORBIDDEN:
            assert bad not in brief, f"forbidden field {bad} present"
            assert f"'{bad}'" not in flat, f"forbidden key {bad} nested"


# ---------------- Legacy publish disabled ----------------------------------
class TestLegacyPublishGone:
    def test_publish_returns_410(self, api_client):
        r = api_client.post(f"{API}/signals/{TARGET}/publish", timeout=30)
        assert r.status_code == 410, f"{r.status_code} {r.text[:300]}"


# ---------------- Fresh 202 dispatch (ONE extra signal only) ---------------
class TestFreshDispatch:
    remote_id = None

    def test_fresh_dispatch_accepted_202(self, api_client):
        r = _post_retry(api_client, f"{API}/signals/{FRESH}/dispatch")
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["ok"] is True, d
        assert d["deduplicated"] is False, "expected a fresh dispatch"
        job = d["job"]
        assert job["status"] == "accepted", job
        assert job["http_status"] == 202, job
        assert job["remote_job_id"], job
        TestFreshDispatch.remote_id = job["remote_job_id"]

    def test_fresh_dispatch_repeat_is_deduplicated(self, api_client):
        r = _post_retry(api_client, f"{API}/signals/{FRESH}/dispatch")
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["deduplicated"] is True, d
        assert d["job"]["remote_job_id"] == TestFreshDispatch.remote_id

    def test_stats_reflect_dispatched_briefs(self, api_client):
        r = api_client.get(f"{API}/signals/stats", timeout=30)
        assert r.status_code == 200
        s = r.json()
        assert s["briefs_dispatched"] >= 3, s
        assert isinstance(s["legacy_courses"], int)
