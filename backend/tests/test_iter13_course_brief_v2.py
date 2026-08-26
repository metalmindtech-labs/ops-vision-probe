"""Iteration 13 — CourseBriefV2 + v2 dispatcher + legacy gating.

Covers:
- CourseBriefV2 validation + forbidden educational-content fields
- Deterministic/stable idempotency key
- HMAC signing header on dispatch (raw-body HMAC-SHA256)
- Dispatch success / dedupe / 404 / missing-URL / retry / timeout exhaustion
- refresh_job state transitions incl. unknown-state rejection
- Legacy flag OFF: live API returns 410 on all v1 publish/syllabus routes

External LearnForge calls are MOCKED (httpx.MockTransport via the
dispatcher._client_factory seam). Tests use a dedicated Mongo database
(radar_iter13_tests) — production data is never touched.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as hmac_lib
import json
import os
import sys
import uuid

import httpx
import pytest
import requests

BACKEND_DIR = "/app/backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")

from services.course_brief import (  # noqa: E402
    CourseBriefV2,
    FORBIDDEN_CONTENT_FIELDS,
    assert_no_content_fields,
    build_course_brief,
    compute_idempotency_key,
)
import services.dispatcher as dispatcher  # noqa: E402
from services.publisher import legacy_publish_enabled, sign_payload  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://course-converter-2.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

TEST_DB = "radar_iter13_tests"
JOBS_URL = "https://mock.learnforge.test/api/course-generation-jobs"


def fixture_signal(**overrides) -> dict:
    sig = {
        "id": str(uuid.uuid4()),
        "event_title": "MBB Case Interview Bootcamp",
        "category": "Consulting",
        "registration_count": 1200,
        "priority_score": 88,
        "source_url": "https://www.joinleland.com/events/mbb-case",
        "notes": "Registrations doubled week-over-week.",
        "paid_offer_title": "ForgeCore: The 21-Day MBB Case Engine",
        "paid_offer_description": "Master the case framework stack",
        "paid_offer_price": 1000,
        "paid_offer_original_price": 1899,
        "cta_headline": "Land Your MBB Offer",
        "cta_subtext": "Outcome-tracked case prep",
        "syllabus_generated": True,
        "syllabus_modules": [{"index": 1, "title": "legacy module"}],
        "created_at": "2026-06-01T00:00:00+00:00",
        "updated_at": "2026-06-01T00:00:00+00:00",
    }
    sig.update(overrides)
    return sig


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _make_db():
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[TEST_DB]
    await db.signals.delete_many({})
    await db.course_jobs.delete_many({})
    return client, db


def mock_factory(handler, calls):
    def factory(timeout: float = 20.0):
        async def counting_handler(request):
            calls.append(request)
            return handler(request)

        return httpx.AsyncClient(
            transport=httpx.MockTransport(counting_handler), timeout=timeout
        )

    return factory


# ---------------------------------------------------------------------------
# 1. Brief validation
# ---------------------------------------------------------------------------
class TestCourseBriefValidation:
    def test_build_brief_shape(self):
        b = build_course_brief(fixture_signal())
        assert b.schema_version == "2.0"
        assert b.demand_evidence.priority_band == "high"
        assert b.commercial_hypothesis.discount_pct == 47
        assert b.commercial_hypothesis.free_module_count == 2
        assert b.commercial_hypothesis.validation_status == "hypothesis"
        assert b.callback.correlation_id.startswith("radar-")
        assert len(b.generation_constraints.prohibited_claims) >= 6

    def test_priority_bands(self):
        assert build_course_brief(fixture_signal(priority_score=95)).demand_evidence.priority_band == "breakout"
        assert build_course_brief(fixture_signal(priority_score=60)).demand_evidence.priority_band == "medium"
        assert build_course_brief(fixture_signal(priority_score=10)).demand_evidence.priority_band == "low"

    def test_rejects_extra_fields(self):
        b = build_course_brief(fixture_signal())
        data = b.model_dump()
        for bad in ("modules", "lessons", "quizzes", "syllabus"):
            with pytest.raises(Exception):
                CourseBriefV2(**{**data, bad: []})

    def test_serialized_brief_has_no_content_fields(self):
        payload = build_course_brief(fixture_signal()).model_dump()
        assert_no_content_fields(payload)  # must not raise
        keys = set()

        def collect(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    keys.add(k)
                    collect(v)
            elif isinstance(d, list):
                for x in d:
                    collect(x)

        collect(payload)
        assert not (keys & FORBIDDEN_CONTENT_FIELDS)

    def test_assert_no_content_fields_catches_nested(self):
        with pytest.raises(ValueError):
            assert_no_content_fields({"a": {"b": [{"syllabus": {}}]}})


# ---------------------------------------------------------------------------
# 2. Idempotency key
# ---------------------------------------------------------------------------
class TestIdempotencyKey:
    def test_deterministic(self):
        sig = fixture_signal(id="fixed-id")
        assert compute_idempotency_key(sig) == compute_idempotency_key(dict(sig))

    def test_stable_across_volatile_fields(self):
        sig = fixture_signal(id="fixed-id")
        sig2 = {**sig, "updated_at": "2027-01-01T00:00:00+00:00", "publish_status": "failed"}
        assert compute_idempotency_key(sig) == compute_idempotency_key(sig2)

    def test_changes_with_content(self):
        sig = fixture_signal(id="fixed-id")
        sig2 = {**sig, "registration_count": 9999}
        assert compute_idempotency_key(sig) != compute_idempotency_key(sig2)


# ---------------------------------------------------------------------------
# 3. HMAC signing
# ---------------------------------------------------------------------------
class TestHmacSigning:
    def test_dispatch_signs_raw_body(self, monkeypatch):
        monkeypatch.setenv("LEARNFORGE_COURSE_JOBS_URL", JOBS_URL)
        monkeypatch.setenv("LEARNFORGE_WEBHOOK_SECRET", "test-secret")
        calls = []

        def handler(request):
            return httpx.Response(202, json={"job_id": "lf-1", "status": "queued"})

        monkeypatch.setattr(dispatcher, "_client_factory", mock_factory(handler, calls))

        async def flow():
            client, db = await _make_db()
            sig = fixture_signal()
            await db.signals.insert_one(dict(sig))
            res = await dispatcher.dispatch_brief(db, sig["id"])
            client.close()
            return res

        res = run(flow())
        assert res["ok"] is True
        req = calls[0]
        body = req.content
        expected = hmac_lib.new(b"test-secret", body, hashlib.sha256).hexdigest()
        assert req.headers["X-Radar-Signature"] == expected
        assert req.headers["X-Radar-Signature"] == sign_payload("test-secret", body)
        assert req.headers["X-Radar-Schema-Version"] == "2.0"
        assert req.headers["X-Radar-Event"] == "course_brief.dispatch"
        # payload on the wire contains no content fields
        assert_no_content_fields(json.loads(body))


# ---------------------------------------------------------------------------
# 4. Dispatch behavior
# ---------------------------------------------------------------------------
class TestDispatch:
    def _dispatch(self, monkeypatch, handler, calls, signal=None, jobs_url=JOBS_URL):
        if jobs_url is None:
            monkeypatch.delenv("LEARNFORGE_COURSE_JOBS_URL", raising=False)
        else:
            monkeypatch.setenv("LEARNFORGE_COURSE_JOBS_URL", jobs_url)
        monkeypatch.setattr(dispatcher, "_client_factory", mock_factory(handler, calls))
        monkeypatch.setattr(dispatcher, "BACKOFF_S", (0.01, 0.01, 0.01))

        async def flow():
            client, db = await _make_db()
            sig = signal or fixture_signal()
            await db.signals.insert_one(dict(sig))
            res = await dispatcher.dispatch_brief(db, sig["id"])
            job_doc = await db.course_jobs.find_one({"signal_id": sig["id"]}, {"_id": 0})
            sig_doc = await db.signals.find_one({"id": sig["id"]}, {"_id": 0})
            client.close()
            return res, job_doc, sig_doc

        return run(flow())

    def test_success_records_job_and_signal(self, monkeypatch):
        calls = []
        res, job, sig = self._dispatch(
            monkeypatch,
            lambda r: httpx.Response(
                202,
                json={"job_id": "lf-42", "status": "queued", "status_url": f"{JOBS_URL}/lf-42"},
            ),
            calls,
        )
        assert res["ok"] and job["status"] == "queued"
        assert job["remote_job_id"] == "lf-42"
        assert sig["course_job_status"] == "queued"

    def test_404_recorded_as_failed_with_hint(self, monkeypatch):
        calls = []
        res, job, sig = self._dispatch(
            monkeypatch, lambda r: httpx.Response(404, json={"detail": "Not Found"}), calls
        )
        assert res["ok"] is False
        assert job["status"] == "failed"
        assert "not deployed" in res["hint"]
        assert len(calls) == 1  # no retry on 4xx
        assert sig["course_job_status"] == "failed"

    def test_missing_url_fails_safely_no_legacy_fallback(self, monkeypatch):
        calls = []
        res, job, _ = self._dispatch(monkeypatch, lambda r: httpx.Response(200), calls, jobs_url=None)
        assert res["ok"] is False and job["status"] == "failed"
        assert "not configured" in res["error"]
        assert len(calls) == 0  # no HTTP call at all → no legacy fallback
        assert "No fallback" in res["hint"]

    def test_retry_on_5xx_then_success(self, monkeypatch):
        calls = []
        responses = [500, 500, 202]

        def handler(r):
            code = responses[len(calls) - 1]
            if code == 202:
                return httpx.Response(202, json={"job_id": "lf-9", "status": "accepted"})
            return httpx.Response(code, text="boom")

        res, job, _ = self._dispatch(monkeypatch, handler, calls)
        assert res["ok"] and job["status"] == "accepted"
        assert job["attempts"] == 3

    def test_timeout_exhaustion_fails(self, monkeypatch):
        calls = []

        def handler(r):
            raise httpx.ConnectError("refused")

        res, job, _ = self._dispatch(monkeypatch, handler, calls)
        assert res["ok"] is False and job["status"] == "failed"
        assert job["attempts"] == 3
        assert "ConnectError" in res["error"]

    def test_malformed_2xx_body_is_accepted_not_ready(self, monkeypatch):
        calls = []
        res, job, _ = self._dispatch(
            monkeypatch, lambda r: httpx.Response(200, text="<html>ok</html>"), calls
        )
        assert res["ok"] and job["status"] == "accepted"
        assert job["status"] != "ready" and job["public_course_url"] is None

    def test_duplicate_dispatch_deduplicated(self, monkeypatch):
        monkeypatch.setenv("LEARNFORGE_COURSE_JOBS_URL", JOBS_URL)
        calls = []
        monkeypatch.setattr(
            dispatcher,
            "_client_factory",
            mock_factory(lambda r: httpx.Response(202, json={"job_id": "lf-1", "status": "queued"}), calls),
        )

        async def flow():
            client, db = await _make_db()
            sig = fixture_signal()
            await db.signals.insert_one(dict(sig))
            r1 = await dispatcher.dispatch_brief(db, sig["id"])
            r2 = await dispatcher.dispatch_brief(db, sig["id"])
            n_jobs = await db.course_jobs.count_documents({"signal_id": sig["id"]})
            client.close()
            return r1, r2, n_jobs

        r1, r2, n_jobs = run(flow())
        assert r1["ok"] and not r1["deduplicated"]
        assert r2["ok"] and r2["deduplicated"]
        assert len(calls) == 1 and n_jobs == 1

    def test_failed_dispatch_allows_retry_dispatch(self, monkeypatch):
        monkeypatch.setenv("LEARNFORGE_COURSE_JOBS_URL", JOBS_URL)
        calls = []
        codes = iter([404, 202])

        def handler(r):
            code = next(codes)
            if code == 202:
                return httpx.Response(202, json={"job_id": "lf-2", "status": "queued"})
            return httpx.Response(404, json={"detail": "Not Found"})

        monkeypatch.setattr(dispatcher, "_client_factory", mock_factory(handler, calls))

        async def flow():
            client, db = await _make_db()
            sig = fixture_signal()
            await db.signals.insert_one(dict(sig))
            r1 = await dispatcher.dispatch_brief(db, sig["id"])
            r2 = await dispatcher.dispatch_brief(db, sig["id"])
            client.close()
            return r1, r2

        r1, r2 = run(flow())
        assert r1["ok"] is False and r2["ok"] is True and not r2["deduplicated"]


# ---------------------------------------------------------------------------
# 5. refresh_job state transitions
# ---------------------------------------------------------------------------
class TestRefreshJob:
    def _seed_job(self, db_and_client, status="queued"):
        client, db = db_and_client
        job = {
            "job_id": "local-1",
            "signal_id": "sig-1",
            "idempotency_key": "k",
            "status": status,
            "remote_job_id": "lf-1",
            "status_url": f"{JOBS_URL}/lf-1",
            "public_course_url": None,
            "dispatched_at": "2026-06-01T00:00:00+00:00",
        }
        return job

    def _refresh(self, monkeypatch, handler):
        monkeypatch.setenv("LEARNFORGE_COURSE_JOBS_URL", JOBS_URL)
        calls = []
        monkeypatch.setattr(dispatcher, "_client_factory", mock_factory(handler, calls))

        async def flow():
            client, db = await _make_db()
            await db.signals.insert_one({"id": "sig-1"})
            job = self._seed_job((client, db))
            await db.course_jobs.insert_one(dict(job))
            res = await dispatcher.refresh_job(db, "local-1")
            client.close()
            return res

        return run(flow())

    def test_transition_to_generating(self, monkeypatch):
        res = self._refresh(
            monkeypatch, lambda r: httpx.Response(200, json={"status": "generating"})
        )
        assert res["ok"] and res["job"]["status"] == "generating"

    def test_ready_with_public_url(self, monkeypatch):
        res = self._refresh(
            monkeypatch,
            lambda r: httpx.Response(
                200, json={"status": "ready", "public_course_url": "https://lf.test/c/x"}
            ),
        )
        assert res["job"]["status"] == "ready"
        assert res["job"]["public_course_url"] == "https://lf.test/c/x"

    def test_unknown_state_rejected_keeps_previous(self, monkeypatch):
        res = self._refresh(
            monkeypatch, lambda r: httpx.Response(200, json={"status": "published"})
        )
        assert res["ok"] is False
        assert res["job"]["status"] == "queued"  # unchanged
        assert "unknown status" in res["job"]["last_check_error"]

    def test_http_error_does_not_advance_state(self, monkeypatch):
        res = self._refresh(monkeypatch, lambda r: httpx.Response(500, text="err"))
        assert res["ok"] is False and res["job"]["status"] == "queued"

    def test_job_not_found(self, monkeypatch):
        async def flow():
            client, db = await _make_db()
            res = await dispatcher.refresh_job(db, "nope")
            client.close()
            return res

        assert run(flow())["error"] == "job_not_found"


# ---------------------------------------------------------------------------
# 6. Legacy flag OFF — live API returns 410, no legacy publish/generation
# ---------------------------------------------------------------------------
class TestLegacyGatingLive:
    @pytest.fixture(scope="class")
    def any_signal_id(self):
        r = requests.get(f"{API}/signals", timeout=20)
        assert r.status_code == 200
        sigs = r.json()
        assert sigs, "expected seeded signals"
        return sigs[0]["id"]

    def test_flag_is_off(self):
        assert legacy_publish_enabled() is False

    def test_publish_gated_410(self, any_signal_id):
        r = requests.post(f"{API}/signals/{any_signal_id}/publish", timeout=20)
        assert r.status_code == 410
        assert r.json()["detail"]["error"] == "legacy_publish_disabled"

    def test_publish_preview_gated_410(self, any_signal_id):
        r = requests.get(f"{API}/signals/{any_signal_id}/publish/preview", timeout=20)
        assert r.status_code == 410

    def test_publish_all_gated_410(self):
        r = requests.post(f"{API}/signals/publish-all-live", timeout=20)
        assert r.status_code == 410

    def test_retry_pending_gated_410(self):
        r = requests.post(f"{API}/signals/retry-pending-publishes", timeout=20)
        assert r.status_code == 410

    def test_syllabus_generation_gated_410(self, any_signal_id):
        r = requests.post(f"{API}/signals/{any_signal_id}/syllabus", timeout=20)
        assert r.status_code == 410

    def test_syllabus_stream_gated_410(self, any_signal_id):
        r = requests.get(f"{API}/signals/{any_signal_id}/syllabus/stream", timeout=20)
        assert r.status_code == 410

    def test_integrations_status_exposes_flag_and_v2(self):
        r = requests.get(f"{API}/integrations/status", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["legacy_publish_enabled"] is False
        assert data["course_jobs"]["schema_version"] == "2.0"
        assert data["course_jobs"]["url"]

    def test_brief_preview_live_read_only_no_content_fields(self, any_signal_id):
        r = requests.get(f"{API}/signals/{any_signal_id}/brief/preview", timeout=20)
        assert r.status_code == 200
        payload = r.json()
        assert payload["schema_version"] == "2.0"
        assert_no_content_fields(payload)
