"""LearnForge v2 dispatch client.

POSTs a signed CourseBriefV2 to LEARNFORGE_COURSE_JOBS_URL (intended:
LearnForge /api/course-generation-jobs). LearnForge owns all course
generation; this client only dispatches briefs and tracks job status.

Guarantees:
- Never creates modules/lessons/quizzes/syllabus content.
- Never falls back to the legacy v1 modules webhook.
- Never logs the HMAC secret or the full payload.
- Failures are recorded honestly (a 404/timeout is a `failed` job, never
  `accepted` or `ready`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from services.course_brief import assert_no_content_fields, build_course_brief
from services.publisher import sign_payload

logger = logging.getLogger(__name__)

JOB_STATES = ("accepted", "queued", "generating", "reviewing", "ready", "failed")
MAX_ATTEMPTS = 3
BACKOFF_S = (1.0, 2.0, 4.0)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs_url() -> Optional[str]:
    url = (os.environ.get("LEARNFORGE_COURSE_JOBS_URL") or "").strip()
    return url or None


def _secret() -> Optional[str]:
    s = (os.environ.get("LEARNFORGE_WEBHOOK_SECRET") or "").strip()
    return s or None


def _secret_fingerprint() -> tuple[str, int]:
    """Non-reversible fingerprint (sha256 prefix) + length of the signing
    secret. Safe to log/surface — never exposes the value."""
    s = _secret()
    if not s:
        return ("unset", 0)
    return (hashlib.sha256(s.encode()).hexdigest()[:8], len(s))


def _remote_expected_fingerprint(resp) -> Optional[str]:
    """Best-effort: pull an expected-secret fingerprint from the receiver's
    error body if it returns one (keys: expected_fp / secret_fp / fingerprint)."""
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    for k in ("expected_fp", "secret_fp", "fingerprint", "expected_secret_fp"):
        v = data.get(k)
        if v:
            return str(v)
    return None


def _client_factory(timeout: float = 20.0) -> httpx.AsyncClient:
    """Seam for tests — override to inject httpx.MockTransport."""
    return httpx.AsyncClient(timeout=timeout)


def _build_headers(body_bytes: bytes, idempotency_key: str, event: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "LearnForge-OpportunityRadar/2.0",
        "X-Radar-Event": event,
        "X-Radar-Schema-Version": "2.0",
        "X-Radar-Idempotency-Key": idempotency_key,
    }
    secret = _secret()
    if secret:
        sig = sign_payload(secret, body_bytes)
        headers["X-Radar-Signature"] = sig
        headers["X-Radar-Signature-Algorithm"] = "hmac-sha256"
    return headers


async def _save_job(db, job: dict) -> None:
    await db.course_jobs.update_one(
        {"job_id": job["job_id"]}, {"$set": job}, upsert=True
    )


async def _mirror_to_signal(db, job: dict) -> None:
    await db.signals.update_one(
        {"id": job["signal_id"]},
        {
            "$set": {
                "course_job_id": job["job_id"],
                "course_job_status": job.get("status"),
                "course_job_public_url": job.get("public_course_url"),
                "course_job_dispatched_at": job.get("dispatched_at"),
                "course_job_error": job.get("error"),
                "updated_at": _now(),
            }
        },
    )


async def get_job_for_signal(db, signal_id: str) -> Optional[dict]:
    return await db.course_jobs.find_one(
        {"signal_id": signal_id}, {"_id": 0}, sort=[("dispatched_at", -1)]
    )


async def dispatch_brief(db, signal_id: str) -> dict:
    """Dispatch the CourseBriefV2 for a signal to LearnForge."""
    signal = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not signal:
        raise ValueError("Signal not found")

    brief = build_course_brief(signal)
    payload = brief.model_dump()
    assert_no_content_fields(payload)

    # Idempotency: an existing non-failed job for identical brief content is
    # returned as-is — we never double-dispatch.
    existing = await db.course_jobs.find_one(
        {"idempotency_key": brief.idempotency_key, "status": {"$ne": "failed"}},
        {"_id": 0},
    )
    if existing:
        return {
            "ok": True,
            "deduplicated": True,
            "job": existing,
            "brief": payload,
            "status_code": None,
            "error": None,
            "hint": "Identical brief already dispatched (idempotency).",
        }

    job = {
        "job_id": str(uuid.uuid4()),
        "signal_id": signal_id,
        "idempotency_key": brief.idempotency_key,
        "status": "failed",
        "remote_job_id": None,
        "status_url": None,
        "public_course_url": None,
        "dispatched_at": _now(),
        "last_checked_at": None,
        "error": None,
        "response_preview": None,
        "attempts": 0,
        "http_status": None,
    }
    result = {
        "ok": False,
        "deduplicated": False,
        "job": None,
        "brief": payload,
        "status_code": None,
        "error": None,
        "hint": None,
    }

    url = _jobs_url()
    if not url:
        # Fail safely — explicitly NO fallback to the legacy v1 webhook.
        job["error"] = "LEARNFORGE_COURSE_JOBS_URL not configured"
        result["error"] = job["error"]
        result["hint"] = (
            "Set LEARNFORGE_COURSE_JOBS_URL in backend/.env to the LearnForge "
            "/api/course-generation-jobs endpoint. No fallback to the legacy "
            "v1 modules webhook is performed."
        )
        await _save_job(db, job)
        await _mirror_to_signal(db, job)
        result["job"] = job
        return result

    body_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    headers = _build_headers(body_bytes, brief.idempotency_key, "course_brief.dispatch")
    # Log metadata only — never the secret, signature, or full payload.
    logger.info(
        "dispatch_brief signal=%s idem=%s body_len=%d",
        signal_id,
        brief.idempotency_key[:12],
        len(body_bytes),
    )

    last_error: Optional[str] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        job["attempts"] = attempt
        try:
            async with _client_factory() as client:
                resp = await client.post(url, content=body_bytes, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(
                "dispatch_brief attempt=%d transport error signal=%s", attempt, signal_id
            )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_S[attempt - 1])
                continue
            break

        job["http_status"] = resp.status_code
        result["status_code"] = resp.status_code
        job["response_preview"] = (resp.text or "")[:300]

        if 200 <= resp.status_code < 300:
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                data = {}
            remote_status = str(data.get("status") or "accepted").lower()
            job["status"] = remote_status if remote_status in JOB_STATES else "accepted"
            job["remote_job_id"] = data.get("job_id") or data.get("id")
            job["status_url"] = data.get("status_url")
            job["public_course_url"] = data.get("public_course_url") or data.get(
                "course_url"
            )
            if job["status"] == "failed":
                job["error"] = data.get("error") or "LearnForge reported failed"
                result["error"] = job["error"]
            result["ok"] = job["status"] != "failed"
            last_error = None
            break

        last_error = f"HTTP {resp.status_code}"
        if resp.status_code >= 500 and attempt < MAX_ATTEMPTS:
            await asyncio.sleep(BACKOFF_S[attempt - 1])
            continue
        if resp.status_code == 404:
            result["hint"] = (
                "LearnForge /api/course-generation-jobs is not deployed yet. "
                "Ship the v2 receiver per docs/LEARNFORGE_V2_CONTRACT.md. "
                "No legacy fallback was attempted."
            )
        elif resp.status_code in (401, 403):
            fp, ln = _secret_fingerprint()
            remote_fp = _remote_expected_fingerprint(resp)
            parts = [
                f"Signature rejected (HTTP {resp.status_code}). ",
                f"Radar signed with secret_fp={fp} (len={ln}). ",
            ]
            if remote_fp:
                match = "MATCH" if remote_fp == fp else "MISMATCH"
                parts.append(f"LearnForge expected secret_fp={remote_fp} → {match}. ")
            parts.append(
                "If the fingerprints differ, the shared LEARNFORGE_WEBHOOK_SECRET "
                "is out of sync — rotate/align both sides so they match."
            )
            result["hint"] = "".join(parts)
        break

    if not result["ok"]:
        job["status"] = "failed"
        job["error"] = job.get("error") or last_error or "dispatch failed"
        result["error"] = result.get("error") or job["error"]

    await _save_job(db, job)
    await _mirror_to_signal(db, job)
    result["job"] = job
    return result


async def refresh_job(db, job_id: str) -> dict:
    """Query LearnForge for job status and update Radar-side metadata only.

    Never generates content, publishes, or modifies existing courses.
    """
    job = await db.course_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return {"ok": False, "error": "job_not_found", "job": None}

    base = _jobs_url()
    status_url = job.get("status_url")
    if not status_url and base and job.get("remote_job_id"):
        status_url = f"{base.rstrip('/')}/{job['remote_job_id']}"
    job["last_checked_at"] = _now()

    if not status_url:
        job["last_check_error"] = "no status_url — LearnForge has not accepted this job"
        await _save_job(db, job)
        return {"ok": False, "error": job["last_check_error"], "job": job}

    try:
        async with _client_factory(10.0) as client:
            resp = await client.get(
                status_url,
                headers={
                    "User-Agent": "LearnForge-OpportunityRadar/2.0",
                    "X-Radar-Event": "course_job.status",
                },
            )
    except Exception as e:  # noqa: BLE001
        job["last_check_error"] = f"{type(e).__name__}: {e}"
        await _save_job(db, job)
        return {"ok": False, "error": job["last_check_error"], "job": job}

    if not (200 <= resp.status_code < 300):
        job["last_check_error"] = f"HTTP {resp.status_code}"
        await _save_job(db, job)
        return {
            "ok": False,
            "error": job["last_check_error"],
            "status_code": resp.status_code,
            "job": job,
        }

    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        data = {}
    new_status = str(data.get("status") or "").lower()
    if new_status in JOB_STATES:
        job["status"] = new_status
        job["last_check_error"] = None
        if data.get("public_course_url"):
            job["public_course_url"] = data["public_course_url"]
        if new_status == "failed":
            job["error"] = data.get("error") or "LearnForge reported failed"
    else:
        # Unknown state — keep the previous status, record the anomaly.
        job["last_check_error"] = f"unknown status '{new_status or 'missing'}' from LearnForge"

    await _save_job(db, job)
    await _mirror_to_signal(db, job)
    return {
        "ok": new_status in JOB_STATES,
        "error": job.get("last_check_error"),
        "status_code": resp.status_code,
        "job": job,
    }
