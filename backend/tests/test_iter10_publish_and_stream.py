"""Iteration 10 — Architect's 3 P0 directives:
 1. Publish must surface 404 + hint diagnostics
 2. SSE stream must show real-time progress (heartbeats + progress events)
 3. All CTAs must route to /signup?course=... (no /en/, /courses/, /scrolls/)
"""
import os
import re
import requests
import pytest

import sys as _sys
_sys.path.insert(0, "/app/backend")
from services.publisher import legacy_publish_enabled as _legacy_on  # noqa: E402
_LEGACY_SKIP = pytest.mark.skipif(
    not _legacy_on(),
    reason="v1 publish/syllabus routes deprecated (410) — RADAR_LEGACY_PUBLISH_ENABLED=false; v2 coverage in test_iter13_course_brief_v2.py",
)
import subprocess
from urllib.parse import urlparse, parse_qs

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
SIGNAL_ID = "e3171073-0ae9-4bf8-ae9b-3bb2e303a576"


def _assert_signup_url(u: str):
    """Validate signup URL shape."""
    assert u, f"URL is empty/None: {u!r}"
    assert u.startswith("https://learnforge-core.vercel.app/signup"), f"bad base: {u}"
    assert "/en/" not in u, f"unexpected /en/: {u}"
    assert "/courses/" not in u, f"unexpected /courses/: {u}"
    assert "/scrolls/" not in u, f"unexpected /scrolls/: {u}"
    parsed = urlparse(u)
    qs = parse_qs(parsed.query)
    assert "course" in qs, f"missing course param: {u}"
    assert "ref" in qs and qs["ref"] == ["radar"], f"missing/bad ref: {u}"
    assert "tier" in qs, f"missing tier: {u}"


# ----- Publish preview -----
@_LEGACY_SKIP
class TestPublishPreview:
    def test_preview_cta_urls(self):
        r = requests.get(f"{BASE_URL}/api/signals/{SIGNAL_ID}/publish/preview", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # The preview wraps payload in different shapes — search for the course object
        # by serializing and inspecting.
        # Try common shapes.
        payload = data.get("payload") or data
        course = payload.get("course") if isinstance(payload, dict) else None
        assert course, f"no course in preview: {data}"
        cta = course.get("cta", {})
        _assert_signup_url(cta.get("paid_url"))
        _assert_signup_url(cta.get("free_url"))
        lm = course.get("lead_magnet", {})
        _assert_signup_url(lm.get("url"))
        assert "tier=forgecore" in cta["paid_url"]
        assert "tier=free" in cta["free_url"]


# ----- Publish endpoint -----
@_LEGACY_SKIP
class TestPublishWebhook:
    def test_publish_returns_404_with_hint_and_clean_ctas(self):
        r = requests.post(f"{BASE_URL}/api/signals/{SIGNAL_ID}/publish", timeout=60)
        assert r.status_code == 200, f"expected wrapper 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is False, f"expected ok=false: {data}"
        assert data.get("status_code") == 404, f"expected 404, got: {data.get('status_code')}"
        hint = data.get("hint") or ""
        assert "/api/courses" in hint and "not deployed" in hint.lower(), f"bad hint: {hint!r}"
        # CTA URL shape inside payload
        payload = data.get("payload") or {}
        course = payload.get("course", {})
        cta = course.get("cta", {})
        _assert_signup_url(cta.get("paid_url"))
        _assert_signup_url(cta.get("free_url"))
        lm = course.get("lead_magnet", {})
        _assert_signup_url(lm.get("url"))


# ----- SSE stream -----
@_LEGACY_SKIP
class TestSyllabusStream:
    def test_stream_emits_start_progress_modules_done(self):
        url = f"{BASE_URL}/api/signals/{SIGNAL_ID}/syllabus/stream"
        # HEAD/headers check
        with requests.get(url, stream=True, timeout=90) as r:
            assert r.status_code == 200, r.text
            # Headers
            ct = r.headers.get("Content-Type", "")
            assert "text/event-stream" in ct, f"bad content-type: {ct}"
            cc = r.headers.get("Cache-Control", "")
            # CF/ingress may rewrite Cache-Control; accept any anti-cache directive.
            assert ("no-cache" in cc) or ("no-store" in cc), f"bad cache-control: {cc}"
            # X-Accel-Buffering may be stripped by CF but stream works (verified via curl).
            # Don't hard-fail on the header — verify real-time behavior via event counts below.

            counts = {"start": 0, "progress": 0, "module": 0, "done": 0, "error": 0, "heartbeat": 0}
            buf = ""
            import time
            t0 = time.time()
            for chunk in r.iter_content(chunk_size=1, decode_unicode=True):
                if chunk is None:
                    continue
                buf += chunk
                # Process complete SSE events split by blank line
                while "\n\n" in buf:
                    event_block, buf = buf.split("\n\n", 1)
                    if event_block.startswith(":"):
                        # comment / heartbeat
                        if "heartbeat" in event_block:
                            counts["heartbeat"] += 1
                        continue
                    ev = None
                    for line in event_block.splitlines():
                        if line.startswith("event:"):
                            ev = line.split(":", 1)[1].strip()
                    if ev and ev in counts:
                        counts[ev] += 1
                if counts["done"] >= 1 or counts["error"] >= 1:
                    break
                if time.time() - t0 > 85:
                    break
            print(f"SSE counts: {counts}")
            assert counts["start"] == 1, f"expected 1 start, counts={counts}"
            assert counts["progress"] >= 3, f"expected >=3 progress, counts={counts}"
            assert counts["module"] == 6, f"expected 6 module events, counts={counts}"
            assert counts["done"] == 1, f"expected 1 done, counts={counts}"
            assert counts["error"] == 0, f"unexpected error event, counts={counts}"
