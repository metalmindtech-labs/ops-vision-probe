import { useMemo, useState } from "react";
import { AlertTriangle, X, TrendingUp, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DASHBOARD } from "@/constants/testIds/dashboard";

function fmtPct(pct) {
    const sign = pct > 0 ? "+" : "";
    return `${sign}${pct}%`;
}

function tierFor(pct) {
    if (pct >= 100) return { label: "BREAKOUT", cls: "text-red-400 border-red-400/40 bg-red-500/5" };
    if (pct >= 50) return { label: "SURGE", cls: "text-amber-300 border-amber-400/40 bg-amber-500/5" };
    return { label: "STRIKE", cls: "text-lime-400 border-lime-400/40 bg-lime-400/5" };
}

export default function StrikeAlertsBanner({ alerts, onAck, onAckAll, onJump }) {
    const [expanded, setExpanded] = useState(true);
    const sorted = useMemo(
        () => [...(alerts || [])].sort((a, b) => b.delta_pct - a.delta_pct),
        [alerts]
    );
    if (!sorted.length) return null;
    const top = sorted[0];

    return (
        <div
            data-testid={DASHBOARD.strikeBanner}
            className="mt-6 border border-lime-400/30 bg-zinc-900/40 rounded-sm overflow-hidden animate-fade-in"
        >
            <button
                onClick={() => setExpanded((v) => !v)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-lime-400/[0.03] transition-colors text-left"
            >
                <div className="flex items-center gap-3 flex-wrap">
                    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-lime-400">
                        <AlertTriangle className="h-3 w-3" />
                        Strike Signals
                    </span>
                    <span className="font-mono text-xs text-zinc-100">
                        {sorted.length} new surge{sorted.length === 1 ? "" : "s"} detected
                    </span>
                    <span className="font-mono text-[10px] text-zinc-500">
                        top:{" "}
                        <span className="text-lime-300">
                            {top.signal_title.slice(0, 60)}
                            {top.signal_title.length > 60 ? "…" : ""}
                        </span>{" "}
                        · {top.prev_count.toLocaleString()} →{" "}
                        {top.new_count.toLocaleString()} ({fmtPct(top.delta_pct)})
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    {expanded && (
                        <span
                            role="button"
                            tabIndex={0}
                            data-testid={DASHBOARD.strikeBannerAckAll}
                            onClick={(e) => {
                                e.stopPropagation();
                                onAckAll();
                            }}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    onAckAll();
                                }
                            }}
                            className="cursor-pointer rounded-sm font-mono text-[10px] uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800 px-2 py-1"
                        >
                            Dismiss All
                        </span>
                    )}
                    {expanded ? (
                        <ChevronUp className="h-4 w-4 text-zinc-500" />
                    ) : (
                        <ChevronDown className="h-4 w-4 text-zinc-500" />
                    )}
                </div>
            </button>

            {expanded && (
                <div className="border-t border-zinc-800 divide-y divide-zinc-800/70">
                    {sorted.map((a) => {
                        const tier = tierFor(a.delta_pct);
                        return (
                            <div
                                key={a.id}
                                data-testid={DASHBOARD.strikeAlertItem(a.id)}
                                className="flex items-center gap-4 px-4 py-2.5 hover:bg-lime-400/[0.02] group"
                            >
                                <span
                                    className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider whitespace-nowrap ${tier.cls}`}
                                >
                                    <TrendingUp className="h-3 w-3" />
                                    {tier.label}
                                </span>
                                <button
                                    onClick={() => onJump?.(a.signal_id)}
                                    className="flex-1 text-left min-w-0"
                                >
                                    <div className="font-mono text-sm text-zinc-100 truncate group-hover:text-lime-300 transition-colors">
                                        {a.signal_title}
                                    </div>
                                    <div className="font-mono text-[10px] text-zinc-500 mt-0.5">
                                        {a.prev_count.toLocaleString()} →{" "}
                                        <span className="text-zinc-200">
                                            {a.new_count.toLocaleString()}
                                        </span>{" "}
                                        regs ·{" "}
                                        <span className="text-lime-400">
                                            {fmtPct(a.delta_pct)}
                                        </span>
                                    </div>
                                </button>
                                <Button
                                    data-testid={DASHBOARD.strikeAlertAck(a.id)}
                                    size="icon"
                                    variant="ghost"
                                    onClick={() => onAck(a.id)}
                                    className="h-7 w-7 rounded-sm text-zinc-500 hover:text-zinc-50 hover:bg-zinc-800"
                                    aria-label="Dismiss alert"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </Button>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
