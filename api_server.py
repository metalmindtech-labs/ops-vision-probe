"""Railway API wrapper for Vision Perception Probe."""
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import shutil
from vision_probe import run_pipeline

app = FastAPI(title="OPS Vision Perception Probe", version="2.1.0")

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
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "result": None, "error": None}
    
    bg.add_task(_run_probe, job_id, req.video_url, api_key)
    return ProbeResponse(job_id=job_id, status="running")

@app.post("/api/v1/upload", response_model=ProbeResponse)
async def upload_probe(bg: BackgroundTasks, file: UploadFile = File(...)):
    api_key = os.environ.get("OPENAI_API_KEY")
    job_id = str(uuid.uuid4())
    file_path = f"/tmp/{job_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    jobs[job_id] = {"status": "running", "result": None, "error": None}
    bg.add_task(_run_file_probe, job_id, file_path, api_key)
    return ProbeResponse(job_id=job_id, status="running")

@app.get("/api/v1/probe/{job_id}")
async def get_probe_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/health")
async def health():
    return {"status": "ok", "probe_type": "vision_perception_probe"}

def _run_probe(job_id, video_url, api_key):
    try:
        event = run_pipeline(video_url=video_url, api_key=api_key, output_path=f"/tmp/{job_id}.json")
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