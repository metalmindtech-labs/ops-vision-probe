import { useEffect, useState } from "react";

// Tracks beforeinstallprompt (Chrome/Edge/Android) and standalone mode.
// Returns { installable, promptInstall, installed, isIOS, isStandalone }.
export default function usePWAInstall() {
    const [deferred, setDeferred] = useState(null);
    const [installed, setInstalled] = useState(false);

    const isStandalone =
        typeof window !== "undefined" &&
        (window.matchMedia?.("(display-mode: standalone)").matches ||
            window.navigator.standalone === true);

    const isIOS =
        typeof navigator !== "undefined" &&
        /iphone|ipad|ipod/i.test(navigator.userAgent || "") &&
        !window.MSStream;

    useEffect(() => {
        const onPrompt = (e) => {
            e.preventDefault();
            setDeferred(e);
        };
        const onInstalled = () => {
            setInstalled(true);
            setDeferred(null);
        };
        window.addEventListener("beforeinstallprompt", onPrompt);
        window.addEventListener("appinstalled", onInstalled);
        return () => {
            window.removeEventListener("beforeinstallprompt", onPrompt);
            window.removeEventListener("appinstalled", onInstalled);
        };
    }, []);

    const promptInstall = async () => {
        if (!deferred) return "unavailable";
        deferred.prompt();
        const choice = await deferred.userChoice;
        setDeferred(null);
        if (choice?.outcome === "accepted") setInstalled(true);
        return choice?.outcome || "dismissed";
    };

    return {
        installable: Boolean(deferred),
        promptInstall,
        installed,
        isIOS,
        isStandalone,
    };
}
