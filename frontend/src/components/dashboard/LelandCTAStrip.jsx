import { ArrowUpRight } from "lucide-react";
import { LEARNFORGE_URL } from "@/lib/learnforge";

export default function LelandCTAStrip() {
    return (
        <div className="relative overflow-hidden border border-lime-400/30 bg-zinc-950 rounded-sm">
            <div className="absolute inset-0 grid-bg opacity-50" />
            <div className="absolute -right-12 -top-12 w-32 h-32 rounded-full bg-lime-400/10 blur-2xl" />
            <div className="relative p-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-lime-400">
                    Demand → LearnForge
                </span>
                <h3 className="mt-3 font-mono text-lg text-zinc-50 leading-tight">
                    Dispatch course briefs to{" "}
                    <span className="text-lime-400">learnforge-core.vercel.app</span>
                </h3>
                <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
                    Every converted signal becomes a signed CourseBriefV2 —
                    dispatched to LearnForge, which owns generation and
                    publishing of the live course.
                </p>
                <a
                    href={LEARNFORGE_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.2em] text-zinc-100 hover:text-lime-400 transition-colors group"
                >
                    Open LearnForge
                    <ArrowUpRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                </a>
            </div>
        </div>
    );
}
