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
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Clipboard, Link2 } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

// Manual ingestion fallback — used when the automated 12-h scraper is
// blocked by Leland's anti-bot challenge. Two modes:
//   1. Paste HTML  → ships raw markup straight to the parser.
//   2. Paste URL   → backend server-side fetches + parses (bypasses
//      browser-side bot checks).
export default function PasteHtmlDialog({
    open,
    onOpenChange,
    onSubmitHtml,
    onSubmitUrl,
}) {
    const [tab, setTab] = useState("url"); // default to URL — one-click workflow
    const [html, setHtml] = useState("");
    const [url, setUrl] = useState("https://www.joinleland.com/events");
    const [busy, setBusy] = useState(false);

    const submitHtml = async () => {
        if (!html || html.length < 50) return;
        setBusy(true);
        try {
            await onSubmitHtml(html);
            setHtml("");
            onOpenChange(false);
        } finally {
            setBusy(false);
        }
    };

    const submitUrl = async () => {
        if (!url || !/^https?:\/\/.+/i.test(url)) return;
        setBusy(true);
        try {
            await onSubmitUrl(url);
            onOpenChange(false);
        } catch {
            // toast surfaced in caller — keep dialog open for retry
        } finally {
            setBusy(false);
        }
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
                        Bypass anti-bot rate limits — feed{" "}
                        <span className="text-zinc-200 font-mono">
                            joinleland.com/events
                        </span>{" "}
                        in either as a URL (server-fetched) or as a raw HTML
                        paste. Each new event is classified by Claude on ingest.
                    </DialogDescription>
                </DialogHeader>

                {/* Tab switcher */}
                <div className="flex items-center gap-1 border border-zinc-800 rounded-sm p-0.5 bg-zinc-900 w-fit">
                    <TabBtn
                        active={tab === "url"}
                        onClick={() => setTab("url")}
                        testid={DASHBOARD.pasteTabUrl}
                        icon={<Link2 className="h-3 w-3" />}
                        label="Paste URL"
                    />
                    <TabBtn
                        active={tab === "html"}
                        onClick={() => setTab("html")}
                        testid={DASHBOARD.pasteTabHtml}
                        icon={<Clipboard className="h-3 w-3" />}
                        label="Paste HTML"
                    />
                </div>

                {tab === "url" && (
                    <div className="space-y-2 mt-2">
                        <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                            joinleland.com URL
                        </Label>
                        <Input
                            data-testid={DASHBOARD.pasteUrlInput}
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://www.joinleland.com/events"
                            className="bg-zinc-900 border-zinc-800 focus:border-lime-400 focus-visible:ring-1 focus-visible:ring-lime-400 rounded-sm font-mono text-[11px]"
                        />
                        <p className="font-mono text-[10px] text-zinc-600">
                            Server-side fetch. Falls back to HTML paste if the
                            upstream returns a bot challenge.
                        </p>
                        <DialogFooter className="mt-2 gap-2">
                            <Button
                                variant="ghost"
                                onClick={() => onOpenChange(false)}
                                className="rounded-sm font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
                            >
                                Cancel
                            </Button>
                            <Button
                                data-testid={DASHBOARD.pasteUrlSubmit}
                                disabled={busy || !/^https?:\/\/.+/i.test(url)}
                                onClick={submitUrl}
                                className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-xs uppercase tracking-wider font-bold disabled:opacity-50"
                            >
                                {busy ? "Fetching…" : "Fetch & Ingest"}
                            </Button>
                        </DialogFooter>
                    </div>
                )}

                {tab === "html" && (
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
                                onClick={submitHtml}
                                className="rounded-sm bg-lime-400 hover:bg-lime-300 text-black font-mono text-xs uppercase tracking-wider font-bold disabled:opacity-50"
                            >
                                {busy ? "Parsing…" : "Ingest & Enrich"}
                            </Button>
                        </DialogFooter>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

function TabBtn({ active, onClick, icon, label, testid }) {
    return (
        <button
            data-testid={testid}
            onClick={onClick}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm font-mono text-[10px] uppercase tracking-[0.2em] transition-colors ${
                active
                    ? "bg-lime-400 text-black"
                    : "text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800"
            }`}
        >
            {icon}
            {label}
        </button>
    );
}
