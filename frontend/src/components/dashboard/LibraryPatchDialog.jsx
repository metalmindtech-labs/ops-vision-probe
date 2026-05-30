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
import { Lock, Copy, Download, ShieldCheck, FileCode2, CheckCircle2 } from "lucide-react";
import { IntegrationsAPI } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds/dashboard";

// "Library Access Gating" drop-in patch for the LearnForge team.
// Hands them a complete `app/[locale]/library/page.tsx` that gates Radar
// Curriculums behind a real purchase check (with admin bypass + empty-state
// CTA), so non-purchasers can no longer see premium content in their library.
export function LibraryPatchButton() {
    const [open, setOpen] = useState(false);
    return (
        <>
            <Button
                data-testid={DASHBOARD.libraryPatchBtn}
                onClick={() => setOpen(true)}
                variant="outline"
                className="rounded-sm border-red-400/40 bg-red-500/5 text-red-300 hover:bg-red-500/10 hover:text-red-200 font-mono text-[10px] sm:text-xs uppercase tracking-wider px-2 sm:px-3"
            >
                <Lock className="h-3.5 w-3.5 sm:mr-2" />
                <span className="hidden sm:inline">Library Gate Fix</span>
                <span className="sm:hidden ml-1">Gate</span>
            </Button>
            <LibraryPatchDialog open={open} onOpenChange={setOpen} />
        </>
    );
}

function LibraryPatchDialog({ open, onOpenChange }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!open || data) return;
        setLoading(true);
        IntegrationsAPI.libraryPatch()
            .then(setData)
            .catch(() => toast.error("Failed to load library patch"))
            .finally(() => setLoading(false));
    }, [open, data]);

    const copyCode = async () => {
        if (!data?.code) return;
        try {
            await navigator.clipboard.writeText(data.code);
            toast.success("Library patch copied", {
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
        a.download = "library-page.tsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.libraryPatchDialog}
                className="bg-zinc-950 border border-red-400/30 rounded-sm text-zinc-50 max-w-4xl max-h-[92vh] overflow-y-auto"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-red-300 flex items-center gap-2">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Library Access Gating · Security Patch
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs leading-relaxed">
                        Drop-in Next.js page that gates Radar Curriculums to
                        actual purchasers. Paste at{" "}
                        <span className="font-mono text-zinc-200">
                            app/[locale]/library/page.tsx
                        </span>{" "}
                        in your <span className="font-mono">learnforge-core</span>{" "}
                        project. Admin bypass via{" "}
                        <span className="font-mono text-lime-300">
                            LEARNFORGE_ADMIN_EMAILS
                        </span>{" "}
                        env var.
                    </DialogDescription>
                </DialogHeader>

                {loading && (
                    <div className="font-mono text-[11px] text-zinc-500 py-12 text-center">
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
                                        · {data.lines} lines · deps:{" "}
                                        {data.deps.join(", ")}
                                    </span>
                                </h4>
                                <div className="flex items-center gap-2">
                                    <Button
                                        data-testid={DASHBOARD.libraryPatchCopyBtn}
                                        onClick={copyCode}
                                        size="sm"
                                        className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-[10px] uppercase tracking-wider font-bold"
                                    >
                                        <Copy className="h-3 w-3 mr-1.5" />
                                        Copy Patch
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
                            <pre className="border border-zinc-800 bg-black rounded-sm p-3 font-mono text-[11px] leading-relaxed text-zinc-300 overflow-auto max-h-[55vh] whitespace-pre">
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
