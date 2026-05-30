"""Time-series history for signals (the "velocity chart" data source).

Every scraper update inserts a snapshot row into ``signal_history``. The
velocity endpoint aggregates these snapshots so the dashboard can render
a lime-on-charcoal multi-series chart showing the exact moment demand
for a course topic accelerates.

For demo readability we also backfill ~24h of synthetic history for
each existing signal on first boot — a smooth random walk ending at the
current registration count.
"""

from __future__ import annotations

import logging
import random
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


async def get_velocity(
    db,
    signal_ids: Iterable[str] | None = None,
    hours: int = 24,
    limit_signals: int = 12,
) -> dict:
    """Return time-series snapshots for the requested signals.

    Output:
    {
      "window_hours": 24,
      "series": [
         {"signal_id": "...", "title": "...", "category": "...",
          "priority_score": 94, "current": 1228,
          "points": [{"t": "ISO", "v": 100}, ...]}
      ]
    }
    """
    # Pick the signals
    q: dict = {}
    if signal_ids:
        q["id"] = {"$in": list(signal_ids)}
    cursor = db.signals.find(q, {"_id": 0}).sort("priority_score", -1)
    signals = await cursor.to_list(min(limit_signals, 50))

    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).isoformat()

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
        series.append(
            {
                "signal_id": s["id"],
                "title": s.get("event_title", ""),
                "category": s.get("category", ""),
                "priority_score": s.get("priority_score") or 0,
                "current": s.get("registration_count") or 0,
                "points": points,
            }
        )
    return {"window_hours": hours, "series": series}


async def backfill_synthetic(db, hours: int = 24, step_minutes: int = 30) -> dict:
    """Seed a believable random-walk history for any signal that has none.

    Only runs for signals that lack history. Produces a monotone-ish curve
    ending at the current registration_count.
    """
    signals = await db.signals.find({}, {"_id": 0}).to_list(2000)
    seeded = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for s in signals:
        sid = s["id"]
        existing = await db.signal_history.count_documents({"signal_id": sid})
        if existing > 0:
            skipped += 1
            continue

        current = int(s.get("registration_count") or 0)
        priority = int(s.get("priority_score") or 0)
        steps = max(2, (hours * 60) // step_minutes)
        # Start ~70-90% of current so the line trends up to NOW
        start = int(current * random.uniform(0.55, 0.85)) if current else 0
        # Generate monotone-ish points with small dips
        docs: list[dict] = []
        prev = start
        rng = random.Random(hash(sid) & 0xFFFFFFFF)
        for i in range(steps):
            ts = now - timedelta(minutes=step_minutes * (steps - 1 - i))
            # Linear baseline from start → current
            baseline = start + (current - start) * (i / (steps - 1)) if steps > 1 else current
            jitter = rng.uniform(-0.02, 0.04) * max(current, 30)
            val = int(max(prev - 1, baseline + jitter))
            # Final point pinned to current
            if i == steps - 1:
                val = current
            prev = val
            docs.append(
                {
                    "signal_id": sid,
                    "registration_count": val,
                    "priority_score": priority,
                    "captured_at": ts.isoformat(),
                    "synthetic": True,
                }
            )
        if docs:
            await db.signal_history.insert_many(docs)
            seeded += 1
    return {"seeded": seeded, "skipped": skipped}
