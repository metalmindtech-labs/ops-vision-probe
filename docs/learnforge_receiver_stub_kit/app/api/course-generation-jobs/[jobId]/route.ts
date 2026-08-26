// app/api/course-generation-jobs/[jobId]/route.ts
// Job-status endpoint. Radar's refresh/poller GETs this to learn when the
// LearnForge pipeline has moved a job to `ready` (and to fetch the public URL).
//
// status in: accepted | queued | generating | reviewing | ready | failed
// When the real pipeline finishes, it sets status="ready" + public_course_url
// on the course_jobs row; this endpoint simply reflects the stored state.

import { NextRequest, NextResponse } from "next/server";
import { supabaseJobStore } from "@/lib/radar/supabase-store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { jobId: string } }
) {
  const { jobId } = params;

  let job;
  try {
    job = await supabaseJobStore.findById(jobId);
  } catch (err) {
    return NextResponse.json(
      { error: "receiver_error", detail: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    );
  }

  if (!job) {
    return NextResponse.json({ error: "job_not_found" }, { status: 404 });
  }

  return NextResponse.json({
    status: job.status,
    job_id: job.id,
    signal_id: job.signal_id,
    correlation_id: job.correlation_id,
    public_course_url: job.public_course_url ?? null,
    error: job.error ?? null,
    updated_at: job.updated_at,
  });
}
