# LearnForge Opportunity Radar

Internal mission-control dashboard: discovers high-demand learning signals
(Leland public event data), scores them, frames offer **hypotheses**, and
dispatches **CourseBriefV2** jobs to LearnForge — which owns all course
generation.

## Responsibility Matrix (v2 architecture)

| Concern | Owner |
|---|---|
| Demand discovery, source evidence, registrations, category | **Radar** |
| Priority scoring, audience/problem analysis | **Radar** |
| Offer / price / CTA **hypotheses** | **Radar** |
| CourseBriefV2 dispatch + job status tracking | **Radar** |
| Syllabus, curriculum, modules/lessons/quizzes, review, persistence | **LearnForge** |
| Learner experience, progress, entitlements | **LearnForge** |
| Checkout and paid access | **Stripe / LearnForge** |

Sequence:
`Leland public demand → Radar discovery/scoring → CourseBriefV2 → LearnForge generation pipeline → completed course → Stripe gate`

Radar never claims to have generated a course, syllabus, lesson, module,
quiz, or educational content. `CourseBriefV2` structurally forbids those
fields (see `backend/services/course_brief.py`).

## Key pieces

- Backend: FastAPI + MongoDB (`backend/server.py`)
  - v2: `services/course_brief.py` (typed brief), `services/dispatcher.py`
    (signed dispatch + job tracking to `LEARNFORGE_COURSE_JOBS_URL`)
  - Legacy v1 modules webhook + Radar-side syllabus generation are
    DEPRECATED, gated behind `RADAR_LEGACY_PUBLISH_ENABLED` (default OFF —
    routes return HTTP 410 when disabled).
- Frontend: React + Tailwind + shadcn (`frontend/src`)
  - Conversion Engine: hypothesis framing → "Preview Course Brief" →
    "Dispatch Brief" → LearnForge job status chip.
- Contract: `docs/LEARNFORGE_V2_CONTRACT.md` (proposed — LearnForge must
  implement `POST /api/course-generation-jobs`; it currently returns 404).

## Tests

```
cd backend && REACT_APP_BACKEND_URL=<preview-url> python -m pytest tests/ -q
```

v2 coverage: `tests/test_iter13_course_brief_v2.py` (brief validation,
forbidden-content assertions, HMAC, idempotency, retries, state
transitions, legacy 410 gating). External LearnForge calls are mocked.
