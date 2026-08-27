-- Source health, so `degraded` can be true honestly.
--
-- docs/PRD.md FR6 requires the API to say when a source was unreachable at the
-- last ingestion. Without a record of what ingestion attempted, `degraded` can
-- only ever be hardcoded false -- which is worse than not having the field,
-- because the UI then promises honesty it cannot deliver.

create table if not exists ingest_run (
  id          uuid primary key default uuid_generate_v4(),
  platform    text not null,
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  ok          boolean,
  posts_seen  integer not null default 0,
  posts_kept  integer not null default 0,
  error       text
);

comment on table ingest_run is
  'One row per platform per ingestion attempt. A failed run is a normal outcome, '
  'recorded and continued past, never an exception (docs/AUTONOMY.md).';

create index if not exists ingest_run_platform_time on ingest_run (platform, started_at desc);

-- The last outcome per platform, which is what a health check actually asks.
create or replace view source_status as
  select distinct on (platform)
         platform, started_at, finished_at, ok, posts_kept, error
  from ingest_run
  order by platform, started_at desc;
