"""Iteration 6 tests: Signal Velocity time-series + Publish Payload Spec."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- /api/signals/velocity ----------
class TestVelocity:
    def test_default_window(self, session):
        r = session.get(f"{API}/signals/velocity?hours=24&limit=6")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("window_hours") == 24
        series = d.get("series", [])
        assert isinstance(series, list) and len(series) == 6
        # sorted by priority_score desc
        scores = [s["priority_score"] for s in series]
        assert scores == sorted(scores, reverse=True), f"Not sorted desc: {scores}"
        # required shape
        for s in series:
            for k in ("signal_id", "title", "category", "priority_score", "current", "points"):
                assert k in s, f"Missing {k} in series item"
            assert isinstance(s["points"], list)
            # >= 30 points per series (backfill seeds 48 at 30min cadence)
            assert len(s["points"]) >= 30, f"{s['title']} has only {len(s['points'])} points"
            for p in s["points"][:3]:
                assert "t" in p and "v" in p
                assert isinstance(p["v"], int)

    def test_hours_clamped_to_168(self, session):
        r = session.get(f"{API}/signals/velocity?hours=999&limit=6")
        assert r.status_code == 200
        assert r.json()["window_hours"] == 168

    def test_hours_min_clamp(self, session):
        r = session.get(f"{API}/signals/velocity?hours=0")
        assert r.status_code == 200
        assert r.json()["window_hours"] == 1

    def test_limit_clamped_to_12(self, session):
        r = session.get(f"{API}/signals/velocity?hours=24&limit=999")
        assert r.status_code == 200
        # capped to <= 12 (depending on total signals)
        assert len(r.json()["series"]) <= 12

    def test_ids_filter(self, session):
        # pick 2 ids from current signals
        signals = session.get(f"{API}/signals").json()
        assert len(signals) >= 2
        ids = [signals[0]["id"], signals[1]["id"]]
        r = session.get(f"{API}/signals/velocity?ids={ids[0]},{ids[1]}")
        assert r.status_code == 200
        d = r.json()
        assert len(d["series"]) == 2
        returned_ids = {s["signal_id"] for s in d["series"]}
        assert returned_ids == set(ids), f"Expected {ids}, got {returned_ids}"

    def test_6h_window_shorter_than_7d(self, session):
        a = session.get(f"{API}/signals/velocity?hours=6&limit=6").json()
        b = session.get(f"{API}/signals/velocity?hours=168&limit=6").json()
        assert a["window_hours"] == 6 and b["window_hours"] == 168
        # 7D should generally have >= points than 6H for the same signal
        a_points = a["series"][0]["points"]
        b_points = b["series"][0]["points"]
        assert len(b_points) >= len(a_points)


# ---------- /api/integrations/publish-payload-spec ----------
class TestPayloadSpec:
    def test_spec_shape(self, session):
        r = session.get(f"{API}/integrations/publish-payload-spec")
        assert r.status_code == 200
        d = r.json()
        for k in ("schema", "example", "request_headers", "expected_response", "webhook_url"):
            assert k in d, f"Missing key: {k}"
        # schema title
        assert d["schema"].get("title") == "LearnForge Radar — Course Publish Webhook (v1)"
        assert d["schema"].get("type") == "object"
        # required headers
        for h in ("X-Radar-Event", "X-Radar-Signature", "User-Agent", "Content-Type"):
            assert h in d["request_headers"], f"Missing header: {h}"
        # example shape matches publisher.build_payload (event/signal_id/published_at/course)
        ex = d["example"]
        for k in ("event", "signal_id", "published_at", "course"):
            assert k in ex
        course = ex["course"]
        for k in ("slug", "title", "category", "cta", "syllabus", "demand"):
            assert k in course, f"course missing {k}"
        assert "modules" in course["syllabus"]
        # expected_response shape
        assert "success" in d["expected_response"]
        assert "failure" in d["expected_response"]


# ---------- Regression: existing endpoints ----------
class TestRegression:
    def test_signals_list(self, session):
        r = session.get(f"{API}/signals")
        assert r.status_code == 200
        assert len(r.json()) >= 7

    def test_signals_stats(self, session):
        r = session.get(f"{API}/signals/stats")
        assert r.status_code == 200
        for k in ("total_signals", "high_priority", "total_registrations", "categories"):
            assert k in r.json()

    def test_scraper_status(self, session):
        r = session.get(f"{API}/scraper/status")
        assert r.status_code == 200
        assert "scheduler_running" in r.json()

    def test_alerts_list(self, session):
        r = session.get(f"{API}/alerts?only_unack=false&limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_integrations_status(self, session):
        r = session.get(f"{API}/integrations/status")
        assert r.status_code == 200
        d = r.json()
        assert "whatsapp" in d and "publish_webhook" in d

    def test_publish_preview(self, session):
        s = session.get(f"{API}/signals").json()[0]
        r = session.get(f"{API}/signals/{s['id']}/publish/preview")
        assert r.status_code == 200
        d = r.json()
        assert d.get("event") == "course.publish"
        assert "course" in d


# ---------- Scrape adds history point ----------
class TestScrapeAddsHistoryPoint:
    def test_ingest_html_records_history(self, session):
        # Use an existing signal title with a higher count to force UPDATE
        signals = session.get(f"{API}/signals").json()
        target = next((s for s in signals if s.get("event_title") and s.get("registration_count", 0) > 0), None)
        assert target, "No suitable signal to test against"
        sid = target["id"]
        title = target["event_title"]
        bigger = (target.get("registration_count") or 0) + 5000

        # Get baseline points count for this signal
        before = session.get(f"{API}/signals/velocity?ids={sid}&hours=168").json()
        before_points = len(before["series"][0]["points"])

        # Build minimal Leland-style text matching the scraper regex.
        # Pattern needs: "<when> <count> registered <title> <Coach F. M.> | <rating> (<reviews>) Register"
        html = (
            f"<html><body>Starts in 2 hours {bigger} registered "
            f"{title} Test C. M. | 4.9 (123) Register</body></html>"
        )
        r = session.post(f"{API}/scraper/ingest-html", json={"html": html})
        assert r.status_code == 200, r.text
        body = r.json()
        # Either updated or created — what we care about is a new history row for this signal
        assert body.get("updated", 0) + body.get("created", 0) >= 0

        after = session.get(f"{API}/signals/velocity?ids={sid}&hours=168").json()
        after_points = len(after["series"][0]["points"])
        assert after_points >= before_points + 1, (
            f"Expected history points to grow from {before_points}; got {after_points}"
        )
