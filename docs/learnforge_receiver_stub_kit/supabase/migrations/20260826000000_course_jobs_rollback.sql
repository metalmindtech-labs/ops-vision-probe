-- supabase/migrations/20260826000000_course_jobs_rollback.sql
-- DOWN migration for the CourseBriefV2 job ledger.
-- Safe to run in staging to reverse 20260826000000_course_jobs.sql.
-- This table is NEW and standalone (no FKs into it), so a clean drop fully
-- reverses the change with zero impact on courses/user_purchases/Stripe data.
--
-- PRODUCTION: only run inside the approved low-traffic window AFTER taking the
-- backup described in STAGING_RUNBOOK.md.

drop trigger  if exists trg_course_jobs_updated_at on public.course_jobs;
drop function if exists public.set_course_jobs_updated_at();
drop index    if exists public.course_jobs_signal_id_idx;
drop index    if exists public.course_jobs_status_idx;
drop table    if exists public.course_jobs;
