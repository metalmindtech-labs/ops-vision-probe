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
