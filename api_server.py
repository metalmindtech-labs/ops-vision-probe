"""Railway API wrapper for Vision Perception Probe."""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
from vision_probe import run_pipeline

app = FastAPI(title="OPS Vision Perception Probe", version="2.0.0")

# Enable CORS for the Sovereign Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store
jobs: dict = {}

class ProbeRequest(BaseModel):
    video_url: str
    keep_artifacts: bool = False

class ProbeResponse(BaseModel):
    job_id: str
    status: str

@app.post("/api/v1/probe", response_model=ProbeResponse)
async def create_probe(req: ProbeRequest, bg: BackgroundTasks):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "result": None, "error": None}
    
    bg.add_task(_run_probe, job_id, req.video_url, api_key, req.keep_artifacts)
    return ProbeResponse(job_id=job_id, status="running")

@app.get("/api/v1/probe/{job_id}")
async def get_probe_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/health")
async def health():
    return {"status": "ok", "probe_type": "vision_perception_probe"}

def _run_probe(job_id: str, video_url: str, api_key: str, keep_artifacts: bool):
    try:
        event = run_pipeline(
            video_url=video_url,
            api_key=api_key,
            output_path=f"/tmp/{job_id}.json",
            keep_artifacts=keep_artifacts,
        )
        jobs[job_id] = {"status": "complete", "result": event, "error": None}
    except Exception as e:
        jobs[job_id] = {"status": "failed", "result": None, "error": str(e)}