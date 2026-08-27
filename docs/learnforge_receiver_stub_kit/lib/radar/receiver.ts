// lib/radar/receiver.ts
// Pure, framework-agnostic processing of an inbound CourseBriefV2 from
// Opportunity Radar. Separated from the Next.js route + Supabase so it can be
// unit-tested with an in-memory JobStore (see tests/receiver.test.ts).
//
// Ownership boundary: this ACCEPTS and records a job. It NEVER generates a
// syllabus/modules/lessons — that is LearnForge's pipeline, wired in later at
// the caller's TODO(generation) seam.

import crypto from "crypto";
import { verifyRadarSignature, secretFingerprint } from "./verify";
import { CourseBriefV2, assertNoContentFields } from "./brief";

export const SUPPORTED_SCHEMA_VERSION = "2.0";

export type JobStatus =
  | "accepted"
  | "queued"
  | "generating"
  | "reviewing"
  | "ready"
  | "failed";

export interface CourseJobRecord {
  id: string;
  idempotency_key: string;
  signal_id: string;
  correlation_id: string;
  status: JobStatus;
  public_course_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAcceptedInput {
  id: string;
  idempotency_key: string;
  signal_id: string;
  correlation_id: string;
  brief: CourseBriefV2;
  now: string;
}

/** Storage seam. Supabase-backed in production (lib/radar/supabase-store.ts). */
export interface JobStore {
  findByIdempotencyKey(key: string): Promise<CourseJobRecord | null>;
  createAccepted(input: CreateAcceptedInput): Promise<CourseJobRecord>;
  findById(id: string): Promise<CourseJobRecord | null>;
}

export interface ProcessDeps {
  rawBody: string;
  getHeader: (name: string) => string | null;
  secret: string | undefined;
  store: JobStore;
  publicBase: string;
  idGen?: () => string;
  now?: () => string;
}

export interface ProcessResult {
  status: number;
  body: Record<string, unknown>;
}

function statusUrl(base: string, id: string): string {
  return `${base.replace(/\/+$/, "")}/api/course-generation-jobs/${id}`;
}

function msg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export async function processCourseBrief(deps: ProcessDeps): Promise<ProcessResult> {
  const { rawBody, getHeader, secret, store, publicBase } = deps;
  const idGen = deps.idGen ?? (() => `lf_job_${crypto.randomUUID()}`);
  const now = deps.now ?? (() => new Date().toISOString());

  // 1) HMAC signature over the raw body (fail closed).
  const signature = getHeader("x-radar-signature");
  if (!verifyRadarSignature(rawBody, signature, secret)) {
    // Return expected_fp (non-reversible) so Radar's hint can show an exact
    // MATCH/MISMATCH against its own signing fingerprint. Never the secret.
    return {
      status: 401,
      body: { error: "invalid_signature", expected_fp: secretFingerprint(secret) },
    };
  }

  // 2) Schema-version header fast-reject (before parsing).
  const headerSchema = getHeader("x-radar-schema-version");
  if (headerSchema && headerSchema !== SUPPORTED_SCHEMA_VERSION) {
    return {
      status: 400,
      body: {
        error: "unsupported_schema_version",
        detail: `expected ${SUPPORTED_SCHEMA_VERSION}, got ${headerSchema}`,
      },
    };
  }

  // 3) Parse JSON.
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawBody);
  } catch {
    return { status: 400, body: { error: "invalid_json" } };
  }

  // 4) Reject any generated educational content (defense-in-depth).
  try {
    assertNoContentFields(parsed);
  } catch (e) {
    return { status: 400, body: { error: "forbidden_content", detail: msg(e) } };
  }

  // 5) Validate the CourseBriefV2 shape (strict).
  const result = CourseBriefV2.safeParse(parsed);
  if (!result.success) {
    return {
      status: 400,
      body: {
        error: "invalid_brief",
        detail: result.error.issues
          .slice(0, 8)
          .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`),
      },
    };
  }
  const brief = result.data;

  // 6) Body schema-version guard.
  if (brief.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    return {
      status: 400,
      body: { error: "unsupported_schema_version", detail: brief.schema_version },
    };
  }

  // 7) Required demand-source attribution (belt-and-suspenders beyond Zod).
  if (!brief.source.provider?.trim() || !brief.source.source_title?.trim()) {
    return {
      status: 400,
      body: {
        error: "missing_source_attribution",
        detail: "source.provider and source.source_title are required",
      },
    };
  }

  // 8) Idempotency: a repeat brief returns the ORIGINAL job, no double work.
  const key = brief.idempotency_key;
  const existing = await store.findByIdempotencyKey(key);
  if (existing) {
    return {
      status: 200,
      body: {
        status: existing.status,
        job_id: existing.id,
        status_url: statusUrl(publicBase, existing.id),
        public_course_url: existing.public_course_url ?? null,
        deduplicated: true,
      },
    };
  }

  // 9) Create the accepted job. TODO(generation): the CALLER enqueues the real
  //    LearnForge generation pipeline here (queue/cron) AFTER this returns.
  //    Do NOT generate content in the request path.
  const record = await store.createAccepted({
    id: idGen(),
    idempotency_key: key,
    signal_id: brief.signal_id,
    correlation_id: brief.callback.correlation_id,
    brief,
    now: now(),
  });

  return {
    status: 202,
    body: {
      status: "accepted",
      job_id: record.id,
      status_url: statusUrl(publicBase, record.id),
      public_course_url: null,
    },
  };
}
