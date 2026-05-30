"""Time-series history for signals (the "velocity chart" data source).

Every scrape persists a real snapshot row into ``signal_history``. We also
take a full-catalog snapshot on every scheduled run so every tracked
signal gets a data point at the 12h cadence — even if the live listing
didn't return it that round.

The chart sharpens over time as real snapshots accumulate. Any synthetic
backfill is opt-in via ``backfill_synthetic`` and now defaults off.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_history(
    db,
    signal_id: str,
    registration_count: int,
    priority_score: int = 0,
    captured_at: str | None = None,
) -> None:
    await db.signal_history.insert_one(
        {
            "signal_id": signal_id,
            "registration_count": int(registration_count or 0),
            "priority_score": int(priority_score or 0),
            "captured_at": captured_at or _now_iso(),
        }
    )


async def history_count(db) -> int:
    return await db.signal_history.count_documents({})


async def purge_synthetic(db) -> int:
    """Remove any rows seeded as synthetic backfill (one-time cleanup)."""
    res = await db.signal_history.delete_many({"synthetic": True})
    return res.deleted_count


async def snapshot_all_signals(db, source: str = "manual") -> dict:
    """Insert a history row for every currently-tracked signal.

    Called from the scheduled scrape job (so every signal has a fresh
    data point every 12h regardless of whether Leland returned it) and
    once at boot if the collection is empty.
    """
    signals = await db.signals.find(
        {}, {"_id": 0, "id": 1, "registration_count": 1, "priority_score": 1}
    ).to_list(2000)
    captured_at = _now_iso()
    if not signals:
        return {"snapshotted": 0, "source": source, "captured_at": captured_at}
    docs = [
        {
            "signal_id": s["id"],
            "registration_count": int(s.get("registration_count") or 0),
            "priority_score": int(s.get("priority_score") or 0),
            "captured_at": captured_at,
            "source": source,
        }
        for s in signals
    ]
    await db.signal_history.insert_many(docs)
    return {"snapshotted": len(docs), "source": source, "captured_at": captured_at}


async def get_velocity(
    db,
    signal_ids: Iterable[str] | None = None,
    hours: int = 24,
    limit_signals: int = 12,
) -> dict:
    """Return time-series snapshots + strike attribution for top-N signals."""
    q: dict = {}
    if signal_ids:
        q["id"] = {"$in": list(signal_ids)}
    cursor = db.signals.find(q, {"_id": 0}).sort("priority_score", -1)
    signals = await cursor.to_list(min(limit_signals, 50))

    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff = cutoff_dt.isoformat()

    series: list[dict] = []
    for s in signals:
        rows = await db.signal_history.find(
            {"signal_id": s["id"], "captured_at": {"$gte": cutoff}},
            {"_id": 0, "captured_at": 1, "registration_count": 1},
        ).sort("captured_at", 1).to_list(2000)
        points = [
            {"t": r["captured_at"], "v": r["registration_count"]}
            for r in rows
        ]

        # Strike attribution: alerts that fired in this window
        alerts = await db.signal_alerts.find(
            {"signal_id": s["id"], "detected_at": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("detected_at", 1).to_list(200)
        strikes = [
            {
                "alert_id": a["id"],
                "t": a["detected_at"],
                "v": a["new_count"],
                "prev_count": a["prev_count"],
                "delta_pct": a["delta_pct"],
                "tier": (
                    "breakout"
                    if a["delta_pct"] >= 100
                    else "surge"
                    if a["delta_pct"] >= 50
                    else "strike"
                ),
            }
            for a in alerts
        ]

        series.append(
            {
                "signal_id": s["id"],
                "title": s.get("event_title", ""),
                "category": s.get("category", ""),
                "priority_score": s.get("priority_score") or 0,
                "current": s.get("registration_count") or 0,
                "points": points,
                "strikes": strikes,
            }
        )
    return {"window_hours": hours, "series": series}


async def backfill_synthetic(db, hours: int = 24, step_minutes: int = 30) -> dict:
    """Opt-in: seed synthetic random-walk history for empty signals.

    DISABLED in normal operation — call only via dev/debug. Kept here so
    the function reference in old code paths doesn't break.
    """
    return {"seeded": 0, "skipped": -1, "disabled": True}
