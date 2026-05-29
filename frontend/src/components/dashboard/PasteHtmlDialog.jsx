import { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Clipboard } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

export default function PasteHtmlDialog({ open, onOpenChange, onSubmit }) {
    const [html, setHtml] = useState("");
    const [busy, setBusy] = useState(false);

    const submit = async () => {
        if (!html || html.length < 50) return;
        setBusy(true);
        await onSubmit(html);
        setBusy(false);
        setHtml("");
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={DASHBOARD.pasteHtmlDialog}
                className="bg-zinc-950 border border-zinc-800 rounded-sm text-zinc-50 max-w-2xl"
            >
                <DialogHeader>
                    <DialogTitle className="font-mono uppercase tracking-[0.2em] text-sm text-lime-400 flex items-center gap-2">
                        <Clipboard className="h-3.5 w-3.5" />
                        Manual Ingestion Fallback
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400 text-xs">
                        Paste raw HTML (or stripped text) from{" "}
                        <span className="text-zinc-200 font-mono">
                            joinleland.com/events
                        </span>{" "}
                        — the parser will extract events and Claude will
                        classify each new one.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-2 mt-2">
                    <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                        HTML / Text payload
                    </Label>
                    <Textarea
                        data-testid={DASHBOARD.pasteHtmlInput}
                        value={html}
                        onChange={(e) => setHtml(e.target.value)}
                        rows={10}
                        placeholder="<html>...</html> or plain text scraped from the events listing"
                        className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-[11px] resize-none"
                    />
                    <p className="font-mono text-[10px] text-zinc-600">
                        Minimum 50 chars · larger blobs are fine
                    </p>
                </div>

                <DialogFooter className="mt-2 gap-2">
                    <Button
                        variant="ghost"
                        onClick={() => onOpenChange(false)}
                        className="rounded-sm font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                    >
                        Cancel
                    </Button>
                    <Button
                        data-testid={DASHBOARD.pasteHtmlSubmit}
                        disabled={busy || !html || html.length < 50}
                        onClick={submit}
                        className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-xs uppercase tracking-wider font-bold disabled:opacity-50"
                    >
                        {busy ? "Parsing…" : "Ingest & Enrich"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
