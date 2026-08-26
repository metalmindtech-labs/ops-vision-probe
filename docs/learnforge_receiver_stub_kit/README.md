# LearnForge Receiver Patch — CourseBriefV2 (Radar → LearnForge)

> **This patch belongs in the `learnforge-core` repository, NOT in Opportunity Radar.**
> It implements the `/api/course-generation-jobs` receiver: it **accepts,
> verifies, and records** a signed `CourseBriefV2` and exposes a job-status
> endpoint. It **does not** generate a syllabus/modules/lessons — that is
> LearnForge's own pipeline, wired in later at the `TODO(generation)` seam.
> Radar never generates courses; this patch preserves that boundary.

## What this unblocks
Opportunity Radar dispatches a signed `CourseBriefV2` to:

```
POST {LEARNFORGE_COURSE_JOBS_URL}   e.g. https://learnforge-core.vercel.app/api/course-generation-jobs
```

That route currently returns **HTTP 404**, so every Radar dispatch honestly
records a `failed` job. Deploying this patch flips 404 → **202 accepted** and
completes the handshake. (Deploy is the LearnForge team's step — this patch does
not deploy anything.)

## Files in this patch
| File | Path in `learnforge-core` | Purpose |
|---|---|---|
| `app/api/course-generation-jobs/route.ts` | same | POST receiver (thin) → `processCourseBrief` → Supabase |
| `app/api/course-generation-jobs/[jobId]/route.ts` | same | GET job status |
| `lib/radar/receiver.ts` | same | **Pure** contract logic (verify → validate → idempotency → accept). Framework/DB-agnostic, unit-tested |
| `lib/radar/verify.ts` | same | Constant-time HMAC-SHA256 over the raw body |
| `lib/radar/brief.ts` | same | Zod `CourseBriefV2` schema + forbidden-content guard + required source attribution |
| `lib/radar/supabase-store.ts` | same | Supabase (service-role) `JobStore` implementation |
| `supabase/migrations/20260826000000_course_jobs.sql` | same | `course_jobs` table + RLS + trigger |
| `tests/receiver.test.ts` | same | Vitest suite (10 cases) against an in-memory store |
| `.env.example` | reference | Required environment variables |

Stack assumption: **Next.js App Router + Supabase** (matches learnforge-core's
existing `@supabase/*` usage). Uses `@supabase/supabase-js` for server writes.

## Required environment variables
Set these in the learnforge-core Vercel project (see `.env.example`):

| Var | Purpose |
|---|---|
| `LEARNFORGE_WEBHOOK_SECRET` | Shared HMAC secret — **must equal** Radar's `backend/.env` value exactly |
| `SUPABASE_URL` (or `NEXT_PUBLIC_SUPABASE_URL`) | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only key for writing the job ledger (bypasses RLS) |
| `LEARNFORGE_PUBLIC_BASE_URL` | Base for the returned `status_url` (default `https://learnforge-core.vercel.app`) |

Install the client if not already present: `npm i @supabase/supabase-js`.

## Database migration
Apply `supabase/migrations/20260826000000_course_jobs.sql`:

```bash
# via Supabase CLI
supabase db push
# or paste the SQL into Supabase Studio → SQL editor and run
```

Creates `public.course_jobs` (`id`, `idempotency_key UNIQUE`, `signal_id`,
`correlation_id`, `status` CHECK, `public_course_url`, `error`, `brief jsonb`,
timestamps + `updated_at` trigger). RLS is **enabled with no anon/auth
policies** — only the service-role receiver can read/write it.

## The contract (enforced by this patch)
### Request headers Radar sends
| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-Radar-Event` | `course_brief.dispatch` |
| `X-Radar-Schema-Version` | `2.0` |
| `X-Radar-Idempotency-Key` | sha256 hex of brief-relevant signal content |
| `X-Radar-Signature` | lowercase hex HMAC-SHA256 of the **raw** body |
| `X-Radar-Signature-Algorithm` | `hmac-sha256` |

### Validation order (see `lib/radar/receiver.ts`)
1. **Signature** — HMAC-SHA256 over `await req.text()`; fail closed → `401 invalid_signature`.
2. **Schema version** — header + body must be `2.0` → `400 unsupported_schema_version`.
3. **JSON parse** → `400 invalid_json`.
4. **Forbidden educational content** — any `modules/lessons/quizzes/syllabus/...` at any depth → `400 forbidden_content`.
5. **Strict schema** (Zod, `extra` rejected) → `400 invalid_brief`.
6. **Demand-source attribution** — `source.provider` + `source.source_title` required → `400 missing_source_attribution`.
7. **Idempotency** — repeat `idempotency_key` returns the original job → `200 { deduplicated: true }`.
8. **Accept** — create `accepted` job → `202`.

### Success response (202)
```json
{
  "status": "accepted",
  "job_id": "lf_job_<uuid>",
  "status_url": "https://learnforge-core.vercel.app/api/course-generation-jobs/lf_job_<uuid>",
  "public_course_url": null
}
```
`status` ∈ `accepted | queued | generating | reviewing | ready | failed`. When
the real pipeline finishes it sets `status = "ready"` + `public_course_url` on
the row; Radar's poller reads the status endpoint and updates its UI.

## The generation seam
`route.ts` has one `TODO(generation)` after a 202: enqueue LearnForge's real
generation job (queue/cron) — **out of band**, never blocking the HTTP
response. This patch deliberately contains zero syllabus/module logic.

## Automated tests
`tests/receiver.test.ts` (Vitest) covers 10 cases: 202 accept, 401 bad/missing
signature, 400 bad schema version, 400 forbidden content (top-level + nested),
400 missing source attribution, 400 strict-extra-field, 400 malformed JSON, and
200 idempotency dedupe. Run in learnforge-core:

```bash
npx vitest run tests/receiver.test.ts
```

> These same 10 scenarios were executed against this exact `receiver.ts` /
> `brief.ts` / `verify.ts` code during authoring (Babel-transpiled Node
> harness) — **10/10 passed**. HMAC parity was also confirmed byte-identical
> across Radar-Python / openssl / Node-crypto.

## Manual verification (local, no deploy)
1. `cp .env.example .env.local` and fill `LEARNFORGE_WEBHOOK_SECRET`, Supabase vars.
2. Apply the migration (above).
3. `npm run dev` (learnforge-core).
4. Run the signed smoke test:
   ```bash
   LEARNFORGE_WEBHOOK_SECRET=<same-as-radar> \
   TARGET=http://localhost:3000/api/course-generation-jobs \
   bash verify_local.sh
   ```
   Expect `HTTP 202` and `status: "accepted"`. Re-run → `HTTP 200` (dedupe).
5. `GET http://localhost:3000/api/course-generation-jobs/<job_id>` → `status: "accepted"`.
6. Tamper the signature → expect `401 invalid_signature`.

## Status / boundary notes
- **Not deployed. Not live.** This is a repository patch for the LearnForge team.
- No production data is modified by applying this patch (the migration only adds
  a new `course_jobs` table).
- Full contract reference: Radar's `docs/LEARNFORGE_V2_CONTRACT.md`.
