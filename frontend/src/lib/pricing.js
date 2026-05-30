// Canonical 'Slam Offer' discount math — must match the server-side
// compute_discount_pct in /app/backend/services/publisher.py exactly so
// the Radar's preview always agrees with what LearnForge will render.
//
// Formula: round(((original - current) / original) * 100)
export function computeDiscountPct(current, original) {
    if (current === null || current === undefined || current === "") return null;
    if (original === null || original === undefined || original === "") return null;
    const cur = Number(current);
    const orig = Number(original);
    if (!Number.isFinite(cur) || !Number.isFinite(orig)) return null;
    if (orig <= 0 || cur < 0) return null;
    if (cur >= orig) return 0;
    return Math.round(((orig - cur) / orig) * 100);
}

export function formatUsd(n) {
    if (n === null || n === undefined || n === "") return null;
    const x = Number(n);
    if (!Number.isFinite(x)) return null;
    return `$${x.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
