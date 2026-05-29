import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { SignalsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import StatGrid from "@/components/dashboard/StatGrid";
import SignalTable from "@/components/dashboard/SignalTable";
import SignalFormDialog from "@/components/dashboard/SignalFormDialog";
import ConversionPanel from "@/components/dashboard/ConversionPanel";
import LelandCTAStrip from "@/components/dashboard/LelandCTAStrip";
import CategoryBreakdown from "@/components/dashboard/CategoryBreakdown";

export default function Dashboard() {
    const [signals, setSignals] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [conversionId, setConversionId] = useState(null);

    const refresh = async () => {
        try {
            const [list, st] = await Promise.all([
                SignalsAPI.list(),
                SignalsAPI.stats(),
            ]);
            setSignals(list);
            setStats(st);
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
                description: `${updated.syllabus_modules.length} modules synthesized.`,
            });
            await refresh();
        } catch (e) {
            toast.error("Syllabus generation failed", {
                description: e?.message,
            });
        }
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
            />
        </div>
    );
}
