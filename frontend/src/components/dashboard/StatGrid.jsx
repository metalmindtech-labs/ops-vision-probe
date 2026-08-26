import { Activity, AlertTriangle, Users, Send } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

function StatCell({ label, value, sub, icon: Icon, accent, testId }) {
    return (
        <div
            data-testid={testId}
            className="group relative border border-zinc-800 bg-zinc-900/40 rounded-sm p-5 hover:border-lime-400/40 transition-colors"
        >
            <div className="flex items-start justify-between">
                <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500">
                    {label}
                </span>
                <Icon
                    className={`h-3.5 w-3.5 ${
                        accent ? "text-lime-400" : "text-zinc-600"
                    }`}
                />
            </div>
            <div className="mt-5 flex items-end justify-between">
                <div
                    className={`font-mono text-3xl sm:text-4xl font-bold tracking-tight ${
                        accent ? "text-lime-400" : "text-zinc-50"
                    }`}
                >
                    {value}
                </div>
                {sub && (
                    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 pb-1">
                        {sub}
                    </span>
                )}
            </div>
            <div className="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-lime-400/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
    );
}

export default function StatGrid({ stats, loading }) {
    const total = stats?.total_signals ?? 0;
    const high = stats?.high_priority ?? 0;
    const reg = stats?.total_registrations ?? 0;
    const dispatched = stats?.briefs_dispatched ?? 0;

    return (
        <section className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <StatCell
                label="Signals Tracked"
                value={loading ? "—" : total.toString().padStart(3, "0")}
                sub="active"
                icon={Activity}
                testId={DASHBOARD.headerStatsTotal}
            />
            <StatCell
                label="High Priority"
                value={loading ? "—" : high.toString().padStart(2, "0")}
                sub="score ≥ 80"
                icon={AlertTriangle}
                accent
                testId={DASHBOARD.headerStatsHigh}
            />
            <StatCell
                label="Total Reg Volume"
                value={loading ? "—" : reg.toLocaleString()}
                sub="learners"
                icon={Users}
                testId={DASHBOARD.headerStatsReg}
            />
            <StatCell
                label="Briefs Dispatched"
                value={loading ? "—" : dispatched.toString().padStart(2, "0")}
                sub="to learnforge"
                icon={Send}
                accent
                testId={DASHBOARD.headerStatsSyllabi}
            />
        </section>
    );
}
