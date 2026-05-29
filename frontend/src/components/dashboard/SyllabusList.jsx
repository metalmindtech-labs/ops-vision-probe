import { Clock } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

export default function SyllabusList({ modules }) {
    if (!modules || modules.length === 0) return null;
    return (
        <section data-testid={DASHBOARD.syllabusList}>
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-lime-400">
                    04 · Generated Syllabus
                </h3>
                <span className="font-mono text-[10px] text-zinc-500">
                    {modules.length} modules
                </span>
            </div>
            <div className="space-y-2">
                {modules.map((m) => (
                    <div
                        key={m.index}
                        className="border border-zinc-800 hover:border-lime-400/30 bg-zinc-900/30 rounded-sm p-4 transition-colors group"
                    >
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
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}
