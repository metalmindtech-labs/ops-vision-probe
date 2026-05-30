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
    MessageCircle,
    Settings2,
    CheckCircle2,
    XCircle,
    Webhook,
    KeyRound,
    FileJson,
    Copy,
    Download,
    Send,
} from "lucide-react";
import { IntegrationsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

export default function IntegrationsBadge({ status, onRefresh }) {
    const [open, setOpen] = useState(false);
    const [testing, setTesting] = useState(false);
    const [specOpen, setSpecOpen] = useState(false);
    const [spec, setSpec] = useState(null);
    const wa = status?.whatsapp;
    const wh = status?.publish_webhook;

    const dotColor = wa?.configured ? "bg-emerald-400" : "bg-zinc-600";

    const testWA = async () => {
        setTesting(true);
        const t = toast.loading("Pinging WhatsApp…");
        try {
            const res = await IntegrationsAPI.testWhatsApp();
            if (res.ok) {
                toast.success("WhatsApp test sent", {
                    id: t,
                    description: `SID: ${res.sid}`,
                });
            } else if (res.skipped) {
                toast.error("WhatsApp not configured", {
                    id: t,
                    description: res.reason,
                });
            } else {
                toast.error("WhatsApp send failed", {
                    id: t,
                    description: res.error,
                });
            }
        } catch (e) {
            toast.error("Test failed", { id: t, description: e?.message });
        } finally {
            setTesting(false);
            if (onRefresh) await onRefresh();
        }
    };

    return (
        <>
            <button
                data-testid={DASHBOARD.integrationsBadge}
                onClick={() => setOpen(true)}
                className="inline-flex items-center gap-2 rounded-sm border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-300 transition-colors"
                title="Integrations status"
            >
                <Settings2 className="h-3 w-3 text-zinc-500" />
                <span className="hidden md:inline">Integrations</span>
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} />
            </button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent
                    data-testid={DASHBOARD.integrationsDialog}
                    className="bg-zinc-950 border border-zinc-800 rounded-sm text-zinc-50 max-w-lg"
                >
                    <DialogHeader>
                        <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-lime-400">
                            Integrations
                        </DialogTitle>
                        <DialogDescription className="text-zinc-400 text-xs">
                            Configure outbound channels in{" "}
                            <span className="font-mono text-zinc-200">
                                /app/backend/.env
                            </span>{" "}
                            and restart the backend to enable.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-3 mt-2 max-h-[70vh] overflow-y-auto pr-1">
                        {/* LearnForge handoff callout — surfaces the 404 root cause
                            and gives the Architect a one-click way to hand off the
                            exact spec the LearnForge team needs to deploy. */}
                        <LearnForgeHandoffCallout webhookUrl={wh?.url} />

                        {/* WhatsApp */}
                        <div className="border border-zinc-800 rounded-sm p-4 space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <MessageCircle className="h-4 w-4 text-emerald-400" />
                                    <span className="font-mono text-sm text-zinc-50">
                                        WhatsApp Push
                                    </span>
                                </div>
                                {wa?.configured ? (
                                    <span className="inline-flex items-center gap-1 rounded-sm border border-emerald-400/40 bg-emerald-400/5 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-emerald-300">
                                        <CheckCircle2 className="h-3 w-3" />
                                        Configured
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-1 rounded-sm border border-zinc-700 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                                        <XCircle className="h-3 w-3" />
                                        Not Configured
                                    </span>
                                )}
                            </div>
                            <div className="font-mono text-[11px] text-zinc-400 space-y-1">
                                <div>
                                    Threshold ≥{" "}
                                    <span className="text-lime-400">
                                        {wa?.threshold ?? 90}
                                    </span>{" "}
                                    priority
                                </div>
                                {wa?.configured ? (
                                    <>
                                        <div>From: {wa.from_number}</div>
                                        <div>To: {wa.to_number_masked}</div>
                                    </>
                                ) : (
                                    <div className="text-zinc-500">
                                        {wa?.reason || "—"}
                                    </div>
                                )}
                            </div>
                            <Button
                                data-testid={DASHBOARD.whatsappTestBtn}
                                onClick={testWA}
                                disabled={testing}
                                size="sm"
                                className="rounded-sm bg-emerald-500 hover:bg-emerald-400 text-black font-mono text-[10px] uppercase tracking-wider font-bold mt-2 disabled:opacity-50"
                            >
                                {testing ? "Sending…" : "Send Test Ping"}
                            </Button>
                            <p className="font-mono text-[10px] text-zinc-600 mt-1">
                                Required env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                                TWILIO_WHATSAPP_TO
                            </p>
                        </div>

                        {/* Publish webhook */}
                        <div className="border border-zinc-800 rounded-sm p-4 space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Webhook className="h-4 w-4 text-lime-400" />
                                    <span className="font-mono text-sm text-zinc-50">
                                        Publish Webhook
                                    </span>
                                </div>
                                {wh?.url ? (
                                    <span className="inline-flex items-center gap-1 rounded-sm border border-lime-400/40 bg-lime-400/5 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-lime-300">
                                        <CheckCircle2 className="h-3 w-3" />
                                        Set
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-1 rounded-sm border border-zinc-700 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                                        <XCircle className="h-3 w-3" />
                                        Not Set
                                    </span>
                                )}
                            </div>
                            <div className="font-mono text-[11px] text-zinc-400 space-y-1 break-all">
                                <div>URL: {wh?.url || "—"}</div>
                                <div className="flex items-center gap-1 flex-wrap">
                                    <KeyRound className="h-3 w-3" />
                                    Signing secret:{" "}
                                    <span
                                        data-testid="webhook-signing-status"
                                        className={`font-bold ${
                                            wh?.has_secret
                                                ? "text-lime-400"
                                                : "text-zinc-500"
                                        }`}
                                    >
                                        {wh?.has_secret ? "ENABLED" : "DISABLED"}
                                    </span>
                                    {wh?.has_secret && (
                                        <span className="text-zinc-600">
                                            · {wh.signature_algorithm || "hmac-sha256"} →{" "}
                                            {wh.signature_header || "X-Radar-Signature"}
                                        </span>
                                    )}
                                </div>
                            </div>
                            <Button
                                data-testid={DASHBOARD.payloadSpecBtn}
                                onClick={async () => {
                                    setSpecOpen(true);
                                    if (!spec) {
                                        try {
                                            const s = await IntegrationsAPI.publishSpec();
                                            setSpec(s);
                                        } catch (e) {
                                            toast.error("Failed to load spec");
                                        }
                                    }
                                }}
                                size="sm"
                                variant="outline"
                                className="rounded-sm border-lime-400/40 bg-lime-400/5 text-lime-300 hover:bg-lime-400/10 hover:text-lime-200 font-mono text-[10px] uppercase tracking-wider mt-2"
                            >
                                <FileJson className="h-3 w-3 mr-1.5" />
                                View Payload Spec
                            </Button>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="ghost"
                            onClick={() => setOpen(false)}
                            className="rounded-sm font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                        >
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <PayloadSpecDialog open={specOpen} onOpenChange={setSpecOpen} spec={spec} />
        </>
    );
}

function PayloadSpecDialog({ open, onOpenChange, spec }) {
    const copyExample = async () => {
        try {
            await navigator.clipboard.writeText(
                JSON.stringify(spec?.example, null, 2)
            );
            toast.success("Example payload copied");
        } catch {
            toast.error("Copy failed");
        }
    };
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.payloadSpecDialog}
                className="bg-zinc-950 border border-zinc-800 rounded-sm text-zinc-50 max-w-3xl max-h-[90vh] overflow-y-auto"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-lime-400 flex items-center gap-2">
                        <FileJson className="h-3.5 w-3.5" />
                        POST /api/courses Payload Contract (v1)
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs">
                        Stable JSON schema for the LearnForge publish webhook.
                        Paste this into your{" "}
                        <span className="font-mono text-zinc-200">learnforge-core</span>{" "}
                        FastAPI handler.
                    </DialogDescription>
                </DialogHeader>

                {!spec && (
                    <div className="font-mono text-[11px] text-zinc-500 py-8 text-center">
                        loading spec…
                    </div>
                )}
                {spec && (
                    <div className="space-y-4 mt-2">
                        <section>
                            <div className="flex items-center justify-between mb-2">
                                <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400">
                                    Endpoint
                                </h4>
                            </div>
                            <pre className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 font-mono text-[11px] text-lime-400 overflow-x-auto">
                                POST {spec.webhook_url || "<configure LEARNFORGE_WEBHOOK_URL>"}
                            </pre>
                        </section>

                        <section>
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                Request Headers
                            </h4>
                            <pre className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 font-mono text-[11px] text-zinc-300 overflow-x-auto">
{Object.entries(spec.request_headers || {})
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n")}
                            </pre>
                        </section>

                        <section>
                            <div className="flex items-center justify-between mb-2">
                                <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400">
                                    Example Payload
                                </h4>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={copyExample}
                                    className="h-6 rounded-sm font-mono text-[10px] uppercase tracking-wider text-zinc-400 hover:text-lime-400 hover:bg-zinc-800"
                                >
                                    <Copy className="h-3 w-3 mr-1" />
                                    Copy
                                </Button>
                            </div>
                            <pre className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 font-mono text-[11px] text-zinc-300 overflow-x-auto max-h-72">
                                {JSON.stringify(spec.example, null, 2)}
                            </pre>
                        </section>

                        <section>
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                Expected Response
                            </h4>
                            <pre className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 font-mono text-[11px] text-zinc-300 overflow-x-auto">
                                {JSON.stringify(spec.expected_response, null, 2)}
                            </pre>
                        </section>

                        <section>
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                JSON Schema
                            </h4>
                            <pre className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 font-mono text-[11px] text-zinc-300 overflow-x-auto max-h-72">
                                {JSON.stringify(spec.schema, null, 2)}
                            </pre>
                        </section>
                    </div>
                )}

                <DialogFooter>
                    <Button
                        variant="ghost"
                        onClick={() => onOpenChange(false)}
                        className="rounded-sm font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                    >
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}


// LearnForge handoff callout — shows the current publish-status flag and
// lets the Architect copy/download the full ingest spec to send to the
// LearnForge team. Lives at the top of the Integrations dialog so the 404
// root cause and the fix are both one click away.
function LearnForgeHandoffCallout({ webhookUrl }) {
    const [copying, setCopying] = useState(false);
    const docUrl = IntegrationsAPI.handoffDocUrl();

    const copy = async () => {
        setCopying(true);
        const t = toast.loading("Building handoff doc…");
        try {
            const md = await IntegrationsAPI.handoffDoc();
            await navigator.clipboard.writeText(md);
            toast.success("Handoff doc copied", {
                id: t,
                description: "Paste into Slack / GitHub issue / PR description.",
            });
        } catch (e) {
            toast.error("Copy failed", { id: t, description: e?.message });
        } finally {
            setCopying(false);
        }
    };

    return (
        <div
            data-testid={DASHBOARD.handoffCallout}
            className="border border-amber-400/30 bg-amber-400/5 rounded-sm p-4 space-y-3"
        >
            <div className="flex items-start gap-3">
                <Send className="h-4 w-4 text-amber-300 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                    <h3 className="font-mono text-xs uppercase tracking-[0.2em] text-amber-300">
                        LearnForge Team Handoff
                    </h3>
                    <p className="font-mono text-[11px] text-zinc-400 mt-1 leading-relaxed">
                        Radar is sending the canonical{" "}
                        <span className="text-zinc-200">course.publish</span>{" "}
                        payload signed with{" "}
                        <span className="text-lime-300">HMAC-SHA256</span>. If
                        publishes are still landing in{" "}
                        <span className="text-red-300">401 Invalid signature</span>{" "}
                        or{" "}
                        <span className="text-red-300">404 Not Found</span>,
                        send this drop-in spec to the LearnForge team — the
                        receiver code in there matches our exact signing
                        scheme, so publishes flip to 200 the moment they
                        deploy + set{" "}
                        <span className="font-mono text-amber-300">
                            LEARNFORGE_WEBHOOK_SECRET
                        </span>{" "}
                        to the same value as Radar's env.
                    </p>
                </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
                <Button
                    data-testid={DASHBOARD.handoffCopyBtn}
                    onClick={copy}
                    disabled={copying}
                    size="sm"
                    className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-[10px] uppercase tracking-wider font-bold disabled:opacity-50"
                >
                    <Copy className="h-3 w-3 mr-1.5" />
                    {copying ? "Copying…" : "Copy Handoff Doc"}
                </Button>
                <a
                    data-testid={DASHBOARD.handoffDownloadBtn}
                    href={docUrl}
                    download="LEARNFORGE_INGEST_SPEC.md"
                    className="inline-flex items-center gap-1.5 rounded-sm border border-zinc-700 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 transition-colors"
                >
                    <Download className="h-3 w-3" />
                    Download .md
                </a>
                <a
                    href={docUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-sm border border-zinc-700 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 transition-colors"
                >
                    <FileJson className="h-3 w-3" />
                    Preview
                </a>
            </div>
        </div>
    );
}
