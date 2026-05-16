"""Railway API wrapper for Vision Perception Probe with Slack Integration."""
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import shutil
import threading
from contextlib import asynccontextmanager
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from vision_probe import run_pipeline

# Slack App Initialization
slack_app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@slack_app.event("app_mention")
def handle_app_mentions(event, say):
    text = event.get("text", "").lower()
    print(f"[Slack] Mention received: {text}")
    if "status" in text:
        say("Sovereign Intelligence Hub: ONLINE. Mission Control active. 🏰⚓️")
    else:
        say("The Ark is listening. Type 'status' for a health check.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Slack Socket Mode in background
    handler = SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN"))
    thread = threading.Thread(target=handler.start, daemon=True)
    thread.start()
    print("[Lifespan] Slack Master Bridge started.")
    yield
    # Shutdown: SocketModeHandler doesn't have a clean stop in this version, daemon thread will exit
    print("[Lifespan] Ark Brain shutting down.")

app = FastAPI(title="OPS Vision Perception Probe", version="2.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict = {}

class ProbeResponse(BaseModel):
    job_id: str
    status: str

class ProbeRequest(BaseModel):
    video_url: str

@app.post("/api/v1/probe", response_model=ProbeResponse)
async def create_probe(req: ProbeRequest, bg: BackgroundTasks):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: raise HTTPException(500, "OPENAI_API_KEY missing")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "result": None, "error": None}
    bg.add_task(_run_probe, job_id, req.video_url, api_key)
    return ProbeResponse(job_id=job_id, status="running")

@app.post("/api/v1/upload", response_model=ProbeResponse)
async def upload_probe(bg: BackgroundTasks, file: UploadFile = File(...)):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: raise HTTPException(500, "OPENAI_API_KEY missing")
    
    job_id = str(uuid.uuid4())
    file_path = f"/tmp/{job_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    jobs[job_id] = {"status": "running", "result": None, "error": None}
    bg.add_task(_run_file_probe, job_id, file_path, api_key)
    return ProbeResponse(job_id=job_id, status="running")

@app.get("/api/v1/probe/{job_id}")
async def get_probe_result(job_id: str):
    if job_id not in jobs: raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/health")
async def health():
    return {"status":"ok", "probe_type":"vision_perception_probe", "slack_active": True}

def _run_probe(job_id, video_url, api_key):
    try:
        event = run_pipeline(video_url, api_key, f"/tmp/{job_id}.json")
        jobs[job_id] = {"status": "complete", "result": event}
    except Exception as e:
        jobs[job_id] = {"status": "failed", "error": str(e)}

def _run_file_probe(job_id, file_path, api_key):
    try:
        from vision_probe import run_pipeline_on_file
        event = run_pipeline_on_file(file_path, api_key)
        jobs[job_id] = {"status": "complete", "result": event}
    except Exception as e:
        jobs[job_id] = {"status": "failed", "error": str(e)}