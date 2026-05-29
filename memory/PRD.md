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

## Implemented (2026-02-29 — v2: Scrape → Signal → Syllabus pipeline)
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
