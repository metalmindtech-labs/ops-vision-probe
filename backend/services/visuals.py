"""Fal.ai Flux.1 Pro image generation — the Radar's visual engine.

Generates a cinematic course-hero image plus one image per syllabus module,
all wrapped in the architect's "Sovereign Style Sheet" so the LearnForge
landing pages get a unified high-end aesthetic.

Surface:
  - `generate_course_visuals(signal_doc) -> dict` returns
      {"hero": <url>, "modules": [{"index": i, "url": <url>}, ...]}
  - Failures degrade gracefully — we return whatever URLs we have plus an
    `errors` list. A publish never blocks on image gen.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import fal_client

logger = logging.getLogger(__name__)


# ----- Sovereign Style Sheet ----------------------------------------------
# Suffixed onto every prompt so the generated image stays on-brand:
# dark mode, cinematic, high-contrast, professional/engineering aesthetic.
STYLE_SUFFIX = (
    "dark mode, cinematic lighting, high contrast, professional engineering "
    "aesthetic, deep charcoal and obsidian black background with subtle cyber "
    "lime / toxic green accents, ultra-detailed, photorealistic, 8K, sharp "
    "focus, dramatic side lighting, volumetric atmosphere, no text, no logos, "
    "no watermarks, no ui chrome, masterpiece, editorial, premium product "
    "photography, cinematic color grading"
)

NEGATIVE_PROMPT = (
    "ai slop, generic, stock-photo, bright, cheerful, pastel, cartoon, "
    "anime, clipart, low-resolution, blurry, oversaturated, neon purple, "
    "watermark, text, ui elements, dashboard, screenshot, logo"
)

# Fal model identifier for Flux.1 Pro
FLUX_PRO_MODEL = "fal-ai/flux-pro/v1.1"


def _key_present() -> bool:
    return bool((os.environ.get("FAL_KEY") or "").strip())


def _hero_prompt(signal: dict) -> str:
    title = signal.get("paid_offer_title") or signal.get("event_title") or "Mastery"
    category = signal.get("category") or "Career"
    subject = signal.get("paid_offer_description") or ""
    return (
        f"Editorial hero banner for an elite training program: '{title}'. "
        f"Domain: {category}. Theme: {subject[:160]}. "
        f"Composition: cinematic wide shot, asymmetric, dramatic depth, single "
        f"powerful focal point. {STYLE_SUFFIX}"
    )


def _module_prompt(signal: dict, module: dict) -> str:
    title = (module or {}).get("title") or "Mastery"
    summary = (module or {}).get("summary") or ""
    category = signal.get("category") or ""
    return (
        f"Editorial module illustration: '{title}'. "
        f"Concept: {summary[:200]}. Domain: {category}. "
        f"Composition: cinematic close-up, single conceptual artifact rendered "
        f"in detail, no human faces, intellectual mood. {STYLE_SUFFIX}"
    )


async def _flux_call(prompt: str, *, aspect: str = "16:9") -> Optional[str]:
    """Single Flux.1 Pro call. Returns image URL or None on failure."""
    if not _key_present():
        logger.warning("flux_call skipped — FAL_KEY missing")
        return None
    image_size = "landscape_16_9" if aspect == "16:9" else "square_hd"
    args = {
        "prompt": prompt,
        "image_size": image_size,
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "enable_safety_checker": True,
        "output_format": "jpeg",
    }
    try:
        # fal_client.submit_async returns a handler; we await .get()
        handler = await fal_client.submit_async(FLUX_PRO_MODEL, arguments=args)
        result = await handler.get()
    except Exception as e:  # noqa: BLE001
        logger.exception("flux_call failed: %s", e)
        return None
    images = (result or {}).get("images") or []
    if not images:
        logger.warning("flux_call returned no images: %s", result)
        return None
    return images[0].get("url")


async def generate_course_visuals(
    signal: dict,
    *,
    skip_existing: bool = True,
    concurrency: int = 3,
) -> dict:
    """Generate a hero + one image per module for the given signal.

    Existing URLs on the signal are preserved when `skip_existing=True`.
    Requests are dispatched with bounded concurrency so we don't hammer
    Fal.ai. Failures are recorded but never raise.
    """
    if not _key_present():
        return {
            "hero": None,
            "modules": [],
            "errors": ["FAL_KEY not configured"],
            "model": FLUX_PRO_MODEL,
            "style": "sovereign-v1",
        }

    existing_hero = signal.get("hero_image_url") if skip_existing else None
    existing_modules = {
        m.get("index"): m
        for m in (signal.get("syllabus_modules") or [])
        if skip_existing and m.get("image_url")
    }

    modules_in = signal.get("syllabus_modules") or []
    sem = asyncio.Semaphore(concurrency)

    async def gated(prompt: str, aspect: str) -> Optional[str]:
        async with sem:
            return await _flux_call(prompt, aspect=aspect)

    hero_task = (
        asyncio.create_task(gated(_hero_prompt(signal), "16:9"))
        if not existing_hero
        else None
    )
    module_tasks = []
    for m in modules_in:
        idx = m.get("index")
        if idx in existing_modules:
            module_tasks.append(None)
            continue
        module_tasks.append(
            asyncio.create_task(gated(_module_prompt(signal, m), "16:9"))
        )

    errors: list[str] = []

    if hero_task is None:
        hero_url = existing_hero
    else:
        try:
            hero_url = await hero_task
            if not hero_url:
                errors.append("hero generation failed")
        except Exception as e:  # noqa: BLE001
            logger.exception("hero task error: %s", e)
            hero_url = None
            errors.append(f"hero: {type(e).__name__}")

    module_results: list[dict] = []
    for m, task in zip(modules_in, module_tasks):
        if task is None:
            module_results.append(
                {"index": m.get("index"), "url": existing_modules[m["index"]]["image_url"]}
            )
            continue
        try:
            url = await task
        except Exception as e:  # noqa: BLE001
            logger.exception("module task error: %s", e)
            url = None
            errors.append(f"module {m.get('index')}: {type(e).__name__}")
        if not url:
            errors.append(f"module {m.get('index')} generation failed")
        module_results.append({"index": m.get("index"), "url": url})

    return {
        "hero": hero_url,
        "modules": module_results,
        "errors": errors,
        "model": FLUX_PRO_MODEL,
        "style": "sovereign-v1",
    }
