import { CircleDot, Clock4, History } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

function timeAgo(iso) {
    if (!iso) return "never";
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return "—";
    const diff = Math.max(0, Date.now() - t);
    const m = Math.floor(diff / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
}

function nextIn(iso) {
    if (!iso) return "—";
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return "—";
    const diff = t - Date.now();
    if (diff <= 0) return "imminent";
    const m = Math.floor(diff / 60000);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ${m % 60}m`;
    return `${Math.floor(h / 24)}d`;
}

export default function ScraperStatusBar({ status }) {
    const last = status?.last_run;
    const running = status?.scheduler_running;
    return (
        <div
            data-testid={DASHBOARD.scraperStatusBar}
            className="mt-6 flex items-center justify-between gap-4 flex-wrap border border-zinc-800 bg-zinc-900/30 rounded-sm px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.2em]"
        >
            <div className="flex items-center gap-5 flex-wrap">
                <div className="flex items-center gap-2">
                    <CircleDot
                        className={`h-3 w-3 ${
                            running ? "text-lime-400 pulse-lime" : "text-zinc-600"
                        }`}
                    />
                    <span className="text-zinc-300">
                        Scheduler {running ? "online" : "offline"}
                    </span>
                </div>
                <div className="flex items-center gap-2 text-zinc-500">
                    <Clock4 className="h-3 w-3" />
                    every {status?.interval_hours ?? 12}h
                </div>
                <div className="flex items-center gap-2 text-zinc-500">
                    <History className="h-3 w-3" />
                    last scrape:{" "}
                    <span className="text-zinc-300">
                        {timeAgo(last?.ran_at)}
                    </span>
                </div>
                {last && (
                    <div className="text-zinc-500">
                        discovered{" "}
                        <span className="text-zinc-100">{last.discovered}</span>{" "}
                        · new{" "}
                        <span className="text-lime-400">{last.created}</span> ·
                        updated{" "}
                        <span className="text-zinc-300">{last.updated}</span>
                    </div>
                )}
            </div>
            <div className="text-zinc-500">
                next in{" "}
                <span className="text-zinc-300">{nextIn(status?.next_run_at)}</span>
            </div>
        </div>
    );
}
