import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    Send,
    FileJson,
    RefreshCw,
    ArrowUpRight,
    CheckCircle2,
    XCircle,
} from "lucide-react";
import { BriefAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

const STATE_STYLES = {
    accepted: "border-zinc-600 text-zinc-300 bg-zinc-800/40",
    queued: "border-sky-400/40 text-sky-300 bg-sky-400/5",
    generating: "border-amber-400/40 text-amber-300 bg-amber-400/5",
    reviewing: "border-violet-400/40 text-violet-300 bg-violet-400/5",
    ready: "border-emerald-400/40 text-emerald-300 bg-emerald-400/5",
    failed: "border-red-400/40 text-red-300 bg-red-500/5",
};

function JobStatusChip({ job }) {
    if (!job) {
        return (
            <span
                data-testid={DASHBOARD.jobStatusChip}
                className="inline-flex items-center gap-1 rounded-sm border border-zinc-700 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-500"
            >
                no brief dispatched
            </span>
        );
    }
    const cls = STATE_STYLES[job.status] || STATE_STYLES.accepted;
    const Icon = job.status === "ready" ? CheckCircle2 : job.status === "failed" ? XCircle : null;
    return (
        <span
            data-testid={DASHBOARD.jobStatusChip}
            className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${cls}`}
        >
            {Icon && <Icon className="h-3 w-3" />}
            {job.status}
        </span>
    );
}

export default function BriefDispatchPanel({ signal, onDispatched }) {
    const [brief, setBrief] = useState(null);
    const [showBrief, setShowBrief] = useState(false);
    const [dispatching, setDispatching] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [result, setResult] = useState(null);
    const [job, setJob] = useState(null);
    const [autoPolling, setAutoPolling] = useState(false);
    const onDispatchedRef = useRef(onDispatched);
    useEffect(() => {
        onDispatchedRef.current = onDispatched;
    }, [onDispatched]);

    useEffect(() => {
        setBrief(null);
        setShowBrief(false);
        setResult(null);
        setJob(null);
        if (signal?.id) {
            BriefAPI.jobStatus(signal.id)
                .then((r) => setJob(r.job))
                .catch(() => {});
        }
    }, [signal?.id]);

    // Auto-poll LearnForge status while the job is non-terminal, so it lights
    // up READY (or failed) on its own without a manual refresh click.
    useEffect(() => {
        const jobId = job?.job_id;
        const status = job?.status;
        const terminal = status === "ready" || status === "failed";
        if (!jobId || terminal) {
            setAutoPolling(false);
            return;
        }
        setAutoPolling(true);
        let cancelled = false;
        const tick = async () => {
            try {
                const r = await BriefAPI.refreshJob(jobId);
                if (cancelled) return;
                const next = r?.job?.status;
                setJob(r.job);
                if (next === "ready") {
                    toast.success("Course is READY on LearnForge", {
                        description: "Generation complete — no refresh needed.",
                    });
                    onDispatchedRef.current?.();
                } else if (next === "failed") {
                    toast.error("LearnForge job failed", {
                        description: r?.job?.error || "Check the job status.",
                    });
                }
            } catch {
                // transient — keep polling silently
            }
        };
        tick(); // leading check so an already-terminal job lights up immediately
        const id = setInterval(tick, 6000);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, [job?.job_id, job?.status]);

    if (!signal) return null;

    const loadPreview = async () => {
        if (brief) {
            setShowBrief((v) => !v);
            return;
        }
        try {
            const b = await BriefAPI.preview(signal.id);
            setBrief(b);
            setShowBrief(true);
        } catch (e) {
            toast.error("Brief preview failed", { description: e?.message });
        }
    };

    const dispatch = async () => {
        setDispatching(true);
        setResult(null);
        const t = toast.loading("Dispatching Course Brief to LearnForge…");
        try {
            const res = await BriefAPI.dispatch(signal.id);
            setResult(res);
            setJob(res.job);
            if (res.ok && res.deduplicated) {
                toast.info("Brief already dispatched", {
                    id: t,
                    description: "Identical brief content — idempotency held.",
                });
            } else if (res.ok) {
                toast.success("Brief dispatched to LearnForge", {
                    id: t,
                    description: `Job ${res.job?.status} · LearnForge now owns generation.`,
                });
            } else {
                toast.error("Dispatch failed", {
                    id: t,
                    description: res.error || `HTTP ${res.status_code ?? "—"}`,
                });
            }
            if (onDispatched) await onDispatched();
        } catch (e) {
            toast.error("Dispatch failed", { id: t, description: e?.message });
        } finally {
            setDispatching(false);
        }
    };

    const refreshStatus = async () => {
        if (!job?.job_id) return;
        setRefreshing(true);
        try {
            const r = await BriefAPI.refreshJob(job.job_id);
            setJob(r.job);
            if (r.ok) {
                toast.success(`LearnForge job: ${r.job?.status}`);
            } else {
                toast.warning("Status check failed", { description: r.error });
            }
        } catch (e) {
            toast.error("Status check failed", { description: e?.message });
        } finally {
            setRefreshing(false);
        }
    };

    return (
        <section className="space-y-3" data-testid="brief-dispatch-panel">
            <div className="flex items-center justify-between">
                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-300">
                    05 · Dispatch to LearnForge
                </h3>
                <JobStatusChip job={job} />
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
                Radar discovers demand and dispatches a signed{" "}
                <span className="font-mono text-zinc-200">CourseBriefV2</span>{" "}
                (evidence + audience + offer hypothesis).{" "}
                <span className="text-zinc-200 font-medium">LearnForge</span>{" "}
                owns syllabus, modules, lessons, review, and course delivery.
            </p>

            <div className="grid grid-cols-2 gap-2">
                <Button
                    data-testid={DASHBOARD.briefPreviewBtn}
                    onClick={loadPreview}
                    variant="outline"
                    className="rounded-sm border-zinc-800 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 font-mono text-[10px] uppercase tracking-wider"
                >
                    <FileJson className="h-3.5 w-3.5 mr-2" />
                    {showBrief ? "Hide Brief" : "Preview Course Brief"}
                </Button>
                <Button
                    data-testid={DASHBOARD.dispatchBriefBtn}
                    onClick={dispatch}
                    disabled={dispatching}
                    className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-[10px] uppercase tracking-wider font-bold disabled:opacity-60"
                >
                    <Send className={`h-3.5 w-3.5 mr-2 ${dispatching ? "animate-pulse" : ""}`} />
                    {dispatching ? "Dispatching…" : "Dispatch Brief"}
                </Button>
            </div>

            {showBrief && brief && (
                <pre
                    data-testid={DASHBOARD.briefPreviewJson}
                    className="text-[10px] text-zinc-400 bg-zinc-950 border border-zinc-800 rounded-sm p-2 overflow-x-auto max-h-64 whitespace-pre"
                >
                    {JSON.stringify(brief, null, 2)}
                </pre>
            )}

            {job && (
                <div className="flex items-center justify-between border border-zinc-800 rounded-sm px-3 py-2 font-mono text-[10px]">
                    <div className="flex items-center gap-2 min-w-0">
                        <span className="text-zinc-500 uppercase tracking-[0.2em]">
                            job
                        </span>
                        <span className="text-zinc-400 truncate">
                            {job.job_id?.slice(0, 8)} · {job.status}
                            {job.dispatched_at
                                ? ` · ${new Date(job.dispatched_at).toLocaleString()}`
                                : ""}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        {autoPolling && (
                            <span
                                data-testid={DASHBOARD.jobAutoSync}
                                className="inline-flex items-center gap-1 text-sky-300/80 uppercase tracking-wider"
                                title="Auto-syncing LearnForge status"
                            >
                                <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
                                auto-sync
                            </span>
                        )}
                        {job.public_course_url && (
                            <a
                                data-testid={DASHBOARD.jobPublicUrl}
                                href={job.public_course_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-lime-300 hover:text-lime-200 uppercase tracking-wider"
                            >
                                course <ArrowUpRight className="h-3 w-3" />
                            </a>
                        )}
                        <button
                            data-testid={DASHBOARD.jobRefreshBtn}
                            onClick={refreshStatus}
                            disabled={refreshing}
                            className="inline-flex items-center gap-1 text-zinc-400 hover:text-lime-300 uppercase tracking-wider disabled:opacity-50"
                        >
                            <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
                            refresh
                        </button>
                    </div>
                </div>
            )}

            {result && !result.deduplicated && (
                <div
                    data-testid={DASHBOARD.dispatchResultPanel}
                    className={`border rounded-sm p-3 font-mono text-[11px] space-y-2 ${
                        result.ok
                            ? "border-emerald-400/30 bg-emerald-400/5"
                            : "border-red-400/30 bg-red-500/5"
                    }`}
                >
                    <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.2em]">
                        <span className={result.ok ? "text-emerald-300" : "text-red-300"}>
                            {result.ok ? "✓ brief accepted" : "✗ dispatch failed"}
                        </span>
                        <span className="text-zinc-500">
                            {result.status_code ? `HTTP ${result.status_code}` : "no response"}
                        </span>
                    </div>
                    {result.error && result.error !== `HTTP ${result.status_code}` && (
                        <div className="text-red-300 text-[10px] leading-relaxed">
                            {result.error}
                        </div>
                    )}
                    {result.hint && (
                        <div className="text-amber-300 text-[10px] leading-relaxed border-t border-amber-400/20 pt-2">
                            <span className="uppercase tracking-[0.2em] text-amber-400/70">
                                debug ·{" "}
                            </span>
                            {result.hint}
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}
