// app/api/course-generation-jobs/route.ts
// LearnForge v2 receiver STUB for CourseBriefV2 dispatched by Opportunity Radar.
//
// Responsibilities of THIS stub:
//   1. Verify the HMAC-SHA256 signature over the raw body.
//   2. Validate the CourseBriefV2 shape and reject any generated content.
//   3. Deduplicate on X-Radar-Idempotency-Key.
//   4. Persist the brief as a CourseJob in `accepted` state.
//   5. Enqueue the REAL generation pipeline at the TODO(generation) seam.
//   6. Respond 202 immediately (never block on generation).
//
// This stub does NOT generate a syllabus/modules/lessons. That is LearnForge's
// job, wired in behind TODO(generation).

import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { verifyRadarSignature } from "@/lib/radar/verify";
import { CourseBriefV2, assertNoContentFields } from "@/lib/radar/brief";

// import { prisma } from "@/lib/prisma"; // swap for your ORM/data layer

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PUBLIC_BASE =
  process.env.LEARNFORGE_PUBLIC_BASE_URL ?? "https://learnforge-core.vercel.app";

export async function POST(req: NextRequest) {
  // 1) Read the RAW body first — signature is computed over these exact bytes.
  const rawBody = await req.text();

  const signature = req.headers.get("x-radar-signature");
  const idempotencyKey = req.headers.get("x-radar-idempotency-key") ?? "";
  const secret = process.env.LEARNFORGE_WEBHOOK_SECRET;

  if (!verifyRadarSignature(rawBody, signature, secret)) {
    return NextResponse.json({ error: "invalid_signature" }, { status: 401 });
  }

  // 2) Parse + validate the brief; reject any generated educational content.
  let brief;
  try {
    const parsed = JSON.parse(rawBody);
    assertNoContentFields(parsed);
    brief = CourseBriefV2.parse(parsed);
  } catch (err) {
    return NextResponse.json(
      { error: "invalid_brief", detail: err instanceof Error ? err.message : String(err) },
      { status: 400 }
    );
  }

  const dedupeKey = idempotencyKey || brief.idempotency_key;

  // 3) Idempotency: return the ORIGINAL job for a repeat brief, no double work.
  // const existing = await prisma.courseJob.findUnique({ where: { idempotencyKey: dedupeKey } });
  // if (existing) {
  //   return NextResponse.json(
  //     {
  //       status: existing.status,
  //       job_id: existing.id,
  //       status_url: `${PUBLIC_BASE}/api/course-generation-jobs/${existing.id}`,
  //       public_course_url: existing.publicCourseUrl ?? null,
  //     },
  //     { status: 200 }
  //   );
  // }

  const jobId = `lf_job_${crypto.randomUUID()}`;

  // 4) Persist the accepted job.
  // await prisma.courseJob.create({
  //   data: {
  //     id: jobId,
  //     idempotencyKey: dedupeKey,
  //     signalId: brief.signal_id,
  //     correlationId: brief.callback.correlation_id,
  //     status: "accepted",
  //     brief: brief as unknown as Prisma.InputJsonValue,
  //     publicCourseUrl: null,
  //   },
  // });

  // 5) TODO(generation): enqueue LearnForge's real syllabus/module generation.
  //    Do NOT generate here — return fast and let the worker do the work.
  //    e.g. await courseGenerationQueue.add("generate", { jobId, signalId: brief.signal_id });

  // 6) Acknowledge. Radar records the job as `accepted` and polls status_url.
  return NextResponse.json(
    {
      status: "accepted",
      job_id: jobId,
      status_url: `${PUBLIC_BASE}/api/course-generation-jobs/${jobId}`,
      public_course_url: null,
    },
    { status: 202 }
  );
}

// Health check so Radar's reachability probe sees the route is live.
export async function GET() {
  return NextResponse.json({
    service: "learnforge-course-generation-jobs",
    schema_version: "2.0",
    method: "POST",
    signature_header: "X-Radar-Signature",
    signature_algorithm: "hmac-sha256",
  });
}
