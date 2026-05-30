"""Iteration 11 — Verify reconcile + publish-history endpoints.

Covers:
- GET /api/learnforge/reconcile: probe + totals + drift structure
- GET /api/signals/{id}/publish-history: signal diag fields + history list
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://course-converter-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
FIXTURE_SIGNAL_ID = "e3171073-0ae9-4bf8-ae9b-3bb2e303a576"


@pytest.fixture(scope="module")
def reconcile_payload():
    r = requests.get(f"{API}/learnforge/reconcile", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestReconcile:
    def test_status_200(self, reconcile_payload):
        assert isinstance(reconcile_payload, dict)

    def test_probe_shape(self, reconcile_payload):
        probe = reconcile_payload.get("learnforge_probe")
        assert probe is not None
        assert probe["url"] == "https://learnforge-core.vercel.app/api/courses"
        assert "reachable" in probe
        assert "status_code" in probe
        assert "error" in probe
        assert "service" in probe

    def test_probe_404_not_deployed(self, reconcile_payload):
        probe = reconcile_payload["learnforge_probe"]
        # Receiver still not deployed → 404 and not reachable
        assert probe["reachable"] is False
        assert probe["status_code"] == 404

    def test_totals_shape(self, reconcile_payload):
        t = reconcile_payload["totals"]
        for key in ("syllabus_generated", "published", "failed", "pending"):
            assert key in t
            assert isinstance(t[key], int)

    def test_drift_shape(self, reconcile_payload):
        d = reconcile_payload["drift"]
        assert "count" in d and isinstance(d["count"], int)
        assert d["count"] > 0, "expected non-zero drift since receiver is 404"
        assert isinstance(d["failed_signals"], list)
        assert isinstance(d["pending_signals"], list)
        assert len(d["failed_signals"]) >= 1
        f0 = d["failed_signals"][0]
        for k in ("id", "title", "status_code", "hint", "retry_count", "next_retry_at"):
            assert k in f0, f"failed_signals entry missing key {k}"
        # hint should mention route-not-deployed
        assert f0["status_code"] == 404
        assert "route" in (f0.get("hint") or "").lower() or "deployed" in (f0.get("hint") or "").lower()


class TestPublishHistory:
    @pytest.fixture(scope="class")
    def history_payload(self):
        r = requests.get(
            f"{API}/signals/{FIXTURE_SIGNAL_ID}/publish-history?limit=5",
            timeout=20,
        )
        assert r.status_code == 200, r.text
        return r.json()

    def test_signal_diag_fields(self, history_payload):
        s = history_payload["signal"]
        required = [
            "publish_status",
            "last_publish_status_code",
            "last_publish_error",
            "last_publish_hint",
            "last_publish_response_preview",
            "last_publish_webhook_url",
            "last_publish_at",
            "publish_retry_count",
            "publish_next_retry_at",
        ]
        for k in required:
            assert k in s, f"missing diag field {k}"

    def test_signal_is_failed(self, history_payload):
        s = history_payload["signal"]
        assert s["publish_status"] == "failed"
        assert s["last_publish_status_code"] == 404

    def test_history_is_list(self, history_payload):
        h = history_payload["history"]
        assert isinstance(h, list)
        if len(h) > 0:
            entry = h[0]
            for k in ("status_code", "error", "hint", "at"):
                assert k in entry, f"history entry missing {k}"

    def test_404_for_unknown_signal(self):
        r = requests.get(f"{API}/signals/__nonexistent__/publish-history", timeout=15)
        assert r.status_code == 404
