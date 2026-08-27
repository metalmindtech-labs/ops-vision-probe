"""Iteration 17 — verify 401 'Invalid signature' fix after webhook secret rotation.

Live staging receiver: https://learnforge-staging.vercel.app/api/course-generation-jobs
Target signal: 06981200-86b3-412e-9fa6-1578665160f5
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
SIGNAL_ID = "06981200-86b3-412e-9fa6-1578665160f5"

STATE = {}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- dispatch (the reported bug) ---
def test_01_dispatch_returns_accepted_not_401(client):
    try:
        r = client.post(f"{BASE_URL}/api/signals/{SIGNAL_ID}/dispatch", timeout=120)
    except requests.RequestException:
        r = client.post(f"{BASE_URL}/api/signals/{SIGNAL_ID}/dispatch", timeout=120)
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    print("DISPATCH:", data.get("ok"), data.get("deduplicated"), data.get("status_code"),
          data.get("error"), data.get("hint"))
    job = data.get("job") or {}
    print("JOB:", {k: job.get(k) for k in
                   ("status", "http_status", "remote_job_id", "status_url", "error")})
    assert data["ok"] is True, f"dispatch not ok: {data}"
    assert job.get("status") == "accepted", job
    assert data.get("status_code") != 401 and job.get("http_status") != 401
    if not data.get("deduplicated"):
        assert job.get("http_status") == 202, job
    assert job.get("remote_job_id"), job
    assert job.get("status_url"), job
    assert not job.get("error")
    STATE["job_id"] = job["job_id"]
    STATE["remote_job_id"] = job["remote_job_id"]
    STATE["idem"] = job.get("idempotency_key")


# --- idempotency on repeat dispatch ---
def test_02_repeat_dispatch_is_deduplicated(client):
    assert "job_id" in STATE, "first dispatch failed"
    r = client.post(f"{BASE_URL}/api/signals/{SIGNAL_ID}/dispatch", timeout=120)
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    job = data.get("job") or {}
    print("REPEAT:", data.get("ok"), data.get("deduplicated"), job.get("status"))
    assert data["ok"] is True
    assert data.get("deduplicated") is True, data
    assert job.get("status") == "accepted"
    assert job.get("remote_job_id") == STATE["remote_job_id"]
    assert job.get("job_id") == STATE["job_id"]


# --- job-status ---
def test_03_job_status_accepted(client):
    r = client.get(f"{BASE_URL}/api/signals/{SIGNAL_ID}/job-status", timeout=60)
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    job = data.get("job") or data
    print("JOB-STATUS:", job.get("status"), job.get("remote_job_id"))
    assert job.get("status") == "accepted", job
    assert job.get("remote_job_id") == STATE.get("remote_job_id")
    assert "_id" not in job  # no raw mongo ObjectId leaked


# --- refresh against live staging GET ---
def test_04_refresh_hits_live_staging(client):
    job_id = STATE.get("job_id")
    assert job_id
    r = client.post(f"{BASE_URL}/api/course-jobs/{job_id}/refresh", timeout=90)
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    print("REFRESH:", data.get("ok"), data.get("status_code"), data.get("error"),
          (data.get("job") or {}).get("status"))
    assert data.get("status_code") == 200, data
    assert data.get("ok") is True, data
    assert (data.get("job") or {}).get("status") == "accepted", data


# --- no 401 anywhere in DB/job record ---
def test_05_no_401_in_job_record(client):
    r = client.get(f"{BASE_URL}/api/signals/{SIGNAL_ID}/job-status", timeout=60)
    job = r.json().get("job") or {}
    assert job.get("http_status") == 202, job
    assert job.get("status") != "failed"
    assert not job.get("error")
    assert not job.get("last_check_error")
    blob = (job.get("response_preview") or "") + str(job.get("error"))
    assert "Invalid signature" not in blob
    assert "Signature rejected" not in blob


# --- truly fresh dispatch: clear Radar-side job for the target signal, re-sign, re-post ---
def test_06_fresh_dispatch_after_clearing_signal_job(client):
    import asyncio

    from motor.motor_asyncio import AsyncIOMotorClient

    async def clear():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        res = await db.course_jobs.delete_many({"signal_id": SIGNAL_ID})
        c.close()
        return res.deleted_count

    backend_env = dotenv_values("/app/backend/.env")
    os.environ.setdefault("MONGO_URL", backend_env["MONGO_URL"])
    os.environ.setdefault("DB_NAME", backend_env["DB_NAME"])
    deleted = asyncio.run(clear())
    print("cleared course_jobs rows:", deleted)

    r = client.post(f"{BASE_URL}/api/signals/{SIGNAL_ID}/dispatch", timeout=120)
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    job = data.get("job") or {}
    print("FRESH DISPATCH:", data.get("ok"), data.get("deduplicated"),
          data.get("status_code"), job.get("status"), job.get("http_status"),
          job.get("remote_job_id"), data.get("error"), data.get("hint"))
    assert data.get("deduplicated") is False, data
    assert data.get("status_code") == 202, data
    assert data["ok"] is True, data
    assert job.get("status") == "accepted"
    assert job.get("http_status") == 202
    assert job.get("remote_job_id")
    assert job.get("status_url")
    assert not job.get("error")
