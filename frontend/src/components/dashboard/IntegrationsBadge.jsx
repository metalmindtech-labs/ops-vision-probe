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
} from "lucide-react";
import { IntegrationsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

export default function IntegrationsBadge({ status, onRefresh }) {
    const [open, setOpen] = useState(false);
    const [testing, setTesting] = useState(false);
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

                    <div className="space-y-3 mt-2">
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
                                <div className="flex items-center gap-1">
                                    <KeyRound className="h-3 w-3" />
                                    Signing secret:{" "}
                                    <span className={wh?.has_secret ? "text-lime-400" : "text-zinc-500"}>
                                        {wh?.has_secret ? "enabled" : "disabled"}
                                    </span>
                                </div>
                            </div>
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
        </>
    );
}
