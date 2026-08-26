-- supabase/migrations/20260826000000_course_jobs.sql
-- CourseBriefV2 job ledger for the Radar -> LearnForge handshake.
-- Run via `supabase db push` or paste into the Supabase SQL editor.

create table if not exists public.course_jobs (
  id                text primary key,                 -- "lf_job_<uuid>"
  idempotency_key   text not null unique,             -- dedupe key from Radar
  signal_id         text not null,
  correlation_id    text not null,
  status            text not null default 'accepted', -- accepted|queued|generating|reviewing|ready|failed
  public_course_url text,
  error             text,
  brief             jsonb not null,                   -- full CourseBriefV2 as received
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint course_jobs_status_check check (
    status in ('accepted','queued','generating','reviewing','ready','failed')
  )
);

create index if not exists course_jobs_signal_id_idx on public.course_jobs (signal_id);
create index if not exists course_jobs_status_idx    on public.course_jobs (status);

-- Keep updated_at fresh on any change.
create or replace function public.set_course_jobs_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_course_jobs_updated_at on public.course_jobs;
create trigger trg_course_jobs_updated_at
  before update on public.course_jobs
  for each row execute function public.set_course_jobs_updated_at();

-- RLS: lock the table down. The receiver uses the SERVICE ROLE key, which
-- bypasses RLS, so no anon/auth policy is granted. This prevents any client
-- (browser/anon) from reading or writing the job ledger.
alter table public.course_jobs enable row level security;
-- (Intentionally no policies for anon/authenticated. Service role only.)
