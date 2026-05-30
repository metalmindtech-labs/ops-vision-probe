"""Publish a converted signal to LearnForge via webhook.

Builds a clean course-publish payload and POSTs it to the configured
LEARNFORGE_WEBHOOK_URL. Tracks per-signal publish status in Mongo so the
UI can show the live state at a glance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _webhook_secret() -> Optional[str]:
    s = (os.environ.get("LEARNFORGE_WEBHOOK_SECRET") or "").strip()
    return s or None


def compute_discount_pct(
    current_price: Optional[float], original_price: Optional[float]
) -> Optional[int]:
    """Canonical 'Slam Offer' discount calculation.

    Formula: round(((original - current) / original) * 100)
    Edge cases:
      - either price missing → None
      - original_price <= 0 → None
      - current_price >= original_price → 0
      - current_price < 0 → None (invalid)
    """
    if current_price is None or original_price is None:
        return None
    try:
        cur = float(current_price)
        orig = float(original_price)
    except (TypeError, ValueError):
        return None
    if orig <= 0 or cur < 0:
        return None
    if cur >= orig:
        return 0
    pct = ((orig - cur) / orig) * 100
    return int(round(pct))


def sign_payload(secret: str, body_bytes: bytes) -> str:
    """HMAC-SHA256 of the raw JSON body using the shared secret.

    Returned as lowercase hex (64 chars). The LearnForge receiver computes
    the same HMAC over `await req.text()` and compares with
    `crypto.timingSafeEqual`.
    """
    mac = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256)
    return mac.hexdigest()


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
    """Stable webhook contract for downstream LearnForge consumers.

    LearnForge's Next.js receiver expects flat top-level `title`, `slug`,
    and `modules` (renamed from the previous nested `syllabus.modules`).
    We also keep the rich nested `course` object for full-fidelity
    downstream consumers and our own debug visibility.

    Discount math: `discount_pct = round(((orig - current) / orig) * 100)`.
    Computed server-side so every consumer renders the same number.
    """
    paid_slug = signal.get("paid_offer_slug") or signal.get("lead_magnet_slug")
    free_slug = signal.get("lead_magnet_slug")
    title = signal.get("paid_offer_title") or signal.get("event_title")
    modules = signal.get("syllabus_modules") or []
    hero_image_url = signal.get("hero_image_url")
    price_usd = signal.get("paid_offer_price")
    original_price_usd = signal.get("paid_offer_original_price")
    discount_pct = compute_discount_pct(price_usd, original_price_usd)
    return {
        # ---- Top-level fields LearnForge's receiver validates ----
        "event": "course.publish",
        "signal_id": signal.get("id"),
        "published_at": _now(),
        "source": "radar",
        "title": title,
        "slug": paid_slug,
        "modules": modules,
        "category": signal.get("category"),
        "summary": signal.get("paid_offer_description") or "",
        "price_usd": price_usd,
        "original_price_usd": original_price_usd,
        "discount_pct": discount_pct,
        "registration_count": signal.get("registration_count") or 0,
        "priority_score": signal.get("priority_score") or 0,
        "source_url": signal.get("source_url"),
        "paid_url": public_paid_url(paid_slug) if paid_slug else None,
        "free_url": public_free_url(free_slug) if free_slug else None,
        # Cinematic visuals (Fal Flux.1 Pro · Sovereign Style Sheet)
        "hero_image_url": hero_image_url,
        "visuals": {
            "hero": hero_image_url,
            "model": signal.get("visuals_model"),
            "style": signal.get("visuals_style"),
        },
        # ---- Rich nested course object (full-fidelity, optional) ----
        "course": {
            "slug": paid_slug,
            "title": title,
            "category": signal.get("category"),
            "summary": signal.get("paid_offer_description") or "",
            "price_usd": price_usd,
            "original_price_usd": original_price_usd,
            "discount_pct": discount_pct,
            "hero_image_url": hero_image_url,
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
            # Modules are also surfaced here for backwards compatibility.
            "modules": modules,
            "syllabus": {"modules": modules},
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
    secret = _webhook_secret() or ""

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
    # Canonical body bytes — both POST body and HMAC must be byte-identical
    # for the receiver's signature verification to succeed.
    body_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    if secret:
        signature_hex = sign_payload(secret, body_bytes)
        # LearnForge's Next.js receiver expects BARE lowercase hex (no
        # `sha256=` prefix). We also include the algorithm + a prefixed
        # variant so any receiver implementation can find it.
        headers["X-Radar-Signature"] = signature_hex
        headers["X-Radar-Signature-Hex"] = signature_hex
        headers["X-Radar-Signature-Sha256"] = f"sha256={signature_hex}"
        headers["X-Radar-Signature-Algorithm"] = "hmac-sha256"
        # Log a fingerprint of both secret + signature so the Architect can
        # cross-compare with Vercel logs without leaking the actual secret.
        secret_fp = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8]
        logger.info(
            "publish_signal sig_first6=%s sig_last6=%s secret_fp=%s body_len=%d url=%s",
            signature_hex[:6],
            signature_hex[-6:],
            secret_fp,
            len(body_bytes),
            url,
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, content=body_bytes, headers=headers)
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
                body_lower = (result["response_preview"] or "").lower()
                if "row-level security" in body_lower or "row level security" in body_lower:
                    result["hint"] = (
                        "Supabase RLS policy on the `courses` table is blocking "
                        "the insert. On LearnForge: either use the service-role "
                        "key in the route handler, or add an INSERT policy: "
                        "`CREATE POLICY \"webhook_insert\" ON courses FOR INSERT "
                        "TO service_role WITH CHECK (true);`"
                    )
                elif "supabasekey is required" in body_lower or "supabase url is required" in body_lower or "supabaseurl is required" in body_lower:
                    result["hint"] = (
                        "LearnForge's Supabase client is missing credentials. "
                        "On Vercel, set `SUPABASE_URL` and "
                        "`SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`) "
                        "in the learnforge-core project env, then redeploy. "
                        "The route handler is wired but createClient() is "
                        "throwing before any DB request runs."
                    )
                elif "duplicate key" in body_lower or "already exists" in body_lower:
                    result["hint"] = (
                        "Receiver tried to INSERT instead of UPSERT. Use "
                        "supabase.from('courses').upsert(row, { onConflict: 'slug' })."
                    )
                else:
                    result["hint"] = (
                        "LearnForge returned a server error. Inspect the "
                        "response_preview and check the Vercel function logs."
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
        # 2xx → live. 405 Method Not Allowed → route exists but doesn't
        # accept GET (LearnForge may only implement POST). Treat as reachable.
        probe["reachable"] = (200 <= resp.status_code < 300) or resp.status_code == 405
        if 200 <= resp.status_code < 300:
            try:
                body = resp.json()
                probe["service"] = body.get("service")
            except Exception:  # noqa: BLE001
                probe["service"] = None
        elif resp.status_code == 405:
            probe["service"] = "learnforge-course-publish (POST-only)"
            probe["error"] = "HTTP 405 (route exists, GET not allowed)"
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
