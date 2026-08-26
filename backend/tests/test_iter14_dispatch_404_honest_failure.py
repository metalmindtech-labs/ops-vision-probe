"""Iteration 14 — verify EXPECTED honest-failure dispatch behaviour.

LearnForge's /api/course-generation-jobs receiver is intentionally NOT deployed,
so a dispatch must record a `failed` job with http_status 404 and a hint, must
not 500, and must not fall back to the legacy v1 publish path.
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
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")

TARGET_SIGNAL = "06981200-86b3-412e-9fa6-1578665160f5"
CONTENT_FIELDS = (
    "modules",
    "lessons",
    "quizzes",
    "syllabus",
    "curriculum",
    "chapters",
)


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def signal_id(api):
    r = api.get(f"{BASE_URL}/api/signals", params={"limit": 200}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    payload = r.json()
    signals = payload if isinstance(payload, list) else payload.get("signals", [])
    ids = [s["id"] for s in signals]
    if TARGET_SIGNAL in ids:
        return TARGET_SIGNAL
    converting = [
        s["id"] for s in signals if s.get("status") in ("converting", "live")
    ]
    if not converting:
        pytest.fail("No converting/live signal available to dispatch")
    return converting[0]


# ---------- health ----------
class TestHealth:
    def test_root_api_up(self, api):
        r = api.get(f"{BASE_URL}/api/signals", params={"limit": 1}, timeout=60)
        assert r.status_code == 200

    def test_stats(self, api):
        r = api.get(f"{BASE_URL}/api/signals/stats", timeout=60)
        assert r.status_code == 200
        assert "briefs_dispatched" in r.json()


# ---------- CourseBriefV2 preview ----------
class TestBriefPreview:
    def test_preview_shape_and_no_content(self, api, signal_id):
        r = api.get(f"{BASE_URL}/api/signals/{signal_id}/brief/preview", timeout=60)
        assert r.status_code == 200, r.text[:400]
        brief = r.json()
        for key in ("source", "demand_evidence", "audience", "commercial_hypothesis"):
            assert key in brief, f"missing {key} in brief: {list(brief)}"
        assert "_id" not in brief
        blob = str(brief).lower()
        for field in CONTENT_FIELDS:
            assert field not in brief, f"brief must not contain '{field}'"
            assert field not in blob, f"'{field}' leaked into brief payload"

    def test_preview_unknown_signal_404(self, api):
        r = api.get(
            f"{BASE_URL}/api/signals/does-not-exist-xyz/brief/preview", timeout=60
        )
        assert r.status_code == 404, r.status_code


# ---------- dispatch (expected honest failure) ----------
class TestDispatchHonestFailure:
    def test_dispatch_returns_200_failed_job_with_404_hint(self, api, signal_id):
        r = api.post(f"{BASE_URL}/api/signals/{signal_id}/dispatch", timeout=120)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:400]}"
        data = r.json()
        assert data["ok"] is False
        assert data.get("deduplicated") is False
        assert data["status_code"] == 404
        job = data["job"]
        assert job["status"] == "failed"
        assert job["http_status"] == 404
        assert job["error"]
        assert "_id" not in job
        hint = (data.get("hint") or "").lower()
        assert "course-generation-jobs" in hint
        assert "not deployed" in hint
        assert "no legacy fallback was attempted" in hint
        # brief echoed back must still be content-free
        for field in CONTENT_FIELDS:
            assert field not in data["brief"]

    def test_dispatch_unknown_signal_404(self, api):
        r = api.post(f"{BASE_URL}/api/signals/nope-not-a-signal/dispatch", timeout=60)
        assert r.status_code == 404, r.status_code

    def test_job_status_reflects_failed_job(self, api, signal_id):
        r = api.get(f"{BASE_URL}/api/signals/{signal_id}/job-status", timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        job = body.get("job")
        assert job is not None, body
        assert job["status"] == "failed"
        assert job["http_status"] == 404
        assert "_id" not in job

    def test_repeated_dispatch_does_not_dedupe_failed_job(self, api, signal_id):
        r = api.post(f"{BASE_URL}/api/signals/{signal_id}/dispatch", timeout=120)
        assert r.status_code == 200
        data = r.json()
        assert data["deduplicated"] is False
        assert data["job"]["status"] == "failed"

    def test_refresh_job_graceful_without_status_url(self, api, signal_id):
        js = api.get(f"{BASE_URL}/api/signals/{signal_id}/job-status", timeout=60).json()
        job_id = js["job"]["job_id"]
        r = api.post(f"{BASE_URL}/api/course-jobs/{job_id}/refresh", timeout=60)
        if r.status_code == 404:
            pytest.skip("no refresh route at /api/course-jobs/{id}/refresh")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["ok"] is False
        assert "status_url" in (body.get("error") or "")


# ---------- legacy publish gated off ----------
class TestLegacyPublishGated:
    def test_publish_returns_410(self, api, signal_id):
        r = api.post(f"{BASE_URL}/api/signals/{signal_id}/publish", timeout=60)
        assert r.status_code == 410, f"{r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", {})
        assert detail.get("error") == "legacy_publish_disabled"

    def test_publish_preview_returns_410(self, api, signal_id):
        r = api.get(f"{BASE_URL}/api/signals/{signal_id}/publish/preview", timeout=60)
        assert r.status_code == 410, r.status_code

    def test_publish_all_live_returns_410(self, api):
        r = api.post(f"{BASE_URL}/api/signals/publish-all-live", timeout=60)
        assert r.status_code == 410, r.status_code
