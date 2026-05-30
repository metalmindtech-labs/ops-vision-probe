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
