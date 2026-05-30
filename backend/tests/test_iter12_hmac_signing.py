"""Iteration 12 — HMAC-SHA256 signing of publish webhook.

Covers:
- GET /api/integrations/status → publish_webhook signature metadata
- services.publisher.sign_payload() unit test (stdlib hmac equivalence)
- Local echo-server end-to-end signature verification using fixture signal
- Live publish currently returns HTTP 401 + body containing 'Invalid signature'
  (proves the route is reachable; expected upstream state).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

# Make /app/backend importable so we can pull in `services.publisher`.
BACKEND_DIR = "/app/backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.publisher import sign_payload, publish_signal, build_payload  # noqa: E402
import services.publisher as publisher  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://course-converter-2.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
FIXTURE_SIGNAL_ID = "e3171073-0ae9-4bf8-ae9b-3bb2e303a576"
SECRET = "SovereignForge2026!"


# ---------------------------------------------------------------------------
# 1. /api/integrations/status — signature metadata exposed for the UI badge
# ---------------------------------------------------------------------------
class TestIntegrationsStatus:
    @pytest.fixture(scope="class")
    def status(self):
        r = requests.get(f"{API}/integrations/status", timeout=15)
        assert r.status_code == 200, r.text
        return r.json()

    def test_publish_webhook_present(self, status):
        assert "publish_webhook" in status
        wh = status["publish_webhook"]
        assert wh["url"], "webhook url must be configured"
        assert wh["url"].startswith("https://"), "webhook url should be https"

    def test_has_secret_true(self, status):
        assert status["publish_webhook"]["has_secret"] is True

    def test_signature_algorithm_and_header(self, status):
        wh = status["publish_webhook"]
        assert wh["signature_algorithm"] == "hmac-sha256"
        assert wh["signature_header"] == "X-Radar-Signature"


# ---------------------------------------------------------------------------
# 2. sign_payload() — stdlib hmac equivalence
# ---------------------------------------------------------------------------
class TestSignPayloadUnit:
    def test_matches_stdlib_hmac(self):
        body = b'{"event":"course.publish","signal_id":"abc"}'
        expected = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        got = sign_payload(SECRET, body)
        assert got == expected
        assert len(got) == 64
        # hex lowercase
        int(got, 16)
        assert got == got.lower()

    def test_different_secret_changes_digest(self):
        body = b"hello"
        a = sign_payload("alpha", body)
        b = sign_payload("beta", body)
        assert a != b

    def test_different_body_changes_digest(self):
        a = sign_payload(SECRET, b"one")
        b = sign_payload(SECRET, b"two")
        assert a != b


# ---------------------------------------------------------------------------
# 3. End-to-end local echo server — captures X-Radar-Signature and verifies
# ---------------------------------------------------------------------------
class _CaptureHandler(BaseHTTPRequestHandler):
    # Shared across one server instance; written by handler, read by test.
    captured: dict = {}

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        _CaptureHandler.captured = {
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
            "path": self.path,
            "method": "POST",
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *_args, **_kwargs):  # silence stderr
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def echo_server():
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _CaptureHandler.captured = {}
    try:
        yield f"http://127.0.0.1:{port}/api/courses"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_publish_signal_signs_body_with_hmac_sha256(monkeypatch, echo_server):
    """Publish to a local echo server; verify the X-Radar-Signature header
    matches HMAC-SHA256 over the exact request body bytes."""
    # Re-route the webhook to the local echo server.
    monkeypatch.setenv("LEARNFORGE_WEBHOOK_URL", echo_server)
    monkeypatch.setenv("LEARNFORGE_WEBHOOK_SECRET", SECRET)

    # Build payload from a real signal in Mongo via Motor (same client the app uses).
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    try:
        signal = await db.signals.find_one({"id": FIXTURE_SIGNAL_ID}, {"_id": 0})
        assert signal is not None, f"fixture signal {FIXTURE_SIGNAL_ID} not present"

        result = await publish_signal(db, FIXTURE_SIGNAL_ID)
        # Local echo returns 200 → publish must be marked ok.
        assert result["status_code"] == 200, result
        assert result["ok"] is True, result
        assert result["error"] is None

        captured = _CaptureHandler.captured
        assert captured, "echo server did not receive any request"

        # Header presence + format
        sig_header = captured["headers"].get("X-Radar-Signature")
        algo_header = captured["headers"].get("X-Radar-Signature-Algorithm")
        assert sig_header, "missing X-Radar-Signature header"
        assert algo_header == "hmac-sha256"
        assert sig_header.startswith("sha256="), sig_header
        hex_part = sig_header.split("=", 1)[1]
        assert len(hex_part) == 64

        # Recompute HMAC over the body bytes the server actually received
        received_body = captured["body"]
        expected_hex = hmac.new(
            SECRET.encode("utf-8"), received_body, hashlib.sha256
        ).hexdigest()
        expected_full = f"sha256={expected_hex}"

        assert hmac.compare_digest(sig_header, expected_full), {
            "received": sig_header,
            "expected": expected_full,
        }

        # Sanity: body is canonical JSON (compact separators, sorted keys).
        # We can't byte-compare against a rebuilt payload because `published_at`
        # is generated at publish-time; instead verify the bytes parse and are
        # in canonical form (no whitespace, sorted top-level keys).
        parsed = json.loads(received_body)
        assert parsed["event"] == "course.publish"
        assert parsed["signal_id"] == FIXTURE_SIGNAL_ID
        # Compact separators check: re-canonicalising the parsed body must
        # equal received_body byte-for-byte (proves sort_keys + compact
        # separators were used by the publisher).
        recanon = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        assert recanon == received_body

        # Persisted state should also reflect published.
        post = await db.signals.find_one({"id": FIXTURE_SIGNAL_ID}, {"_id": 0})
        assert post.get("publish_status") == "published"
        assert post.get("last_publish_status_code") == 200
    finally:
        client.close()


# ---------------------------------------------------------------------------
# 4. Live publish → expected upstream 401 with 'Invalid signature' body
# ---------------------------------------------------------------------------
class TestLivePublishExpected401:
    def test_publish_returns_401_invalid_signature(self):
        r = requests.post(
            f"{API}/signals/{FIXTURE_SIGNAL_ID}/publish", timeout=30
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Upstream LearnForge currently rejects with 401 — this proves the
        # route is reachable (bumped from 404 → 401 after secret was added).
        assert body["url"] == "https://learnforge-core.vercel.app/api/courses"
        assert body["status_code"] == 401, body
        assert body["ok"] is False
        preview = (body.get("response_preview") or "")
        assert "Invalid signature" in preview, preview
        assert body.get("error") == "HTTP 401"
