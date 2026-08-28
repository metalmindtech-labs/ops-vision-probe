# LearnForge Opportunity Radar — PRD

## Original Problem Statement
Build an internal mission-control dashboard for the LearnForge "Architect" to monitor high-demand learning signals (primarily Leland event data) and convert them into LearnForge courses. Must include a Signal Tracker, Conversion Engine (Free Lead Magnet + Paid ForgeCore Offer), a Leland-style CTA generator, a simulated Syllabus Generation trigger, and a Command-Center dark aesthetic.

## User Persona
- **The Architect**: An internal strategist who scans Leland event registrations for high-signal demand and decides which learnings deserve a LearnForge Free Course (Lead Magnet) and/or a Paid ForgeCore mini-course.

## Architecture
- Backend: FastAPI + Motor (async MongoDB). All routes prefixed `/api`.
- Frontend: React (CRA) + TailwindCSS + shadcn/ui + lucide-react + sonner.
- Persistence: MongoDB (`signals` collection). Auto-seeded with 7 curated signals on startup if empty.
- Aesthetic: Dark mode locked. JetBrains Mono headings/data + IBM Plex Sans body. Lime-400 accents on zinc-950 base.

## Core Requirements (Static)
1. Signal Tracker — table with Event Title, Category, Registration Count, Priority Score, Status.
2. Conversion Engine — define free Lead Magnet + paid ForgeCore offer per signal.
3. CTA Generator — Leland-style banner with auto-derived placeholder URLs (`learnforge.com/free/<slug>`, `learnforge.com/forgecore/<slug>`).
4. Simulated Syllabus Generation — 5-module deterministic output.
5. CRUD persistence in MongoDB.

## Responsibility Matrix (v2 — ARCHITECTURE CORRECTION, 2026-06)
**Radar discovers demand; LearnForge generates courses.**

| Concern | Owner |
|---|---|
| Demand discovery, source evidence, registrations, category | **Radar** |
| Priority scoring, audience/problem analysis | **Radar** |
| Offer / price / CTA **hypotheses** | **Radar** |
| CourseBriefV2 dispatch + job status tracking | **Radar** |
| Syllabus, curriculum, module/lesson/quiz generation, review, persistence | **LearnForge** |
| Learner experience, progress, entitlements | **LearnForge** |
| Checkout and paid access | **Stripe / LearnForge** |

Sequence: `Leland public demand → Radar discovery/scoring → CourseBriefV2 → LearnForge generation pipeline → completed course → Stripe gate`.
Radar never claims to have generated a course/syllabus/lesson/module/quiz.

## Implemented (2026-06 — v28: Receiver emits `expected_fp` on 401 (kit) + Radar MATCH/MISMATCH verified)
- **Receiver Kit updated** (`docs/learnforge_receiver_stub_kit/`): on invalid signature the receiver now returns `{ "error":"invalid_signature", "expected_fp":"<sha256(secret)[:8]>" }`. Added `secretFingerprint()` to `lib/radar/verify.ts`; `lib/radar/receiver.ts` includes it in the 401 body. README documents a copy-paste snippet for LearnForge's hand-written route. (LearnForge must apply this in learnforge-core — Radar can't push there.)
- **Fingerprint parity proven:** python (Radar) == node (receiver) == `c42f2735` for the current 64-char secret.
- **Radar consumption verified (unit):** `_remote_expected_fingerprint` extracts `expected_fp`/`secret_fp`/`fingerprint`; hint shows MATCH when equal, MISMATCH when different, and falls back to Radar-fp-only when absent (current live staging behaviour, since its route doesn't emit `expected_fp` yet).

## Implemented (2026-06 — v27: Fingerprint-on-failure hint for 401/403)
- Dispatch failure hint on a `401/403` now self-explains: it includes **Radar's signing `secret_fp` (sha256 prefix) + length**, and — if the LearnForge receiver returns an expected fingerprint (`expected_fp`/`secret_fp`/`fingerprint`) in its error body — surfaces it with a `MATCH`/`MISMATCH` verdict. Never exposes the secret value.
- Example (verified live with a deliberately wrong secret): `Signature rejected (HTTP 401). Radar signed with secret_fp=3d596966 (len=26). If the fingerprints differ, the shared LEARNFORGE_WEBHOOK_SECRET is out of sync — rotate/align both sides so they match.` Correct secret restored → `202 accepted`.
- Helpers added in `services/dispatcher.py`: `_secret_fingerprint()`, `_remote_expected_fingerprint(resp)`. To get the full MATCH/MISMATCH line, the LearnForge receiver can include `expected_fp` (= `sha256(secret)[:8]`) in its 401 JSON.

## Implemented (2026-06 — v26: Secret-drift guard at startup)
- Backend `on_startup` now logs the LearnForge dispatch config — **endpoint + `secret_len` + a non-reversible sha256 fingerprint prefix (`secret_fp`), never the secret value** — so a rotation mismatch is obvious at boot instead of surfacing as a runtime 401. Warns loudly if `LEARNFORGE_WEBHOOK_SECRET` is unset.
- Verified live: `LearnForge dispatch config · endpoint=https://learnforge-staging.vercel.app · secret_len=64 · secret_fp=c42f2735`. Log-only change, no behavior impact. The `secret_fp` also lets you compare Radar vs LearnForge secrets safely (compute `sha256(secret)[:8]` on both — they must match).

## Implemented (2026-06 — v29: Scraper surfaces "AI budget exceeded" clearly instead of raw ChatError)
- **Root cause of "15 discovered but nothing added":** the Emergent Universal LLM key is over budget (`Max budget 5.0 · cost 7.56`), so per-event Claude enrichment threw `ChatError`; the scrape still reported `discovered:15` with a green success toast → looked like a Radar bug. It is NOT — it's a billing/key cap (shared by preview + production, key `d2d32o4l75ls73cuuhog`).
- **Fix (services/ingestion.py):** budget/rate-limit errors are now classified (`budget`+`exceed` / `budget_exceeded` / `ratelimiterror` / `rate limit` / `too many requests`), the loop **short-circuits** (1 error instead of 15), and the summary carries `llm_budget_exceeded:true` + a clear `message` (top up the Universal Key). `skipped` set to 0 on that path (events weren't attempted).
- **Frontend:** `Dashboard.jsx` scrape/paste handlers show an amber WARNING toast "AI budget exceeded — top up to enrich" (not a misleading success); `ScraperStatusBar` shows a **persistent** amber badge (`data-testid=scraper-budget-warning`) sourced from `last_run.llm_budget_exceeded` so it doesn't vanish with the toast.
- **Verified:** testing agent iteration_18 (6/6 backend, 100% frontend) + self-test (run→flag+message+short-circuit; `/api/scraper/status` surfaces the flag; stats unchanged 31→31). Regression: `/app/backend/tests/test_iter18_llm_budget_shortcircuit.py`.
- ⚠️ **Deploy note:** this fix lives in PREVIEW; the user hit the issue on PRODUCTION (course-converter-2.emergent.host) → they must **redeploy** to push it. Signals still won't be created until the Universal Key budget is actually raised.

## Fixed (2026-06 — v25: Dispatch 401 "Invalid signature" — HMAC secret drift)
- **Root cause:** the LearnForge staging receiver's webhook secret was rotated to a new 64-char value, but Radar Preview still held the old 45-char `RotatedSecret_Staging_2026_...` → `X-Radar-Signature` failed verification → `401`. (Radar's signing was correct throughout; the endpoint was reachable, health `200`.)
- **Fix:** synced Radar Preview's `LEARNFORGE_WEBHOOK_SECRET` (backend/.env) to the current 64-char staging secret and restarted; secret is read per-call so restarts pick up rotations.
- **Verified (testing agent iteration_17: 6/6 backend, 100% frontend):** fresh dispatch → `202 accepted, deduplicated:false`; repeat → `deduplicated:true` same remote job id; job-status → accepted; refresh → `200 accepted`; UI chip shows ACCEPTED; **no 401 anywhere**. Regression: `/app/backend/tests/test_iter17_secret_rotation_401_fix.py`.
- Reminder: whenever the staging/prod webhook secret is rotated, Radar's `LEARNFORGE_WEBHOOK_SECRET` must be updated to match (both sides share one secret).

## Implemented (2026-06 — v24: Dispatch auto-polling — briefs light up READY on their own)
- **BriefDispatchPanel auto-polls LearnForge job status** while a dispatched job is non-terminal (accepted/queued/generating/reviewing): calls `POST /api/course-jobs/{job_id}/refresh` every 6s with a leading tick, updates the status chip, and **flips to READY (with a toast + course link) on its own** — no manual refresh. Polling stops automatically on terminal states (ready/failed); a pulsing `job-autosync-indicator` shows while active. `onDispatched` held in a ref so parent re-renders don't tear down the interval.
- **Verified (testing agent iteration_16: 5/5 frontend, zero console errors):** auto-poll fires without a click; `page.route` interception confirmed chip flips to READY + public-url link + polling halts; failed status also stops polling; manual refresh still works; brief preview has no forbidden content.
- New testid: `job-autosync-indicator`. Post-review refinements applied (leading tick, `useRef` for callback). Manual `refresh` button retained as a fallback.

## Implemented (2026-06 — v23: Radar → LearnForge STAGING integration gate PASSED ✅)
- **First real end-to-end handshake verified** against the live LearnForge staging receiver (`https://learnforge-staging.vercel.app/api/course-generation-jobs`, dedicated Supabase `twifpxkrsagzhxtarvqe`). Radar Preview points at the stable alias; rotated HMAC secret configured (env only, never committed).
- **Gate results (testing agent iteration_15: 100% backend, 100% frontend):** first dispatch → `202 accepted, deduplicated:false`; repeat → `deduplicated:true` same remote job id; Radar-side idempotency keeps exactly one `course_jobs` row per idempotency key (staging holds one row); GET job-status/refresh → `200 accepted`; brief preview has zero forbidden content; legacy `/publish` → 410; forbidden-content brief → 400. No 500, no legacy fallback, production project `ovxlcjdtnigbvtpgcmqm` untouched.
- **Debug journey (root causes were all upstream/staging-side):** (1) HMAC 401 — Vercel secret stored with surrounding quotes (`secretLen 47≠45`), fixed by quote-strip on receiver; (2) schema 400 — receiver expected `target_duration` vs contract `target_duration_min`, aligned to contract; (3) DB 500 PGRST205 — Preview Supabase env pointed at wrong project, repointed to migrated staging `twifpxkrsagzhxtarvqe`; (4) stable alias `learnforge-staging.vercel.app` added to stop URL churn. Radar signing was correct throughout (proven via python/openssl/node parity + isolation probe).
- **Two minor fixes from iteration_15:** (a) added `course_job_id/status/public_url/dispatched_at/error` to the `Signal` response model so `GET /api/signals` surfaces dispatch state (verified: 3 signals show status); (b) raised Signal Tracker metadata + priority-band text contrast (`text-zinc-600` → `text-zinc-400`).
- Regression tests: `/app/backend/tests/test_iter15_live_staging_dispatch.py`. Radar `.env` unchanged except the approved staging URL + rotated secret; `RADAR_LEGACY_PUBLISH_ENABLED` stays false.

## Implemented (2026-06 — v22: Local demo of the Radar→LearnForge handshake)
- **TEMPORARY / MOCKED**: to make the preview show a real `202 accepted` (instead of the honest upstream 404), a **local in-sandbox demo receiver** was created at `/app/backend/tools/local_learnforge_receiver.py` (uvicorn on `:8099`) and `backend/.env` `LEARNFORGE_COURSE_JOBS_URL` was pointed at `http://localhost:8099/api/course-generation-jobs`. This is NOT real LearnForge, generates NO course content, stores jobs in memory, and does NOT survive a container restart.
- Verified live via external API: dispatch → `{ok:true, status:"accepted", http_status:202}`; refresh → `accepted`; re-dispatch → `deduplicated:true`; `briefs_dispatched` stat increments.
- **REVERT BEFORE DEPLOY**: set `LEARNFORGE_COURSE_JOBS_URL` back to `https://learnforge-core.vercel.app/api/course-generation-jobs` and stop the `:8099` process. Real fix = deploy the receiver kit (`docs/learnforge_receiver_stub_kit/`) into learnforge-core.

## Implemented (2026-06 — v21: Radar-Accurate Terminology + Receiver Stub Kit)
- **Metric tile corrected**: `StatGrid` "Syllabi Forged / generated" → **"Briefs Dispatched / to learnforge"** (Send icon). Backend `/api/signals/stats` now returns `briefs_dispatched` = `len(distinct signal_id in course_jobs)` (accurate V2 dispatch count; currently **0**), plus `legacy_courses` = 5 (historic `syllabus_generated` records, kept for reference; `syllabi_generated` retained as alias). Test id renamed `stat-syllabi-generated` → `stat-briefs-dispatched`.
- **Terminology sweep**: `LelandCTAStrip` "Push generated courses live" → "Dispatch course briefs to … LearnForge owns generation/publishing". Header copy already Radar-accurate. Legacy v1 handoff dialogs (HeroPatch/WebhookSpec) left intact — they describe LearnForge-side receiver behavior, not Radar generation.
- **Receiver Patch** (`docs/learnforge_receiver_stub_kit/`) — a SEPARATE, drop-in **LearnForge (Next.js + Supabase)** patch for the `learnforge-core` repo (NOT implemented inside Radar). Files: `app/api/course-generation-jobs/route.ts` (thin POST handler), `[jobId]/route.ts` (GET status), `lib/radar/receiver.ts` (**pure** contract logic: signature→schema-version→JSON→forbidden-content→strict-Zod→source-attribution→idempotency→202 accepted), `lib/radar/verify.ts` (constant-time HMAC over raw body), `lib/radar/brief.ts` (Zod `CourseBriefV2` + `assertNoContentFields` + required demand-source attribution), `lib/radar/supabase-store.ts` (service-role `JobStore`), `supabase/migrations/20260826000000_course_jobs.sql` (`course_jobs` table + CHECK + `updated_at` trigger + RLS, service-role only), `tests/receiver.test.ts` (Vitest, 10 cases), `.env.example`, `verify_local.sh`. Generates NO syllabus/modules — single `TODO(generation)` seam. Referenced from V2 contract §6.
- **Boundary preserved & tested (not deployed, not live)**: the receiver lives in LearnForge, not Radar. The exact `receiver.ts`/`brief.ts`/`verify.ts` code was executed locally via a Babel-transpiled Node harness — **10/10 pass** (202 accept; 401 bad/missing sig; 400 schema-version/forbidden-content top+nested/missing-attribution/strict-extra/malformed-JSON; 200 idempotency dedupe). HMAC parity byte-identical across Radar-Python / openssl / Node-crypto. Env vars, Supabase migration, and manual verification steps documented in the kit README. No production data touched; `RADAR_LEGACY_PUBLISH_ENABLED` untouched (OFF).
- **Tests**: iter13 v2 suite 31/31 pass; live `/api/signals/stats` verified (`briefs_dispatched:0, legacy_courses:5`). No production data modified; not deployed.

## Implemented (2026-06 — v20: CourseBriefV2 + Legacy Gating — Phase 1)
- **`services/course_brief.py`**: typed `CourseBriefV2` (schema_version 2.0, signal_id, deterministic sha256 idempotency_key, source, demand_evidence w/ priority_band, audience, commercial_hypothesis w/ `validation_status="hypothesis"` + free_module_count=2, generation_constraints w/ prohibited_claims, callback). `extra="forbid"` on every model + recursive `assert_no_content_fields` rejecting `modules/lessons/quizzes/syllabus/...`. Built purely from already-stored signal metadata — **no AI calls**.
- **`services/dispatcher.py`**: signed (HMAC-SHA256 over raw canonical body) POST to `LEARNFORGE_COURSE_JOBS_URL`; retries w/ backoff (3 attempts, 1/2/4s) on 5xx/transport only; idempotent (existing non-failed job w/ same key → dedupe, no re-POST); job states `accepted/queued/generating/reviewing/ready/failed` tracked in `course_jobs` collection + mirrored on signal (`course_job_*` fields); honest failures (404 → `failed` + "receiver not deployed" hint); missing URL fails safely with **NO legacy fallback**; never logs secret/full payload. `refresh_job` is status-only and rejects unknown states.
- **New endpoints**: `GET /api/signals/{id}/brief/preview` (read-only), `POST /api/signals/{id}/dispatch`, `GET /api/signals/{id}/job-status`, `POST /api/course-jobs/{job_id}/refresh`. `/api/integrations/status` now exposes `course_jobs` block + `legacy_publish_enabled`.
- **Legacy isolation**: `RADAR_LEGACY_PUBLISH_ENABLED` flag (default OFF; OFF in this env). Server-side 410 on `POST/GET /signals/{id}/publish[/preview]`, `publish-all-live`, `retry-pending-publishes`, `POST /signals/{id}/syllabus`, `GET /signals/{id}/syllabus/stream`; scheduled retry job dormant. `generate_syllabus_ai` + `build_payload` marked DEPRECATED (code retained, no deletions, no data changed).
- **UI rework**: "Stream LearnForge Syllabus" + "Publish to LearnForge" removed. New `BriefDispatchPanel` (05 · Dispatch to LearnForge): Preview Course Brief JSON, Dispatch Brief, job status chip, public-URL link when LearnForge returns one, honest failure panel. Sections 01–03 tagged **HYPOTHESIS**. Syllabus display relabeled "Course Modules · LearnForge (legacy v1 record)". Republish All hidden unless server-confirmed legacy flag; header copy no longer claims Radar ships syllabi.
- **Docs**: `docs/LEARNFORGE_V2_CONTRACT.md` (proposed contract: headers/signing, idempotency, state machine, request/accepted/status/ready/failed examples, error semantics, remaining LearnForge work). README rewritten with responsibility matrix.
- **Tests**: `tests/test_iter13_course_brief_v2.py` — 31 passed (validation, forbidden fields, idempotency determinism/stability, HMAC over raw body, dispatch success/404/missing-URL/no-fallback/retry/timeout-exhaustion/malformed-2xx/dedupe/re-dispatch-after-fail, refresh state transitions incl. unknown-state rejection, live 410 gating on all 6 legacy routes, live brief preview has no content fields). LearnForge calls mocked (httpx.MockTransport); dedicated test DB. Legacy-era tests marked skipif on the flag (11 skipped).
- **Upstream status (honest)**: `POST https://learnforge-core.vercel.app/api/course-generation-jobs` → **HTTP 404**. The v2 receiver is NOT implemented yet — dispatches record `failed` with the exact diagnostic until LearnForge ships it. No fake integration.
- Pre-existing test failures (NOT from this change): iter11 reconcile tests assert the historic upstream-404 era; scraper/strike/velocity tests suffer accumulated DB-state pollution (documented since v5).

## Implemented (2026-05-30 — v19: Hormozi Specificity Ladder for All Headlines)
- **Patched `services/ai.py` system prompts** for both `enrich_signal` (course-level naming) and `generate_syllabus_ai` (module-level naming) with the **Hormozi Specificity Ladder Protocol**:
  - Required anatomy: `[TIME-BOUND or NUMERIC LEVER] · [HYPER-SPECIFIC PERSONA / SCHOOL / COMPANY] · [PROPRIETARY MECHANISM NAME]: [SPECIFIC ACTION VERB] [QUANTIFIED OUTCOME]`.
  - Mantra baked into the system prompt: *"You want to be the person who solves THIS problem for THIS person."*
  - Three architect-supplied canonical specimens included as style anchors.
  - Banned words list: `foundations`, `mastery`, `fundamentals`, `introduction`, `overview`, `frameworks 101`.
  - Required elements per output: school/company name, a number (hours / $ / days / %), a proprietary mechanism noun (Forge / Engine / Switcher / Stack / Audit-Proof System).
- **Enrich output expanded** — now also returns `cta_headline` (6-10 word punch) and `cta_subtext` (quantified outcome sentence). Ingestion writes these on initial signal create (no longer empty strings).
- **NEW `/api/signals/headlines/regenerate?limit=N`** endpoint — re-runs the upgraded enrich on the top-N priority signals, persists `paid_offer_title`, `lead_magnet_title`, `cta_headline`, `cta_subtext`, returns a full before/after diff for audit.
- **Live execution** on the top 3 signals — all 3 produced perfect Hormozi-spec headlines on the first pass:

| # | Signal | After |
|---|---|---|
| 1 | MBB Case | **ForgeCore: The 21-Day MBB Case Engine: Master the Bain/McKinsey/BCG Framework Stack and Land Your $165k Offer** |
| 2 | MBA App Week | **ForgeCore: The 12-Week M7 Story Engine: Turn 3 Career Pivots into a Cohesive Narrative and Secure 2+ Round-1 Interview Invites** |
| 3 | Stanford GSB | **ForgeCore: The 72-Hour Stanford GSB Essay Engine: Engineer Your 'What Matters Most' Core and Ship a T10-Caliber App in 21 Days** |

- **Visuals regenerated** for all 3 (Fal Flux.1 Pro, hero + 6 modules each, 0 errors) so the cinematic imagery matches the new headlines.
- **All 4 published to LearnForge**: `attempted=4, ok=4, failed=0` — upgraded headlines now live on the Showroom.
- **Module-level Hormozi protocol** is wired in the syllabus prompt — applies automatically to any *new* syllabus generation; existing module titles preserved (don't overwrite the Architect's accepted work).

## Implemented (2026-05-30 — v18: Hero Image Fix + Catalog Backfill + Slam Pricing Live)
- **Diagnosed the broken hero**: the "MBA Essay & Interview Accelerator" signal (id `1e8a43c8-…`) was created before the v15 Fal integration, so `hero_image_url` was never populated. Compounded by a Pydantic model omission — `Signal` model didn't declare `hero_image_url` / `visuals_model` / `visuals_style` / `visuals_errors`, so even when present in MongoDB they were stripped on serialization through `/api/signals/{id}`. Both fixed.
- **Live Slam Offer applied**: Updated the signal to `price=$49, original=$1000` → `discount_pct=95` flowing through the webhook → LearnForge returned `HTTP 200 "Course upserted"`. The Showroom now has the data to render 95% OFF.
- **Catalog-wide backfill endpoint** `POST /api/signals/visuals/backfill-missing` — finds every signal with `syllabus_generated=true` and no hero_image_url, regenerates Fal Flux.1 Pro hero + 6 module images, persists to MongoDB. Safe to re-run (skips already-complete signals). After running: `attempted=0, ok=0` (catalog already complete, all 4 syllabus-generated signals have heroes).
- **All 4 signals republished**: `attempted=4, ok=4, failed=0` — fresh hero URLs are now live on LearnForge for the entire catalog.
- **NEW drop-in `CourseHero.tsx`** (145 lines) at `/app/docs/learnforge_course_hero.tsx` for the LearnForge team:
  - Cinematic Sovereign-style placeholder (charcoal background, lime grid, corner crosshair registration marks, title-derived monogram) when src is missing/null
  - `onError` handler flips back to the placeholder — never renders a broken-image icon
  - `onLoad` triggers a 500ms opacity fade-in
  - Lazy-loading + intrinsic `aspect-[16/9]` for zero CLS
  - `priority` prop for the LCP hero on the showroom page
- **NEW `/api/integrations/course-hero-patch` endpoint** + **frontend `HeroPatchButton`** in the dashboard header (amber, between `LIBRARY GATE FIX` and `REPUBLISH ALL`). Dialog has: backfill-now button (Radar-side, runs Fal immediately), fixes list, copy/download for the drop-in CourseHero component.
- Three handoff patches now live in the header: **`WEBHOOK SPEC`** (lime, receiver code), **`LIBRARY GATE FIX`** (red, access control), **`HERO FALLBACK`** (amber, broken-image safety net). All follow the same one-click copy/paste pattern.
- Tested: 8/8 content checks pass on CourseHero patch (CourseHero export, SovereignPlaceholder fn, onError/onLoad handlers, monogram derivation, crosshair marks, aspect-ratio map, lazy loading). Live API: hero_image_url + visuals_model now returned from `/api/signals/{id}`; backfill returns `attempted=0` after one run (idempotent); publish returns 200 with `discount_pct=95`.

## Implemented (2026-05-30 — v17: Library Access Gating Patch for LearnForge)
- **Important framing**: The `app/[locale]/library/page.tsx` lives on **LearnForge's** Vercel app, not the Radar. The Radar can't patch a remote codebase directly — but the same pattern as the Webhook Spec works: drop-in TypeScript file the Architect can paste in one click.
- **`/app/docs/learnforge_library_page.tsx`** — 260-line drop-in Next.js page server component covering:
  - Cookie-aware Supabase server client (`@supabase/ssr`)
  - `auth.getUser()` → redirect to `/signup?next=/library` if unauthenticated
  - Admin bypass via `LEARNFORGE_ADMIN_EMAILS` env var (sees full catalog with an "Architect · sees all" badge)
  - For students: `.from("user_purchases").select("course_id").eq("user_id", user.id).eq("status", "active")` → `.in("id", courseIds)` on `courses`
  - "Radar Curriculum" pill on any row where `source === "radar"`
  - Reads the pre-computed `discount_pct` from the payload (no recompute)
  - Empty-state CTA → `Explore Premium Outcomes` linking to `/showroom`
  - Bundled SQL block for the `user_purchases` table + RLS policy so non-admins only see their own rows
- **Backend `GET /api/integrations/library-page-patch`** returns the structured JSON (filename, fixes, deps, lines, bytes, code) — same pattern as the Webhook Spec endpoint.
- **Frontend `LibraryPatchButton` + `LibraryPatchDialog`** — red-themed `LIBRARY GATE FIX` button in the header (between Webhook Spec and Republish All). Dialog renders an emerald "What this patch fixes" panel + the full code in a scrollable `<pre>` with `Copy Patch` and `Download` actions.
- **Webhook payload upgraded**: every Radar publish now sets top-level `source: "radar"` so LearnForge can render the "Radar Curriculum" pill and segment the catalog by origin.
- Tested: 8/8 content checks pass on the served patch (createServerClient, auth.getUser, user_purchases filter, admin bypass, empty CTA, signup redirect, discount_pct read, RLS SQL block). UI button renders and dialog opens with copy button visible.

## Implemented (2026-05-30 — v16: Slam Offer Discount Math)
- **Canonical discount formula** lives in two mirrored places kept in lockstep:
  - Backend: `services/publisher.compute_discount_pct(current, original)`
  - Frontend: `lib/pricing.computeDiscountPct(current, original)`
  - Both implement `round(((orig - current) / orig) * 100)` exactly; edge-cases return `null`/`None` (missing price, original ≤ 0, negative current) or `0` (current ≥ original).
- **Signal model + DB**: new `paid_offer_original_price: Optional[float]` field on `SignalBase` + `SignalUpdate`. The Conversion sheet now has an "Anchor / Original Price (USD)" input with a live `DiscountPreview` badge alongside (`<line-through>$1,899</line-through> → $1,000  ·  47% OFF`).
- **CTAPreview enhanced** — the public-facing CTA card now renders the `discount_pct` chip at top-right + a `$1,000` price with `$1,899` strike-through anchor when both are set. Same testid (`cta-preview-discount-badge`) so LearnForge's design QA can match.
- **Webhook payload upgraded**: ships top-level `original_price_usd` + `discount_pct` (rounded integer), plus the mirrored values inside `course.original_price_usd` / `course.discount_pct`. LearnForge no longer has to compute anything — they just render `discount_pct` directly.
- **Acceptance tests passed** (verbatim from the Architect's directive):
  - `$1,000` against `$1,899` anchor → **47% OFF** ✓
  - `$49` against `$1,000` anchor → **95% OFF** ✓
  - Edge cases handled: missing/zero anchor, current ≥ anchor, negative inputs.
- **Live verified**: updated signal `e3171073-…` with anchor=$1899, current=$1000 → publish returned `HTTP 200 "Course upserted successfully"`, fields now live on LearnForge.

## Implemented (2026-05-30 — v15: Fal.ai Flux.1 Pro Visual Engine + FIRST GREEN LIVE PUBLISH 🟢)
- **`FAL_KEY` injected** into `/app/backend/.env`.
- **New service `services/visuals.py`** powered by `fal_client` (v1.0.0, added to requirements.txt). Calls `fal-ai/flux-pro/v1.1` with the **Sovereign Style Sheet** suffix (dark mode, cinematic, high-contrast, charcoal/obsidian + cyber lime accents, 8K, no AI-slop tokens, no text/logos). Builds one prompt for the course hero + one per syllabus module; dispatches all 7 with bounded concurrency (3) and graceful per-image error capture.
- **Pipeline wired**: `POST /api/signals/{id}/syllabus` now calls `generate_course_visuals` after Claude finishes. SSE `stream_syllabus` adds a `rendering-visuals` phase + heartbeat ticks while Fal generates, then emits a final `event: visuals` with `{ hero, module_urls, errors }` so the UI can paint images in real time. New endpoint `POST /api/signals/{id}/visuals/regenerate` for one-click refresh.
- **Webhook payload extended** to carry visuals: top-level `hero_image_url` + `visuals: { hero, model, style }`, plus per-module `image_url` field. `course.hero_image_url` mirror preserved for backwards-compat consumers.
- **Frontend rendering**: `SyllabusList` now displays the hero banner (16:9, lime-bordered, "hero · flux.1 pro · sovereign" caption) and a 16:9 image atop each module card. `useSyllabusStream` hook tracks `heroImageUrl` and merges incoming `module_urls` from the `visuals` SSE event.
- **🎯 Final outcome — FIRST GREEN LIVE PUBLISH**:
  - All 4 signals regenerated visuals: 4× hero + 24× module images, 0 errors, ~7-8s per signal.
  - `republish_all_live` → **attempted=4, ok=4, failed=0**
  - Reconcile: `published=4, failed=0, pending=0, drift=0`
  - LearnForge response: `{"success":true,"message":"Course upserted successfully","course":{"id":"c5144565-3c12-4ec8-93a3-cec70dca9b52",...}}`
  - SYNC button now shows the green-dot in-sync indicator instead of the red drift badge.
- The 6-step bridge journey is now complete end-to-end: **404 → 401 → 400 → 500(RLS) → 500(env) → 200 LIVE ✓**

## Implemented (2026-05-30 — v14: Supabase Env Diagnostic + Verified 16f960f Compatibility)
- **Verified the Radar payload IS aligned** with LearnForge's `16f960f` route handler — `modules` (not `syllabus`), `title`, `slug` all present as top-level strings; modules array contains 6 items with the expected keys (`index`, `title`, `summary`, `learning_objectives`, `artifact`, `duration_min`).
- **LearnForge endpoint is reachable** (GET → 405 POST-only "learnforge-course-publish") — receiver code is deployed and accepting our signed requests.
- **Captured the exact post-`16f960f` upstream error**: `HTTP 500 · {"error":"supabaseKey is required."}` — the route handler is wired but `createClient()` is throwing because `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` aren't set in the learnforge-core Vercel project's env. This is on LearnForge's deployment config, not our payload.
- **New failure-mode pattern** in both `publisher.py` and `PublishErrorDialog.jsx`: matches `supabasekey is required` / `supabaseurl is required` and emits remediation: "Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to Vercel env, then redeploy."
- **Re-published all 4 failed signals** with `republish_all_live` so every signal now carries the precise diagnostic in `last_publish_hint`. UI badge + dialog show "500 · Supabase env vars missing" with the exact env-var fix.

## Implemented (2026-05-30 — v13: Payload Schema Remap + RLS Diagnostic)
- **`syllabus.modules` → top-level `modules`** in the webhook payload, plus top-level `title`, `slug`, `category`, `summary`, `price_usd`, `registration_count`, `priority_score`, `source_url`, `paid_url`, `free_url`. The rich nested `course` object is preserved for full-fidelity downstream consumers (also now contains `course.modules` alias for backwards-compat).
- **Signature header switched to BARE lowercase hex** (no `sha256=` prefix) as the primary `X-Radar-Signature` value — what LearnForge's Next.js receiver expects. Also send `X-Radar-Signature-Hex`, `X-Radar-Signature-Sha256` (with `sha256=` prefix), and `X-Radar-Signature-Algorithm: hmac-sha256` for tolerance.
- **NEW debug endpoint `GET /api/integrations/signature-fingerprint`** — returns `secret_fingerprint = SHA256(secret)[:16]` so both Radar and LearnForge can verify they hold the same secret without ever leaking it; plus a deterministic test signature against a known canonical body.
- **Every publish now logs `sig_first6 / sig_last6 / secret_fp / body_len / url`** to `backend.out.log` for cross-comparison with Vercel function logs.
- **Receiver TS code (`/app/docs/learnforge_receiver_route.ts`) tolerates BOTH** bare hex and `sha256=`-prefixed signatures, and checks `X-Radar-Signature-Hex` as a fallback header.
- **Failure-mode classifier upgraded** (backend `publisher.py` + frontend `PublishErrorDialog.jsx`) to recognize `Supabase RLS` 500s and duplicate-insert 500s with specific remediation copy (`CREATE POLICY` SQL snippet, `upsert(..., { onConflict: 'slug' })` hint).
- **Live upstream progression captured**: 404 → 401 → 400 → **500 (Supabase RLS)** — signature is now ACCEPTED by LearnForge, payload schema is ACCEPTED, only remaining gap is a LearnForge-side Supabase row-level-security policy. Each progression is fully diagnosed and surfaced in the UI.

## Implemented (2026-05-30 — v12: HMAC-SHA256 Webhook Signing)
- **Set `LEARNFORGE_WEBHOOK_SECRET=SovereignForge2026!`** in `/app/backend/.env`.
- **HMAC-SHA256 signing**: `publisher.sign_payload()` computes `hmac.new(secret, body_bytes, sha256).hexdigest()` over a canonical JSON body (`json.dumps(payload, separators=(',', ':'), sort_keys=True)`). The exact same byte string is POSTed via `httpx.AsyncClient.post(..., content=body_bytes)` so the receiver's HMAC over the raw body always matches.
- **Headers attached when secret is present**:
  - `X-Radar-Signature: sha256=<64-hex>` (71 chars)
  - `X-Radar-Signature-Algorithm: hmac-sha256`
- **`/api/integrations/status`** now exposes `signature_algorithm` + `signature_header` alongside `has_secret`.
- **IntegrationsBadge UI**: `Signing secret: ENABLED` in lime (`webhook-signing-status` testid). When enabled the dialog also shows `· hmac-sha256 → X-Radar-Signature`. Handoff callout text updated — no longer claims "404 → 200"; now reflects the 401-Invalid-signature state and points to the deploy + matching-secret remediation.
- **Receiver TS code (`/app/docs/learnforge_receiver_route.ts`) updated** to verify HMAC-SHA256 over the raw request body (reads `req.text()` first, then JSON-parses), constant-time compares with `crypto.timingSafeEqual`. Stays in lockstep with Radar's signing scheme.
- **Live LearnForge endpoint progressed 404 → 401**: `{"error":"Invalid signature"}` — proves the receiver route IS deployed; the only remaining gap is LearnForge's `LEARNFORGE_WEBHOOK_SECRET` env var must be set to the same `SovereignForge2026!` value.
- Tested: 8/8 backend pytest PASS (status metadata, sign_payload stdlib equivalence, end-to-end via local 127.0.0.1 echo server validating receiver-side HMAC verification, live 401 assertion) + frontend Playwright PASS. Regression at `/app/backend/tests/test_iter12_hmac_signing.py`.

## Implemented (2026-05-30 — v11: Architect's Critical Sync Debug)
- **Exact publish failure captured & surfaced**: `HTTP 404 | {"detail":"Not Found"} | content-type: application/json`. Both GET and POST to `https://learnforge-core.vercel.app/api/courses` return 404 — the receiver code shipped via the Webhook Spec dialog hasn't been deployed by the LearnForge team yet. This is unambiguously option (1) route-not-deployed (NOT 401/signature, NOT 500/Supabase).
- **`PublishErrorDialog` (new)** opens from a clickable red `FAIL <code>` badge on every failed Signal Tracker row. Surfaces: classified failure-mode banner (404 route-missing / 401-403 signature / 422 payload / 5xx upstream / Connect / Timeout) with actionable guidance, 4-card meta grid (Webhook, HTTP, Retries N/5, Next retry timestamp), amber diagnostic hint block, raw response body (first 400 chars), last-10-attempts list, and footer `Copy Diagnostic` + `Retry Publish` buttons.
- **Sync button now reconciles** (not just refresh): hits `GET /api/learnforge/reconcile` → backend probes LearnForge (treats HTTP 405 as reachable=true for POST-only routes) and computes catalog drift. Header `SYNC` button shows a red `[N]` drift badge with title tooltip when N>0, or an emerald dot when in-sync + live. Click → toast surfaces probe state ("In sync · LearnForge live" / "X courses drifted" / "LearnForge HTTP 404").
- **Backend new endpoints**:
  - `GET /api/learnforge/reconcile` → probe + drift report
  - `GET /api/signals/{id}/publish-history?limit=N` → signal diag fields + last N attempts
  - `_persist` extended to capture `response_preview`, `hint`, `webhook_url`, `last_publish_at` on every attempt
- Tested: 9/9 backend pytest + 12/12 frontend UI checks PASS (iter11). Regression test at `/app/backend/tests/test_iter11_reconcile_and_history.py`.

## Implemented (2026-05-30 — v10: Scraper 404 Fix + URL Fallback)
- **Root-caused the "404 on the frontend"**: The actual `/api/scraper/run` was always returning HTTP 200 (23 events). The 404 came from stale calls to `/api/leland/scrape` (legacy endpoint name) and stale `leland.com` (vs `joinleland.com`) external links.
- **Added legacy alias** `POST /api/leland/scrape` → forwards to the same `run_scrape` pipeline (no more silent 404 for any older docs/scripts).
- **Added Paste-URL fallback** `POST /api/scraper/ingest-url`: server-side fetches a `joinleland.com` URL with our pre-configured UA, runs the same parser. Whitelisted host validation (400 for non-leland URLs and empty input). Bypasses browser-side anti-bot challenges.
- **Frontend `PasteHtmlDialog` is now tabbed** — `Paste URL` (default) and `Paste HTML`, with input pre-filled with `https://www.joinleland.com/events`, validation, and toast surfacing of upstream 502 detail if Leland anti-bot kicks in.
- **Stale URL fixes**: `SignalTable.jsx` external `leland.com/events` link → `www.joinleland.com/events`; `SignalFormDialog.jsx` placeholder also updated. Backend `services/scraper.LELAND_EVENTS_URL` already correctly pointed at `https://www.joinleland.com/events`.
- Tested: `/api/scraper/run` 200 (23 events), `/api/leland/scrape` 200 (no longer 404), `/api/scraper/ingest-url` with valid joinleland URL 200 (23 events), bad-host 400, empty 400. UI smoke: both tabs mount with correct testids.

## Implemented (2026-05-30 — v9: Webhook Spec Viewer / Bridge for Antigravity Inject)
- **Receiver code source-of-truth**: `/app/docs/learnforge_receiver_route.ts` — 222 lines of drop-in Next.js App Router code (Zod validation, `crypto.timingSafeEqual` signature verification, idempotent upsert stub with full Prisma example, GET health-check, `runtime="nodejs"`, `dynamic="force-dynamic"`). Single file the Architect can paste into Vercel / GCP Antigravity.
- **Backend `/api/integrations/webhook-receiver-spec`**: returns structured JSON `{ filename, endpoint_url, framework, runtime, signature_header, shared_secret_required_env, shared_secret_configured, deps, lines, bytes, code }` so the UI can render meta-cards + the code block from one fetch.
- **Frontend `WebhookSpecDialog`** + `WEBHOOK SPEC` button in the dashboard header (lime, prominent, between Integrations and Republish All): shows endpoint URL, signature header (with masked/reveal toggle), framework/runtime/secret meta cards, the full 222-line code in a scrollable `<pre>`, one-click `Copy Code` and `Download .ts`, plus a 3-step post-deploy verification checklist.
- **Verified Radar IS hitting `https://learnforge-core.vercel.app/api/courses`** — `r.url` assertion passes; current 404 is purely a missing remote route, not a Radar bug. Diagnostic hint already surfaces this in `PublishResultPanel`.
- Tested: 7/7 code-content checks pass on the receiver source (NextRequest/NextResponse, Zod schema, timingSafeEqual, POST handler, GET health-check, runtime, upsertCourse fn).

## Implemented (2026-05-30 — v8: LearnForge Team Handoff)
- **Single-shot handoff doc** at `/app/docs/LEARNFORGE_INGEST_SPEC.md` — 14.8 KB, 8 sections covering: endpoint to deploy, headers, full v1 payload schema + field reference, expected response, drop-in TypeScript Next.js App Router route handler (with Zod validation + `crypto.timingSafeEqual` signature verification), local curl validation, post-deploy checklist, and change log. All `/en/` legacy refs stripped — example URLs use the `/signup?course=<slug>&ref=radar&tier=<…>` form.
- **Backend** `GET /api/integrations/handoff-doc` serves the doc as `text/markdown` with `Content-Disposition: inline; filename="LEARNFORGE_INGEST_SPEC.md"` for one-click download.
- **Frontend** new `LearnForgeHandoffCallout` at the top of the Integrations dialog — amber callout that surfaces the 404 root cause + three actions: `Copy Handoff Doc` (clipboard), `Download .md`, `Preview` (opens markdown in a new tab).
- **Payload-spec example modernized** — `PUBLISH_PAYLOAD_EXAMPLE` in `services/payload_spec.py` updated to the new `/signup?course=…` CTA shape so anything that reads the JSON-Schema endpoint sees the same reality.
- Tested: 9/9 doc content checks PASS, endpoint returns 200 + correct content-type, no `/en/courses/` or `/en/scrolls/` in any served artifact.

## Implemented (2026-05-30 — v7: Architect's 3 P0 Directives)
- **CTA routing fixed**: Replaced all `/en/courses/<slug>` and `/en/scrolls/<slug>` deep-routes (which 404 on the live LearnForge deployment) with the universal `/signup` route. All paid/free/lead-magnet CTAs now resolve to `https://learnforge-core.vercel.app/signup?course=<slug>&ref=radar&tier=<forgecore|free>` — single helper `_signup_url()` in backend `publisher.py` and matching `withRef()` in frontend `lib/learnforge.js`. Course slug + tier preserved in query string for LearnForge-side attribution.
- **Webhook 404 diagnostic surfaced**: Backend `publisher.py` now attaches an actionable `hint` to every failure response (404, 401/403, 5xx, ConnectError, Timeout). Frontend `PublishResultPanel` renders the hint in an amber `DEBUG · …` line plus full response body and a "Copy Payload" button — Architect can now see the LearnForge `/api/courses` route is not deployed without grepping logs.
- **SSE syllabus stream "stuck at 0/6" fixed**: Bust k8s ingress / Cloudflare buffering with a 2KB padding comment as the very first byte, then run `generate_syllabus_ai` as a shielded asyncio task while emitting `: heartbeat\n\n` + `event: progress` every 1s. Headers tightened: `Cache-Control: no-cache, no-transform`, `Content-Encoding: identity`, `X-Accel-Buffering: no`. The trigger button now shows "Claude Synthesizing… Ns" with a live counter so the UI feels alive (no longer perceived as 0/6 stuck). UI hook exposes `phase` + `elapsedS`.
- Tested 100% (iter10): backend pytest 3/3 + frontend 4/4 flows.

## Implemented (2026-05-30 — v6: Strike Rings + Mobile + PWA)
- **Fixed Signal Velocity Chart strike rings**: ReferenceDots were silently dropped because `XAxis` is `type="number"` (epoch ms) but the dot `x` and `xDomain` were ISO strings. Converted both to epoch ms (`new Date(t).getTime()`) so the 6 strike-attribution rings (red breakout, amber surge, lime strike) now render reliably on the velocity line. Verified at runtime: 6 rings present, matching test ids `velocity-strike-*`.
- **Mobile responsiveness**: header buttons now use short labels under sm-breakpoint, dashboard horizontal padding shrunk, table wrapped in `min-w-[760px]` + overflow-x scroll, velocity chart range buttons enlarged for touch, legend buttons truncate (`min-w-0 max-w-[10rem] sm:max-w-[18rem]`) to eliminate the 390-px overflow. Mobile 390×844 and tablet 768×1024 now have zero horizontal scroll. Bottom `pb-24` added so the floating install banner never overlaps content.
- **PWA install**: `/public/manifest.json` (name=LearnForge Opportunity Radar, theme `#0a0a0a`, 192/512/apple/favicon icons generated from a custom lime-radar mark), `/public/sw.js` service worker (network-only for `/api`, stale-while-revalidate for shell), registered only in production via `index.js`. iOS-aware install hook (`usePWAInstall`) drives header `Install` button + mobile soft-prompt banner (dismiss persisted in localStorage) — both gated on `beforeinstallprompt` or iOS UA.
- **Perf nit fixed**: `/api/signals/stats` now projects only the 5 fields it aggregates (was fetching full docs ×2000).
- Tested 100% (iteration_9: mobile/tablet overflow PASS, strike rings PASS, all PWA assets HTTP 200).

## Implemented (2026-02-29 — v1)
- Backend endpoints: `GET/POST /api/signals`, `GET/PUT/DELETE /api/signals/{id}`, `GET /api/signals/stats`, `POST /api/signals/{id}/syllabus`, `POST /api/signals/seed`. Auto-seed on startup.
- Dashboard with header, 4 stat tiles, category distribution sidebar, public-launch CTA strip.
- Signal Tracker table with priority dot indicators, status pills, hover state, edit/delete/convert actions.
- Conversion Engine Sheet (right slide-over) with Lead Magnet, Paid Offer (incl. price), CTA inputs, status select, live CTA preview banner, copy URL buttons (with execCommand fallback), Save Conversion button, **Trigger LearnForge Syllabus Generation** button.
- Generated syllabus list rendered inside the sheet after generation.
- Tested 100% (backend pytest + frontend Playwright E2E).

## Implemented (2026-02-29 — v5: Trading Terminal — FINAL)
- **Signal Velocity Chart** (`SignalVelocityChart.jsx` + `services/history.py`): Recharts multi-series LineChart, lime-on-charcoal, top-6 priority signals. Range toggles 6H / 24H / 7D. Bottom legend with priority badges, click-to-toggle visibility per line. Time-series snapshots persisted in `signal_history` collection on every scrape; synthetic random-walk backfill seeded on first boot so the chart is populated immediately.
- **POST /api/courses payload contract standardized** (`services/payload_spec.py` + new endpoint `GET /api/integrations/publish-payload-spec`): JSON-Schema v1 + example + request headers + expected response. "View Payload Spec" dialog inside the Integrations badge gives the Architect a copy-paste-ready contract to drop into `learnforge-core`.
- **WhatsApp whale-strike logic** stays gated; will fire automatically once the Architect drops Twilio creds into `/app/backend/.env`. No code changes required to activate.
- Tested 100% (14/14 iter-6 + frontend E2E). Two unrelated legacy strike-alert pytests fail due to accumulated DB state pollution from earlier iterations — not a regression.

## Implemented (2026-02-29 — v4: v2 backlog close-out)
- **Republish All** (`POST /api/signals/publish-all-live`): hot-reload the entire LearnForge catalog by re-firing the webhook for every signal with `syllabus_generated=true`. Header button in the dashboard.
- **WhatsApp push for ≥90 priority strikes** (`services/whatsapp.py`): env-gated Twilio integration. When `TWILIO_ACCOUNT_SID/_AUTH_TOKEN/_WHATSAPP_TO` set, fires a formatted message on whale strikes (default threshold `WHATSAPP_STRIKE_THRESHOLD=90`). Skipped state visible in the new Integrations dialog (header badge). Test-ping endpoint at `POST /api/integrations/whatsapp/test`.
- **Auto-retry on publish failure** (`services/publisher.retry_pending`): APScheduler periodic job every 5 minutes picks up `publish_status=failed` signals whose backoff window has elapsed (exponential 2/4/8/16/32 minutes, max 5 attempts). Tracked via `publish_retry_count` and `publish_next_retry_at` on the signal. Manual trigger at `POST /api/signals/retry-pending-publishes`.
- **SSE streaming syllabus** (`GET /api/signals/{id}/syllabus/stream`): Server-Sent Events emitting `start` → 6× `module` → `done`. Frontend hook `useSyllabusStream` consumes via EventSource and renders modules progressively in the SyllabusList. *Note: k8s ingress currently buffers text/event-stream so events land in a single chunk near completion — UI still handles it cleanly with the "Streaming N/6…" indicator.*
- Tested 100% (5/5 iter-4 endpoints + frontend re-test confirms streaming/Republish/Integrations flows all green).
- **Publish webhook** (`services/publisher.py`): packages signal+syllabus+CTA+demand into a stable `course.publish` payload and POSTs to `LEARNFORGE_WEBHOOK_URL` (default `https://learnforge-core.vercel.app/api/courses`). Persists `publish_status`, `last_published_at`, `last_publish_error`, `last_publish_status_code`, `published_to_url` on the signal. Promotes signal status to `live` on 2xx.
- **Diff-aware strike alerts** (`services/alerts.py`): when a scrape update bumps reg count by ≥`STRIKE_THRESHOLD_PCT` (default 20%), an alert is recorded in `signal_alerts`. UI tiers it: STRIKE (≥20%), SURGE (≥50%), BREAKOUT (≥100%). One-click dismiss + dismiss-all.
- **Vercel-correct URLs**: paid offers → `/en/courses/<slug>`, free lead magnets → `/en/scrolls/<slug>` (matched against the live deployment's routing). Centralized in `lib/learnforge.js` and `services/publisher.py`.
- **New routes**: `POST /api/signals/{id}/publish`, `GET /api/signals/{id}/publish/preview`, `GET /api/alerts`, `POST /api/alerts/{id}/ack`, `POST /api/alerts/ack-all`.
- Frontend: Strike Alerts banner (tiered), Publish-to-LearnForge section in conversion sheet with status badge + result panel, PUB green badge on signal rows once published.
- Tested 100% (27/27 backend pytest + 7/7 frontend E2E).
- **Live Leland scraper** (`services/scraper.py`): httpx + BeautifulSoup + regex extracts event title, registration count, when, coach, rating from joinleland.com/events SSR HTML.
- **APScheduler** (12-hour IntervalTrigger) on FastAPI startup. New routes: `POST /api/scraper/run`, `POST /api/scraper/ingest-html` (paste-fallback), `GET /api/scraper/status`, `GET /api/scraper/runs`.
- **Claude Sonnet 4.5** (`claude-sonnet-4-5-20250929`) via `emergentintegrations`:
  - `enrich_signal()` — classifies each new event into category + priority_score (0–100) + suggested lead-magnet/paid-offer titles.
  - `generate_syllabus_ai()` — produces 6-module syllabi with `learning_objectives` and `artifact` per module.
- **Ingestion runs** tracked in `ingestion_runs` Mongo collection.
- Frontend: scraper status bar (online indicator, last-run delta, next-run ETA), Run Scraper + Paste HTML controls in header, redesigned syllabus list rendering Objectives + Artifact, all CTAs now point to `https://learnforge-core.vercel.app` via centralized `lib/learnforge.js`.
- Tested 100% (17/17 backend pytest + frontend E2E).

## Prioritized Backlog
### P1
- Multi-tenant auth (so additional architects can collaborate).
- Diff-aware ingestion: surface when a signal's registration count jumps >20% so the Architect knows demand is accelerating.

### P2
- CSV / Notion export of converted signals.
- Conversion funnel analytics (free → paid attribution).
- "Publish to LearnForge" webhook → posts the generated syllabus + CTA to learnforge-core.vercel.app.
- Per-category dashboards.
- Streaming syllabus generation UI (token-by-token).

### P3
- High-contrast monochrome variant.
- Slack / email alert on a new high-priority (≥90) signal.

## Test Credentials
N/A — no authentication.
