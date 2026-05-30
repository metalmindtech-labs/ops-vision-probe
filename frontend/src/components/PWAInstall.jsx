import { useEffect, useState } from "react";
import { Download, Share, X, Plus } from "lucide-react";
import usePWAInstall from "@/hooks/usePWAInstall";
import { Button } from "@/components/ui/button";
import { DASHBOARD } from "@/constants/testIds/dashboard";

const DISMISS_KEY = "radar:install-dismissed-v1";

// Header install button — visible only when installable on Chromium/Android
// or when on iOS (we surface manual instructions instead of an event).
export function InstallButton() {
    const { installable, promptInstall, installed, isIOS, isStandalone } =
        usePWAInstall();
    const [iosOpen, setIosOpen] = useState(false);

    if (installed || isStandalone) return null;
    if (!installable && !isIOS) return null;

    const onClick = async () => {
        if (isIOS && !installable) {
            setIosOpen(true);
            return;
        }
        await promptInstall();
    };

    return (
        <>
            <Button
                data-testid={DASHBOARD.installBtn}
                onClick={onClick}
                variant="outline"
                className="rounded-sm border-lime-400/40 bg-lime-400/5 text-lime-300 hover:bg-lime-400/10 hover:text-lime-200 font-mono text-xs uppercase tracking-wider"
            >
                <Download className="h-3.5 w-3.5 mr-2" />
                Install
            </Button>
            {iosOpen && <IOSInstructions onClose={() => setIosOpen(false)} />}
        </>
    );
}

function IOSInstructions({ onClose }) {
    return (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="w-full max-w-md border border-lime-400/40 bg-zinc-950 rounded-sm shadow-2xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
                    <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-lime-400">
                        Install on iOS
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-zinc-500 hover:text-zinc-100 transition-colors"
                        aria-label="close"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
                <ol className="px-5 py-4 space-y-3 font-mono text-xs text-zinc-300">
                    <li className="flex items-start gap-2">
                        <span className="text-lime-400">1.</span>
                        <span>
                            Tap the <Share className="inline h-3.5 w-3.5 mx-1 text-zinc-100" />
                            Share button in Safari's toolbar.
                        </span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="text-lime-400">2.</span>
                        <span>
                            Scroll and choose
                            <span className="ml-1 inline-flex items-center gap-1 text-zinc-100">
                                <Plus className="h-3.5 w-3.5" /> Add to Home Screen
                            </span>
                            .
                        </span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="text-lime-400">3.</span>
                        <span>Confirm — Radar launches as a standalone app.</span>
                    </li>
                </ol>
            </div>
        </div>
    );
}

// Floating soft-prompt banner — appears once until dismissed, only on mobile
// and only when a browser-supplied install event is available (or iOS).
export function InstallPromptBanner() {
    const { installable, promptInstall, installed, isIOS, isStandalone } =
        usePWAInstall();
    const [dismissed, setDismissed] = useState(true);
    const [iosOpen, setIosOpen] = useState(false);

    useEffect(() => {
        try {
            setDismissed(localStorage.getItem(DISMISS_KEY) === "1");
        } catch {
            setDismissed(false);
        }
    }, []);

    if (installed || isStandalone || dismissed) return null;
    if (!installable && !isIOS) return null;

    const dismiss = () => {
        try {
            localStorage.setItem(DISMISS_KEY, "1");
        } catch {
            /* noop */
        }
        setDismissed(true);
    };

    const onInstall = async () => {
        if (isIOS && !installable) {
            setIosOpen(true);
            return;
        }
        const outcome = await promptInstall();
        if (outcome === "accepted" || outcome === "dismissed") dismiss();
    };

    return (
        <>
            <div
                data-testid={DASHBOARD.installPrompt}
                className="md:hidden fixed left-3 right-3 bottom-3 z-50 border border-lime-400/40 bg-zinc-950/95 backdrop-blur rounded-sm shadow-2xl px-3 py-2.5 flex items-center gap-3 animate-fade-in"
            >
                <Download className="h-4 w-4 text-lime-400 shrink-0" />
                <div className="flex-1 min-w-0">
                    <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-200">
                        Install Radar
                    </p>
                    <p className="font-mono text-[10px] text-zinc-500 truncate">
                        Full-screen · offline shell · home-screen launch
                    </p>
                </div>
                <Button
                    size="sm"
                    onClick={onInstall}
                    className="h-7 rounded-sm bg-lime-400 text-black hover:bg-lime-300 font-mono text-[10px] uppercase tracking-wider font-bold px-2.5"
                >
                    Install
                </Button>
                <button
                    data-testid={DASHBOARD.installDismiss}
                    onClick={dismiss}
                    aria-label="dismiss"
                    className="text-zinc-500 hover:text-zinc-100 transition-colors"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>
            {iosOpen && <IOSInstructions onClose={() => setIosOpen(false)} />}
        </>
    );
}
