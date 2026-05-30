from fastapi import FastAPI, APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import asyncio
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
import re
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.ingestion import run_scrape, ingest_html, latest_run
from services.ai import generate_syllabus_ai
from services.publisher import (
    publish_signal,
    build_payload,
    republish_all_live,
    retry_pending,
)
from services.alerts import list_alerts, ack_alert, ack_all
from services.whatsapp import get_status as whatsapp_status, send_whatsapp
from services.history import (
    get_velocity,
    backfill_synthetic,
    history_count,
    purge_synthetic,
    snapshot_all_signals,
)
from services.payload_spec import (
    PUBLISH_PAYLOAD_SPEC,
    PUBLISH_PAYLOAD_EXAMPLE,
    HEADERS_SPEC,
    EXPECTED_RESPONSE,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="LearnForge Opportunity Radar API")
api_router = APIRouter(prefix="/api")

scheduler = AsyncIOScheduler(timezone="UTC")


# -------- Helpers --------

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-") or "course"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------- Models --------

class SignalBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_title: str
    category: str
    registration_count: int = 0
    priority_score: int = 50
    source_url: Optional[str] = None
    notes: Optional[str] = None
    lead_magnet_title: Optional[str] = None
    lead_magnet_description: Optional[str] = None
    paid_offer_title: Optional[str] = None
    paid_offer_description: Optional[str] = None
    paid_offer_price: Optional[float] = None
    cta_headline: Optional[str] = None
    cta_subtext: Optional[str] = None
    status: str = "tracked"


class SignalCreate(SignalBase):
    pass


class SignalUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_title: Optional[str] = None
    category: Optional[str] = None
    registration_count: Optional[int] = None
    priority_score: Optional[int] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None
    lead_magnet_title: Optional[str] = None
    lead_magnet_description: Optional[str] = None
    paid_offer_title: Optional[str] = None
    paid_offer_description: Optional[str] = None
    paid_offer_price: Optional[float] = None
    cta_headline: Optional[str] = None
    cta_subtext: Optional[str] = None
    status: Optional[str] = None


class Signal(SignalBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_magnet_slug: Optional[str] = None
    paid_offer_slug: Optional[str] = None
    syllabus_generated: bool = False
    syllabus_modules: List[dict] = Field(default_factory=list)
    publish_status: Optional[str] = None
    last_published_at: Optional[str] = None
    last_publish_error: Optional[str] = None
    last_publish_status_code: Optional[int] = None
    published_to_url: Optional[str] = None
    publish_retry_count: Optional[int] = 0
    publish_next_retry_at: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


def derive_slugs(signal: dict) -> dict:
    if signal.get("lead_magnet_title"):
        signal["lead_magnet_slug"] = slugify(signal["lead_magnet_title"])
    if signal.get("paid_offer_title"):
        signal["paid_offer_slug"] = slugify(signal["paid_offer_title"])
    return signal


# -------- Signal CRUD --------

@api_router.get("/")
async def root():
    return {"service": "LearnForge Opportunity Radar", "status": "online"}


@api_router.get("/signals", response_model=List[Signal])
async def list_signals():
    docs = await db.signals.find({}, {"_id": 0}).sort("priority_score", -1).to_list(1000)
    return docs


@api_router.get("/signals/velocity")
async def signals_velocity(hours: int = 24, limit: int = 6, ids: Optional[str] = None):
    """Return time-series snapshots for the top-N signals.

    Query params:
      - hours: lookback window (default 24, max 168)
      - limit: number of signals (default 6, max 12)
      - ids: optional comma-separated signal IDs (overrides ranking)
    """
    hours = max(1, min(int(hours), 168))
    limit = max(1, min(int(limit), 12))
    signal_ids = [s for s in (ids or "").split(",") if s] if ids else None
    return await get_velocity(db, signal_ids=signal_ids, hours=hours, limit_signals=limit)


@api_router.get("/signals/stats")
async def signal_stats():
    docs = await db.signals.find(
        {},
        {
            "_id": 0,
            "priority_score": 1,
            "registration_count": 1,
            "status": 1,
            "category": 1,
            "syllabus_generated": 1,
        },
    ).to_list(2000)
    total = len(docs)
    high_priority = sum(1 for d in docs if (d.get("priority_score") or 0) >= 80)
    total_reg = sum((d.get("registration_count") or 0) for d in docs)
    converting = sum(1 for d in docs if d.get("status") == "converting")
    live = sum(1 for d in docs if d.get("status") == "live")
    syllabi = sum(1 for d in docs if d.get("syllabus_generated"))
    categories: dict = {}
    for d in docs:
        cat = d.get("category", "Uncategorized")
        categories[cat] = categories.get(cat, 0) + 1
    return {
        "total_signals": total,
        "high_priority": high_priority,
        "total_registrations": total_reg,
        "converting": converting,
        "live": live,
        "syllabi_generated": syllabi,
        "categories": [
            {"name": k, "count": v}
            for k, v in sorted(categories.items(), key=lambda x: -x[1])
        ],
    }


@api_router.get("/signals/{signal_id}", response_model=Signal)
async def get_signal(signal_id: str):
    doc = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Signal not found")
    return doc


@api_router.post("/signals", response_model=Signal)
async def create_signal(payload: SignalCreate):
    signal = Signal(**payload.model_dump())
    doc = signal.model_dump()
    doc = derive_slugs(doc)
    await db.signals.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.put("/signals/{signal_id}", response_model=Signal)
async def update_signal(signal_id: str, payload: SignalUpdate):
    existing = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Signal not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["updated_at"] = now_iso()
    merged = {**existing, **updates}
    merged = derive_slugs(merged)
    await db.signals.update_one({"id": signal_id}, {"$set": merged})
    merged.pop("_id", None)
    return merged


@api_router.delete("/signals/{signal_id}")
async def delete_signal(signal_id: str):
    result = await db.signals.delete_one({"id": signal_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"deleted": True, "id": signal_id}


@api_router.post("/signals/{signal_id}/syllabus", response_model=Signal)
async def trigger_syllabus(signal_id: str):
    existing = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Signal not found")
    modules = await generate_syllabus_ai(existing)
    updates = {
        "syllabus_generated": True,
        "syllabus_modules": modules,
        "status": "converting" if existing.get("status") == "tracked" else existing.get("status"),
        "updated_at": now_iso(),
    }
    await db.signals.update_one({"id": signal_id}, {"$set": updates})
    merged = {**existing, **updates}
    merged.pop("_id", None)
    return merged


# -------- Scraper / Ingestion --------

@api_router.post("/scraper/run")
async def scraper_run():
    """Trigger an immediate scrape of the Leland live listing."""
    return await run_scrape(db, trigger="manual")


@api_router.post("/scraper/ingest-html")
async def scraper_ingest_html(payload: dict = Body(...)):
    """Fallback ingestion: paste raw HTML (or stripped text) from Leland."""
    html = (payload or {}).get("html", "")
    if not html or len(html) < 50:
        raise HTTPException(status_code=400, detail="html payload too small")
    return await ingest_html(db, html, trigger="manual-paste")


@api_router.get("/scraper/status")
async def scraper_status():
    last = await latest_run(db)
    job = scheduler.get_job("leland_scrape") if scheduler.running else None
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.astimezone(timezone.utc).isoformat()
    return {
        "last_run": last,
        "next_run_at": next_run,
        "scheduler_running": scheduler.running,
        "interval_hours": 12,
    }


@api_router.get("/scraper/runs")
async def scraper_runs(limit: int = 20):
    docs = (
        await db.ingestion_runs.find({}, {"_id": 0})
        .sort("ran_at", -1)
        .to_list(min(max(limit, 1), 200))
    )
    return docs


# -------- Publish & Alerts --------

@api_router.post("/signals/{signal_id}/publish")
async def publish_signal_route(signal_id: str):
    existing = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Signal not found")
    return await publish_signal(db, signal_id)


@api_router.get("/signals/{signal_id}/publish/preview")
async def publish_preview(signal_id: str):
    existing = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Signal not found")
    return build_payload(existing)


@api_router.get("/alerts")
async def alerts_list(only_unack: bool = True, limit: int = 50):
    return await list_alerts(db, only_unack=only_unack, limit=limit)


@api_router.post("/alerts/{alert_id}/ack")
async def alerts_ack(alert_id: str):
    doc = await ack_alert(db, alert_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Alert not found")
    return doc


@api_router.post("/alerts/ack-all")
async def alerts_ack_all():
    return {"acknowledged": await ack_all(db)}


# -------- Bulk republish + Streaming syllabus + Integrations --------

@api_router.post("/signals/publish-all-live")
async def signals_publish_all_live():
    return await republish_all_live(db)


@api_router.post("/signals/retry-pending-publishes")
async def signals_retry_pending_publishes():
    return await retry_pending(db)


@api_router.get("/integrations/status")
async def integrations_status():
    ws = whatsapp_status()
    return {
        "whatsapp": {
            "configured": ws.configured,
            "from_number": ws.from_number if ws.configured else None,
            "to_number_masked": ws.to_number_masked or None,
            "threshold": ws.threshold,
            "reason": ws.reason,
        },
        "publish_webhook": {
            "url": os.environ.get("LEARNFORGE_WEBHOOK_URL") or None,
            "has_secret": bool((os.environ.get("LEARNFORGE_WEBHOOK_SECRET") or "").strip()),
        },
    }


@api_router.post("/integrations/whatsapp/test")
async def integrations_whatsapp_test():
    result = send_whatsapp(
        "🛰️ *LearnForge Radar* — test ping. WhatsApp is wired up correctly."
    )
    return result


@api_router.get("/integrations/publish-payload-spec")
async def integrations_publish_spec():
    """Stable JSON-Schema contract for LearnForge POST /api/courses ingestion."""
    return {
        "schema": PUBLISH_PAYLOAD_SPEC,
        "example": PUBLISH_PAYLOAD_EXAMPLE,
        "request_headers": HEADERS_SPEC,
        "expected_response": EXPECTED_RESPONSE,
        "webhook_url": os.environ.get("LEARNFORGE_WEBHOOK_URL") or None,
    }


# -------- Signal velocity (time-series) --------

@api_router.get("/signals/{signal_id}/syllabus/stream")
async def stream_syllabus(signal_id: str):
    """Server-Sent Events syllabus generator.

    Emits `module` events one-by-one so the UI can render progressively
    (command-center feel). The full syllabus is generated server-side via
    Claude Sonnet 4.5 and then drip-fed to the client. While the LLM call
    is in flight we emit `: heartbeat` comments every second so any
    intermediate proxy (k8s ingress / Cloudflare / nginx) does NOT buffer
    the connection and the UI gets visible progress.
    """
    existing = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Signal not found")

    async def event_stream():
        # 2KB padding comment busts default nginx/cloudfront proxy buffers
        # so the very first `start` event is visible to the client.
        yield ":" + (" " * 2048) + "\n\n"
        yield "retry: 5000\n\n"
        yield f"event: start\ndata: {json.dumps({'signal_id': signal_id})}\n\n"

        # Run the LLM call concurrently with a 1s heartbeat so the
        # connection looks alive even while Claude is thinking.
        task = asyncio.create_task(generate_syllabus_ai(existing))
        ticks = 0
        try:
            while not task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
                except asyncio.TimeoutError:
                    ticks += 1
                    yield f": heartbeat {ticks}\n\n"
                    yield (
                        "event: progress\ndata: "
                        + json.dumps({"phase": "synthesizing", "elapsed_s": ticks})
                        + "\n\n"
                    )
            modules = task.result()
        except Exception as e:  # noqa: BLE001
            logger.exception("stream_syllabus LLM error: %s", e)
            yield (
                "event: error\ndata: "
                + json.dumps({"error": f"{type(e).__name__}: {e}"})
                + "\n\n"
            )
            return

        for m in modules:
            yield f"event: module\ndata: {json.dumps(m)}\n\n"
            await asyncio.sleep(0.25)

        updates = {
            "syllabus_generated": True,
            "syllabus_modules": modules,
            "status": "converting"
            if existing.get("status") == "tracked"
            else existing.get("status"),
            "updated_at": now_iso(),
        }
        await db.signals.update_one({"id": signal_id}, {"$set": updates})
        yield f"event: done\ndata: {json.dumps({'count': len(modules)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Encoding": "identity",
        },
    )


@api_router.post("/signals/seed")
async def seed_signals():
    """Seed initial 7 curated Leland-style signals (idempotent)."""
    existing_count = await db.signals.count_documents({})
    if existing_count > 0:
        return {"seeded": False, "existing": existing_count}

    seed_data = [
        {
            "event_title": "Cracking the MBB Consulting Case Interview",
            "category": "Consulting",
            "registration_count": 1228,
            "priority_score": 94,
            "source_url": "https://leland.com/events/mbb-case",
            "notes": "Peak interest October-January. McKinsey/BCG/Bain pipeline.",
            "lead_magnet_title": "The MBB Case Cheat Sheet",
            "lead_magnet_description": "10-page distilled framework for case interview structuring.",
            "paid_offer_title": "ForgeCore: MBB Case Mastery",
            "paid_offer_description": "8-module mini-course with 12 live cases and feedback.",
            "paid_offer_price": 299,
            "cta_headline": "Land Your MBB Offer",
            "cta_subtext": "Trained by ex-McKinsey EMs. Outcome-tracked.",
            "status": "converting",
        },
        {
            "event_title": "Stanford GSB Application Strategy Workshop",
            "category": "MBA Admissions",
            "registration_count": 982,
            "priority_score": 91,
            "source_url": "https://leland.com/events/gsb-strategy",
            "notes": "R1 deadline cluster. High intent buyers.",
            "lead_magnet_title": "GSB Essay Teardown Pack",
            "lead_magnet_description": "Annotated essays from 5 admits with line-by-line breakdowns.",
            "paid_offer_title": "ForgeCore: GSB Admit Playbook",
            "paid_offer_description": "End-to-end strategy + essay reviews + 3 coach calls.",
            "paid_offer_price": 499,
            "cta_headline": "Get Into Stanford GSB",
            "cta_subtext": "The complete operating system for top-3 MBA admits.",
            "status": "tracked",
        },
        {
            "event_title": "Breaking Into Product Management at FAANG",
            "category": "Product Management",
            "registration_count": 1547,
            "priority_score": 88,
            "source_url": "https://leland.com/events/pm-faang",
            "notes": "Highest registration volume of the quarter.",
            "lead_magnet_title": "PM Interview Loop Map",
            "lead_magnet_description": "Visual guide to all 6 PM interview rounds + question banks.",
            "paid_offer_title": "ForgeCore: PM Switcher",
            "paid_offer_description": "Pivot-to-PM accelerator. Mock loops with FAANG PMs.",
            "paid_offer_price": 349,
            "cta_headline": "Pivot Into Product",
            "cta_subtext": "From engineer/analyst/consultant to FAANG PM in 12 weeks.",
            "status": "tracked",
        },
        {
            "event_title": "Investment Banking SA Recruiting Live Q&A",
            "category": "Finance",
            "registration_count": 743,
            "priority_score": 82,
            "source_url": "https://leland.com/events/ib-sa",
            "notes": "Sophomore summer pipeline. Recurring demand.",
            "lead_magnet_title": "IB Networking Email Templates",
            "lead_magnet_description": "20 cold/warm outreach templates with response rates.",
            "paid_offer_title": "ForgeCore: IB SA Sprint",
            "paid_offer_description": "Resume + behaviorals + technicals + networking system.",
            "paid_offer_price": 399,
            "cta_headline": "Lock In Your IB SA Seat",
            "cta_subtext": "Built by ex-Goldman, Morgan Stanley, and Evercore analysts.",
            "status": "live",
        },
        {
            "event_title": "Medical School Personal Statement Workshop",
            "category": "Medical Admissions",
            "registration_count": 612,
            "priority_score": 76,
            "source_url": "https://leland.com/events/med-ps",
            "notes": "AMCAS opens June. Build pipeline by March.",
            "lead_magnet_title": "Med PS Opening Lines Vault",
            "lead_magnet_description": "30 high-performing essay openings from accepted applicants.",
            "paid_offer_title": "ForgeCore: Med PS Studio",
            "paid_offer_description": "5-round essay revision system with physician readers.",
            "paid_offer_price": 249,
            "cta_headline": "Write A PS That Gets You In",
            "cta_subtext": "Reviewed by admitted MDs at Harvard, Hopkins, UCSF.",
            "status": "tracked",
        },
        {
            "event_title": "Big Law Summer Associate Recruiting",
            "category": "Law",
            "registration_count": 489,
            "priority_score": 71,
            "source_url": "https://leland.com/events/biglaw-sa",
            "notes": "1L outreach window. Tight conversion timeline.",
            "lead_magnet_title": "Big Law Firm Tier Map",
            "lead_magnet_description": "V100 firms ranked by practice, pay, and pipeline.",
            "paid_offer_title": "ForgeCore: 1L Recruiting OS",
            "paid_offer_description": "OCI prep, callback strategy, and offer negotiation.",
            "paid_offer_price": 379,
            "cta_headline": "Win Big Law OCI",
            "cta_subtext": "From ex-Cravath, Wachtell, and Sullivan & Cromwell associates.",
            "status": "tracked",
        },
        {
            "event_title": "Tech Career Pivot for Non-CS Majors",
            "category": "Tech Careers",
            "registration_count": 1103,
            "priority_score": 85,
            "source_url": "https://leland.com/events/tech-pivot",
            "notes": "Massive top-of-funnel. Career switcher demographic.",
            "lead_magnet_title": "Non-CS to Tech Roadmap",
            "lead_magnet_description": "12-week curriculum + project portfolio template.",
            "paid_offer_title": "ForgeCore: Tech Pivot Accelerator",
            "paid_offer_description": "Mentorship + portfolio + interview prep cohort.",
            "paid_offer_price": 449,
            "cta_headline": "Launch Your Tech Career",
            "cta_subtext": "Career-switcher success rate: 78%. Cohort-based.",
            "status": "converting",
        },
    ]

    docs = []
    for raw in seed_data:
        sig = Signal(**raw)
        doc = sig.model_dump()
        doc = derive_slugs(doc)
        docs.append(doc)
    await db.signals.insert_many(docs)
    return {"seeded": True, "count": len(docs)}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def scheduled_scrape_job():
    try:
        result = await run_scrape(db, trigger="schedule")
        logger.info("Scheduled scrape OK: %s", result)
        # Snapshot every tracked signal so the velocity chart has a real
        # data point at the 12h cadence even if Leland didn't return that
        # event this round.
        snap = await snapshot_all_signals(db, source="schedule")
        logger.info("Scheduled snapshot: %s", snap)
    except Exception as e:  # noqa: BLE001
        logger.exception("Scheduled scrape failed: %s", e)


async def scheduled_retry_job():
    try:
        result = await retry_pending(db)
        if result["attempted"]:
            logger.info("Scheduled publish-retry: %s", result)
    except Exception as e:  # noqa: BLE001
        logger.exception("Scheduled retry failed: %s", e)


@app.on_event("startup")
async def on_startup():
    try:
        count = await db.signals.count_documents({})
        if count == 0:
            logger.info("Auto-seeding signals collection (empty).")
            await seed_signals()
    except Exception as e:  # noqa: BLE001
        logger.exception("Auto-seed failed: %s", e)

    # Schedule the 12h Leland scraper job (first run 12h from boot)
    try:
        from datetime import timedelta
        first_run = datetime.now(timezone.utc) + timedelta(hours=12)
        scheduler.add_job(
            scheduled_scrape_job,
            trigger=IntervalTrigger(hours=12),
            id="leland_scrape",
            replace_existing=True,
            next_run_time=first_run,
        )
        scheduler.add_job(
            scheduled_retry_job,
            trigger=IntervalTrigger(minutes=5),
            id="publish_retry",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "APScheduler started · leland_scrape every 12h · first run %s · publish_retry every 5m",
            first_run.isoformat(),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Scheduler start failed: %s", e)


@app.on_event("shutdown")
async def on_shutdown():
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
    finally:
        client.close()
