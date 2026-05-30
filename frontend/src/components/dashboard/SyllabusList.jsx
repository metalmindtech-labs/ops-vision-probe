import { Clock, Target, Package, Activity } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

export default function SyllabusList({ modules, streaming = false, heroImageUrl = null }) {
    if (!modules || modules.length === 0) {
        if (streaming) {
            return (
                <section data-testid={DASHBOARD.syllabusList}>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-lime-400">
                            04 · AI-Generated Syllabus
                        </h3>
                        <span className="font-mono text-[10px] text-lime-400 inline-flex items-center gap-1.5">
                            <Activity className="h-3 w-3 animate-pulse" />
                            streaming · claude sonnet 4.5
                        </span>
                    </div>
                    <div className="font-mono text-[11px] text-zinc-500 border border-dashed border-zinc-800 rounded-sm p-6 text-center">
                        <span className="blink text-lime-400">_</span> waiting for first module…
                    </div>
                </section>
            );
        }
        return null;
    }
    return (
        <section data-testid={DASHBOARD.syllabusList}>
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-lime-400">
                    04 · AI-Generated Syllabus
                </h3>
                <span className="font-mono text-[10px] text-zinc-500 inline-flex items-center gap-1.5">
                    {streaming && (
                        <Activity className="h-3 w-3 text-lime-400 animate-pulse" />
                    )}
                    {streaming
                        ? "streaming…"
                        : `${modules.length} modules · claude 4.5 · flux pro`}
                </span>
            </div>
            {heroImageUrl && (
                <div
                    data-testid="syllabus-hero-image"
                    className="mb-3 relative border border-lime-400/30 rounded-sm overflow-hidden group"
                >
                    <img
                        src={heroImageUrl}
                        alt="Course hero — Fal Flux.1 Pro · Sovereign style"
                        loading="lazy"
                        className="w-full aspect-[16/9] object-cover"
                    />
                    <div className="absolute inset-x-0 bottom-0 px-3 py-1.5 bg-gradient-to-t from-black/80 to-transparent">
                        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-lime-400">
                            hero · flux.1 pro · sovereign
                        </span>
                    </div>
                </div>
            )}
            <div className="space-y-2">
                {modules.map((m) => (
                    <div
                        key={m.index}
                        className="border border-zinc-800 hover:border-lime-400/30 bg-zinc-900/30 rounded-sm overflow-hidden transition-colors group animate-fade-in"
                    >
                        {m.image_url && (
                            <img
                                src={m.image_url}
                                alt={`Module ${m.index} — Fal Flux.1 Pro`}
                                loading="lazy"
                                className="w-full aspect-[16/9] object-cover border-b border-zinc-800"
                            />
                        )}
                        <div className="p-4">
                        <div className="flex items-start gap-4">
                            <span className="font-mono text-xs text-lime-400 mt-1 min-w-[28px]">
                                {String(m.index).padStart(2, "0")}
                            </span>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                    <h4 className="font-mono text-sm text-zinc-50 truncate group-hover:text-lime-300 transition-colors">
                                        {m.title}
                                    </h4>
                                    <span className="inline-flex items-center gap-1 font-mono text-[10px] text-zinc-500 whitespace-nowrap">
                                        <Clock className="h-3 w-3" />
                                        {m.duration_min}m
                                    </span>
                                </div>
                                <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                                    {m.summary}
                                </p>

                                {m.learning_objectives &&
                                    m.learning_objectives.length > 0 && (
                                        <div className="mt-3 space-y-1">
                                            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                                                <Target className="h-2.5 w-2.5" />
                                                Objectives
                                            </div>
                                            <ul className="space-y-0.5">
                                                {m.learning_objectives.map(
                                                    (lo, i) => (
                                                        <li
                                                            key={i}
                                                            className="text-[11px] text-zinc-300 pl-3 relative leading-relaxed"
                                                        >
                                                            <span className="absolute left-0 top-1.5 w-1 h-px bg-lime-400/60" />
                                                            {lo}
                                                        </li>
                                                    )
                                                )}
                                            </ul>
                                        </div>
                                    )}

                                {m.artifact && (
                                    <div className="mt-2 flex items-start gap-1.5 border-t border-zinc-800/60 pt-2">
                                        <Package className="h-3 w-3 text-lime-400 mt-0.5 shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                                                Artifact:{" "}
                                            </span>
                                            <span className="text-[11px] text-zinc-300">
                                                {m.artifact}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}
