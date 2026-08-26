// lib/radar/supabase-store.ts
// Supabase-backed JobStore for CourseBriefV2 jobs. Uses the SERVICE ROLE key
// (server-only) so inserts bypass RLS; never import this in client code.
//
// Requires env:
//   NEXT_PUBLIC_SUPABASE_URL           (or SUPABASE_URL)
//   SUPABASE_SERVICE_ROLE_KEY

import { createClient, SupabaseClient } from "@supabase/supabase-js";
import type {
  CourseJobRecord,
  CreateAcceptedInput,
  JobStore,
} from "./receiver";

let _client: SupabaseClient | null = null;

function admin(): SupabaseClient {
  if (_client) return _client;
  const url =
    process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url) throw new Error("SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL is not set");
  if (!key) throw new Error("SUPABASE_SERVICE_ROLE_KEY is not set");
  _client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return _client;
}

export const supabaseJobStore: JobStore = {
  async findByIdempotencyKey(key: string): Promise<CourseJobRecord | null> {
    const { data, error } = await admin()
      .from("course_jobs")
      .select("*")
      .eq("idempotency_key", key)
      .maybeSingle();
    if (error) throw new Error(`course_jobs lookup failed: ${error.message}`);
    return (data as CourseJobRecord) ?? null;
  },

  async createAccepted(input: CreateAcceptedInput): Promise<CourseJobRecord> {
    const row = {
      id: input.id,
      idempotency_key: input.idempotency_key,
      signal_id: input.signal_id,
      correlation_id: input.correlation_id,
      status: "accepted" as const,
      public_course_url: null,
      error: null,
      brief: input.brief,
      created_at: input.now,
      updated_at: input.now,
    };
    const { data, error } = await admin()
      .from("course_jobs")
      .insert(row)
      .select("*")
      .single();
    if (error) throw new Error(`course_jobs insert failed: ${error.message}`);
    return data as CourseJobRecord;
  },

  async findById(id: string): Promise<CourseJobRecord | null> {
    const { data, error } = await admin()
      .from("course_jobs")
      .select("*")
      .eq("id", id)
      .maybeSingle();
    if (error) throw new Error(`course_jobs lookup failed: ${error.message}`);
    return (data as CourseJobRecord) ?? null;
  },
};
