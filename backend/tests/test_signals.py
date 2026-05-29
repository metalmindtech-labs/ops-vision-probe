"""Backend tests for LearnForge Opportunity Radar API."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://course-converter-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- Health ----
def test_root(session):
    r = session.get(f"{API}/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "online"


# ---- List signals (auto-seeded) ----
def test_list_signals_seeded_and_sorted(session):
    r = session.get(f"{API}/signals")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 7, f"Expected at least 7 seeded signals, got {len(data)}"
    # priority_score sorted desc
    scores = [d["priority_score"] for d in data]
    assert scores == sorted(scores, reverse=True), f"Not sorted desc: {scores}"
    # no _id leakage
    for d in data:
        assert "_id" not in d
        assert "id" in d
        assert "event_title" in d


# ---- Stats ----
def test_signals_stats(session):
    r = session.get(f"{API}/signals/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ["total_signals", "high_priority", "total_registrations", "syllabi_generated", "categories"]:
        assert key in data, f"Missing {key}"
    assert isinstance(data["categories"], list)
    if data["categories"]:
        assert "name" in data["categories"][0] and "count" in data["categories"][0]
    # high_priority should be count of priority>=80
    signals = session.get(f"{API}/signals").json()
    expected_hp = sum(1 for s in signals if s["priority_score"] >= 80)
    assert data["high_priority"] == expected_hp


# ---- 404 ----
def test_get_signal_404(session):
    r = session.get(f"{API}/signals/nonexistent-id-xyz")
    assert r.status_code == 404


# ---- Full CRUD + conversion + syllabus flow ----
class TestCRUDFlow:
    created_id = None

    def test_create_signal(self, session):
        payload = {
            "event_title": "TEST_AI Engineering Bootcamp",
            "category": "Tech Careers",
            "registration_count": 250,
            "priority_score": 77,
            "source_url": "https://leland.com/events/test",
            "notes": "test notes",
        }
        r = session.post(f"{API}/signals", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["event_title"] == payload["event_title"]
        assert data["category"] == payload["category"]
        assert data["registration_count"] == 250
        assert data["priority_score"] == 77
        assert "id" in data and isinstance(data["id"], str)
        assert data["status"] == "tracked"
        assert data["syllabus_generated"] is False
        TestCRUDFlow.created_id = data["id"]

    def test_get_created_persisted(self, session):
        assert TestCRUDFlow.created_id
        r = session.get(f"{API}/signals/{TestCRUDFlow.created_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["event_title"] == "TEST_AI Engineering Bootcamp"

    def test_update_conversion_fields_and_slugs(self, session):
        sid = TestCRUDFlow.created_id
        payload = {
            "lead_magnet_title": "Free AI Eng Starter Pack",
            "lead_magnet_description": "kickoff guide",
            "paid_offer_title": "ForgeCore: AI Eng Sprint",
            "paid_offer_description": "8-week intensive",
            "paid_offer_price": 399.0,
            "cta_headline": "Become an AI Engineer",
            "cta_subtext": "Real reps. Real outcomes.",
            "status": "converting",
        }
        r = session.put(f"{API}/signals/{sid}", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["lead_magnet_title"] == payload["lead_magnet_title"]
        assert d["paid_offer_price"] == 399.0
        assert d["status"] == "converting"
        # Slugs derived
        assert d.get("lead_magnet_slug") == "free-ai-eng-starter-pack"
        assert d.get("paid_offer_slug") == "forgecore-ai-eng-sprint"

        # Verify persistence
        g = session.get(f"{API}/signals/{sid}").json()
        assert g["lead_magnet_slug"] == "free-ai-eng-starter-pack"
        assert g["paid_offer_slug"] == "forgecore-ai-eng-sprint"
        assert g["status"] == "converting"

    def test_trigger_syllabus(self, session):
        sid = TestCRUDFlow.created_id
        r = session.post(f"{API}/signals/{sid}/syllabus")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["syllabus_generated"] is True
        assert isinstance(d["syllabus_modules"], list)
        assert len(d["syllabus_modules"]) == 5
        m0 = d["syllabus_modules"][0]
        for key in ["index", "title", "summary", "duration_min"]:
            assert key in m0
        # Status was already "converting"; should remain converting
        assert d["status"] in ("converting", "live")

    def test_syllabus_bumps_tracked_to_converting(self, session):
        # Create a fresh tracked signal and verify status bumps
        r = session.post(f"{API}/signals", json={
            "event_title": "TEST_Bump Status",
            "category": "Tech Careers",
            "registration_count": 5,
            "priority_score": 60,
        })
        sid = r.json()["id"]
        assert r.json()["status"] == "tracked"
        rs = session.post(f"{API}/signals/{sid}/syllabus")
        assert rs.status_code == 200
        assert rs.json()["status"] == "converting"
        # cleanup
        session.delete(f"{API}/signals/{sid}")

    def test_delete_signal_and_404(self, session):
        sid = TestCRUDFlow.created_id
        r = session.delete(f"{API}/signals/{sid}")
        assert r.status_code == 200
        assert r.json().get("deleted") is True
        # Verify 404 after delete
        g = session.get(f"{API}/signals/{sid}")
        assert g.status_code == 404
        # Delete again -> 404
        d2 = session.delete(f"{API}/signals/{sid}")
        assert d2.status_code == 404


# ---- Cleanup any TEST_ leftovers ----
def test_cleanup_test_data(session):
    signals = session.get(f"{API}/signals").json()
    for s in signals:
        if s.get("event_title", "").startswith("TEST_"):
            session.delete(f"{API}/signals/{s['id']}")
