"""Claude Sonnet 4.5-powered enrichment + syllabus generation.

All LLM calls go through emergentintegrations.LlmChat with the Emergent
Universal Key (EMERGENT_LLM_KEY). The model is locked to
``claude-sonnet-4-5-20250929`` per architect's directive.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"


def _api_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY missing from environment")
    return key


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of the model's response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    # Find the outermost {...}
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in response: {raw[:200]}")
    return json.loads(raw[start : end + 1])


async def enrich_signal(
    event_title: str,
    registration_count: int,
    when: Optional[str] = None,
    coach: Optional[str] = None,
    rating: Optional[float] = None,
) -> dict:
    """Classify a raw Leland event into LearnForge signal metadata.

    Returns dict with: category, priority_score (0-100), notes,
    suggested_lead_magnet_title, suggested_paid_offer_title.
    """
    system = (
        "You are a course-strategy analyst for LearnForge. You convert raw "
        "Leland event signals into structured course-conversion metadata. "
        "Reply with a single JSON object, no prose."
    )
    user = (
        "Classify this Leland free-event signal and produce conversion metadata.\n\n"
        f"Event title: {event_title}\n"
        f"Registrations: {registration_count}\n"
        f"When: {when or 'unknown'}\n"
        f"Coach: {coach or 'unknown'} (rating {rating or 'n/a'})\n\n"
        "Categories to pick ONE from: "
        "Consulting, MBA Admissions, Product Management, Finance, "
        "Medical Admissions, Law, Tech Careers, Career Switching, "
        "GRE/GMAT, College Admissions, AI/ML, Leadership, Other.\n\n"
        "priority_score rubric (0-100): "
        "registrations 0-50 → 40-55, "
        "50-150 → 55-70, "
        "150-500 → 70-82, "
        "500-1500 → 82-92, "
        "1500+ → 92-99. "
        "Boost +3 if title implies imminent deadline / cohort, -3 if generic AMA.\n\n"
        "Output JSON shape:\n"
        "{\n"
        '  "category": "...",\n'
        '  "priority_score": <int>,\n'
        '  "notes": "<one-sentence demand signal>",\n'
        '  "suggested_lead_magnet_title": "<short, outcome-oriented free asset title>",\n'
        '  "suggested_paid_offer_title": "ForgeCore: <short product name>"\n'
        "}\n"
    )
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"enrich-{uuid.uuid4()}",
        system_message=system,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)
    response = await chat.send_message(UserMessage(text=user))
    try:
        data = _extract_json(response)
    except Exception as e:  # noqa: BLE001
        logger.exception("enrich_signal parse fail: %s | raw=%s", e, response[:300])
        # Reasonable fallback so the pipeline never blocks ingestion
        return {
            "category": "Other",
            "priority_score": min(99, max(40, 40 + registration_count // 30)),
            "notes": f"Auto-classified fallback. Raw signal: {registration_count} registrations.",
            "suggested_lead_magnet_title": f"{event_title.split(':')[0][:48]} — Field Guide",
            "suggested_paid_offer_title": f"ForgeCore: {event_title.split(':')[0][:42]}",
        }
    # Coerce types
    data["priority_score"] = int(data.get("priority_score") or 60)
    data["priority_score"] = max(0, min(100, data["priority_score"]))
    data["category"] = (data.get("category") or "Other").strip()
    return data


async def generate_syllabus_ai(signal: dict) -> list[dict]:
    """Generate a structured LearnForge course syllabus with Claude Sonnet 4.5."""
    title = (
        signal.get("paid_offer_title")
        or signal.get("event_title")
        or "LearnForge Course"
    )
    category = signal.get("category", "Career")
    reg = signal.get("registration_count", 0)
    paid_desc = signal.get("paid_offer_description") or ""
    notes = signal.get("notes") or ""

    system = (
        "You are LearnForge's lead curriculum architect. You design tight, "
        "high-fidelity mini-courses (ForgeCore) for ambitious professionals. "
        "Every module ships a tangible artifact, not just lecture content. "
        "Reply with a single JSON object, no prose."
    )
    user = (
        f"Design a 6-module ForgeCore syllabus for the course titled \"{title}\".\n\n"
        f"Domain: {category}\n"
        f"Source-of-demand: {reg:,} Leland free-event registrations.\n"
        f"Positioning: {paid_desc or 'professional outcome-focused mini-course'}\n"
        f"Architect notes: {notes}\n\n"
        "Each module must include:\n"
        "  - index (1-6)\n"
        "  - title (short, action-oriented)\n"
        "  - summary (1-2 sentences)\n"
        "  - learning_objectives (array of 2-3 strings)\n"
        "  - artifact (the tangible thing the learner produces)\n"
        "  - duration_min (int, realistic, 30-90)\n\n"
        "Output JSON shape:\n"
        "{\n"
        '  "modules": [\n'
        '    {"index":1,"title":"...","summary":"...",\n'
        '     "learning_objectives":["..."],"artifact":"...","duration_min":45},\n'
        "    ... 6 total ...\n"
        "  ]\n"
        "}\n"
    )
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"syllabus-{signal.get('id', uuid.uuid4())}",
        system_message=system,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)
    response = await chat.send_message(UserMessage(text=user))
    try:
        data = _extract_json(response)
        modules = data.get("modules") or []
        # Defensive coercion
        cleaned = []
        for i, m in enumerate(modules, start=1):
            cleaned.append(
                {
                    "index": int(m.get("index") or i),
                    "title": str(m.get("title") or f"Module {i}")[:140],
                    "summary": str(m.get("summary") or "")[:400],
                    "learning_objectives": [
                        str(x)[:160] for x in (m.get("learning_objectives") or [])
                    ][:4],
                    "artifact": str(m.get("artifact") or "")[:200],
                    "duration_min": int(m.get("duration_min") or 45),
                }
            )
        return cleaned or _fallback_modules(title, category)
    except Exception as e:  # noqa: BLE001
        logger.exception("generate_syllabus_ai parse fail: %s | raw=%s", e, response[:400])
        return _fallback_modules(title, category)


def _fallback_modules(title: str, category: str) -> list[dict]:
    base = [
        ("Foundations & Market Context", "Why this skill, who is hiring, and the signal data."),
        ("Frameworks & Mental Models", f"Operating principles used by top performers in {category}."),
        ("Tactical Playbook", f"Step-by-step execution. Templates and scripts for {category}."),
        ("Live Reps & Simulations", "Guided practice with feedback loops."),
        ("Portfolio Artifact", f"Ship a portfolio-grade artifact tied to '{title}'."),
        ("Launch & 30/60/90", "Post-course execution roadmap and outcomes tracking."),
    ]
    return [
        {
            "index": i + 1,
            "title": t,
            "summary": s,
            "learning_objectives": [f"Master {category} fundamentals", "Apply to a real scenario"],
            "artifact": "Worksheet / deliverable",
            "duration_min": 45 + i * 5,
        }
        for i, (t, s) in enumerate(base)
    ]
