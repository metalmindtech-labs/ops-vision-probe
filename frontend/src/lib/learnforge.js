// Single source of truth for the public LearnForge destination.
// Update this constant if the destination ever changes.
export const LEARNFORGE_URL = "https://learnforge-core.vercel.app";

export const learnforgeFreeUrl = (slug) =>
    `${LEARNFORGE_URL}/free/${slug}`;

export const learnforgePaidUrl = (slug) =>
    `${LEARNFORGE_URL}/forgecore/${slug}`;
