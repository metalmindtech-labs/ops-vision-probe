// app/api/course-generation-jobs/[jobId]/route.ts
// Job-status endpoint. Radar's refresh/poller GETs this to learn when the
// LearnForge pipeline has moved a job to `ready` (and to fetch the public URL).
//
// status ∈ accepted | queued | generating | reviewing | ready | failed
// When your real pipeline finishes, set status="ready" + publicCourseUrl.

import { NextRequest, NextResponse } from "next/server";
// import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { jobId: string } }
) {
  const { jobId } = params;

  // const job = await prisma.courseJob.findUnique({ where: { id: jobId } });
  // if (!job) {
  //   return NextResponse.json({ error: "job_not_found" }, { status: 404 });
  // }
  // return NextResponse.json({
  //   status: job.status,
  //   job_id: job.id,
  //   signal_id: job.signalId,
  //   correlation_id: job.correlationId,
  //   public_course_url: job.publicCourseUrl ?? null,
  //   error: job.error ?? null,
  //   updated_at: job.updatedAt.toISOString(),
  // });

  // Stub fallback (until the data layer is wired): report accepted.
  return NextResponse.json({
    status: "accepted",
    job_id: jobId,
    public_course_url: null,
    error: null,
  });
}
