// LearnForge — components/CourseHero.tsx (DROP-IN)
//
// Cinematic image renderer for course heroes & module cards. Handles:
//   1. Missing URL → renders a Sovereign-style placeholder (no broken <img>)
//   2. Loading state → cinematic gradient + grid + spinner until image loads
//   3. Load error → flips back to the placeholder, never a broken icon
//   4. Lazy load + intrinsic 16:9 aspect ratio (prevents CLS)
//
// Usage:
//   <CourseHero src={course.hero_image_url} title={course.title} priority />
//   <CourseHero src={module.image_url} title={module.title} ratio="16:9" />
//
// Save at: learnforge-core/components/CourseHero.tsx
// Then swap any `<img src={course.hero_image_url} />` for `<CourseHero ... />`

"use client";

import { useState } from "react";

type CourseHeroProps = {
    src?: string | null;
    title?: string;
    /** "16:9" | "1:1" | "21:9" — defaults to 16:9 */
    ratio?: "16:9" | "1:1" | "21:9";
    /** Set true for the LCP hero on the showroom page */
    priority?: boolean;
    className?: string;
};

const ASPECT = {
    "16:9": "aspect-[16/9]",
    "1:1": "aspect-square",
    "21:9": "aspect-[21/9]",
} as const;

export function CourseHero({
    src,
    title = "",
    ratio = "16:9",
    priority = false,
    className = "",
}: CourseHeroProps) {
    const [state, setState] = useState<"loading" | "loaded" | "error">(
        src ? "loading" : "error",
    );

    const showImage = src && state !== "error";

    return (
        <div
            className={`relative ${ASPECT[ratio]} overflow-hidden bg-zinc-950 ${className}`}
        >
            {/* Always render the placeholder underneath — even while the
                image loads. The image fades in on top once decoded. */}
            <SovereignPlaceholder title={title} />

            {showImage && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                    src={src!}
                    alt={title}
                    loading={priority ? "eager" : "lazy"}
                    decoding={priority ? "sync" : "async"}
                    onLoad={() => setState("loaded")}
                    onError={() => setState("error")}
                    className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-500 ${
                        state === "loaded" ? "opacity-100" : "opacity-0"
                    }`}
                />
            )}

            {/* Soft bottom gradient for any text overlay */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/70 to-transparent" />
        </div>
    );
}

// ----------------------------------------------------------------------
// Sovereign-style placeholder — dark charcoal, cyber-lime grid, subtle
// glow. Matches the Radar's visual language so a missing image still
// reads as "intentional" and not "broken".
// ----------------------------------------------------------------------
function SovereignPlaceholder({ title }: { title: string }) {
    // Derive a 1-2 char monogram so each missing card still feels unique.
    const monogram = (title || "LF")
        .split(/\s+/)
        .map((w) => w[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();

    return (
        <div
            aria-hidden
            className="absolute inset-0 grid place-items-center"
            style={{
                background:
                    "radial-gradient(120% 80% at 50% 30%, rgba(163,230,53,0.10) 0%, rgba(10,10,10,0) 55%), #0a0a0a",
            }}
        >
            {/* Cinematic engineering grid */}
            <div
                className="absolute inset-0 opacity-30"
                style={{
                    backgroundImage:
                        "linear-gradient(rgba(163,230,53,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(163,230,53,0.08) 1px, transparent 1px)",
                    backgroundSize: "32px 32px",
                }}
            />
            {/* Centered monogram + caption */}
            <div className="relative z-10 flex flex-col items-center gap-2">
                <div className="font-mono text-4xl sm:text-6xl font-bold tracking-tight text-zinc-100/80 select-none">
                    {monogram}
                </div>
                <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-lime-400/70 flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-lime-400 animate-pulse" />
                    LearnForge · Radar Curriculum
                </div>
            </div>
            {/* Corner registration marks (engineering aesthetic) */}
            <Crosshair className="top-3 left-3" />
            <Crosshair className="top-3 right-3 rotate-90" />
            <Crosshair className="bottom-3 left-3 -rotate-90" />
            <Crosshair className="bottom-3 right-3 rotate-180" />
        </div>
    );
}

function Crosshair({ className = "" }: { className?: string }) {
    return (
        <svg
            className={`absolute h-4 w-4 text-lime-400/60 ${className}`}
            viewBox="0 0 16 16"
            fill="none"
        >
            <path
                d="M0 0 H6 M0 0 V6"
                stroke="currentColor"
                strokeWidth="1.5"
            />
        </svg>
    );
}
