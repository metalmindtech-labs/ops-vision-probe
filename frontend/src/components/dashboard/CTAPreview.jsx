import { ArrowRight } from "lucide-react";
import { DASHBOARD } from "@/constants/testIds/dashboard";

const BG =
    "https://static.prod-images.emergentagent.com/jobs/c9d4ad82-ee78-430f-ba33-adadcbc6a8f0/images/4a2534d30c85ebdbcd6a97c742c3f3d16e8a1a300f16b232c076e3eab8c5edd1.png";

export default function CTAPreview({ headline, subtext, paidUrl, freeUrl }) {
    return (
        <div
            data-testid={DASHBOARD.ctaPreview}
            className="relative overflow-hidden border border-zinc-800 rounded-sm"
        >
            <div
                className="absolute inset-0 bg-cover bg-center opacity-60"
                style={{ backgroundImage: `url(${BG})` }}
            />
            <div className="absolute inset-0 bg-gradient-to-tr from-zinc-950 via-zinc-950/85 to-zinc-950/40" />
            <div className="absolute inset-0 grid-bg opacity-40" />

            <div className="relative p-6 sm:p-8">
                <div className="flex items-center gap-2 mb-4">
                    <span className="h-1.5 w-1.5 rounded-full bg-lime-400 pulse-lime" />
                    <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-lime-400">
                        LearnForge · Powered by Leland Signal
                    </span>
                </div>

                <h3 className="font-mono text-2xl sm:text-3xl font-bold text-zinc-50 leading-tight tracking-tight max-w-md">
                    {headline}
                </h3>
                <p className="mt-2 text-sm text-zinc-300 max-w-md">{subtext}</p>

                <div className="mt-6 flex flex-wrap items-center gap-3">
                    <a
                        href={paidUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 bg-lime-400 hover:bg-lime-300 text-black font-mono text-xs uppercase tracking-[0.2em] font-bold px-4 py-2.5 rounded-sm transition-colors group"
                    >
                        Enroll in ForgeCore
                        <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
                    </a>
                    <a
                        href={freeUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 border border-zinc-700 hover:border-lime-400/60 text-zinc-100 hover:text-lime-300 font-mono text-xs uppercase tracking-[0.2em] px-4 py-2.5 rounded-sm transition-colors"
                    >
                        Grab the Free Drop
                    </a>
                </div>
            </div>
        </div>
    );
}
