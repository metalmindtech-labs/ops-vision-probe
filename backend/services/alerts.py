"""Diff-aware demand-surge alerts ("strikes").

When the scraper updates an existing signal and the registration count
jumps by more than the configured threshold (default 20%), an alert is
recorded so the Architect can see accelerating demand at a glance.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

STRIKE_THRESHOLD = float(os.environ.get("STRIKE_THRESHOLD_PCT", "20")) / 100.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_strike(prev_count: int, new_count: int) -> bool:
    if prev_count <= 0:
        return new_count >= 50  # cold-start surge: any large first read
    return (new_count - prev_count) / max(prev_count, 1) >= STRIKE_THRESHOLD


async def record_strike(
    db,
    signal_id: str,
    signal_title: str,
    prev_count: int,
    new_count: int,
) -> dict:
    delta = new_count - prev_count
    delta_pct = round(delta / max(prev_count, 1) * 100.0, 1)
    alert = {
        "id": str(uuid.uuid4()),
        "signal_id": signal_id,
        "signal_title": signal_title,
        "prev_count": prev_count,
        "new_count": new_count,
        "delta": delta,
        "delta_pct": delta_pct,
        "detected_at": _now(),
        "acknowledged": False,
        "acknowledged_at": None,
    }
    await db.signal_alerts.insert_one(dict(alert))
    alert.pop("_id", None)
    return alert


async def list_alerts(db, only_unack: bool = True, limit: int = 50) -> list[dict]:
    q: dict = {}
    if only_unack:
        q["acknowledged"] = False
    docs = (
        await db.signal_alerts.find(q, {"_id": 0})
        .sort("detected_at", -1)
        .to_list(min(max(limit, 1), 200))
    )
    return docs


async def ack_alert(db, alert_id: str) -> Optional[dict]:
    res = await db.signal_alerts.update_one(
        {"id": alert_id},
        {"$set": {"acknowledged": True, "acknowledged_at": _now()}},
    )
    if res.matched_count == 0:
        return None
    return await db.signal_alerts.find_one({"id": alert_id}, {"_id": 0})


async def ack_all(db) -> int:
    res = await db.signal_alerts.update_many(
        {"acknowledged": False},
        {"$set": {"acknowledged": True, "acknowledged_at": _now()}},
    )
    return res.modified_count
