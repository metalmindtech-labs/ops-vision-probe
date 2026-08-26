// lib/radar/brief.ts
// Zod schema for CourseBriefV2 (the Radar → LearnForge contract) plus a
// defensive guard that rejects any generated educational content. Radar
// promises never to send modules/lessons/quizzes/syllabus; we assert it here
// too so a contract regression is caught at the boundary.

import { z } from "zod";

const FORBIDDEN_CONTENT_KEYS = new Set([
  "modules",
  "module",
  "lessons",
  "lesson",
  "quizzes",
  "quiz",
  "syllabus",
  "syllabus_modules",
  "curriculum",
  "chapters",
  "units",
  "lesson_plan",
  "learning_objectives",
  "course_content",
]);

export const SourceEvidence = z.object({
  provider: z.string().default("leland"),
  source_url: z.string().nullable().optional(),
  source_title: z.string(),
  observed_at: z.string().nullable().optional(),
});

export const DemandEvidence = z.object({
  registrations: z.number().int().nonnegative(),
  priority_score: z.number().int(),
  priority_band: z.string(),
  category: z.string(),
  velocity_note: z.string().nullable().optional(),
});

export const AudienceProfile = z.object({
  primary_persona: z.string(),
  current_state: z.string(),
  desired_outcome: z.string(),
  pain_points: z.array(z.string()).default([]),
});

export const CommercialHypothesis = z.object({
  offer_title: z.string().nullable().optional(),
  promise: z.string().nullable().optional(),
  price_usd: z.number().nullable().optional(),
  anchor_price_usd: z.number().nullable().optional(),
  discount_pct: z.number().int().nullable().optional(),
  free_module_count: z.number().int().default(2),
  cta_headline: z.string().nullable().optional(),
  cta_subtext: z.string().nullable().optional(),
  validation_status: z.literal("hypothesis"),
});

export const GenerationConstraints = z.object({
  difficulty: z.string().default("intermediate"),
  language: z.string().default("en"),
  target_duration_min: z.number().int(),
  suggested_module_count: z.number().int(),
  required_outcomes: z.array(z.string()).default([]),
  prohibited_claims: z.array(z.string()).default([]),
});

export const Callback = z.object({
  correlation_id: z.string(),
  status_url: z.string().nullable().optional(),
});

export const CourseBriefV2 = z
  .object({
    schema_version: z.literal("2.0"),
    signal_id: z.string(),
    idempotency_key: z.string(),
    source: SourceEvidence,
    demand_evidence: DemandEvidence,
    audience: AudienceProfile,
    commercial_hypothesis: CommercialHypothesis,
    generation_constraints: GenerationConstraints,
    callback: Callback,
  })
  .strict();

export type CourseBriefV2 = z.infer<typeof CourseBriefV2>;

/** Recursively reject any generated-educational-content key at any depth. */
export function assertNoContentFields(value: unknown): void {
  if (Array.isArray(value)) {
    for (const item of value) assertNoContentFields(item);
  } else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) {
      if (FORBIDDEN_CONTENT_KEYS.has(k)) {
        throw new Error(`CourseBriefV2 must not contain generated content field '${k}'`);
      }
      assertNoContentFields(v);
    }
  }
}
