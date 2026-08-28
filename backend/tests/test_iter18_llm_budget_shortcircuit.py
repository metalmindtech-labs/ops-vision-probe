"""Iteration 18 — scraper LLM budget-exceeded short-circuit path."""

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


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def scrape_run(client):
    before = client.get(f"{BASE_URL}/api/signals/stats", timeout=60)
    assert before.status_code == 200, before.text
    resp = client.post(f"{BASE_URL}/api/scraper/run", timeout=300)
    after = client.get(f"{BASE_URL}/api/signals/stats", timeout=60)
    assert after.status_code == 200, after.text
    return {
        "before": before.json(),
        "resp": resp,
        "after": after.json(),
    }


class TestScraperBudgetPath:
    def test_status_200(self, scrape_run):
        assert scrape_run["resp"].status_code == 200, scrape_run["resp"].text[:800]

    def test_budget_flag_and_message(self, scrape_run):
        data = scrape_run["resp"].json()
        print("SCRAPE RESULT:", data)
        assert data.get("llm_budget_exceeded") is True, (
            f"Expected llm_budget_exceeded=True, got: {data}"
        )
        msg = data.get("message") or ""
        assert msg.strip(), "message field empty"
        assert "universal key" in msg.lower()

    def test_discovered_and_created(self, scrape_run):
        data = scrape_run["resp"].json()
        assert data.get("discovered", 0) > 0, f"discovered not >0: {data}"
        assert data.get("created") == 0, f"created should be 0: {data}"

    def test_errors_short_circuited(self, scrape_run):
        data = scrape_run["resp"].json()
        errors = data.get("errors") or []
        assert len(errors) <= 2, f"errors not short-circuited: {errors}"
        assert len(errors) >= 1, "expected at least one friendly error entry"
        joined = " ".join(errors).lower()
        assert "llm budget exceeded" in joined, f"unfriendly error text: {errors}"
        assert "top up the universal key" in joined, f"missing guidance: {errors}"
        assert "chaterror" not in joined, f"raw ChatError leaked: {errors}"

    def test_no_signals_created(self, scrape_run):
        b, a = scrape_run["before"], scrape_run["after"]
        print("STATS before:", b, "after:", a)
        key = "total" if "total" in b else next(
            (k for k in b if "total" in k.lower()), None
        )
        assert key, f"no total-like key in stats: {b}"
        assert a[key] == b[key], f"signal count changed {b[key]} -> {a[key]}"

    def test_latest_run_persisted(self, client, scrape_run):
        r = client.get(f"{BASE_URL}/api/scraper/status", timeout=60)
        if r.status_code == 404:
            pytest.skip("no last-run endpoint")
        assert r.status_code == 200, r.text[:400]
        data = r.json() or {}
        print("LAST RUN:", data)
        assert "_id" not in str(data)
