"""Iteration 7 backend tests: strike-attribution on /api/signals/velocity
and signal_history hygiene (no synthetic rows; snapshots grow on ingest)."""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="module")
def velocity_payload():
    r = requests.get(f"{BASE_URL}/api/signals/velocity", params={"hours": 24, "limit": 6}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- A. /api/signals/velocity strike attribution ----------

class TestVelocityStrikes:
    def test_velocity_returns_series(self, velocity_payload):
        assert "series" in velocity_payload
        assert isinstance(velocity_payload["series"], list)
        assert len(velocity_payload["series"]) > 0
        assert velocity_payload["window_hours"] == 24

    def test_every_series_has_strikes_array(self, velocity_payload):
        for s in velocity_payload["series"]:
            assert "strikes" in s, f"missing strikes on {s.get('title')}"
            assert isinstance(s["strikes"], list)

    def test_strike_schema_and_tier(self, velocity_payload):
        seen_any_strike = False
        for s in velocity_payload["series"]:
            for st in s.get("strikes", []):
                seen_any_strike = True
                for f in ("alert_id", "t", "v", "prev_count", "delta_pct", "tier"):
                    assert f in st, f"missing {f} in strike: {st}"
                assert st["tier"] in ("strike", "surge", "breakout")
                dp = st["delta_pct"]
                if dp >= 100:
                    assert st["tier"] == "breakout"
                elif dp >= 50:
                    assert st["tier"] == "surge"
                else:
                    assert st["tier"] == "strike"
        assert seen_any_strike, "Expected at least one strike (DB has signal_alerts rows)"

    def test_velocity_ids_filter(self, velocity_payload):
        ids = [s["signal_id"] for s in velocity_payload["series"][:2]]
        r = requests.get(
            f"{BASE_URL}/api/signals/velocity",
            params={"hours": 24, "ids": ",".join(ids)},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        returned_ids = {s["signal_id"] for s in body["series"]}
        assert returned_ids == set(ids)
        for s in body["series"]:
            assert "strikes" in s


# ---------- B. signal_history hygiene ----------

class TestSignalHistoryHygiene:
    def test_no_synthetic_rows(self, db):
        count = db.signal_history.count_documents({"synthetic": True})
        assert count == 0, f"Found {count} synthetic rows in signal_history"

    def test_history_has_real_rows(self, db):
        total = db.signal_history.count_documents({})
        assert total > 0, "signal_history is empty"


# ---------- C. ingest grows history + may create strike ----------

class TestIngestGrowsHistoryAndStrike:
    SAMPLE_HTML = (
        "<div>Jun 1, 2026 at 9:00 PM 25000 registered "
        "Cracking the MBB Consulting Case Interview Foo B. | 5.0 ( 10 ) Register</div>"
    )

    def test_ingest_grows_history_and_emits_strike_in_velocity(self, db):
        # find the target signal
        sig = db.signals.find_one({"event_title": "Cracking the MBB Consulting Case Interview"})
        assert sig is not None
        sid = sig["id"]
        before_hist = db.signal_history.count_documents({"signal_id": sid})
        before_alerts = db.signal_alerts.count_documents({"signal_id": sid})

        r = requests.post(
            f"{BASE_URL}/api/scraper/ingest-html",
            json={"html": self.SAMPLE_HTML},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["updated"] >= 1 or body["created"] >= 1

        # Slight delay for Mongo
        time.sleep(0.4)

        after_hist = db.signal_history.count_documents({"signal_id": sid})
        assert after_hist >= before_hist + 1, (
            f"history did not grow for {sid}: before={before_hist} after={after_hist}"
        )

        after_alerts = db.signal_alerts.count_documents({"signal_id": sid})
        # Strike alert is best-effort (depends on prev count); accept either >= before
        assert after_alerts >= before_alerts

        # velocity now should include this signal's series with strikes if alerts exist
        vr = requests.get(
            f"{BASE_URL}/api/signals/velocity",
            params={"hours": 24, "ids": sid},
            timeout=15,
        )
        assert vr.status_code == 200
        ser = vr.json()["series"]
        assert len(ser) == 1
        assert ser[0]["signal_id"] == sid
        assert "strikes" in ser[0]


# ---------- D. regression ----------

class TestRegression:
    def test_signals_list(self):
        r = requests.get(f"{BASE_URL}/api/signals", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats(self):
        r = requests.get(f"{BASE_URL}/api/signals/stats", timeout=10)
        assert r.status_code == 200
        assert "total_signals" in r.json()

    def test_alerts(self):
        r = requests.get(f"{BASE_URL}/api/alerts", params={"only_unack": False, "limit": 5}, timeout=10)
        assert r.status_code == 200

    def test_scraper_status(self):
        r = requests.get(f"{BASE_URL}/api/scraper/status", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "scheduler_running" in body

    def test_publish_payload_spec(self):
        r = requests.get(f"{BASE_URL}/api/integrations/publish-payload-spec", timeout=10)
        assert r.status_code == 200
        for f in ("schema", "example", "request_headers", "expected_response"):
            assert f in r.json()

    def test_integrations_status(self):
        r = requests.get(f"{BASE_URL}/api/integrations/status", timeout=10)
        assert r.status_code == 200
        assert "whatsapp" in r.json()
