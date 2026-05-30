import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { SignalsAPI, ScraperAPI, AlertsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import StatGrid from "@/components/dashboard/StatGrid";
import SignalTable from "@/components/dashboard/SignalTable";
import SignalFormDialog from "@/components/dashboard/SignalFormDialog";
import ConversionPanel from "@/components/dashboard/ConversionPanel";
import LelandCTAStrip from "@/components/dashboard/LelandCTAStrip";
import CategoryBreakdown from "@/components/dashboard/CategoryBreakdown";
import ScraperStatusBar from "@/components/dashboard/ScraperStatusBar";
import PasteHtmlDialog from "@/components/dashboard/PasteHtmlDialog";
import StrikeAlertsBanner from "@/components/dashboard/StrikeAlertsBanner";

export default function Dashboard() {
    const [signals, setSignals] = useState([]);
    const [stats, setStats] = useState(null);
    const [scraperStatus, setScraperStatus] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [conversionId, setConversionId] = useState(null);
    const [pasteOpen, setPasteOpen] = useState(false);
    const [scraperBusy, setScraperBusy] = useState(false);

    const refresh = async () => {
        try {
            const [list, st, scStatus, al] = await Promise.all([
                SignalsAPI.list(),
                SignalsAPI.stats(),
                ScraperAPI.status().catch(() => null),
                AlertsAPI.list(true).catch(() => []),
            ]);
            setSignals(list);
            setStats(st);
            setScraperStatus(scStatus);
            setAlerts(al);
        } catch (e) {
            toast.error("Failed to load signals", {
                description: e?.message ?? "Network error",
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        refresh();
    }, []);

    const activeSignal = useMemo(
        () => signals.find((s) => s.id === conversionId) || null,
        [signals, conversionId]
    );

    const handleCreate = () => {
        setEditing(null);
        setFormOpen(true);
    };

    const handleEdit = (signal) => {
        setEditing(signal);
        setFormOpen(true);
    };

    const handleDelete = async (id) => {
        try {
            await SignalsAPI.remove(id);
            toast.success("Signal deleted");
            await refresh();
        } catch (e) {
            toast.error("Delete failed", { description: e?.message });
        }
    };

    const handleSubmit = async (payload) => {
        try {
            if (editing) {
                await SignalsAPI.update(editing.id, payload);
                toast.success("Signal updated");
            } else {
                await SignalsAPI.create(payload);
                toast.success("Signal logged into radar");
            }
            setFormOpen(false);
            await refresh();
        } catch (e) {
            toast.error("Save failed", { description: e?.message });
        }
    };

    const handleConvert = (signal) => {
        setConversionId(signal.id);
    };

    const handleConversionSave = async (id, patch) => {
        try {
            await SignalsAPI.update(id, patch);
            toast.success("Conversion data synced");
            await refresh();
        } catch (e) {
            toast.error("Save failed", { description: e?.message });
        }
    };

    const handleTriggerSyllabus = async (id) => {
        try {
            const updated = await SignalsAPI.triggerSyllabus(id);
            toast.success("Syllabus generated", {
                description: `${updated.syllabus_modules.length} modules synthesized by Claude Sonnet 4.5.`,
            });
            await refresh();
        } catch (e) {
            toast.error("Syllabus generation failed", {
                description: e?.message,
            });
        }
    };

    const handleRunScraper = async () => {
        setScraperBusy(true);
        const t = toast.loading("Scraping Leland event-stream…", {
            description: "Claude is classifying new signals.",
        });
        try {
            const result = await ScraperAPI.run();
            toast.success("Scrape complete", {
                id: t,
                description: `${result.discovered} discovered · ${result.created} new · ${result.updated} updated`,
            });
            await refresh();
        } catch (e) {
            toast.error("Scrape failed", { id: t, description: e?.message });
        } finally {
            setScraperBusy(false);
        }
    };

    const handlePasteHtml = async (html) => {
        const t = toast.loading("Parsing pasted HTML…");
        try {
            const result = await ScraperAPI.ingestHtml(html);
            toast.success("HTML ingested", {
                id: t,
                description: `${result.discovered} events · ${result.created} new · ${result.updated} updated`,
            });
            await refresh();
        } catch (e) {
            toast.error("Paste ingest failed", {
                id: t,
                description: e?.message,
            });
        }
    };

    const handleAckAlert = async (id) => {
        try {
            await AlertsAPI.ack(id);
            setAlerts((a) => a.filter((x) => x.id !== id));
        } catch (e) {
            toast.error("Dismiss failed", { description: e?.message });
        }
    };

    const handleAckAll = async () => {
        try {
            await AlertsAPI.ackAll();
            setAlerts([]);
            toast.success("All strike alerts cleared");
        } catch (e) {
            toast.error("Dismiss-all failed", { description: e?.message });
        }
    };

    const handleJumpToSignal = (id) => {
        setConversionId(id);
    };

    return (
        <div
            data-testid={DASHBOARD.root}
            className="min-h-screen bg-zinc-950 text-zinc-50 grid-bg"
        >
            <div className="scanline min-h-screen">
                <div className="mx-auto max-w-[1480px] px-4 sm:px-6 lg:px-8 py-6 lg:py-10">
                    <DashboardHeader
                        onAdd={handleCreate}
                        onRefresh={refresh}
                        onRunScraper={handleRunScraper}
                        onPasteHtml={() => setPasteOpen(true)}
                        scraperBusy={scraperBusy}
                    />

                    <ScraperStatusBar status={scraperStatus} />

                    <StrikeAlertsBanner
                        alerts={alerts}
                        onAck={handleAckAlert}
                        onAckAll={handleAckAll}
                        onJump={handleJumpToSignal}
                    />

                    <StatGrid stats={stats} loading={loading} />

                    <div className="mt-10 grid grid-cols-1 lg:grid-cols-4 gap-6">
                        <div className="lg:col-span-3">
                            <SignalTable
                                signals={signals}
                                loading={loading}
                                onConvert={handleConvert}
                                onEdit={handleEdit}
                                onDelete={handleDelete}
                            />
                        </div>
                        <div className="lg:col-span-1 space-y-6">
                            <CategoryBreakdown categories={stats?.categories || []} />
                            <LelandCTAStrip />
                        </div>
                    </div>
                </div>
            </div>

            <SignalFormDialog
                open={formOpen}
                onOpenChange={setFormOpen}
                initial={editing}
                onSubmit={handleSubmit}
            />

            <ConversionPanel
                signal={activeSignal}
                open={!!conversionId}
                onOpenChange={(v) => !v && setConversionId(null)}
                onSave={handleConversionSave}
                onTriggerSyllabus={handleTriggerSyllabus}
                onPublished={refresh}
            />

            <PasteHtmlDialog
                open={pasteOpen}
                onOpenChange={setPasteOpen}
                onSubmit={handlePasteHtml}
            />
        </div>
    );
}
