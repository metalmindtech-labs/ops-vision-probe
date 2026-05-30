"""Ingestion pipeline.

Wires Leland scraper output → AI signal enrichment → MongoDB upsert.
Tracks a per-run summary row in ``ingestion_runs`` for the UI.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from services.scraper import (
    parse_events_from_html,
    scrape_live,
    ScrapedEvent,
)
from services.ai import enrich_signal
from services.alerts import is_strike, record_strike

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-") or "course"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ingest_events(
    db, events: List[ScrapedEvent], trigger: str
) -> dict:
    """Upsert scraped events into the signals collection, enriching new ones."""
    created = 0
    updated = 0
    skipped = 0
    errors: List[str] = []
    run_id = str(uuid.uuid4())

    for ev in events:
        try:
            existing = await db.signals.find_one(
                {"event_title": ev.event_title}, {"_id": 0}
            )
            if existing:
                old_count = existing.get("registration_count", 0) or 0
                new_count = max(old_count, ev.registration_count)
                patch = {
                    "registration_count": new_count,
                    "source_url": existing.get("source_url") or ev.source,
                    "updated_at": _now(),
                    "last_seen_at": _now(),
                }
                # Bump priority slightly if registrations grew >10%
                if ev.registration_count > old_count * 1.1 and old_count > 0:
                    patch["priority_score"] = min(
                        100, (existing.get("priority_score") or 60) + 2
                    )
                await db.signals.update_one(
                    {"event_title": ev.event_title}, {"$set": patch}
                )
                # Strike detection: surge alert
                if is_strike(old_count, ev.registration_count):
                    await record_strike(
                        db,
                        signal_id=existing.get("id"),
                        signal_title=ev.event_title,
                        prev_count=old_count,
                        new_count=ev.registration_count,
                        category=existing.get("category", ""),
                        priority_score=patch.get(
                            "priority_score",
                            existing.get("priority_score") or 0,
                        ),
                    )
                updated += 1
                continue

            # New signal — enrich via Claude
            enrich = await enrich_signal(
                event_title=ev.event_title,
                registration_count=ev.registration_count,
                when=ev.when,
                coach=ev.coach,
                rating=ev.rating,
            )
            doc = {
                "id": str(uuid.uuid4()),
                "event_title": ev.event_title,
                "category": enrich["category"],
                "registration_count": ev.registration_count,
                "priority_score": enrich["priority_score"],
                "source_url": ev.source,
                "notes": enrich.get("notes") or "",
                "lead_magnet_title": enrich.get("suggested_lead_magnet_title") or "",
                "lead_magnet_description": "",
                "lead_magnet_slug": _slugify(
                    enrich.get("suggested_lead_magnet_title") or ev.event_title
                ),
                "paid_offer_title": enrich.get("suggested_paid_offer_title") or "",
                "paid_offer_description": "",
                "paid_offer_price": None,
                "paid_offer_slug": _slugify(
                    enrich.get("suggested_paid_offer_title") or ev.event_title
                ),
                "cta_headline": "",
                "cta_subtext": "",
                "status": "tracked",
                "syllabus_generated": False,
                "syllabus_modules": [],
                "ingested_by": trigger,
                "coach": ev.coach,
                "event_when": ev.when,
                "created_at": _now(),
                "updated_at": _now(),
                "last_seen_at": _now(),
            }
            await db.signals.insert_one(doc)
            created += 1
        except Exception as e:  # noqa: BLE001
            logger.exception("ingest error for %s: %s", ev.event_title, e)
            errors.append(f"{ev.event_title}: {type(e).__name__}")

    skipped = max(0, len(events) - created - updated - len(errors))
    summary = {
        "id": run_id,
        "trigger": trigger,
        "discovered": len(events),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "ran_at": _now(),
    }
    await db.ingestion_runs.insert_one(dict(summary))
    summary.pop("_id", None)
    return summary


async def run_scrape(db, trigger: str = "manual") -> dict:
    events = await scrape_live()
    return await ingest_events(db, events, trigger=trigger)


async def ingest_html(db, html: str, trigger: str = "manual-paste") -> dict:
    events = parse_events_from_html(html)
    return await ingest_events(db, events, trigger=trigger)


async def latest_run(db) -> Optional[dict]:
    doc = await db.ingestion_runs.find_one(
        {}, {"_id": 0}, sort=[("ran_at", -1)]
    )
    return doc
