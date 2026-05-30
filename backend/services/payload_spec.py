"""Stable JSON-Schema spec for the LearnForge publish webhook.

Surfaced at GET /api/integrations/publish-payload-spec so the Architect
can paste it directly into the learnforge-core POST /api/courses handler
without re-deriving the shape from code.
"""

PUBLISH_PAYLOAD_SPEC = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://learnforge-core.vercel.app/schemas/course-publish.v1.json",
    "title": "LearnForge Radar — Course Publish Webhook (v1)",
    "description": (
        "Payload posted by the Opportunity Radar to LearnForge's "
        "POST /api/courses endpoint when an Architect publishes a "
        "converted signal. Stable contract — backwards-compatible "
        "additions only."
    ),
    "type": "object",
    "required": ["event", "signal_id", "published_at", "course"],
    "properties": {
        "event": {"const": "course.publish"},
        "signal_id": {"type": "string", "format": "uuid"},
        "published_at": {"type": "string", "format": "date-time"},
        "course": {
            "type": "object",
            "required": ["slug", "title", "category", "cta", "syllabus", "demand"],
            "properties": {
                "slug": {"type": "string", "examples": ["forgecore-mbb-case-mastery"]},
                "title": {"type": "string"},
                "category": {
                    "type": "string",
                    "examples": [
                        "Consulting", "MBA Admissions", "Product Management",
                        "Finance", "Medical Admissions", "Law", "Tech Careers",
                        "Career Switching", "Other",
                    ],
                },
                "summary": {"type": "string"},
                "price_usd": {"type": ["number", "null"]},
                "lead_magnet": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "slug": {"type": ["string", "null"]},
                        "url": {"type": ["string", "null"], "format": "uri"},
                    },
                },
                "cta": {
                    "type": "object",
                    "required": ["paid_url"],
                    "properties": {
                        "headline": {"type": "string"},
                        "subtext": {"type": "string"},
                        "free_url": {"type": ["string", "null"], "format": "uri"},
                        "paid_url": {"type": "string", "format": "uri"},
                    },
                },
                "syllabus": {
                    "type": "object",
                    "required": ["modules"],
                    "properties": {
                        "modules": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["index", "title", "summary", "duration_min"],
                                "properties": {
                                    "index": {"type": "integer", "minimum": 1},
                                    "title": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "learning_objectives": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "artifact": {"type": "string"},
                                    "duration_min": {"type": "integer"},
                                },
                            },
                        }
                    },
                },
                "demand": {
                    "type": "object",
                    "required": ["registration_count", "priority_score"],
                    "properties": {
                        "registration_count": {"type": "integer"},
                        "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "source_url": {"type": ["string", "null"], "format": "uri"},
                    },
                },
            },
        },
    },
}


PUBLISH_PAYLOAD_EXAMPLE = {
    "event": "course.publish",
    "signal_id": "1e8a43c8-a6e1-4d29-aa15-e1fedde2ef73",
    "published_at": "2026-05-30T01:24:00Z",
    "course": {
        "slug": "forgecore-mbb-case-mastery",
        "title": "ForgeCore: MBB Case Mastery",
        "category": "Consulting",
        "summary": "8-module mini-course with 12 live cases and feedback.",
        "price_usd": 299,
        "lead_magnet": {
            "title": "The MBB Case Cheat Sheet",
            "description": "10-page distilled framework for case interview structuring.",
            "slug": "the-mbb-case-cheat-sheet",
            "url": "https://learnforge-core.vercel.app/signup?course=the-mbb-case-cheat-sheet&ref=radar&tier=free",
        },
        "cta": {
            "headline": "Land Your MBB Offer",
            "subtext": "Trained by ex-McKinsey EMs. Outcome-tracked.",
            "free_url": "https://learnforge-core.vercel.app/signup?course=the-mbb-case-cheat-sheet&ref=radar&tier=free",
            "paid_url": "https://learnforge-core.vercel.app/signup?course=forgecore-mbb-case-mastery&ref=radar&tier=forgecore",
        },
        "syllabus": {
            "modules": [
                {
                    "index": 1,
                    "title": "Decode the Case: Structure in 60 Seconds",
                    "summary": "Master the MECE framework and rapid case structuring.",
                    "learning_objectives": [
                        "Apply MECE principles to structure any case type in under 90 seconds",
                        "Build a reusable framework cheat-sheet for the top 5 archetypes",
                    ],
                    "artifact": "Personal Framework One-Pager",
                    "duration_min": 60,
                }
            ]
        },
        "demand": {
            "registration_count": 1228,
            "priority_score": 94,
            "source_url": "https://leland.com/events/mbb-case",
        },
    },
}


HEADERS_SPEC = {
    "X-Radar-Event": "course.publish",
    "X-Radar-Signature": "<value of LEARNFORGE_WEBHOOK_SECRET if set, else absent>",
    "User-Agent": "LearnForge-OpportunityRadar/1.0",
    "Content-Type": "application/json",
}


EXPECTED_RESPONSE = {
    "success": {
        "status_code": "2xx",
        "body": {"ok": True, "course_id": "<your_internal_id>"},
        "note": "Any 2xx flips Radar publish_status to 'published' and signal.status to 'live'.",
    },
    "failure": {
        "status_code": "4xx / 5xx",
        "body": "any (Radar stores response_preview[:400] in publish_log)",
        "note": "Triggers exponential-backoff auto-retry (2/4/8/16/32 minutes, max 5 attempts).",
    },
}
