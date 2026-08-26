"""CourseBriefV2 — the v2 contract between Radar and LearnForge.

Canonical ownership: Radar owns demand discovery, evidence, scoring,
audience/problem analysis and commercial HYPOTHESES. LearnForge owns all
syllabus/module/lesson/quiz generation, review and course delivery.

This model therefore contains NO generated educational content — and
rejects it (extra="forbid" + explicit forbidden-key scan).
"""

from __future__ import annotations

import hashlib
import json
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from services.publisher import compute_discount_pct

SCHEMA_VERSION = "2.0"

# Keys that would represent generated educational content. A CourseBriefV2
# payload must never contain any of these at any nesting level.
FORBIDDEN_CONTENT_FIELDS = {
    "modules",
    "module",
    "lessons",
    "lesson",
    "quizzes",
    "quiz",
    "syllabus",
    "syllabus_modules",
    "curriculum",
    "chapters",
    "units",
    "lesson_plan",
    "learning_objectives",
    "course_content",
}


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "leland"
    source_url: Optional[str] = None
    source_title: str
    observed_at: Optional[str] = None


class DemandEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registrations: int = 0
    priority_score: int = 0
    priority_band: str = "low"
    category: str = "Other"
    velocity_note: Optional[str] = None


class AudienceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_persona: str
    current_state: str
    desired_outcome: str
    pain_points: List[str] = Field(default_factory=list)


class CommercialHypothesis(BaseModel):
    """All fields are HYPOTHESES derived from demand signals — unvalidated
    until LearnForge/Stripe conversion data proves them."""

    model_config = ConfigDict(extra="forbid")
    offer_title: Optional[str] = None
    promise: Optional[str] = None
    price_usd: Optional[float] = None
    anchor_price_usd: Optional[float] = None
    discount_pct: Optional[int] = None
    free_module_count: int = 2
    cta_headline: Optional[str] = None
    cta_subtext: Optional[str] = None
    validation_status: Literal["hypothesis"] = "hypothesis"


class GenerationConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    difficulty: str = "intermediate"
    language: str = "en"
    target_duration_min: int = 270
    suggested_module_count: int = 6
    required_outcomes: List[str] = Field(default_factory=list)
    prohibited_claims: List[str] = Field(default_factory=list)


class Callback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correlation_id: str
    status_url: Optional[str] = None


class CourseBriefV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["2.0"] = SCHEMA_VERSION
    signal_id: str
    idempotency_key: str
    source: SourceEvidence
    demand_evidence: DemandEvidence
    audience: AudienceProfile
    commercial_hypothesis: CommercialHypothesis
    generation_constraints: GenerationConstraints
    callback: Callback


def assert_no_content_fields(payload) -> None:
    """Recursively reject any generated-educational-content key."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k in FORBIDDEN_CONTENT_FIELDS:
                raise ValueError(
                    f"CourseBriefV2 must not contain generated content field '{k}'"
                )
            assert_no_content_fields(v)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_content_fields(item)


DEFAULT_PROHIBITED_CLAIMS = [
    "No unverified income, salary, or compensation claims",
    "No unverified admissions or acceptance-rate claims",
    "No unverified employment or placement-rate claims",
    "No unverified success-rate or social-proof statistics",
    "Do not copy or paraphrase proprietary Leland course content",
    "Preserve source attribution for all demand evidence",
]

_PERSONA_BY_CATEGORY = {
    "Consulting": "Aspiring management consultants targeting MBB offers",
    "MBA Admissions": "MBA applicants targeting M7/T15 programs",
    "Product Management": "Career-switchers targeting PM roles at top tech companies",
    "Finance": "Candidates targeting IB/PE/finance roles",
    "Medical Admissions": "Pre-med students targeting MD/DO admissions",
    "Law": "Applicants targeting T14 law schools",
    "Tech Careers": "Engineers and analysts leveling into top tech roles",
    "Career Switching": "Professionals engineering a deliberate career pivot",
    "GRE/GMAT": "Test-takers targeting top-percentile GRE/GMAT scores",
    "College Admissions": "College applicants targeting selective universities",
    "AI/ML": "Professionals building applied AI/ML skills",
    "Leadership": "Emerging leaders and new managers",
}


def _priority_band(score: int) -> str:
    if score >= 90:
        return "breakout"
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def compute_idempotency_key(signal: dict) -> str:
    """Deterministic + stable: same brief-relevant signal content → same key.

    Volatile fields (timestamps, publish state) are excluded on purpose.
    """
    basis = {
        "signal_id": signal.get("id"),
        "source_title": signal.get("event_title"),
        "source_url": signal.get("source_url"),
        "registrations": signal.get("registration_count") or 0,
        "priority_score": signal.get("priority_score") or 0,
        "category": signal.get("category"),
        "offer_title": signal.get("paid_offer_title"),
        "promise": signal.get("paid_offer_description"),
        "price_usd": signal.get("paid_offer_price"),
        "anchor_price_usd": signal.get("paid_offer_original_price"),
        "cta_headline": signal.get("cta_headline"),
        "cta_subtext": signal.get("cta_subtext"),
        "schema_version": SCHEMA_VERSION,
    }
    canonical = json.dumps(basis, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_course_brief(signal: dict) -> CourseBriefV2:
    """Build a CourseBriefV2 from ALREADY-STORED signal + enrichment metadata.

    No AI calls, no content generation — purely deterministic derivation.
    """
    category = signal.get("category") or "Other"
    score = int(signal.get("priority_score") or 0)
    notes = (signal.get("notes") or "").strip()
    offer_title = signal.get("paid_offer_title") or None
    promise = (
        signal.get("paid_offer_description")
        or signal.get("cta_subtext")
        or None
    )
    price = signal.get("paid_offer_price")
    anchor = signal.get("paid_offer_original_price")

    current_state = (
        "Registered interest via a free public Leland event; seeking a "
        "structured path to the outcome."
    )
    if notes:
        current_state = f"{current_state} Demand note: {notes}"

    desired_outcome = (
        signal.get("cta_subtext")
        or (f"Achieve the outcome promised by '{offer_title}'" if offer_title else
            "Convert free-event interest into a concrete career outcome")
    )

    required_outcomes = [
        x for x in [signal.get("cta_subtext"), signal.get("paid_offer_description")]
        if x
    ]

    return CourseBriefV2(
        signal_id=signal.get("id"),
        idempotency_key=compute_idempotency_key(signal),
        source=SourceEvidence(
            provider="leland",
            source_url=signal.get("source_url"),
            source_title=signal.get("event_title") or "Untitled event",
            observed_at=signal.get("updated_at") or signal.get("created_at"),
        ),
        demand_evidence=DemandEvidence(
            registrations=int(signal.get("registration_count") or 0),
            priority_score=score,
            priority_band=_priority_band(score),
            category=category,
            velocity_note=notes or None,
        ),
        audience=AudienceProfile(
            primary_persona=_PERSONA_BY_CATEGORY.get(
                category, f"Ambitious professionals in {category}"
            ),
            current_state=current_state,
            desired_outcome=desired_outcome,
            pain_points=[
                "No structured path from free-event interest to a concrete outcome",
                "Limited access to insider frameworks and reps",
                "Time-constrained preparation window",
            ],
        ),
        commercial_hypothesis=CommercialHypothesis(
            offer_title=offer_title,
            promise=promise,
            price_usd=price,
            anchor_price_usd=anchor,
            discount_pct=compute_discount_pct(price, anchor),
            free_module_count=2,
            cta_headline=signal.get("cta_headline") or None,
            cta_subtext=signal.get("cta_subtext") or None,
        ),
        generation_constraints=GenerationConstraints(
            difficulty="intermediate",
            language="en",
            target_duration_min=270,
            suggested_module_count=6,
            required_outcomes=required_outcomes,
            prohibited_claims=list(DEFAULT_PROHIBITED_CLAIMS),
        ),
        callback=Callback(correlation_id=f"radar-{signal.get('id')}"),
    )
