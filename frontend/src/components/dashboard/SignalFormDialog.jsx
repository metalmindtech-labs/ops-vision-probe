import { useEffect, useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { DASHBOARD } from "@/constants/testIds/dashboard";

const EMPTY = {
    event_title: "",
    category: "",
    registration_count: 0,
    priority_score: 60,
    source_url: "",
    notes: "",
};

const CATEGORIES = [
    "Consulting",
    "MBA Admissions",
    "Product Management",
    "Finance",
    "Medical Admissions",
    "Law",
    "Tech Careers",
    "Engineering",
    "Career Switching",
    "Other",
];

export default function SignalFormDialog({
    open,
    onOpenChange,
    initial,
    onSubmit,
}) {
    const [data, setData] = useState(EMPTY);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (open) {
            setData(
                initial
                    ? {
                          event_title: initial.event_title || "",
                          category: initial.category || "",
                          registration_count:
                              initial.registration_count || 0,
                          priority_score: initial.priority_score ?? 60,
                          source_url: initial.source_url || "",
                          notes: initial.notes || "",
                      }
                    : EMPTY
            );
        }
    }, [open, initial]);

    const set = (k, v) => setData((d) => ({ ...d, [k]: v }));

    const submit = async () => {
        if (!data.event_title.trim() || !data.category.trim()) return;
        setSaving(true);
        await onSubmit({
            ...data,
            registration_count: Number(data.registration_count) || 0,
            priority_score: Number(data.priority_score) || 0,
        });
        setSaving(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.formDialog}
                className="bg-zinc-950 border border-zinc-800 rounded-sm text-zinc-50 max-w-xl"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-lime-400">
                        {initial ? "Edit Signal" : "Log New Signal"}
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs">
                        Manually log a high-demand learning signal from Leland
                        (or elsewhere) into the radar.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 mt-2">
                    <div className="space-y-1.5">
                        <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                            Event Title *
                        </Label>
                        <Input
                            data-testid={DASHBOARD.formEventTitle}
                            value={data.event_title}
                            onChange={(e) => set("event_title", e.target.value)}
                            placeholder="Cracking the MBB Consulting Case Interview"
                            className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                            <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                Category *
                            </Label>
                            <Input
                                data-testid={DASHBOARD.formCategory}
                                list="signal-categories"
                                value={data.category}
                                onChange={(e) => set("category", e.target.value)}
                                placeholder="Consulting"
                                className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                            />
                            <datalist id="signal-categories">
                                {CATEGORIES.map((c) => (
                                    <option key={c} value={c} />
                                ))}
                            </datalist>
                        </div>
                        <div className="space-y-1.5">
                            <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                Registration Count
                            </Label>
                            <Input
                                data-testid={DASHBOARD.formRegistration}
                                type="number"
                                min={0}
                                value={data.registration_count}
                                onChange={(e) =>
                                    set("registration_count", e.target.value)
                                }
                                className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                Priority Score
                            </Label>
                            <span className="font-mono text-sm text-lime-400">
                                {data.priority_score}
                            </span>
                        </div>
                        <Slider
                            data-testid={DASHBOARD.formPriority}
                            value={[data.priority_score]}
                            onValueChange={(v) => set("priority_score", v[0])}
                            max={100}
                            step={1}
                            className="[&_[role=slider]]:bg-lime-400 [&_[role=slider]]:border-lime-400"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                            Source URL
                        </Label>
                        <Input
                            data-testid={DASHBOARD.formSourceUrl}
                            value={data.source_url}
                            onChange={(e) => set("source_url", e.target.value)}
                            placeholder="https://leland.com/events/..."
                            className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-xs"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                            Notes
                        </Label>
                        <Textarea
                            data-testid={DASHBOARD.formNotes}
                            value={data.notes}
                            onChange={(e) => set("notes", e.target.value)}
                            rows={3}
                            placeholder="Demand pattern, conversion timing, audience segment…"
                            className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-xs resize-none"
                        />
                    </div>
                </div>

                <DialogFooter className="mt-4 gap-2">
                    <Button
                        data-testid={DASHBOARD.formCancel}
                        variant="ghost"
                        onClick={() => onOpenChange(false)}
                        className="rounded-sm font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                    >
                        Cancel
                    </Button>
                    <Button
                        data-testid={DASHBOARD.formSubmit}
                        disabled={saving || !data.event_title.trim() || !data.category.trim()}
                        onClick={submit}
                        className="rounded-sm bg-lime-400 text-black hover:bg-lime-300 font-mono text-xs uppercase tracking-wider font-bold disabled:opacity-50"
                    >
                        {saving ? "Saving…" : initial ? "Update" : "Log Signal"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
