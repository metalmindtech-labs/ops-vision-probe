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
    Webhook,
    Copy,
    Download,
    CheckCircle2,
    XCircle,
    FileCode2,
    KeyRound,
    Server,
    Eye,
    EyeOff,
} from "lucide-react";
import { IntegrationsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

// Bridge component — shows the LearnForge team the *exact* Next.js receiver
// code they need to deploy at /api/courses, with one-click copy + download.
// This is the "Webhook Spec Viewer" the Architect can hand to GCP/Vercel.
export function WebhookSpecButton() {
    const [open, setOpen] = useState(false);
    return (
        <>
            <Button
                data-testid={DASHBOARD.webhookSpecBtn}
                onClick={() => setOpen(true)}
                variant="outline"
                className="rounded-sm border-lime-400/40 bg-lime-400/5 text-lime-300 hover:bg-lime-400/10 hover:text-lime-200 font-mono text-[10px] sm:text-xs uppercase tracking-wider px-2 sm:px-3"
            >
                <FileCode2 className="h-3.5 w-3.5 sm:mr-2" />
                <span className="hidden sm:inline">Webhook Spec</span>
                <span className="sm:hidden ml-1">Spec</span>
            </Button>
            <WebhookSpecDialog open={open} onOpenChange={setOpen} />
        </>
    );
}

function WebhookSpecDialog({ open, onOpenChange }) {
    const [spec, setSpec] = useState(null);
    const [loading, setLoading] = useState(false);
    const [revealed, setRevealed] = useState(false);

    useEffect(() => {
        if (!open || spec) return;
        setLoading(true);
        IntegrationsAPI.receiverSpec()
            .then(setSpec)
            .catch(() => toast.error("Failed to load receiver spec"))
            .finally(() => setLoading(false));
    }, [open, spec]);

    const copyCode = async () => {
        if (!spec?.code) return;
        try {
            await navigator.clipboard.writeText(spec.code);
            toast.success("Receiver code copied", {
                description: `${spec.lines} lines · paste into ${spec.filename}`,
            });
        } catch {
            toast.error("Copy failed");
        }
    };

    const download = () => {
        if (!spec?.code) return;
        const blob = new Blob([spec.code], { type: "text/typescript;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "route.ts";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.webhookSpecDialog}
                className="bg-zinc-950 border border-lime-400/30 rounded-sm text-zinc-50 max-w-4xl max-h-[92vh] overflow-y-auto"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-lime-400 flex items-center gap-2">
                        <Webhook className="h-3.5 w-3.5" />
                        Webhook Receiver Code · LearnForge Bridge
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs leading-relaxed">
                        Drop-in TypeScript route for{" "}
                        <span className="font-mono text-zinc-200">
                            learnforge-core
                        </span>
                        . Validates payload, verifies{" "}
                        <span className="font-mono text-lime-300">
                            X-Radar-Signature
                        </span>
                        , and upserts the course. Paste at{" "}
                        <span className="font-mono text-zinc-200">
                            app/api/courses/route.ts
                        </span>{" "}
                        in your Vercel / GCP Antigravity project — Radar flips
                        404 → 200 the moment the route is live.
                    </DialogDescription>
                </DialogHeader>

                {loading && (
                    <div className="font-mono text-[11px] text-zinc-500 py-12 text-center">
                        loading receiver spec…
                    </div>
                )}

                {spec && (
                    <div className="space-y-4 mt-2">
                        {/* Meta strip */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[10px]">
                            <MetaCard
                                icon={<Server className="h-3 w-3" />}
                                label="Endpoint"
                                value="POST /api/courses"
                            />
                            <MetaCard
                                icon={<FileCode2 className="h-3 w-3" />}
                                label="Framework"
                                value="Next.js · App Router"
                            />
                            <MetaCard
                                icon={<FileCode2 className="h-3 w-3" />}
                                label="Runtime"
                                value={spec.node_runtime}
                            />
                            <MetaCard
                                icon={<KeyRound className="h-3 w-3" />}
                                label="Secret env"
                                value={spec.shared_secret_required_env}
                            />
                        </div>

                        {/* Target URL */}
                        <section>
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                Deploy this route at
                            </h4>
                            <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 flex items-center gap-2 overflow-x-auto">
                                <code className="font-mono text-[11px] text-lime-400 whitespace-nowrap">
                                    POST {spec.endpoint_url}
                                </code>
                            </div>
                        </section>

                        {/* Signature secret */}
                        <section>
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 mb-2">
                                Signature header
                            </h4>
                            <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 space-y-2">
                                <div className="font-mono text-[11px] text-zinc-300 break-all">
                                    {spec.signature_header}:{" "}
                                    <SecretValue
                                        present={spec.shared_secret_configured}
                                        revealed={revealed}
                                        onToggle={() => setRevealed((v) => !v)}
                                    />
                                </div>
                                <p className="font-mono text-[10px] text-zinc-500 leading-relaxed">
                                    Set the same{" "}
                                    <span className="text-lime-300">
                                        {spec.shared_secret_required_env}
                                    </span>{" "}
                                    on LearnForge's Vercel env. If left unset
                                    on either side, Radar still publishes and
                                    LearnForge accepts unsigned requests.
                                </p>
                            </div>
                        </section>

                        {/* The code */}
                        <section>
                            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                                <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 flex items-center gap-2">
                                    <FileCode2 className="h-3 w-3" />
                                    {spec.filename}
                                    <span className="text-zinc-600 normal-case tracking-normal">
                                        · {spec.lines} lines · deps:{" "}
                                        {spec.deps.join(", ")}
                                    </span>
                                </h4>
                                <div className="flex items-center gap-2">
                                    <Button
                                        data-testid={DASHBOARD.webhookSpecCopyBtn}
                                        onClick={copyCode}
                                        size="sm"
                                        className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-[10px] uppercase tracking-wider font-bold"
                                    >
                                        <Copy className="h-3 w-3 mr-1.5" />
                                        Copy Code
                                    </Button>
                                    <Button
                                        onClick={download}
                                        size="sm"
                                        variant="outline"
                                        className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-mono text-[10px] uppercase tracking-wider"
                                    >
                                        <Download className="h-3 w-3 mr-1.5" />
                                        Download
                                    </Button>
                                </div>
                            </div>
                            <pre className="border border-zinc-800 bg-black rounded-sm p-3 font-mono text-[11px] leading-relaxed text-zinc-300 overflow-auto max-h-[50vh] whitespace-pre">
                                {spec.code}
                            </pre>
                        </section>

                        {/* Verification steps */}
                        <section className="border border-emerald-400/20 bg-emerald-400/5 rounded-sm p-3 space-y-2">
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-emerald-300 flex items-center gap-2">
                                <CheckCircle2 className="h-3 w-3" />
                                After deploy — verify in 30 seconds
                            </h4>
                            <ol className="font-mono text-[10px] text-zinc-300 space-y-1 ml-3 list-decimal">
                                <li>
                                    GET{" "}
                                    <span className="text-lime-300 break-all">
                                        {spec.endpoint_url}
                                    </span>{" "}
                                    → expect{" "}
                                    <span className="text-zinc-100">
                                        {`{ok:true, service:"learnforge-course-publish"}`}
                                    </span>
                                </li>
                                <li>
                                    Hit{" "}
                                    <span className="text-lime-300">
                                        Publish to LearnForge
                                    </span>{" "}
                                    on any signal with a generated syllabus →
                                    expect green ✓ WEBHOOK 2xx in the
                                    PublishResultPanel.
                                </li>
                                <li>
                                    Click{" "}
                                    <span className="text-lime-300">
                                        Republish All
                                    </span>{" "}
                                    in the header → every queued failed
                                    publish flips to{" "}
                                    <span className="text-emerald-300">
                                        status=live
                                    </span>
                                    .
                                </li>
                            </ol>
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

function MetaCard({ icon, label, value }) {
    return (
        <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-2">
            <div className="flex items-center gap-1.5 text-zinc-500 uppercase tracking-[0.2em] text-[9px]">
                {icon}
                {label}
            </div>
            <div className="text-zinc-200 mt-0.5 truncate">{value}</div>
        </div>
    );
}

function SecretValue({ present, revealed, onToggle }) {
    if (!present) {
        return (
            <span className="inline-flex items-center gap-1 text-zinc-500">
                <XCircle className="h-3 w-3" />
                not configured on Radar
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-2">
            <span className="text-lime-300">
                {revealed ? "<see /app/backend/.env>" : "•••••••••• (configured)"}
            </span>
            <button
                onClick={onToggle}
                className="text-zinc-500 hover:text-zinc-200 transition-colors"
                aria-label={revealed ? "hide" : "reveal"}
            >
                {revealed ? (
                    <EyeOff className="h-3 w-3" />
                ) : (
                    <Eye className="h-3 w-3" />
                )}
            </button>
        </span>
    );
}
