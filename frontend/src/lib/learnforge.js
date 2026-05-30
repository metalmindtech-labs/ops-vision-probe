// Single source of truth for the public LearnForge destination.
// As of Architect directive (2026-05-30) all visitor-facing enrollment CTAs
// land on the universal /signup route. Localized sub-paths (/en/*) and the
// /courses/<slug>, /scrolls/<slug> deep-routes are temporarily disabled
// because those routes are not yet deployed on learnforge-core.vercel.app
// — they 404. /signup is a live, locale-aware redirect. The course slug is
// preserved as a query param (?course=<slug>) so the LearnForge signup page
// can attribute the lead back to the originating ForgeCore offer.
export const LEARNFORGE_URL = "https://learnforge-core.vercel.app";
export const LEARNFORGE_SIGNUP_URL = `${LEARNFORGE_URL}/signup`;

const withRef = (slug, kind) => {
    if (!slug) return LEARNFORGE_SIGNUP_URL;
    const u = new URL(LEARNFORGE_SIGNUP_URL);
    u.searchParams.set("course", slug);
    u.searchParams.set("ref", "radar");
    if (kind) u.searchParams.set("tier", kind);
    return u.toString();
};

// Paid enrollment CTA (ForgeCore offer)
export const learnforgeCourseUrl = (slug) => withRef(slug, "forgecore");
// Free lead-magnet CTA (Scroll)
export const learnforgeScrollUrl = (slug) => withRef(slug, "free");
// Generic signup CTA (no slug context)
export const learnforgeSignupUrl = () => LEARNFORGE_SIGNUP_URL;

// Legacy aliases preserved
export const learnforgePaidUrl = learnforgeCourseUrl;
export const learnforgeFreeUrl = learnforgeScrollUrl;
export const LEARNFORGE_LOCALE = "en";
