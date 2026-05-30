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


def public_paid_url(slug: str) -> str:
    return f"{_public_base()}/en/courses/{slug}"


def public_free_url(slug: str) -> str:
    return f"{_public_base()}/en/scrolls/{slug}"


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
    )
    return result


async def _persist(
    db,
    signal_id: str,
    payload: dict,
    status: str,
    error: Optional[str] = None,
    status_code: Optional[int] = None,
) -> None:
    paid_url = payload["course"]["cta"]["paid_url"]
    updates = {
        "publish_status": status,
        "last_published_at": _now() if status == "published" else None,
        "last_publish_error": error,
        "last_publish_status_code": status_code,
        "published_to_url": paid_url,
        "updated_at": _now(),
    }
    if status == "published":
        # Promote pipeline state to "live"
        updates["status"] = "live"
    await db.signals.update_one({"id": signal_id}, {"$set": updates})
    await db.publish_log.insert_one(
        {
            "signal_id": signal_id,
            "status": status,
            "error": error,
            "status_code": status_code,
            "url": payload["course"]["cta"]["paid_url"],
            "at": _now(),
        }
    )
