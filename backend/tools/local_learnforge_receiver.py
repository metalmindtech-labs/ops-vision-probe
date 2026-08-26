"""LOCAL DEMO ONLY — in-sandbox stand-in for LearnForge's /api/course-generation-jobs.

This is NOT the real LearnForge and NOT production. It exists solely to let the
Radar preview show a real 202 'accepted' end-to-end without touching the
learnforge-core repo, secrets, or any deployment. It stores jobs in memory and
generates NO course content — it mirrors the CourseBriefV2 contract only.

Run:  LEARNFORGE_WEBHOOK_SECRET=... uvicorn tools.local_learnforge_receiver:app --port 8099
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import Dict

from fastapi import FastAPI, Request, Response

app = FastAPI(title="LOCAL LearnForge Receiver (DEMO)")

_JOBS: Dict[str, dict] = {}
_BY_IDEM: Dict[str, str] = {}
SUPPORTED_SCHEMA = "2.0"
PUBLIC_BASE = os.environ.get("LOCAL_RECEIVER_BASE", "http://localhost:8099")
FORBIDDEN = {
    "modules", "module", "lessons", "lesson", "quizzes", "quiz", "syllabus",
    "syllabus_modules", "curriculum", "chapters", "units", "lesson_plan",
    "learning_objectives", "course_content",
}


def _secret() -> str:
    return (os.environ.get("LEARNFORGE_WEBHOOK_SECRET") or "").strip()


def _verify(raw: bytes, sig: str | None) -> bool:
    secret = _secret()
    if not secret or not sig:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig.strip().lower())


def _has_forbidden(v) -> str | None:
    if isinstance(v, dict):
        for k, sub in v.items():
            if k in FORBIDDEN:
                return k
            found = _has_forbidden(sub)
            if found:
                return found
    elif isinstance(v, list):
        for item in v:
            found = _has_forbidden(item)
            if found:
                return found
    return None


def _status_url(job_id: str) -> str:
    return f"{PUBLIC_BASE.rstrip('/')}/api/course-generation-jobs/{job_id}"


@app.get("/api/course-generation-jobs")
async def health():
    return {
        "service": "local-learnforge-demo",
        "schema_version": SUPPORTED_SCHEMA,
        "note": "DEMO stand-in — not real LearnForge, generates no content",
    }


@app.post("/api/course-generation-jobs")
async def receive(request: Request):
    raw = await request.body()

    if not _verify(raw, request.headers.get("x-radar-signature")):
        return Response(json.dumps({"error": "invalid_signature"}), status_code=401,
                        media_type="application/json")

    hdr_schema = request.headers.get("x-radar-schema-version")
    if hdr_schema and hdr_schema != SUPPORTED_SCHEMA:
        return Response(json.dumps({"error": "unsupported_schema_version"}),
                        status_code=400, media_type="application/json")

    try:
        payload = json.loads(raw)
    except Exception:
        return Response(json.dumps({"error": "invalid_json"}), status_code=400,
                        media_type="application/json")

    bad = _has_forbidden(payload)
    if bad:
        return Response(json.dumps({"error": "forbidden_content", "detail": bad}),
                        status_code=400, media_type="application/json")

    if payload.get("schema_version") != SUPPORTED_SCHEMA:
        return Response(json.dumps({"error": "unsupported_schema_version"}),
                        status_code=400, media_type="application/json")

    src = payload.get("source") or {}
    if not (src.get("provider") or "").strip() or not (src.get("source_title") or "").strip():
        return Response(json.dumps({"error": "missing_source_attribution"}),
                        status_code=400, media_type="application/json")

    idem = payload.get("idempotency_key") or ""
    if idem in _BY_IDEM:
        jid = _BY_IDEM[idem]
        job = _JOBS[jid]
        return Response(
            json.dumps({"status": job["status"], "job_id": jid,
                        "status_url": _status_url(jid),
                        "public_course_url": job.get("public_course_url"),
                        "deduplicated": True}),
            status_code=200, media_type="application/json")

    jid = f"lf_job_{uuid.uuid4()}"
    _JOBS[jid] = {
        "id": jid, "status": "accepted", "signal_id": payload.get("signal_id"),
        "correlation_id": (payload.get("callback") or {}).get("correlation_id"),
        "public_course_url": None, "error": None,
    }
    _BY_IDEM[idem] = jid
    return Response(
        json.dumps({"status": "accepted", "job_id": jid,
                    "status_url": _status_url(jid), "public_course_url": None}),
        status_code=202, media_type="application/json")


@app.get("/api/course-generation-jobs/{job_id}")
async def status(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        return Response(json.dumps({"error": "job_not_found"}), status_code=404,
                        media_type="application/json")
    return {
        "status": job["status"], "job_id": job_id,
        "signal_id": job.get("signal_id"),
        "correlation_id": job.get("correlation_id"),
        "public_course_url": job.get("public_course_url"), "error": job.get("error"),
    }
