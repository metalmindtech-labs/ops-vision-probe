// Single source of truth for the public LearnForge destination.
// LearnForge is deployed on Vercel with Next.js i18n — all visitor-facing
// routes are prefixed with the locale (currently `/en`).
export const LEARNFORGE_URL = "https://learnforge-core.vercel.app";
export const LEARNFORGE_LOCALE = "en";

// Paid offers land on /en/courses/<slug>. Free lead-magnets land on
// /en/scrolls/<slug> (the "Scrolls" library route already exists on the
// live deployment). Keep these helpers in lockstep with the publisher
// service on the backend (services/publisher.py).
export const learnforgeCourseUrl = (slug) =>
    `${LEARNFORGE_URL}/${LEARNFORGE_LOCALE}/courses/${slug}`;

export const learnforgeScrollUrl = (slug) =>
    `${LEARNFORGE_URL}/${LEARNFORGE_LOCALE}/scrolls/${slug}`;

// Legacy aliases (preserved so old imports continue to work).
export const learnforgePaidUrl = learnforgeCourseUrl;
export const learnforgeFreeUrl = learnforgeScrollUrl;
