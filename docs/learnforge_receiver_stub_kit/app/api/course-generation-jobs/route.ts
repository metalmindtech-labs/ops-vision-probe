// app/api/course-generation-jobs/route.ts
// LearnForge v2 receiver for CourseBriefV2 dispatched by Opportunity Radar.
//
// This handler ACCEPTS and records a job (202). It does NOT generate a
// syllabus/modules/lessons — that is LearnForge's pipeline, wired in at the
// TODO(generation) seam below AFTER the job is persisted.

import { NextRequest, NextResponse } from "next/server";
import { processCourseBrief } from "@/lib/radar/receiver";
import { supabaseJobStore } from "@/lib/radar/supabase-store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PUBLIC_BASE =
  process.env.LEARNFORGE_PUBLIC_BASE_URL ?? "https://learnforge-core.vercel.app";

export async function POST(req: NextRequest) {
  // Read the RAW body first — the HMAC signature is over these exact bytes.
  const rawBody = await req.text();

  let result;
  try {
    result = await processCourseBrief({
      rawBody,
      getHeader: (name) => req.headers.get(name),
      secret: process.env.LEARNFORGE_WEBHOOK_SECRET,
      store: supabaseJobStore,
      publicBase: PUBLIC_BASE,
    });
  } catch (err) {
    // Storage/transport failure — honest 500, Radar records the job as failed.
    return NextResponse.json(
      { error: "receiver_error", detail: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    );
  }

  // TODO(generation): if result.status === 202, enqueue LearnForge's real
  // generation pipeline for result.body.job_id. Do it out-of-band (queue/cron);
  // never block this response on generation.
  // e.g. if (result.status === 202) await courseQueue.add("generate", {
  //   jobId: result.body.job_id, signalId: /* from brief */ });

  return NextResponse.json(result.body, { status: result.status });
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
