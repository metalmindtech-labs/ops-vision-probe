import { useEffect, useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    AlertCircle,
    Copy,
    Webhook,
    Clock,
    Repeat,
    XCircle,
    CheckCircle2,
    Globe,
} from "lucide-react";
import { PublishAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

// Detailed publish-failure inspector — opens from the red FAIL badge in the
// Signal Tracker. Surfaces the exact response from LearnForge plus the last
// N retry attempts so the Architect can diagnose 404 / 401 / 500 mode in
// one glance.
export default function PublishErrorDialog({ open, onOpenChange, signalId }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [retrying, setRetrying] = useState(false);

    useEffect(() => {
        if (!open || !signalId) return;
        setLoading(true);
        PublishAPI.history(signalId, 10)
            .then(setData)
            .catch(() => toast.error("Failed to load publish history"))
            .finally(() => setLoading(false));
    }, [open, signalId]);

    const retry = async () => {
        setRetrying(true);
        const t = toast.loading("Retrying publish…");
        try {
            const r = await PublishAPI.publish(signalId);
            if (r.ok) {
                toast.success("Publish succeeded", {
                    id: t,
                    description: `HTTP ${r.status_code}`,
                });
                onOpenChange(false);
            } else {
                toast.error(`Still failing — HTTP ${r.status_code}`, {
                    id: t,
                    description: r.hint || r.error,
                });
                // refresh history
                const next = await PublishAPI.history(signalId, 10);
                setData(next);
            }
        } catch (e) {
            toast.error("Retry failed", {
                id: t,
                description: e?.message,
            });
        } finally {
            setRetrying(false);
        }
    };

    const copyDiagnostic = async () => {
        if (!data) return;
        const s = data.signal;
        const block = [
            `# Publish failure diagnostic`,
            `signal_id    : ${s.id}`,
            `title        : ${s.event_title}`,
            `webhook_url  : ${s.last_publish_webhook_url || "—"}`,
            `status_code  : ${s.last_publish_status_code ?? "—"}`,
            `error        : ${s.last_publish_error || "—"}`,
            `hint         : ${s.last_publish_hint || "—"}`,
            `attempt_at   : ${s.last_publish_at || "—"}`,
            `retry_count  : ${s.publish_retry_count ?? 0}/5`,
            `next_retry_at: ${s.publish_next_retry_at || "—"}`,
            ``,
            `## Response body (first 400 chars)`,
            s.last_publish_response_preview || "(no body captured)",
        ].join("\n");
        try {
            await navigator.clipboard.writeText(block);
            toast.success("Diagnostic copied");
        } catch {
            toast.error("Copy failed");
        }
    };

    const s = data?.signal;
    const failureMode = classifyFailure(s);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.publishErrorDialog}
                className="bg-zinc-950 border border-red-400/30 rounded-sm text-zinc-50 max-w-3xl max-h-[88vh] overflow-y-auto"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-red-300 flex items-center gap-2">
                        <AlertCircle className="h-3.5 w-3.5" />
                        Publish Failure · Error Log
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs">
                        Exact response captured from{" "}
                        <span className="font-mono text-zinc-200">
                            POST {s?.last_publish_webhook_url || "/api/courses"}
                        </span>
                        . Use this to triage with the LearnForge team.
                    </DialogDescription>
                </DialogHeader>

                {loading && (
                    <div className="font-mono text-[11px] text-zinc-500 py-12 text-center">
                        loading diagnostic…
                    </div>
                )}

                {s && (
                    <div className="space-y-4 mt-2">
                        {/* Failure mode banner */}
                        <FailureModeBanner mode={failureMode} sig={s} />

                        {/* Meta grid */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[10px]">
                            <MetaCard
                                icon={<Globe className="h-3 w-3" />}
                                label="Webhook"
                                value="POST /api/courses"
                            />
                            <MetaCard
                                icon={<AlertCircle className="h-3 w-3" />}
                                label="HTTP"
                                value={s.last_publish_status_code ?? "—"}
                                accent={
                                    s.last_publish_status_code === 200
                                        ? "lime"
                                        : "red"
                                }
                            />
                            <MetaCard
                                icon={<Repeat className="h-3 w-3" />}
                                label="Retries"
                                value={`${s.publish_retry_count ?? 0} / 5`}
                            />
                            <MetaCard
                                icon={<Clock className="h-3 w-3" />}
                                label="Next retry"
                                value={
                                    s.publish_next_retry_at
                                        ? new Date(
                                              s.publish_next_retry_at
                                          ).toLocaleTimeString()
                                        : "—"
                                }
                            />
                        </div>

                        {/* Hint */}
                        {s.last_publish_hint && (
                            <section className="border border-amber-400/30 bg-amber-400/5 rounded-sm p-3">
                                <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-amber-300 mb-1">
                                    Diagnostic
                                </h4>
                                <p className="font-mono text-[11px] text-zinc-300 leading-relaxed">
                                    {s.last_publish_hint}
                                </p>
                            </section>
                        )}

                        {/* Response body */}
                        <section>
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                Response body (first 400 chars)
                            </h4>
                            <pre className="border border-zinc-800 bg-black rounded-sm p-3 font-mono text-[11px] leading-relaxed text-zinc-300 overflow-auto max-h-32 whitespace-pre-wrap">
                                {s.last_publish_response_preview ||
                                    "(no body captured)"}
                            </pre>
                        </section>

                        {/* Recent attempts */}
                        {data.history && data.history.length > 0 && (
                            <section>
                                <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                    Last {data.history.length} attempts
                                </h4>
                                <div className="border border-zinc-800 rounded-sm divide-y divide-zinc-800 overflow-hidden">
                                    {data.history.map((h, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center gap-3 px-3 py-2 font-mono text-[10px]"
                                        >
                                            {h.status === "published" ? (
                                                <CheckCircle2 className="h-3 w-3 text-emerald-300 shrink-0" />
                                            ) : (
                                                <XCircle className="h-3 w-3 text-red-300 shrink-0" />
                                            )}
                                            <span className="text-zinc-500 w-32 truncate">
                                                {h.at
                                                    ? new Date(h.at).toLocaleString()
                                                    : "—"}
                                            </span>
                                            <span
                                                className={
                                                    h.status_code === 200
                                                        ? "text-lime-300"
                                                        : "text-red-300"
                                                }
                                            >
                                                HTTP {h.status_code ?? "—"}
                                            </span>
                                            <span className="text-zinc-400 truncate flex-1">
                                                {h.error || "ok"}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        )}
                    </div>
                )}

                <DialogFooter className="flex-wrap gap-2">
                    <Button
                        variant="ghost"
                        onClick={copyDiagnostic}
                        className="rounded-sm font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                    >
                        <Copy className="h-3 w-3 mr-1.5" />
                        Copy Diagnostic
                    </Button>
                    <Button
                        onClick={retry}
                        disabled={retrying || !s}
                        className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-xs uppercase tracking-wider font-bold disabled:opacity-50"
                    >
                        <Webhook className={`h-3 w-3 mr-1.5 ${retrying ? "animate-pulse" : ""}`} />
                        {retrying ? "Retrying…" : "Retry Publish"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function classifyFailure(s) {
    if (!s) return null;
    const code = s.last_publish_status_code;
    if (code === 200) return null;
    if (code === 404)
        return {
            kind: "route-missing",
            title: "404 · Route not deployed",
            detail:
                "LearnForge's /api/courses route does not exist yet. Deploy the receiver code from the Webhook Spec dialog.",
            color: "amber",
        };
    if (code === 401 || code === 403)
        return {
            kind: "signature",
            title: `${code} · Signature mismatch`,
            detail:
                "LearnForge rejected the X-Radar-Signature. Set LEARNFORGE_WEBHOOK_SECRET to the same value on both Radar and LearnForge.",
            color: "amber",
        };
    if (code === 422)
        return {
            kind: "payload",
            title: "422 · Invalid payload",
            detail:
                "Zod validation rejected the payload. Inspect the response body — usually a field type/name mismatch.",
            color: "amber",
        };
    if (code >= 500)
        return {
            kind: "upstream-500",
            title: `${code} · Upstream error`,
            detail:
                "LearnForge function crashed. Likely DB upsert failure — check the 'courses' table schema (price_usd nullable? metadata column?).",
            color: "red",
        };
    if (code == null && s.last_publish_error?.startsWith?.("ConnectError"))
        return {
            kind: "connect",
            title: "Connection failed",
            detail: "Couldn't reach the webhook host. Check LEARNFORGE_WEBHOOK_URL.",
            color: "red",
        };
    if (code == null && s.last_publish_error?.startsWith?.("Timeout"))
        return {
            kind: "timeout",
            title: "Upstream timeout (>20s)",
            detail: "LearnForge function timed out — cold start? Retry will run automatically.",
            color: "amber",
        };
    return null;
}

function FailureModeBanner({ mode }) {
    if (!mode) return null;
    const colorMap = {
        amber: "border-amber-400/40 bg-amber-400/5 text-amber-300",
        red: "border-red-400/40 bg-red-500/5 text-red-300",
    };
    return (
        <div
            className={`border rounded-sm p-3 space-y-1 ${colorMap[mode.color] || colorMap.red}`}
        >
            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em]">
                {mode.title}
            </h4>
            <p className="font-mono text-[11px] text-zinc-300 leading-relaxed">
                {mode.detail}
            </p>
        </div>
    );
}

function MetaCard({ icon, label, value, accent }) {
    const valueColor =
        accent === "red"
            ? "text-red-300"
            : accent === "lime"
              ? "text-lime-300"
              : "text-zinc-200";
    return (
        <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-2">
            <div className="flex items-center gap-1.5 text-zinc-500 uppercase tracking-[0.2em] text-[9px]">
                {icon}
                {label}
            </div>
            <div className={`${valueColor} mt-0.5 truncate`}>{value}</div>
        </div>
    );
}
