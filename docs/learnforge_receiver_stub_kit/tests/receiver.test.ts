// tests/receiver.test.ts
// Vitest suite for the CourseBriefV2 receiver. Run in learnforge-core:
//   npx vitest run tests/receiver.test.ts
//
// Tests the pure processCourseBrief() with an in-memory JobStore — no network,
// no Supabase, no deployment. Covers: HMAC accept/reject, schema-version guard,
// forbidden educational content, required demand-source attribution, malformed
// body, idempotency dedupe, and the 202 accepted contract.

import { describe, it, expect, beforeEach } from "vitest";
import crypto from "crypto";
import {
  processCourseBrief,
  JobStore,
  CourseJobRecord,
  CreateAcceptedInput,
} from "../lib/radar/receiver";

const SECRET = "SovereignForge2026!";
const PUBLIC_BASE = "https://learnforge-core.vercel.app";

function sign(secret: string, rawBody: string): string {
  return crypto.createHmac("sha256", secret).update(rawBody, "utf8").digest("hex");
}

function canonical(obj: unknown): string {
  // Compact, key-sorted JSON — matches Radar's dispatcher body encoding.
  const sort = (v: any): any =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.keys(v)
          .sort()
          .reduce((a, k) => ((a[k] = sort(v[k])), a), {} as any)
      : Array.isArray(v)
      ? v.map(sort)
      : v;
  return JSON.stringify(sort(obj));
}

function validBrief(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "2.0",
    signal_id: "sig-1",
    idempotency_key: "idem-" + Math.random().toString(36).slice(2),
    source: {
      provider: "leland",
      source_url: "https://leland.com/events/x",
      source_title: "Cracking the MBB Case Interview",
      observed_at: "2026-06-01T00:00:00Z",
    },
    demand_evidence: {
      registrations: 113888,
      priority_score: 100,
      priority_band: "breakout",
      category: "Consulting",
      velocity_note: null,
    },
    audience: {
      primary_persona: "Aspiring MBB consultants",
      current_state: "Registered interest via a free event",
      desired_outcome: "Land an MBB offer",
      pain_points: ["No structured path"],
    },
    commercial_hypothesis: {
      offer_title: "ForgeCore: MBB Case Engine",
      promise: "8 modules, 12 live cases",
      price_usd: 299,
      anchor_price_usd: 1899,
      discount_pct: 84,
      free_module_count: 2,
      cta_headline: "Land Your MBB Offer",
      cta_subtext: "Master the framework stack",
      validation_status: "hypothesis",
    },
    generation_constraints: {
      difficulty: "intermediate",
      language: "en",
      target_duration_min: 270,
      suggested_module_count: 6,
      required_outcomes: ["Land an MBB offer"],
      prohibited_claims: ["No unverified income claims"],
    },
    callback: { correlation_id: "radar-sig-1", status_url: null },
    ...overrides,
  };
}

class InMemoryStore implements JobStore {
  byKey = new Map<string, CourseJobRecord>();
  byId = new Map<string, CourseJobRecord>();
  async findByIdempotencyKey(key: string) {
    return this.byKey.get(key) ?? null;
  }
  async findById(id: string) {
    return this.byId.get(id) ?? null;
  }
  async createAccepted(input: CreateAcceptedInput): Promise<CourseJobRecord> {
    const rec: CourseJobRecord = {
      id: input.id,
      idempotency_key: input.idempotency_key,
      signal_id: input.signal_id,
      correlation_id: input.correlation_id,
      status: "accepted",
      public_course_url: null,
      error: null,
      created_at: input.now,
      updated_at: input.now,
    };
    this.byKey.set(rec.idempotency_key, rec);
    this.byId.set(rec.id, rec);
    return rec;
  }
}

function run(body: string, headers: Record<string, string>, store: JobStore) {
  return processCourseBrief({
    rawBody: body,
    getHeader: (n) => headers[n.toLowerCase()] ?? null,
    secret: SECRET,
    store,
    publicBase: PUBLIC_BASE,
    idGen: () => "lf_job_test",
    now: () => "2026-06-01T00:00:00.000Z",
  });
}

function headersFor(body: string, extra: Record<string, string> = {}) {
  return {
    "content-type": "application/json",
    "x-radar-event": "course_brief.dispatch",
    "x-radar-schema-version": "2.0",
    "x-radar-idempotency-key": "hdr",
    "x-radar-signature": sign(SECRET, body),
    "x-radar-signature-algorithm": "hmac-sha256",
    ...extra,
  };
}

describe("processCourseBrief", () => {
  let store: InMemoryStore;
  beforeEach(() => {
    store = new InMemoryStore();
  });

  it("accepts a valid signed brief with 202 + job_id + status_url", async () => {
    const body = canonical(validBrief());
    const res = await run(body, headersFor(body), store);
    expect(res.status).toBe(202);
    expect(res.body.status).toBe("accepted");
    expect(res.body.job_id).toBe("lf_job_test");
    expect(res.body.status_url).toBe(
      `${PUBLIC_BASE}/api/course-generation-jobs/lf_job_test`
    );
    expect(res.body.public_course_url).toBeNull();
  });

  it("rejects an invalid signature with 401", async () => {
    const body = canonical(validBrief());
    const res = await run(body, headersFor(body, { "x-radar-signature": "deadbeef" }), store);
    expect(res.status).toBe(401);
    expect(res.body.error).toBe("invalid_signature");
  });

  it("rejects a missing signature with 401", async () => {
    const body = canonical(validBrief());
    const h = headersFor(body);
    delete (h as any)["x-radar-signature"];
    const res = await run(body, h, store);
    expect(res.status).toBe(401);
  });

  it("rejects an unsupported schema version (header) with 400", async () => {
    const body = canonical(validBrief());
    const res = await run(body, headersFor(body, { "x-radar-schema-version": "1.0" }), store);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("unsupported_schema_version");
  });

  it("rejects generated educational content (forbidden field) with 400", async () => {
    const body = canonical(validBrief({ modules: [{ title: "Module 1" }] }));
    const res = await run(body, headersFor(body), store);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("forbidden_content");
  });

  it("rejects nested forbidden content (syllabus) with 400", async () => {
    const brief = validBrief();
    (brief as any).generation_constraints.syllabus = ["x"];
    const body = canonical(brief);
    const res = await run(body, headersFor(body), store);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("forbidden_content");
  });

  it("rejects missing demand-source attribution with 400", async () => {
    const brief = validBrief();
    (brief as any).source.source_title = "";
    const body = canonical(brief);
    const res = await run(body, headersFor(body), store);
    expect(res.status).toBe(400);
    // Zod min(1) trips first as invalid_brief; both are acceptable 400s.
    expect(["invalid_brief", "missing_source_attribution"]).toContain(res.body.error);
  });

  it("rejects an unknown extra field (strict schema) with 400", async () => {
    const body = canonical(validBrief({ price_final: 299 }));
    const res = await run(body, headersFor(body), store);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("invalid_brief");
  });

  it("rejects malformed JSON with 400", async () => {
    const body = "{not json";
    const res = await run(body, headersFor(body), store);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("invalid_json");
  });

  it("deduplicates a repeat idempotency key with 200 + original job_id", async () => {
    const brief = validBrief({ idempotency_key: "same-key" });
    const body = canonical(brief);
    const first = await run(body, headersFor(body), store);
    expect(first.status).toBe(202);
    const second = await run(body, headersFor(body), store);
    expect(second.status).toBe(200);
    expect(second.body.deduplicated).toBe(true);
    expect(second.body.job_id).toBe(first.body.job_id);
  });
});
