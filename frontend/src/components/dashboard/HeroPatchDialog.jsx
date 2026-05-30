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
    Image,
    Copy,
    Download,
    CheckCircle2,
    FileCode2,
    Wand2,
} from "lucide-react";
import { IntegrationsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

// Drop-in `<CourseHero>` React component for LearnForge's showroom.
// Solves broken-image cases with a cinematic Sovereign-style placeholder
// + an option to backfill missing Radar visuals catalog-wide.
export function HeroPatchButton() {
    const [open, setOpen] = useState(false);
    return (
        <>
            <Button
                data-testid={DASHBOARD.heroPatchBtn}
                onClick={() => setOpen(true)}
                variant="outline"
                className="rounded-sm border-amber-400/40 bg-amber-400/5 text-amber-300 hover:bg-amber-400/10 hover:text-amber-200 font-mono text-[10px] sm:text-xs uppercase tracking-wider px-2 sm:px-3"
            >
                <Image className="h-3.5 w-3.5 sm:mr-2" />
                <span className="hidden sm:inline">Hero Fallback</span>
                <span className="sm:hidden ml-1">Hero</span>
            </Button>
            <HeroPatchDialog open={open} onOpenChange={setOpen} />
        </>
    );
}

function HeroPatchDialog({ open, onOpenChange }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [backfilling, setBackfilling] = useState(false);

    useEffect(() => {
        if (!open || data) return;
        setLoading(true);
        IntegrationsAPI.heroPatch()
            .then(setData)
            .catch(() => toast.error("Failed to load hero patch"))
            .finally(() => setLoading(false));
    }, [open, data]);

    const copyCode = async () => {
        if (!data?.code) return;
        try {
            await navigator.clipboard.writeText(data.code);
            toast.success("CourseHero copied", {
                description: `${data.lines} lines · paste at ${data.filename}`,
            });
        } catch {
            toast.error("Copy failed");
        }
    };

    const download = () => {
        if (!data?.code) return;
        const blob = new Blob([data.code], {
            type: "text/typescript;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "CourseHero.tsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    };

    const backfill = async () => {
        setBackfilling(true);
        const t = toast.loading("Backfilling Fal Flux.1 Pro visuals…");
        try {
            const r = await IntegrationsAPI.backfillMissingVisuals();
            if (r.attempted === 0) {
                toast.success("Catalog already complete", {
                    id: t,
                    description: "Every signal with a syllabus has visuals.",
                });
            } else {
                toast.success(`${r.ok} hero${r.ok === 1 ? "" : "es"} generated`, {
                    id: t,
                    description: `${r.failed} failed of ${r.attempted} attempted`,
                });
            }
        } catch (e) {
            toast.error("Backfill failed", {
                id: t,
                description: e?.message,
            });
        } finally {
            setBackfilling(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.heroPatchDialog}
                className="bg-zinc-950 border border-amber-400/30 rounded-sm text-zinc-50 max-w-4xl max-h-[92vh] overflow-y-auto"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-amber-300 flex items-center gap-2">
                        <Image className="h-3.5 w-3.5" />
                        Course Hero · Broken-Image Fallback
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs leading-relaxed">
                        Two-part fix: (1) drop-in{" "}
                        <span className="font-mono text-zinc-200">
                            CourseHero.tsx
                        </span>{" "}
                        component for the LearnForge showroom that renders a
                        cinematic placeholder when an image URL is missing or
                        fails to load — never a broken-image icon. (2) One-click
                        Radar-side backfill that runs Fal Flux.1 Pro for every
                        signal still missing visuals.
                    </DialogDescription>
                </DialogHeader>

                {/* Backfill action — Radar-side, runs immediately */}
                <section className="border border-lime-400/30 bg-lime-400/5 rounded-sm p-4 flex items-center gap-3 flex-wrap">
                    <Wand2 className="h-4 w-4 text-lime-300 shrink-0" />
                    <div className="flex-1 min-w-0">
                        <h4 className="font-mono text-[11px] uppercase tracking-[0.2em] text-lime-300">
                            Backfill missing visuals (Radar-side)
                        </h4>
                        <p className="font-mono text-[10px] text-zinc-400 leading-relaxed">
                            Generates Fal Flux.1 Pro hero + module images for
                            any signal with a syllabus but no{" "}
                            <span className="text-zinc-200">hero_image_url</span>.
                            Skips anything already complete.
                        </p>
                    </div>
                    <Button
                        onClick={backfill}
                        disabled={backfilling}
                        className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-[10px] uppercase tracking-wider font-bold disabled:opacity-50"
                    >
                        <Wand2
                            className={`h-3 w-3 mr-1.5 ${backfilling ? "animate-spin" : ""}`}
                        />
                        {backfilling ? "Generating…" : "Run Backfill"}
                    </Button>
                </section>

                {loading && (
                    <div className="font-mono text-[11px] text-zinc-500 py-8 text-center">
                        loading patch…
                    </div>
                )}

                {data && (
                    <div className="space-y-4 mt-2">
                        <section className="border border-emerald-400/20 bg-emerald-400/5 rounded-sm p-3 space-y-1.5">
                            <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-emerald-300">
                                What this patch fixes
                            </h4>
                            <ul className="font-mono text-[10px] text-zinc-300 space-y-1 ml-1">
                                {data.fixes.map((f, i) => (
                                    <li
                                        key={i}
                                        className="flex items-start gap-1.5"
                                    >
                                        <CheckCircle2 className="h-3 w-3 text-emerald-300 mt-0.5 shrink-0" />
                                        <span>{f}</span>
                                    </li>
                                ))}
                            </ul>
                        </section>

                        <section>
                            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                                <h4 className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 flex items-center gap-2">
                                    <FileCode2 className="h-3 w-3" />
                                    {data.filename}
                                    <span className="text-zinc-600 normal-case tracking-normal">
                                        · {data.lines} lines
                                    </span>
                                </h4>
                                <div className="flex items-center gap-2">
                                    <Button
                                        data-testid={DASHBOARD.heroPatchCopyBtn}
                                        onClick={copyCode}
                                        size="sm"
                                        className="rounded-sm bg-amber-400 hover:bg-amber-300 text-black font-mono text-[10px] uppercase tracking-wider font-bold"
                                    >
                                        <Copy className="h-3 w-3 mr-1.5" />
                                        Copy Component
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
                                {data.code}
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
