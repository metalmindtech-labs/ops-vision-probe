"""Publish a converted signal to LearnForge via webhook.

Builds a clean course-publish payload and POSTs it to the configured
LEARNFORGE_WEBHOOK_URL. Tracks per-signal publish status in Mongo so the
UI can show the live state at a glance.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_base() -> str:
    return os.environ.get(
        "LEARNFORGE_PUBLIC_BASE", "https://learnforge-core.vercel.app"
    ).rstrip("/")


def _webhook_url() -> Optional[str]:
    url = (os.environ.get("LEARNFORGE_WEBHOOK_URL") or "").strip()
    return url or None


def _signup_url(slug: Optional[str], tier: str) -> str:
    """All public-facing enrollment CTAs land on /signup (no /en/, no deep
    course/scroll routes — those 404 on the live LearnForge deployment).
    The slug is preserved as ?course=<slug>&tier=<tier>&ref=radar so
    LearnForge can attribute and route after sign-up.
    """
    base = f"{_public_base()}/signup"
    if not slug:
        return base
    from urllib.parse import urlencode

    qs = urlencode({"course": slug, "ref": "radar", "tier": tier})
    return f"{base}?{qs}"


def public_paid_url(slug: str) -> str:
    return _signup_url(slug, tier="forgecore")


def public_free_url(slug: str) -> str:
    return _signup_url(slug, tier="free")


def build_payload(signal: dict) -> dict:
    """Stable webhook contract for downstream LearnForge consumers."""
    paid_slug = signal.get("paid_offer_slug") or signal.get("lead_magnet_slug")
    free_slug = signal.get("lead_magnet_slug")
    return {
        "event": "course.publish",
        "signal_id": signal.get("id"),
        "published_at": _now(),
        "course": {
            "slug": paid_slug,
            "title": signal.get("paid_offer_title") or signal.get("event_title"),
            "category": signal.get("category"),
            "summary": signal.get("paid_offer_description") or "",
            "price_usd": signal.get("paid_offer_price"),
            "lead_magnet": {
                "title": signal.get("lead_magnet_title") or "",
                "description": signal.get("lead_magnet_description") or "",
                "slug": free_slug,
                "url": public_free_url(free_slug) if free_slug else None,
            },
            "cta": {
                "headline": signal.get("cta_headline") or "",
                "subtext": signal.get("cta_subtext") or "",
                "free_url": public_free_url(free_slug) if free_slug else None,
                "paid_url": public_paid_url(paid_slug) if paid_slug else None,
            },
            "syllabus": {
                "modules": signal.get("syllabus_modules") or [],
            },
            "demand": {
                "registration_count": signal.get("registration_count") or 0,
                "priority_score": signal.get("priority_score") or 0,
                "source_url": signal.get("source_url"),
            },
        },
    }


async def publish_signal(db, signal_id: str) -> dict:
    """POST the signal payload to the LearnForge webhook + persist result."""
    signal = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not signal:
        raise ValueError("Signal not found")

    payload = build_payload(signal)
    url = _webhook_url()
    secret = os.environ.get("LEARNFORGE_WEBHOOK_SECRET") or ""

    result: dict = {
        "ok": False,
        "url": url,
        "status_code": None,
        "response_preview": None,
        "error": None,
        "payload": payload,
    }

    if not url:
        result["error"] = "LEARNFORGE_WEBHOOK_URL not configured"
        await _persist(db, signal_id, payload, status="failed", error=result["error"])
        return result

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "LearnForge-OpportunityRadar/1.0",
        "X-Radar-Event": "course.publish",
    }
    if secret:
        headers["X-Radar-Signature"] = secret

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        result["status_code"] = resp.status_code
        result["response_preview"] = (resp.text or "")[:400]
        result["ok"] = 200 <= resp.status_code < 300
        if not result["ok"]:
            result["error"] = f"HTTP {resp.status_code}"
            # Surface actionable diagnostics for common failure modes so the
            # Architect can see WHY this failed in the UI without grepping logs.
            if resp.status_code == 404:
                result["hint"] = (
                    "The webhook URL returned 404 — the LearnForge `/api/courses` "
                    "route is not deployed yet. Either deploy that route on "
                    "learnforge-core.vercel.app, or point LEARNFORGE_WEBHOOK_URL "
                    "at a working ingest endpoint."
                )
            elif resp.status_code == 401 or resp.status_code == 403:
                result["hint"] = (
                    "Webhook rejected the request — set LEARNFORGE_WEBHOOK_SECRET "
                    "to a value LearnForge will accept on the X-Radar-Signature header."
                )
            elif resp.status_code >= 500:
                result["hint"] = (
                    "LearnForge returned a server error. Inspect the response_preview "
                    "and check the Vercel function logs."
                )
    except httpx.ConnectError as e:
        logger.exception("publish_signal connect error: %s", e)
        result["error"] = f"ConnectError: {e}"
        result["hint"] = (
            "Could not reach the webhook host. Check LEARNFORGE_WEBHOOK_URL and "
            "ensure the LearnForge deployment is live."
        )
    except httpx.TimeoutException as e:
        logger.exception("publish_signal timeout: %s", e)
        result["error"] = f"Timeout: {e}"
        result["hint"] = (
            "The webhook did not respond within 20s. LearnForge function may be "
            "cold-starting; retry will run automatically."
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("publish_signal http error: %s", e)
        result["error"] = f"{type(e).__name__}: {e}"

    status = "published" if result["ok"] else "failed"
    await _persist(
        db,
        signal_id,
        payload,
        status=status,
        error=result["error"],
        status_code=result["status_code"],
        response_preview=result.get("response_preview"),
        hint=result.get("hint"),
        url=result.get("url"),
    )
    return result


async def _persist(
    db,
    signal_id: str,
    payload: dict,
    status: str,
    error: Optional[str] = None,
    status_code: Optional[int] = None,
    response_preview: Optional[str] = None,
    hint: Optional[str] = None,
    url: Optional[str] = None,
) -> None:
    paid_url = payload["course"]["cta"]["paid_url"]
    existing = await db.signals.find_one({"id": signal_id}, {"_id": 0}) or {}
    retry_count = existing.get("publish_retry_count") or 0
    updates: dict = {
        "publish_status": status,
        "last_published_at": _now() if status == "published" else None,
        "last_publish_error": error,
        "last_publish_status_code": status_code,
        "last_publish_response_preview": response_preview,
        "last_publish_hint": hint,
        "last_publish_at": _now(),
        "last_publish_webhook_url": url,
        "published_to_url": paid_url,
        "updated_at": _now(),
    }
    if status == "published":
        updates["status"] = "live"
        updates["publish_retry_count"] = 0
        updates["publish_next_retry_at"] = None
    else:
        new_retry = min(retry_count + 1, 5)
        # Exponential backoff: 2,4,8,16,32 minutes
        from datetime import timedelta

        delay = timedelta(minutes=2 ** new_retry)
        updates["publish_retry_count"] = new_retry
        updates["publish_next_retry_at"] = (
            datetime.now(timezone.utc) + delay
        ).isoformat() if new_retry < 5 else None
    await db.signals.update_one({"id": signal_id}, {"$set": updates})
    await db.publish_log.insert_one(
        {
            "signal_id": signal_id,
            "status": status,
            "error": error,
            "status_code": status_code,
            "hint": hint,
            "response_preview": response_preview,
            "url": url or paid_url,
            "at": _now(),
        }
    )


async def republish_all_live(db) -> dict:
    """Republish every signal that has a syllabus generated.

    Used as a "hot-reload" for the LearnForge catalog after schema/prompt
    changes — re-fires the webhook for every converted course in one strike.
    """
    cursor = db.signals.find(
        {"syllabus_generated": True},
        {"_id": 0},
    )
    docs = await cursor.to_list(1000)
    results: list[dict] = []
    ok_count = 0
    fail_count = 0
    for d in docs:
        try:
            r = await publish_signal(db, d["id"])
            results.append(
                {
                    "signal_id": d["id"],
                    "title": d.get("event_title"),
                    "ok": r.get("ok"),
                    "status_code": r.get("status_code"),
                    "error": r.get("error"),
                }
            )
            if r.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        except Exception as e:  # noqa: BLE001
            fail_count += 1
            results.append(
                {
                    "signal_id": d["id"],
                    "title": d.get("event_title"),
                    "ok": False,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
    return {
        "attempted": len(docs),
        "ok": ok_count,
        "failed": fail_count,
        "results": results,
        "ran_at": _now(),
    }


async def retry_pending(db) -> dict:
    """Retry signals whose publish failed and whose backoff window has elapsed."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.signals.find(
        {
            "publish_status": "failed",
            "publish_retry_count": {"$lt": 5},
            "publish_next_retry_at": {"$lte": now, "$ne": None},
        },
        {"_id": 0},
    )
    docs = await cursor.to_list(100)
    ok = 0
    fail = 0
    for d in docs:
        r = await publish_signal(db, d["id"])
        if r.get("ok"):
            ok += 1
        else:
            fail += 1
    return {"attempted": len(docs), "ok": ok, "failed": fail, "ran_at": _now()}



async def reconcile_with_learnforge(db) -> dict:
    """Two-way sync probe between Radar and LearnForge.

    1. Probes the LearnForge endpoint (GET) so we know if the receiver is
       even deployed.
    2. Pulls the locally-known publish state for every signal with a
       generated syllabus.
    3. Computes drift — what should be live on LearnForge but is in a
       `failed`/`pending` state on the Radar side.

    Used by the Sync button to give the Architect a single-glance view of
    catalog drift between the two systems.
    """
    webhook = _webhook_url() or "https://learnforge-core.vercel.app/api/courses"
    probe: dict = {"url": webhook, "reachable": False, "status_code": None, "error": None, "service": None}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(webhook, headers={"User-Agent": "LearnForge-OpportunityRadar/1.0"})
        probe["status_code"] = resp.status_code
        probe["reachable"] = 200 <= resp.status_code < 300
        if probe["reachable"]:
            try:
                body = resp.json()
                probe["service"] = body.get("service")
            except Exception:  # noqa: BLE001
                probe["service"] = None
        else:
            probe["error"] = f"HTTP {resp.status_code}"
    except httpx.ConnectError as e:
        probe["error"] = f"ConnectError: {e}"
    except httpx.TimeoutException as e:
        probe["error"] = f"Timeout: {e}"
    except Exception as e:  # noqa: BLE001
        probe["error"] = f"{type(e).__name__}: {e}"

    docs = await db.signals.find(
        {"syllabus_generated": True},
        {
            "_id": 0,
            "id": 1,
            "event_title": 1,
            "publish_status": 1,
            "last_publish_status_code": 1,
            "last_publish_error": 1,
            "last_publish_hint": 1,
            "publish_retry_count": 1,
            "publish_next_retry_at": 1,
            "last_published_at": 1,
        },
    ).to_list(1000)

    published = [d for d in docs if d.get("publish_status") == "published"]
    failed = [d for d in docs if d.get("publish_status") == "failed"]
    pending = [
        d for d in docs if d.get("publish_status") not in {"published", "failed"}
    ]

    return {
        "ran_at": _now(),
        "learnforge_probe": probe,
        "totals": {
            "syllabus_generated": len(docs),
            "published": len(published),
            "failed": len(failed),
            "pending": len(pending),
        },
        "drift": {
            "count": len(failed) + len(pending),
            "failed_signals": [
                {
                    "id": d["id"],
                    "title": d.get("event_title"),
                    "status_code": d.get("last_publish_status_code"),
                    "error": d.get("last_publish_error"),
                    "hint": d.get("last_publish_hint"),
                    "retry_count": d.get("publish_retry_count", 0),
                    "next_retry_at": d.get("publish_next_retry_at"),
                }
                for d in failed[:25]
            ],
            "pending_signals": [
                {"id": d["id"], "title": d.get("event_title")} for d in pending[:25]
            ],
        },
    }


async def get_publish_history(db, signal_id: str, limit: int = 10) -> list[dict]:
    """Last N publish attempts for a signal, newest first."""
    cursor = (
        db.publish_log.find({"signal_id": signal_id}, {"_id": 0})
        .sort("at", -1)
        .limit(limit)
    )
    return await cursor.to_list(limit)
