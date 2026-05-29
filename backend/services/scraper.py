"""Leland event-stream scraper.

The public Leland events listing renders the upcoming free events as an SPA,
but the SSR-rendered HTML still contains the core event metadata.

Pattern observed in raw HTML (after stripping tags):
    ... {when} {N} registered {title} {coach} | {rating} ( {reviews} ) Register ...

This module extracts that information from either a fetched listing or a
pasted HTML blob (manual fallback when anti-bot measures rotate).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

LELAND_EVENTS_URL = "https://www.joinleland.com/events"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    event_title: str
    registration_count: int
    when: Optional[str] = None
    coach: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    source: str = LELAND_EVENTS_URL


# Examples of the rendered text segments we want to chunk on:
#   "Starts in 1 hour 140 registered Part 2: Identify Your Target ..."
#   "Jun 1, 2026 at 9:00 PM 71 registered Inside the Mind of an MBA..."
WHEN_PREFIXES = [
    r"Starts in [^A-Z0-9]*\d+\s*(?:hour|hours|minute|minutes|day|days)",
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4}\s*(?:at\s*\d{1,2}:\d{2}\s*(?:AM|PM))?",
]
WHEN_PATTERN = re.compile("(" + "|".join(WHEN_PREFIXES) + ")", re.IGNORECASE)

# Capture: when, registered count, title, coach + rating
EVENT_PATTERN = re.compile(
    r"(?P<when>(?:Starts in [^0-9]*\d+\s*(?:hour|hours|minute|minutes|day|days))"
    r"|(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4}(?:\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM))?))"
    r"\s+(?P<count>[\d,]+)\s+registered\s+"
    r"(?P<title>.+?)\s+"
    r"(?P<coach>[A-Z][a-z]+(?:\s+[A-Z]\.)+?(?:\s+and\s+[A-Z][a-z]+(?:\s+[A-Z]\.)+?)?)"
    r"\s*\|\s*"
    r"(?P<rating>\d+(?:\.\d+)?)\s*\(\s*(?P<reviews>\d+)\s*\)\s*Register",
    re.IGNORECASE,
)


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def parse_events_from_html(html: str) -> List[ScrapedEvent]:
    """Parse the Leland listing HTML and yield ScrapedEvent rows.

    Handles both the live SSR HTML and pasted snippets where the
    surrounding chrome has been stripped.
    """
    text = _strip_html(html) if "<" in html else re.sub(r"\s+", " ", html)
    events: List[ScrapedEvent] = []
    seen = set()
    for m in EVENT_PATTERN.finditer(text):
        title = m.group("title").strip(" -|")
        # Title can absorb trailing date words from the next item;
        # trim at any subsequent "Starts in" or month token.
        title = re.split(
            r"\b(?:Starts in|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
            title,
            maxsplit=1,
        )[0].strip(" -|")
        if not title or len(title) < 4:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            count = int(m.group("count").replace(",", ""))
        except ValueError:
            count = 0
        try:
            rating = float(m.group("rating"))
        except ValueError:
            rating = None
        try:
            reviews = int(m.group("reviews"))
        except ValueError:
            reviews = None
        events.append(
            ScrapedEvent(
                event_title=title,
                registration_count=count,
                when=m.group("when").strip(),
                coach=m.group("coach").strip(),
                rating=rating,
                reviews=reviews,
            )
        )
    return events


async def fetch_listing_html(url: str = LELAND_EVENTS_URL, timeout: float = 25.0) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=timeout
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def scrape_live() -> List[ScrapedEvent]:
    try:
        html = await fetch_listing_html()
        return parse_events_from_html(html)
    except Exception as e:  # noqa: BLE001
        logger.exception("Leland live scrape failed: %s", e)
        return []


def event_to_dict(e: ScrapedEvent) -> dict:
    return asdict(e)
