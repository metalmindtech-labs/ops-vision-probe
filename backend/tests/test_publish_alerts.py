"""Backend tests for LearnForge Opportunity Radar — publish webhook + strike alerts."""
import os
import time
import requests
import pytest

import sys as _sys
_sys.path.insert(0, "/app/backend")
from services.publisher import legacy_publish_enabled as _legacy_on  # noqa: E402
_LEGACY_SKIP = pytest.mark.skipif(
    not _legacy_on(),
    reason="v1 publish/syllabus routes deprecated (410) — RADAR_LEGACY_PUBLISH_ENABLED=false; v2 coverage in test_iter13_course_brief_v2.py",
)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

STRIKE_HTML = (
    "Jun 1, 2026 at 9:00 PM 9999 registered "
    "Cracking the MBB Consulting Case Interview Foo B. | 5.0 ( 10 ) Register"
)


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _mbb_signal(session):
    docs = session.get(f"{API}/signals", timeout=30).json()
    for d in docs:
        if d.get("event_title", "").startswith("Cracking the MBB Consulting Case"):
            return d
    return None


# ---------- Publish preview ----------
@_LEGACY_SKIP
class TestPublishPreview:
    def test_preview_payload_structure(self, session):
        sig = _mbb_signal(session)
        assert sig, "MBB seed signal missing"
        r = session.get(f"{API}/signals/{sig['id']}/publish/preview", timeout=30)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["event"] == "course.publish"
        assert p["signal_id"] == sig["id"]
        course = p["course"]
        for k in ["slug", "title", "category", "summary", "price_usd",
                  "lead_magnet", "cta", "syllabus", "demand"]:
            assert k in course, f"missing course.{k}"
        # CTA URLs use /en/courses and /en/scrolls — no /forgecore/ or /free/
        free_url = course["cta"]["free_url"]
        paid_url = course["cta"]["paid_url"]
        assert "/en/scrolls/" in free_url, free_url
        assert "/en/courses/" in paid_url, paid_url
        assert "/forgecore/" not in free_url
        assert "/forgecore/" not in paid_url
        assert "/free/" not in free_url
        assert "/free/" not in paid_url
        # demand block
        assert course["demand"]["registration_count"] == sig["registration_count"]
        assert course["demand"]["priority_score"] == sig["priority_score"]
        # syllabus modules list (possibly empty)
        assert isinstance(course["syllabus"]["modules"], list)
        # lead_magnet block
        assert "slug" in course["lead_magnet"]
        assert "url" in course["lead_magnet"]
        if course["lead_magnet"]["url"]:
            assert "/en/scrolls/" in course["lead_magnet"]["url"]

    def test_preview_404(self, session):
        r = session.get(f"{API}/signals/does-not-exist/publish/preview", timeout=30)
        assert r.status_code == 404


# ---------- Publish ----------
@_LEGACY_SKIP
class TestPublish:
    def test_publish_attempt_records_failure(self, session):
        sig = _mbb_signal(session)
        assert sig
        r = session.post(f"{API}/signals/{sig['id']}/publish", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        # Expected fields
        for k in ["ok", "status_code", "response_preview", "error", "url", "payload"]:
            assert k in body, f"missing {k}"
        # Webhook currently 404s — verify radar correctly reports failure
        assert body["ok"] is False
        # status_code may be 404 (real HTTP) or None (network err)
        assert body["status_code"] in (404, None) or 400 <= body["status_code"] < 600
        if body["status_code"] == 404:
            assert body["error"] == "HTTP 404"
        assert body["url"], "url should be the configured webhook"

        # Now GET signal — should reflect publish_status persisted
        g = session.get(f"{API}/signals/{sig['id']}", timeout=30).json()
        assert g["publish_status"] == "failed"
        assert g["last_publish_error"] is not None
        # last_publish_status_code may be int or None
        assert "last_publish_status_code" in g
        assert "published_to_url" in g
        assert "/en/courses/" in (g["published_to_url"] or "")

    def test_publish_404_for_unknown_signal(self, session):
        r = session.post(f"{API}/signals/no-such-id/publish", timeout=30)
        assert r.status_code == 404


# ---------- Signal model now has publish_status fields ----------
def test_signal_includes_publish_fields(session):
    sig = _mbb_signal(session)
    assert sig
    g = session.get(f"{API}/signals/{sig['id']}", timeout=30).json()
    for k in ["publish_status", "last_published_at", "last_publish_error",
              "last_publish_status_code", "published_to_url"]:
        assert k in g, f"missing {k}"


# ---------- Alerts list + ack ----------
class TestAlerts:
    def test_alerts_list_unack(self, session):
        r = session.get(f"{API}/alerts", timeout=30)
        assert r.status_code == 200, r.text
        alerts = r.json()
        assert isinstance(alerts, list)
        # all must be unack'd, sorted desc by detected_at
        for a in alerts:
            assert a["acknowledged"] is False
            for k in ["id", "signal_id", "signal_title", "prev_count", "new_count",
                      "delta", "delta_pct", "detected_at"]:
                assert k in a, f"alert missing {k}"
        ts = [a["detected_at"] for a in alerts]
        assert ts == sorted(ts, reverse=True), f"alerts not sorted desc: {ts}"

    def test_ack_invalid_404(self, session):
        r = session.post(f"{API}/alerts/nope-no-id/ack", timeout=30)
        assert r.status_code == 404


# ---------- Strike alert via ingest-html ----------
class TestStrikeIngestion:
    def test_strike_created_on_reg_surge(self, session):
        before_sig = _mbb_signal(session)
        assert before_sig
        before_count = before_sig["registration_count"]

        # Pre-snapshot existing alert IDs (only_unack=False to see all)
        before_alerts = session.get(
            f"{API}/alerts?only_unack=false&limit=200", timeout=30
        ).json()
        before_ids = {a["id"] for a in before_alerts}

        # Ingest the surge HTML — bumps MBB count to 9999
        r = session.post(
            f"{API}/scraper/ingest-html",
            json={"html": STRIKE_HTML},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["updated"] >= 1, s

        # Brief settle (alert insert is awaited but be tolerant)
        time.sleep(0.5)

        after_alerts = session.get(
            f"{API}/alerts?only_unack=false&limit=200", timeout=30
        ).json()
        new_alerts = [a for a in after_alerts if a["id"] not in before_ids]
        assert new_alerts, "expected at least 1 new strike alert"
        # Find one matching MBB title
        mbb_new = [a for a in new_alerts if "MBB" in a["signal_title"]]
        assert mbb_new, f"no MBB strike: {new_alerts}"
        alert = mbb_new[0]
        # Delta math
        assert alert["new_count"] == 9999
        assert alert["new_count"] > alert["prev_count"]
        assert alert["delta"] == alert["new_count"] - alert["prev_count"]
        assert alert["delta_pct"] >= 20.0
        assert alert["acknowledged"] is False

        # Persist alert id for ack test
        TestStrikeIngestion._alert_id = alert["id"]
        TestStrikeIngestion._mbb_prev = before_count

    def test_ack_single_alert(self, session):
        aid = getattr(TestStrikeIngestion, "_alert_id", None)
        assert aid, "strike alert id missing"
        r = session.post(f"{API}/alerts/{aid}/ack", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == aid
        assert d["acknowledged"] is True
        assert d.get("acknowledged_at")

        # Should no longer appear in unack list
        unack = session.get(f"{API}/alerts?only_unack=true", timeout=30).json()
        assert aid not in [a["id"] for a in unack]

    def test_ack_all(self, session):
        # Ensure at least one unacked alert exists; create surge again
        session.post(
            f"{API}/scraper/ingest-html",
            json={
                "html": "Jun 1, 2026 at 9:00 PM 12345 registered "
                        "Cracking the MBB Consulting Case Interview Foo B. | 5.0 ( 10 ) Register"
            },
            timeout=120,
        )
        time.sleep(0.5)
        r = session.post(f"{API}/alerts/ack-all", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "acknowledged" in body
        assert isinstance(body["acknowledged"], int)
        # No unack remaining
        unack = session.get(f"{API}/alerts?only_unack=true", timeout=30).json()
        assert unack == []
