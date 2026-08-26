# LearnForge ↔ Opportunity Radar — v2 Integration Contract

**Status: PROPOSED CONTRACT — NOT YET A LIVE INTEGRATION.**
As of 2026-06, `POST https://learnforge-core.vercel.app/api/course-generation-jobs`
returns HTTP 404. LearnForge must implement this receiver before v2 dispatches
can succeed. Radar records honest `failed` jobs until then.

## Responsibility Matrix (canonical ownership)

| Concern | Owner |
|---|---|
| Demand discovery, source evidence, registration counts, category | **Radar** |
| Priority scoring, audience/problem analysis | **Radar** |
| Offer / price / CTA **hypotheses** | **Radar** |
| Dispatch + job status tracking | **Radar** |
| Syllabus creation, curriculum architecture | **LearnForge** |
| Module / lesson / quiz generation, educational content | **LearnForge** |
| Review, verification, course persistence, learner experience | **LearnForge** |
| Progress + course entitlements | **LearnForge** |
| Checkout and paid access | **Stripe / LearnForge** |

Sequence:
`Leland public demand → Radar discovery/scoring → CourseBriefV2 → LearnForge generation pipeline → completed course → Stripe gate`

Radar **never** claims it generated a course, syllabus, lesson, module, quiz,
or educational content. `CourseBriefV2` structurally forbids those fields.

## 1. Dispatch request

`POST {LEARNFORGE_COURSE_JOBS_URL}` (intended: `/api/course-generation-jobs`)

### Headers
| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `User-Agent` | `LearnForge-OpportunityRadar/2.0` |
| `X-Radar-Event` | `course_brief.dispatch` |
| `X-Radar-Schema-Version` | `2.0` |
| `X-Radar-Idempotency-Key` | 64-char sha256 hex, deterministic per brief content |
| `X-Radar-Signature` | bare lowercase hex HMAC-SHA256 of the **raw body** using the shared `LEARNFORGE_WEBHOOK_SECRET` |
| `X-Radar-Signature-Algorithm` | `hmac-sha256` |

Signing rules: the body is canonical JSON (`sort_keys`, separators `,`/`:`),
the exact bytes POSTed are the exact bytes signed. Verify with a
constant-time compare (`crypto.timingSafeEqual`) over `await req.text()`.

Idempotency: same brief-relevant signal content ⇒ same key. Receivers MUST
treat a repeated key as a no-op and return the existing job.

### Body: `CourseBriefV2` (example, no secrets / production IDs)
```json
{
  "schema_version": "2.0",
  "signal_id": "<uuid>",
  "idempotency_key": "<sha256-hex>",
  "source": {
    "provider": "leland",
    "source_url": "https://www.joinleland.com/events/example",
    "source_title": "MBB Case Interview Bootcamp",
    "observed_at": "2026-06-01T00:00:00+00:00"
  },
  "demand_evidence": {
    "registrations": 1200,
    "priority_score": 88,
    "priority_band": "high",
    "category": "Consulting",
    "velocity_note": "Registrations doubled week-over-week."
  },
  "audience": {
    "primary_persona": "Aspiring management consultants targeting MBB offers",
    "current_state": "Registered interest via a free public Leland event; seeking a structured path to the outcome.",
    "desired_outcome": "Land a consulting offer",
    "pain_points": ["No structured path", "Limited access to frameworks", "Time-constrained prep"]
  },
  "commercial_hypothesis": {
    "offer_title": "ForgeCore: The 21-Day MBB Case Engine",
    "promise": "Master the case framework stack",
    "price_usd": 1000,
    "anchor_price_usd": 1899,
    "discount_pct": 47,
    "free_module_count": 2,
    "cta_headline": "Land Your MBB Offer",
    "cta_subtext": "Outcome-tracked case prep",
    "validation_status": "hypothesis"
  },
  "generation_constraints": {
    "difficulty": "intermediate",
    "language": "en",
    "target_duration_min": 270,
    "suggested_module_count": 6,
    "required_outcomes": ["Outcome-tracked case prep"],
    "prohibited_claims": [
      "No unverified income, salary, or compensation claims",
      "No unverified admissions or acceptance-rate claims",
      "No unverified employment or placement-rate claims",
      "No unverified success-rate or social-proof statistics",
      "Do not copy or paraphrase proprietary Leland course content",
      "Preserve source attribution for all demand evidence"
    ]
  },
  "callback": { "correlation_id": "radar-<signal_id>", "status_url": null }
}
```

**Forbidden fields** (any nesting level): `modules`, `lessons`, `quizzes`,
`syllabus`, `syllabus_modules`, `curriculum`, `chapters`, `units`,
`lesson_plan`, `learning_objectives`, `course_content`. Receivers SHOULD
reject payloads containing them with HTTP 422.

## 2. Accepted response (LearnForge → Radar)

`HTTP 202` (or 200/201):
```json
{
  "job_id": "<learnforge-job-id>",
  "status": "queued",
  "status_url": "https://learnforge-core.vercel.app/api/course-generation-jobs/<job_id>",
  "public_course_url": null
}
```

## 3. Job states

`accepted → queued → generating → reviewing → ready | failed`

- Radar treats any other status string as an anomaly (keeps prior state,
  records `last_check_error`).
- `ready` MUST include `public_course_url`.
- `failed` SHOULD include `error` (human-readable summary).

### Status response (GET status_url)
```json
{ "job_id": "<id>", "status": "generating", "public_course_url": null, "error": null }
```

### Ready
```json
{ "job_id": "<id>", "status": "ready", "public_course_url": "https://learnforge-core.vercel.app/courses/<slug>" }
```

### Failed
```json
{ "job_id": "<id>", "status": "failed", "error": "Generation exceeded review threshold: unverifiable claim detected in module 3" }
```

## 4. Error semantics & retries (Radar behavior)

| Condition | Radar behavior |
|---|---|
| 5xx / timeout / connect error | Retry up to 3 attempts, backoff 1s/2s/4s |
| 404 | Fail immediately; hint: v2 receiver not deployed |
| 401/403 | Fail immediately; hint: HMAC secret mismatch |
| Other 4xx | Fail immediately with response preview |
| Missing `LEARNFORGE_COURSE_JOBS_URL` | Fail safely; **never** falls back to legacy v1 webhook |
| Duplicate idempotency key (non-failed job) | Returns existing job, no re-POST |

Failures are always recorded as `failed` — never `accepted`/`ready`.

## 5. Legacy v1 (deprecated)

The v1 `POST /api/courses` payload (top-level `title`/`slug`/`modules`) is
retained behind `RADAR_LEGACY_PUBLISH_ENABLED` (default **OFF**) for
backward compatibility only. It ships generated modules from Radar, which
violates the ownership boundary, and will be removed once v2 is live.

## 6. Remaining LearnForge-side work

1. Implement `POST /api/course-generation-jobs` (validate schema 2.0, verify
   HMAC, enforce idempotency, reject forbidden content fields).
2. Implement `GET /api/course-generation-jobs/{job_id}` status endpoint.
3. Wire LearnForge's own generation pipeline (syllabus → modules → review).
4. Return `public_course_url` on `ready`; gate paid access via Stripe.
5. Set `LEARNFORGE_WEBHOOK_SECRET` in the LearnForge environment (same shared
   secret Radar signs with — value not reproduced here).


> **Drop-in starting point:** `docs/learnforge_receiver_stub_kit/` ships a
> ready-to-paste Next.js receiver stub (route + status endpoint + HMAC verify +
> Zod schema + Prisma model + `verify_local.sh` smoke test) that covers steps
> 1, 2 and 5 above. It acknowledges briefs as `accepted` and leaves a single
> `TODO(generation)` seam for step 3 — it intentionally generates no content.
