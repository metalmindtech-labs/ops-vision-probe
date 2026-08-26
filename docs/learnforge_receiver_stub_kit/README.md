# LearnForge Receiver Stub Kit — CourseBriefV2 (Radar → LearnForge)

> **This kit belongs in the `learnforge-core` repository, NOT in Opportunity Radar.**
> It is a *stub*: it accepts, verifies, deduplicates, and acknowledges a signed
> `CourseBriefV2` and exposes a job-status endpoint. It **does not** generate a
> syllabus/modules/lessons — that is LearnForge's real generation pipeline, which
> you wire into the `TODO(generation)` seam. Radar never generates courses.

## Why this exists
Opportunity Radar discovers demand and dispatches a signed `CourseBriefV2` to:

```
POST {LEARNFORGE_COURSE_JOBS_URL}   e.g. https://learnforge-core.vercel.app/api/course-generation-jobs
```

Today that route returns **HTTP 404** because LearnForge hasn't shipped the
receiver yet, so every Radar dispatch honestly records a `failed` job. Deploy
this stub to flip 404 → `202 accepted` and unblock the end-to-end handshake.

## What's in the kit
| File | Drop into `learnforge-core` at | Purpose |
|---|---|---|
| `app/api/course-generation-jobs/route.ts` | same path | POST receiver: verify HMAC, idempotency, persist, ack `accepted` |
| `app/api/course-generation-jobs/[jobId]/route.ts` | same path | GET status: return job state + `public_course_url` when ready |
| `lib/radar/verify.ts` | `lib/radar/verify.ts` | HMAC-SHA256 raw-body verification (constant-time) |
| `lib/radar/brief.ts` | `lib/radar/brief.ts` | Zod schema for `CourseBriefV2` + forbidden-content guard |
| `prisma/course_jobs.prisma.snippet` | merge into `schema.prisma` | `CourseJob` model (swap for your ORM if not Prisma) |
| `verify_local.sh` | run anywhere | Local curl smoke test with a correctly-signed body |

## Environment (LearnForge side)
```
LEARNFORGE_WEBHOOK_SECRET=SovereignForge2026!   # MUST match Radar's backend/.env exactly
```
The secret is the **only** shared credential. Radar signs the raw request body
with HMAC-SHA256; this stub verifies the same.

## Contract summary (full spec: docs/LEARNFORGE_V2_CONTRACT.md in Radar)
### Request headers Radar sends
| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-Radar-Event` | `course_brief.dispatch` |
| `X-Radar-Schema-Version` | `2.0` |
| `X-Radar-Idempotency-Key` | sha256 hex of brief-relevant signal content |
| `X-Radar-Signature` | lowercase hex HMAC-SHA256 of the **raw** body |
| `X-Radar-Signature-Algorithm` | `hmac-sha256` |

### Signing (must match exactly)
Radar computes `HMAC_SHA256(secret, rawBodyBytes)` where `rawBodyBytes` is the
exact bytes it POSTs (a compact, key-sorted JSON string). **Verify over
`await req.text()` — never re-serialize before verifying.**

### Expected success response (this stub returns)
```json
HTTP 202
{
  "status": "accepted",
  "job_id": "lf_job_<uuid>",
  "status_url": "https://learnforge-core.vercel.app/api/course-generation-jobs/lf_job_<uuid>",
  "public_course_url": null
}
```
`status` ∈ `accepted | queued | generating | reviewing | ready | failed`.
When your real pipeline finishes, set `status: "ready"` + a `public_course_url`
on the job; Radar's poller/refresh will pick it up.

### Error semantics
| Situation | Response | Radar behavior |
|---|---|---|
| Missing/invalid signature | `401 {"error":"invalid_signature"}` | job → `failed`, hint: check shared secret |
| Body fails schema / contains generated content | `400 {"error":"invalid_brief","detail":...}` | job → `failed` |
| Duplicate idempotency key | `200` with the **original** `job_id` | dedupe, no double work |
| Route not deployed | `404` | job → `failed`, hint: "ship the v2 receiver" |

## Install (3 steps)
1. Copy the files to the paths in the table above.
2. Set `LEARNFORGE_WEBHOOK_SECRET` in the Vercel project env (same value as Radar).
3. Run `bash verify_local.sh` against your dev server, then redeploy.

## The generation seam
`route.ts` marks a single `TODO(generation)` where you enqueue your real
LearnForge job (BullMQ / Inngest / Vercel Queue / cron). The stub persists the
brief and returns `accepted` immediately — **do not** block the HTTP response on
generation. This kit deliberately contains zero syllabus/module logic.
