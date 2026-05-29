import { useEffect, useState } from "react";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetDescription,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { Zap, Copy, ArrowUpRight, Sparkles } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";
import { learnforgeFreeUrl, learnforgePaidUrl } from "@/lib/learnforge";
import CTAPreview from "@/components/dashboard/CTAPreview";
import SyllabusList from "@/components/dashboard/SyllabusList";

export default function ConversionPanel({
    signal,
    open,
    onOpenChange,
    onSave,
    onTriggerSyllabus,
}) {
    const [form, setForm] = useState(null);
    const [saving, setSaving] = useState(false);
    const [forging, setForging] = useState(false);

    useEffect(() => {
        if (signal) {
            setForm({
                lead_magnet_title: signal.lead_magnet_title || "",
                lead_magnet_description: signal.lead_magnet_description || "",
                paid_offer_title: signal.paid_offer_title || "",
                paid_offer_description: signal.paid_offer_description || "",
                paid_offer_price: signal.paid_offer_price ?? "",
                cta_headline: signal.cta_headline || "",
                cta_subtext: signal.cta_subtext || "",
                status: signal.status || "tracked",
            });
        }
    }, [signal]);

    if (!signal || !form) return null;

    const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

    const save = async () => {
        setSaving(true);
        await onSave(signal.id, {
            ...form,
            paid_offer_price:
                form.paid_offer_price === "" ? null : Number(form.paid_offer_price),
        });
        setSaving(false);
    };

    const trigger = async () => {
        setForging(true);
        await onTriggerSyllabus(signal.id);
        setForging(false);
    };

    const leadSlug = (form.lead_magnet_title || "lead-magnet")
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .trim()
        .replace(/\s+/g, "-");
    const paidSlug = (form.paid_offer_title || "paid-offer")
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .trim()
        .replace(/\s+/g, "-");

    const freeUrl = learnforgeFreeUrl(leadSlug);
    const paidUrl = learnforgePaidUrl(paidSlug);

    const copy = async (text, label) => {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                const ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
            }
            toast.success(`${label} copied`);
        } catch {
            toast.error("Copy failed");
        }
    };

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent
                data-testid={DASHBOARD.conversionSheet}
                side="right"
                className="bg-zinc-950 border-l border-zinc-800 text-zinc-50 w-full sm:max-w-2xl overflow-y-auto p-0"
            >
                <div className="grid-bg">
                    <SheetHeader className="px-6 pt-6 pb-4 border-b border-zinc-800 space-y-2">
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-lime-400">
                                conversion engine
                            </span>
                            <span className="font-mono text-[10px] text-zinc-600">
                                · signal:{signal.id.slice(0, 8)}
                            </span>
                        </div>
                        <SheetTitle className="font-mono text-xl text-zinc-50 leading-tight">
                            {signal.event_title}
                        </SheetTitle>
                        <SheetDescription className="sr-only">
                            Conversion Engine for {signal.event_title}. Define
                            lead magnet, paid offer, and CTA, then trigger
                            syllabus generation.
                        </SheetDescription>
                        <div className="flex items-center gap-3 text-xs text-zinc-400 font-mono">
                            <span>{signal.category}</span>
                            <span className="text-zinc-700">|</span>
                            <span>
                                {(signal.registration_count || 0).toLocaleString()}+
                                regs
                            </span>
                            <span className="text-zinc-700">|</span>
                            <span className="text-lime-400">
                                priority {signal.priority_score}
                            </span>
                        </div>
                    </SheetHeader>

                    <div className="px-6 py-6 space-y-8">
                        {/* Lead Magnet (Free) */}
                        <section>
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-300">
                                    01 · Lead Magnet
                                    <span className="text-zinc-600"> / free</span>
                                </h3>
                                <span className="font-mono text-[10px] text-zinc-500">
                                    top-of-funnel
                                </span>
                            </div>
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                        Title
                                    </Label>
                                    <Input
                                        data-testid={DASHBOARD.leadMagnetTitle}
                                        value={form.lead_magnet_title}
                                        onChange={(e) =>
                                            set("lead_magnet_title", e.target.value)
                                        }
                                        placeholder="The MBB Case Cheat Sheet"
                                        className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                        Description
                                    </Label>
                                    <Textarea
                                        data-testid={DASHBOARD.leadMagnetDesc}
                                        value={form.lead_magnet_description}
                                        onChange={(e) =>
                                            set(
                                                "lead_magnet_description",
                                                e.target.value
                                            )
                                        }
                                        rows={2}
                                        placeholder="A short description that promises a tangible outcome."
                                        className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-xs resize-none"
                                    />
                                </div>
                            </div>
                        </section>

                        <Separator className="bg-zinc-800" />

                        {/* Paid Offer */}
                        <section>
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-300">
                                    02 · ForgeCore Paid Offer
                                </h3>
                                <span className="font-mono text-[10px] text-zinc-500">
                                    mini-course
                                </span>
                            </div>
                            <div className="space-y-3">
                                <div className="grid grid-cols-3 gap-3">
                                    <div className="col-span-2 space-y-1.5">
                                        <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                            Title
                                        </Label>
                                        <Input
                                            data-testid={DASHBOARD.paidOfferTitle}
                                            value={form.paid_offer_title}
                                            onChange={(e) =>
                                                set("paid_offer_title", e.target.value)
                                            }
                                            placeholder="ForgeCore: MBB Case Mastery"
                                            className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                                        />
                                    </div>
                                    <div className="space-y-1.5">
                                        <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                            Price (USD)
                                        </Label>
                                        <Input
                                            data-testid={DASHBOARD.paidOfferPrice}
                                            type="number"
                                            min={0}
                                            value={form.paid_offer_price}
                                            onChange={(e) =>
                                                set("paid_offer_price", e.target.value)
                                            }
                                            placeholder="299"
                                            className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                        Description
                                    </Label>
                                    <Textarea
                                        data-testid={DASHBOARD.paidOfferDesc}
                                        value={form.paid_offer_description}
                                        onChange={(e) =>
                                            set("paid_offer_description", e.target.value)
                                        }
                                        rows={2}
                                        placeholder="What the learner ships at the end of this course."
                                        className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-xs resize-none"
                                    />
                                </div>
                            </div>
                        </section>

                        <Separator className="bg-zinc-800" />

                        {/* CTA */}
                        <section>
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-300">
                                    03 · Leland-Style CTA
                                </h3>
                                <span className="font-mono text-[10px] text-zinc-500">
                                    high-contrast banner
                                </span>
                            </div>
                            <div className="grid grid-cols-1 gap-3">
                                <div className="space-y-1.5">
                                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                        Headline
                                    </Label>
                                    <Input
                                        data-testid={DASHBOARD.ctaHeadline}
                                        value={form.cta_headline}
                                        onChange={(e) =>
                                            set("cta_headline", e.target.value)
                                        }
                                        placeholder="Land Your MBB Offer"
                                        className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                        Subtext
                                    </Label>
                                    <Input
                                        data-testid={DASHBOARD.ctaSubtext}
                                        value={form.cta_subtext}
                                        onChange={(e) =>
                                            set("cta_subtext", e.target.value)
                                        }
                                        placeholder="Trained by ex-MBB EMs. Outcome-tracked."
                                        className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-sm"
                                    />
                                </div>
                            </div>

                            <div className="mt-5">
                                <CTAPreview
                                    headline={
                                        form.cta_headline || signal.event_title
                                    }
                                    subtext={
                                        form.cta_subtext ||
                                        `Built on a signal of ${(signal.registration_count || 0).toLocaleString()}+ learners.`
                                    }
                                    paidUrl={paidUrl}
                                    freeUrl={freeUrl}
                                />
                            </div>

                            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-xs">
                                <button
                                    data-testid={DASHBOARD.ctaCopyFreeBtn}
                                    onClick={() => copy(freeUrl, "Free URL")}
                                    className="flex items-center justify-between border border-zinc-800 hover:border-lime-400/40 hover:bg-lime-400/5 transition-colors px-3 py-2 rounded-sm group"
                                >
                                    <span className="truncate text-zinc-300 group-hover:text-lime-300">
                                        {freeUrl}
                                    </span>
                                    <Copy className="h-3 w-3 ml-2 text-zinc-500 group-hover:text-lime-400" />
                                </button>
                                <button
                                    data-testid={DASHBOARD.ctaCopyPaidBtn}
                                    onClick={() => copy(paidUrl, "Paid URL")}
                                    className="flex items-center justify-between border border-zinc-800 hover:border-lime-400/40 hover:bg-lime-400/5 transition-colors px-3 py-2 rounded-sm group"
                                >
                                    <span className="truncate text-zinc-300 group-hover:text-lime-300">
                                        {paidUrl}
                                    </span>
                                    <Copy className="h-3 w-3 ml-2 text-zinc-500 group-hover:text-lime-400" />
                                </button>
                            </div>
                        </section>

                        <Separator className="bg-zinc-800" />

                        {/* Status + actions */}
                        <section className="space-y-4">
                            <div className="grid grid-cols-2 gap-3 items-end">
                                <div className="space-y-1.5">
                                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                                        Pipeline Status
                                    </Label>
                                    <Select
                                        value={form.status}
                                        onValueChange={(v) => set("status", v)}
                                    >
                                        <SelectTrigger
                                            data-testid={DASHBOARD.statusSelect}
                                            className="bg-zinc-900 border-zinc-800 focus:ring-1 focus:ring-lime-400 rounded-sm font-mono text-xs uppercase tracking-wider"
                                        >
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent className="bg-zinc-950 border-zinc-800 rounded-sm font-mono text-xs">
                                            <SelectItem value="tracked">
                                                Tracked
                                            </SelectItem>
                                            <SelectItem value="converting">
                                                Converting
                                            </SelectItem>
                                            <SelectItem value="live">Live</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <Button
                                    data-testid={DASHBOARD.saveConversion}
                                    onClick={save}
                                    disabled={saving}
                                    className="rounded-sm bg-zinc-100 hover:bg-white text-black font-mono text-xs uppercase tracking-wider font-bold disabled:opacity-50"
                                >
                                    {saving ? "Syncing…" : "Save Conversion"}
                                </Button>
                            </div>

                            <Button
                                data-testid={DASHBOARD.triggerSyllabus}
                                onClick={trigger}
                                disabled={forging}
                                className="w-full rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-sm uppercase tracking-[0.2em] font-bold py-6 disabled:opacity-60 group"
                            >
                                {forging ? (
                                    <>
                                        <Sparkles className="h-4 w-4 mr-2 animate-pulse" />
                                        Forging Syllabus…
                                    </>
                                ) : (
                                    <>
                                        <Zap className="h-4 w-4 mr-2 group-hover:translate-x-0.5 transition-transform" />
                                        Trigger LearnForge Syllabus Generation
                                    </>
                                )}
                            </Button>

                            <a
                                href={paidUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center justify-center gap-2 font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 hover:text-lime-400 transition-colors"
                            >
                                Preview on LearnForge
                                <ArrowUpRight className="h-3 w-3" />
                            </a>
                        </section>

                        {signal.syllabus_generated && (
                            <>
                                <Separator className="bg-zinc-800" />
                                <SyllabusList modules={signal.syllabus_modules} />
                            </>
                        )}
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
}
