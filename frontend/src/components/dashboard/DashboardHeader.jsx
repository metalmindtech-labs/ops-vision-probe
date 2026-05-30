import { Button } from "@/components/ui/button";
import { Plus, RefreshCw, Radar, Terminal, Satellite, Clipboard, RotateCw } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";
import IntegrationsBadge from "@/components/dashboard/IntegrationsBadge";
import { InstallButton } from "@/components/PWAInstall";

export default function DashboardHeader({
    onAdd,
    onRefresh,
    onRunScraper,
    onPasteHtml,
    onRepublishAll,
    integrationsStatus,
    refreshIntegrations,
    scraperBusy,
    republishBusy,
}) {
    return (
        <header className="relative">
            <div className="flex items-start justify-between gap-6 flex-wrap">
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <span className="inline-flex items-center gap-2 px-2 py-1 border border-lime-400/30 bg-lime-400/5 rounded-sm">
                            <Radar className="h-3 w-3 text-lime-400" />
                            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-lime-400">
                                Live · v0.1.0
                            </span>
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500">
                            mission control / leland → learnforge
                        </span>
                    </div>
                    <h1 className="font-mono text-2xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-zinc-50 leading-[1.05]">
                        OPPORTUNITY{" "}
                        <span className="text-lime-400">RADAR</span>
                        <span className="text-lime-400 blink">_</span>
                    </h1>
                    <p className="mt-3 max-w-2xl text-xs sm:text-sm text-zinc-400">
                        Convert high-demand Leland event signals into{" "}
                        <span className="text-zinc-200 font-medium">
                            LearnForge
                        </span>{" "}
                        course output. Track demand · define lead magnets &amp;
                        paid offers · ship syllabi · launch CTAs.
                    </p>
                </div>

                <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap w-full sm:w-auto">
                    <IntegrationsBadge
                        status={integrationsStatus}
                        onRefresh={refreshIntegrations}
                    />
                    <InstallButton />
                    <Button
                        data-testid={DASHBOARD.republishAllBtn}
                        onClick={onRepublishAll}
                        disabled={republishBusy}
                        variant="outline"
                        className="rounded-sm border-zinc-800 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 font-mono text-[10px] sm:text-xs uppercase tracking-wider disabled:opacity-60 px-2 sm:px-3"
                    >
                        <RotateCw className={`h-3.5 w-3.5 sm:mr-2 ${republishBusy ? "animate-spin" : ""}`} />
                        <span className="hidden sm:inline">{republishBusy ? "Republishing…" : "Republish All"}</span>
                        <span className="sm:hidden ml-1">{republishBusy ? "…" : "Pub"}</span>
                    </Button>
                    <Button
                        data-testid={DASHBOARD.pasteHtmlBtn}
                        onClick={onPasteHtml}
                        variant="outline"
                        className="rounded-sm border-zinc-800 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 font-mono text-[10px] sm:text-xs uppercase tracking-wider px-2 sm:px-3"
                    >
                        <Clipboard className="h-3.5 w-3.5 sm:mr-2" />
                        <span className="hidden sm:inline">Paste HTML</span>
                        <span className="sm:hidden ml-1">Paste</span>
                    </Button>
                    <Button
                        data-testid={DASHBOARD.runScraperBtn}
                        onClick={onRunScraper}
                        disabled={scraperBusy}
                        variant="outline"
                        className="rounded-sm border-lime-400/40 bg-lime-400/5 text-lime-300 hover:bg-lime-400/10 hover:text-lime-200 font-mono text-[10px] sm:text-xs uppercase tracking-wider disabled:opacity-60 px-2 sm:px-3"
                    >
                        <Satellite
                            className={`h-3.5 w-3.5 sm:mr-2 ${scraperBusy ? "animate-pulse" : ""}`}
                        />
                        <span className="hidden sm:inline">{scraperBusy ? "Scraping…" : "Run Scraper"}</span>
                        <span className="sm:hidden ml-1">{scraperBusy ? "…" : "Scrape"}</span>
                    </Button>
                    <Button
                        data-testid={DASHBOARD.refreshBtn}
                        onClick={onRefresh}
                        variant="outline"
                        className="rounded-sm border-zinc-800 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 font-mono text-[10px] sm:text-xs uppercase tracking-wider px-2 sm:px-3"
                    >
                        <RefreshCw className="h-3.5 w-3.5 sm:mr-2" />
                        <span className="hidden sm:inline">Sync</span>
                    </Button>
                    <Button
                        data-testid={DASHBOARD.addSignalBtn}
                        onClick={onAdd}
                        className="rounded-sm bg-lime-400 text-black hover:bg-lime-300 font-mono text-[10px] sm:text-xs uppercase tracking-wider font-bold px-2 sm:px-3"
                    >
                        <Plus className="h-3.5 w-3.5 sm:mr-2" />
                        <span className="hidden sm:inline">Log Signal</span>
                        <span className="sm:hidden ml-1">Log</span>
                    </Button>
                </div>
            </div>

            <div className="mt-6 flex items-center gap-3 text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-600">
                <Terminal className="h-3 w-3" />
                <span>~/learnforge/radar</span>
                <span className="text-zinc-700">/</span>
                <span className="text-lime-400/70">scanning leland event-stream</span>
                <span className="h-px flex-1 bg-zinc-800 ml-2" />
            </div>
        </header>
    );
}
