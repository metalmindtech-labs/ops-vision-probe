import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowUpRight, Pencil, Trash2, Zap } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

function PriorityCell({ score }) {
    const tier =
        score >= 85 ? "critical" : score >= 70 ? "high" : score >= 50 ? "med" : "low";
    const color =
        tier === "critical"
            ? "text-lime-400"
            : tier === "high"
              ? "text-amber-300"
              : tier === "med"
                ? "text-sky-300"
                : "text-zinc-500";
    return (
        <div className="flex items-center gap-2">
            <span
                className={`priority-dot inline-block w-1.5 h-1.5 rounded-full ${color}`}
                style={{ backgroundColor: "currentColor" }}
            />
            <span className={`font-mono text-sm ${color}`}>{score}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-600">
                {tier}
            </span>
        </div>
    );
}

function StatusPill({ status, published }) {
    const map = {
        tracked: { label: "TRACKED", cls: "border-zinc-700 text-zinc-400" },
        converting: {
            label: "CONVERTING",
            cls: "border-lime-400/40 text-lime-400 bg-lime-400/5",
        },
        live: {
            label: "LIVE",
            cls: "border-emerald-400/40 text-emerald-300 bg-emerald-400/5",
        },
    };
    const cfg = map[status] || map.tracked;
    return (
        <div className="flex items-center gap-1.5 flex-wrap">
            <Badge
                variant="outline"
                className={`rounded-sm font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 ${cfg.cls}`}
            >
                {cfg.label}
            </Badge>
            {published && (
                <Badge
                    variant="outline"
                    className="rounded-sm font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border-emerald-400/40 text-emerald-300 bg-emerald-400/5"
                    title="Published to LearnForge"
                >
                    PUB
                </Badge>
            )}
        </div>
    );
}

export default function SignalTable({
    signals,
    loading,
    onConvert,
    onEdit,
    onDelete,
}) {
    return (
        <section className="border border-zinc-800 bg-zinc-900/30 rounded-sm terminal-shadow">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
                <div className="flex items-center gap-3">
                    <span className="h-2 w-2 rounded-full bg-lime-400 pulse-lime" />
                    <h2 className="font-mono text-sm uppercase tracking-[0.25em] text-zinc-300">
                        Signal Tracker
                    </h2>
                </div>
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-600">
                    sorted · priority desc
                </span>
            </div>

            <div className="overflow-x-auto">
                <Table data-testid={DASHBOARD.signalTable}>
                    <TableHeader>
                        <TableRow className="border-zinc-800 hover:bg-transparent">
                            <TableHead className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 w-[38%]">
                                Event Title
                            </TableHead>
                            <TableHead className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                Category
                            </TableHead>
                            <TableHead className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 text-right">
                                Registrations
                            </TableHead>
                            <TableHead className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                Priority
                            </TableHead>
                            <TableHead className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                Status
                            </TableHead>
                            <TableHead className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 text-right">
                                Actions
                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading && (
                            <TableRow>
                                <TableCell
                                    colSpan={6}
                                    className="text-center py-10 font-mono text-xs text-zinc-500"
                                >
                                    Acquiring signal lock…
                                </TableCell>
                            </TableRow>
                        )}
                        {!loading && signals.length === 0 && (
                            <TableRow>
                                <TableCell
                                    colSpan={6}
                                    className="text-center py-12 font-mono text-xs text-zinc-500"
                                >
                                    No signals yet. Log your first opportunity.
                                </TableCell>
                            </TableRow>
                        )}
                        {!loading &&
                            signals.map((s) => (
                                <TableRow
                                    key={s.id}
                                    data-testid={DASHBOARD.signalRow(s.id)}
                                    className="border-zinc-800 hover:bg-lime-400/[0.03] transition-colors group"
                                >
                                    <TableCell className="py-4">
                                        <div className="flex flex-col gap-0.5">
                                            <span className="text-sm font-medium text-zinc-100 group-hover:text-lime-300 transition-colors">
                                                {s.event_title}
                                            </span>
                                            <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-600 truncate max-w-md">
                                                {s.source_url ||
                                                    "leland.com/events/…"}
                                            </span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <span className="font-mono text-xs text-zinc-300">
                                            {s.category}
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <span className="font-mono text-sm text-zinc-100">
                                            {(s.registration_count || 0).toLocaleString()}
                                        </span>
                                        <span className="font-mono text-xs text-lime-400/80 ml-1">
                                            +
                                        </span>
                                    </TableCell>
                                    <TableCell
                                        data-testid={DASHBOARD.signalRowPriority(
                                            s.id
                                        )}
                                    >
                                        <PriorityCell score={s.priority_score || 0} />
                                    </TableCell>
                                    <TableCell>
                                        <StatusPill
                                            status={s.status}
                                            published={s.publish_status === "published"}
                                        />
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <div className="inline-flex items-center gap-1">
                                            <Button
                                                data-testid={DASHBOARD.signalRowConvert(
                                                    s.id
                                                )}
                                                size="sm"
                                                onClick={() => onConvert(s)}
                                                className="h-7 rounded-sm bg-lime-400 text-black hover:bg-lime-300 font-mono text-[10px] uppercase tracking-wider px-2"
                                            >
                                                <Zap className="h-3 w-3 mr-1" />
                                                Convert
                                            </Button>
                                            <Button
                                                size="icon"
                                                variant="ghost"
                                                onClick={() => onEdit(s)}
                                                className="h-7 w-7 rounded-sm text-zinc-500 hover:text-zinc-50 hover:bg-zinc-800"
                                            >
                                                <Pencil className="h-3.5 w-3.5" />
                                            </Button>
                                            <Button
                                                data-testid={DASHBOARD.signalRowDelete(
                                                    s.id
                                                )}
                                                size="icon"
                                                variant="ghost"
                                                onClick={() => onDelete(s.id)}
                                                className="h-7 w-7 rounded-sm text-zinc-600 hover:text-red-400 hover:bg-red-500/10"
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                    </TableBody>
                </Table>
            </div>

            <div className="px-5 py-3 border-t border-zinc-800 flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-600">
                    {signals.length} signal{signals.length === 1 ? "" : "s"} ·
                    last sync now
                </span>
                <a
                    href="https://leland.com/events"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 hover:text-lime-400 inline-flex items-center gap-1 transition-colors"
                >
                    source: leland event-stream
                    <ArrowUpRight className="h-3 w-3" />
                </a>
            </div>
        </section>
    );
}
