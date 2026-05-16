"""Railway API wrapper for Vision Perception Probe with High-Persistence Slack Integration."""
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import shutil
import threading
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from vision_probe import run_pipeline

# Slack App Initialization
slack_app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@slack_app.event("app_mention")
def handle_app_mentions(event, say, client):
    channel_id = event.get("channel")
    text = event.get("text", "").lower()
    print(f"[Slack] Mention received in {channel_id}: {text}")
    
    # Manual checkmark reaction to prove we are receiving the event
    client.reactions_add(name="white_check_mark", channel=channel_id, timestamp=event.get("ts"))
    
    if "status" in text:
        client.chat_postMessage(channel=channel_id, text="Sovereign Intelligence Hub: ONLINE. Mission Control active. 🏰⚓️")
    else:
        client.chat_postMessage(channel=channel_id, text="The Ark is listening. Type 'status' for a health check.")

def start_slack_bridge():
    print("[Slack] Initializing Socket Mode Handler...")
    try:
        handler = SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN"))
        handler.start()
    except Exception as e:
        print(f"[Slack] CRITICAL ERROR: {str(e)}")

app = FastAPI(title="OPS Vision Perception Probe", version="2.4.0")

# Start Slack Bridge in a more persistent thread
slack_thread = threading.Thread(target=start_slack_bridge, daemon=True)
slack_thread.start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status":"ok", "slack_thread_alive": slack_thread.is_alive()}

# ... (Keep existing /api/v1/probe and /api/v1/upload endpoints) ...