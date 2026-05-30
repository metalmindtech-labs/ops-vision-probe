"""Twilio WhatsApp push for high-priority strike signals.

Gated on env config — if TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and
TWILIO_WHATSAPP_TO are not all set, sends are skipped (status='skipped')
and the Radar continues to operate normally. The UI surfaces the
configuration state via /api/integrations/status.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppStatus:
    configured: bool
    from_number: str
    to_number_masked: str
    threshold: int
    reason: str = ""


def _truthy(value: str | None) -> bool:
    return bool((value or "").strip())


def _mask(num: str) -> str:
    if not num:
        return ""
    n = num.replace("whatsapp:", "")
    if len(n) <= 4:
        return "***"
    return f"{n[:3]}…{n[-3:]}"


def get_status() -> WhatsAppStatus:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    to = os.environ.get("TWILIO_WHATSAPP_TO")
    frm = os.environ.get("TWILIO_WHATSAPP_FROM") or "whatsapp:+14155238886"
    try:
        threshold = int(os.environ.get("WHATSAPP_STRIKE_THRESHOLD", "90"))
    except ValueError:
        threshold = 90
    configured = _truthy(sid) and _truthy(tok) and _truthy(to)
    reason = ""
    if not configured:
        missing = [
            n
            for n, v in [
                ("TWILIO_ACCOUNT_SID", sid),
                ("TWILIO_AUTH_TOKEN", tok),
                ("TWILIO_WHATSAPP_TO", to),
            ]
            if not _truthy(v)
        ]
        reason = f"missing: {', '.join(missing)}"
    return WhatsAppStatus(
        configured=configured,
        from_number=frm,
        to_number_masked=_mask(to or ""),
        threshold=threshold,
        reason=reason,
    )


def send_whatsapp(body: str) -> dict:
    """Synchronous Twilio call. Returns {ok, sid, error, skipped}."""
    status = get_status()
    if not status.configured:
        return {
            "ok": False,
            "skipped": True,
            "reason": status.reason,
            "sid": None,
            "error": None,
        }
    try:
        from twilio.rest import Client  # local import (kept optional)

        client = Client(
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"],
        )
        msg = client.messages.create(
            from_=status.from_number,
            to=f"whatsapp:{os.environ['TWILIO_WHATSAPP_TO'].lstrip('whatsapp:')}",
            body=body[:1500],
        )
        return {"ok": True, "skipped": False, "sid": msg.sid, "error": None}
    except Exception as e:  # noqa: BLE001
        logger.exception("WhatsApp send failed: %s", e)
        return {
            "ok": False,
            "skipped": False,
            "sid": None,
            "error": f"{type(e).__name__}: {e}",
        }


def format_strike_message(
    signal_title: str,
    category: str,
    prev_count: int,
    new_count: int,
    delta_pct: float,
    priority_score: int,
    dashboard_url: str | None = None,
) -> str:
    arrow = "🚀" if delta_pct >= 100 else "⚡"
    lines = [
        f"{arrow} *LearnForge Radar — STRIKE*",
        "",
        f"*{signal_title}*",
        f"_{category}_",
        "",
        f"Registrations: {prev_count:,} → *{new_count:,}* ({delta_pct:+.1f}%)",
        f"Priority: {priority_score}/100",
    ]
    if dashboard_url:
        lines.extend(["", f"Open Radar: {dashboard_url}"])
    return "\n".join(lines)
