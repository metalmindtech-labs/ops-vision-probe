import { useEffect, useMemo, useState } from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    CartesianGrid,
    ReferenceDot,
} from "recharts";
import { VelocityAPI } from "@/lib/api";
import { TrendingUp, Activity } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

const RANGES = [
    { label: "6H", hours: 6 },
    { label: "24H", hours: 24 },
    { label: "7D", hours: 168 },
];

// Lime-on-charcoal palette — variants for up to 6 series
const SERIES_COLORS = [
    "#a3e635", // lime-400 (primary)
    "#84cc16", // lime-500
    "#bef264", // lime-300
    "#facc15", // amber 400 (whale tier hint)
    "#38bdf8", // sky 400
    "#f472b6", // pink 400
];

function fmtTime(epoch, hours) {
    const d = new Date(epoch);
    if (hours <= 24) {
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    }
    return `${d.getMonth() + 1}/${d.getDate()}`;
}

function fmtNumber(n) {
    if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
    return n.toString();
}

function TerminalTooltip({ active, payload, label, hours, seriesIndex }) {
    if (!active || !payload || !payload.length) return null;
    const d = new Date(typeof label === "number" ? label : Date.parse(label));
    return (
        <div className="border border-lime-400/40 bg-zinc-950/95 backdrop-blur px-3 py-2 rounded-sm font-mono text-[11px] shadow-lg">
            <div className="text-zinc-500 mb-1 uppercase tracking-wider">
                {d.toLocaleString([], {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false,
                })}
            </div>
            {payload.map((p) => (
                <div key={p.dataKey} className="flex items-center gap-2">
                    <span
                        className="inline-block w-2 h-0.5"
                        style={{ background: p.color }}
                    />
                    <span className="text-zinc-300 truncate max-w-[18rem]">
                        {seriesIndex[p.dataKey]?.title || p.dataKey}
                    </span>
                    <span className="text-zinc-100 ml-auto">
                        {p.value?.toLocaleString?.() ?? p.value}
                    </span>
                </div>
            ))}
        </div>
    );
}

export default function SignalVelocityChart() {
    const [hours, setHours] = useState(24);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [hiddenIds, setHiddenIds] = useState(new Set());

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        VelocityAPI.get({ hours, limit: 6 })
            .then((d) => {
                if (!cancelled) setData(d);
            })
            .catch(() => {})
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [hours]);

    const { merged, series, seriesIndex, strikes, xDomain } = useMemo(() => {
        if (!data?.series)
            return { merged: [], series: [], seriesIndex: {}, strikes: [], xDomain: undefined };
        const tBuckets = new Map();
        for (const s of data.series) {
            for (const p of s.points) {
                const epoch = new Date(p.t).getTime();
                if (!tBuckets.has(epoch)) tBuckets.set(epoch, { t: epoch });
                tBuckets.get(epoch)[s.signal_id] = p.v;
            }
        }
        // Include strike timestamps so the auto-domain X-axis extends to
        // cover them and ReferenceDots fall inside the visible range.
        for (const s of data.series) {
            for (const st of s.strikes || []) {
                const epoch = new Date(st.t).getTime();
                if (!tBuckets.has(epoch)) tBuckets.set(epoch, { t: epoch });
            }
        }
        const idx = {};
        data.series.forEach((s, i) => {
            idx[s.signal_id] = {
                title: s.title,
                category: s.category,
                priority: s.priority_score,
                current: s.current,
                color: SERIES_COLORS[i % SERIES_COLORS.length],
            };
        });
        const sorted = [...tBuckets.values()].sort((a, b) => a.t - b.t);
        // Fill forward to keep lines continuous when a snapshot is missing
        const last = {};
        for (const row of sorted) {
            for (const s of data.series) {
                if (row[s.signal_id] != null) last[s.signal_id] = row[s.signal_id];
                else if (last[s.signal_id] != null) row[s.signal_id] = last[s.signal_id];
            }
        }
        // Flatten strikes with per-series colour for ReferenceDot rendering
        const flatStrikes = [];
        for (const s of data.series) {
            const color = idx[s.signal_id].color;
            for (const st of s.strikes || []) {
                flatStrikes.push({
                    ...st,
                    signal_id: s.signal_id,
                    title: s.title,
                    color,
                });
            }
        }
        // Force a stable X-axis window (epoch ms — XAxis is type="number")
        // so sparse real data + older strikes remain visible in lookback.
        const now = Date.now();
        const cutoff = now - hours * 3600 * 1000;
        const xDomain = [cutoff, now];
        // Normalize strike x to epoch ms (XAxis is type="number")
        for (const st of flatStrikes) {
            st.tEpoch = new Date(st.t).getTime();
        }
        return {
            merged: sorted,
            series: data.series,
            seriesIndex: idx,
            strikes: flatStrikes,
            xDomain,
        };
    }, [data, hours]);

    const toggle = (id) => {
        setHiddenIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    return (
        <section
            data-testid={DASHBOARD.velocityChart}
            className="border border-zinc-800 bg-zinc-900/30 rounded-sm terminal-shadow"
        >
            <div className="flex items-center justify-between px-3 sm:px-5 py-3 border-b border-zinc-800 flex-wrap gap-3">
                <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                    <span className="h-2 w-2 rounded-full bg-lime-400 pulse-lime" />
                    <h2 className="font-mono text-sm uppercase tracking-[0.25em] text-zinc-300 inline-flex items-center gap-2">
                        <TrendingUp className="h-3.5 w-3.5 text-lime-400" />
                        Signal Velocity
                    </h2>
                    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-600">
                        top 6 · registrations / time
                    </span>
                </div>
                <div className="inline-flex items-center border border-zinc-800 rounded-sm overflow-hidden">
                    {RANGES.map((r) => (
                        <button
                            key={r.hours}
                            data-testid={DASHBOARD.velocityRangeBtn(r.label)}
                            onClick={() => setHours(r.hours)}
                            className={`px-3 py-1.5 sm:px-2.5 sm:py-1 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors ${
                                hours === r.hours
                                    ? "bg-lime-400 text-black"
                                    : "text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                            }`}
                        >
                            {r.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="p-3 sm:p-5 pt-4">
                {loading && (
                    <div className="h-64 flex items-center justify-center font-mono text-[11px] uppercase tracking-[0.25em] text-zinc-600">
                        <Activity className="h-3 w-3 mr-2 animate-pulse text-lime-400" />
                        acquiring time-series…
                    </div>
                )}
                {!loading && merged.length === 0 && (
                    <div className="h-64 flex items-center justify-center font-mono text-[11px] uppercase tracking-[0.25em] text-zinc-600">
                        no data in window
                    </div>
                )}
                {!loading && merged.length > 0 && (
                    <>
                        <div className="h-72 -ml-2" style={{ minHeight: 288 }}>
                            <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={260}>
                                <LineChart
                                    data={merged}
                                    margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
                                >
                                    <CartesianGrid
                                        stroke="#27272a"
                                        strokeDasharray="2 4"
                                        vertical={false}
                                    />
                                    <XAxis
                                        dataKey="t"
                                        type="number"
                                        scale="time"
                                        domain={xDomain || ["auto", "auto"]}
                                        tickFormatter={(v) => fmtTime(v, hours)}
                                        stroke="#52525b"
                                        tick={{
                                            fontSize: 10,
                                            fontFamily: "JetBrains Mono",
                                            fill: "#71717a",
                                        }}
                                        minTickGap={40}
                                        axisLine={{ stroke: "#27272a" }}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        tickFormatter={fmtNumber}
                                        stroke="#52525b"
                                        tick={{
                                            fontSize: 10,
                                            fontFamily: "JetBrains Mono",
                                            fill: "#71717a",
                                        }}
                                        axisLine={{ stroke: "#27272a" }}
                                        tickLine={false}
                                        width={48}
                                    />
                                    <Tooltip
                                        content={
                                            <TerminalTooltip
                                                hours={hours}
                                                seriesIndex={seriesIndex}
                                            />
                                        }
                                        cursor={{
                                            stroke: "#a3e635",
                                            strokeOpacity: 0.3,
                                            strokeDasharray: "2 3",
                                        }}
                                    />
                                    {series.map((s, i) => (
                                        <Line
                                            key={s.signal_id}
                                            type="monotone"
                                            dataKey={s.signal_id}
                                            stroke={
                                                SERIES_COLORS[i % SERIES_COLORS.length]
                                            }
                                            strokeWidth={1.5}
                                            dot={{
                                                r: 2,
                                                fill: SERIES_COLORS[i % SERIES_COLORS.length],
                                                strokeWidth: 0,
                                            }}
                                            activeDot={{
                                                r: 3,
                                                stroke: "#000",
                                                strokeWidth: 1,
                                            }}
                                            connectNulls
                                            isAnimationActive
                                            animationDuration={650}
                                            hide={hiddenIds.has(s.signal_id)}
                                        />
                                    ))}
                                    {/* Strike-attribution rings */}
                                    {strikes.map((st) => {
                                        if (hiddenIds.has(st.signal_id)) return null;
                                        const ringColor =
                                            st.tier === "breakout"
                                                ? "#f87171" // red-400
                                                : st.tier === "surge"
                                                  ? "#fbbf24" // amber-400
                                                  : "#a3e635"; // lime-400
                                        return (
                                            <ReferenceDot
                                                key={st.alert_id}
                                                data-testid={DASHBOARD.velocityStrikeDot(
                                                    st.alert_id
                                                )}
                                                x={st.tEpoch}
                                                y={st.v}
                                                r={6}
                                                fill="none"
                                                stroke={ringColor}
                                                strokeWidth={2}
                                                ifOverflow="extendDomain"
                                            >
                                                <title>
                                                    {st.tier.toUpperCase()} ·{" "}
                                                    {st.title} ·{" "}
                                                    {st.prev_count.toLocaleString()}{" "}
                                                    →{" "}
                                                    {Number(
                                                        st.v
                                                    ).toLocaleString()}{" "}
                                                    ({st.delta_pct > 0 ? "+" : ""}
                                                    {st.delta_pct}%)
                                                </title>
                                            </ReferenceDot>
                                        );
                                    })}
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Legend / Toggles */}
                        <div className="mt-3 pt-3 border-t border-zinc-800 flex flex-wrap gap-x-4 gap-y-2">
                            {series.map((s, i) => {
                                const color = SERIES_COLORS[i % SERIES_COLORS.length];
                                const hidden = hiddenIds.has(s.signal_id);
                                return (
                                    <button
                                        key={s.signal_id}
                                        data-testid={DASHBOARD.velocityLegendItem(
                                            s.signal_id
                                        )}
                                        onClick={() => toggle(s.signal_id)}
                                        className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.15em] transition-opacity max-w-full min-w-0 ${
                                            hidden ? "opacity-30" : ""
                                        }`}
                                    >
                                        <span
                                            className="inline-block w-3 h-0.5 shrink-0"
                                            style={{ background: color }}
                                        />
                                        <span className="text-zinc-300 max-w-[10rem] sm:max-w-[18rem] truncate min-w-0">
                                            {s.title}
                                        </span>
                                        <span className="text-zinc-500 shrink-0">
                                            {fmtNumber(s.current)}
                                        </span>
                                        <span
                                            className={`px-1 py-0.5 rounded-sm border shrink-0 ${
                                                s.priority_score >= 90
                                                    ? "text-lime-400 border-lime-400/40"
                                                    : "text-zinc-500 border-zinc-700"
                                            }`}
                                        >
                                            p{s.priority_score}
                                        </span>
                                        {s.strikes && s.strikes.length > 0 && (
                                            <span
                                                className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded-sm border border-red-400/40 text-red-300 shrink-0"
                                                title={`${s.strikes.length} strike(s) in window`}
                                            >
                                                ◎ {s.strikes.length}
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </>
                )}
            </div>
        </section>
    );
}
