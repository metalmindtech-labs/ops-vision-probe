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

## Prioritized Backlog
### P1
- Leland event-stream auto-ingest (live scraper or scheduled job).
- AI-powered syllabus generation (swap in `emergentintegrations` Claude/GPT) gated behind a feature flag.
- Multi-tenant auth (so additional architects can collaborate).

### P2
- CSV / Notion export of converted signals.
- Conversion funnel analytics (free → paid attribution).
- Bulk priority recalculation based on registration deltas over time.
- Public LearnForge course landing page generation (mirror the dashboard CTA preview).

### P3
- Dark-mode-only locked, but consider a high-contrast monochrome variant.
- Per-category dashboards.

## Test Credentials
N/A — no authentication.
