-- The corpus schema from docs/TRD.md, as Postgres.
--
-- The spike validated it against real RedNote posts before this ran; where the
-- two differ, the differences are recorded in docs/TRD.md with the reason.

create extension if not exists "uuid-ossp";
create extension if not exists vector;
create extension if not exists pg_trgm;

-- ---------------------------------------------------------------- source_post
-- This table is the product. A recommendation that cannot reach a row here is
-- not a recommendation.

create table if not exists source_post (
  id                uuid primary key default uuid_generate_v4(),
  platform          text not null,
  platform_post_id  text not null,
  url               text not null,
  author_handle     text,
  posted_at         timestamptz,
  posted_at_raw     text,
  captured_at       timestamptz not null default now(),
  langs             text[] not null default '{}',
  raw_text          text,
  media_urls        text[] not null default '{}',
  raw_payload       jsonb not null default '{}'::jsonb,
  unique (platform, platform_post_id)
);

comment on column source_post.posted_at_raw is
  'RedNote renders relative or partial dates ("Feb 17", "3 days ago") with no year. '
  'The verbatim string is kept because parsing it is lossy and re-parsing offline is free.';
comment on column source_post.langs is
  'Plural by design. A single-language column would erase the code-switching that is the corpus.';

create index if not exists source_post_captured on source_post (captured_at desc);
create index if not exists source_post_platform on source_post (platform);

-- ---------------------------------------------------------------------- venue

create table if not exists venue (
  id                 uuid primary key default uuid_generate_v4(),
  name               text not null,
  name_normalized    text not null,
  aliases            text[] not null default '{}',
  lat                double precision,
  lng                double precision,
  geohash            text,
  address            text,
  area               text,
  city               text default 'Kuala Lumpur',
  geocoder           text,
  geocode_confidence real,
  place_id           text,
  created_at         timestamptz not null default now()
);

comment on column venue.lat is
  'Null is the normal state until geocoding catches up. A venue with null coordinates is '
  'excluded from distance-filtered queries and stays rankable by preference. Never deleted.';

create index if not exists venue_norm     on venue (name_normalized);
create index if not exists venue_geohash  on venue (geohash);
create index if not exists venue_name_trgm on venue using gin (name gin_trgm_ops);

-- -------------------------------------------------------------------- mention
-- The many-to-many, and the reason it exists: the spike's first real capture was
-- one post naming nine restaurants.

create table if not exists mention (
  id              uuid primary key default uuid_generate_v4(),
  post_id         uuid not null references source_post(id) on delete cascade,
  venue_id        uuid not null references venue(id) on delete cascade,
  dishes          text[] not null default '{}',
  sentiment       real,
  price_band      smallint,
  excerpt         text,
  excerpt_origin  text not null default 'model',
  extractor_model text,
  extracted_at    timestamptz not null default now(),
  confidence      real,
  unique (post_id, venue_id),
  constraint mention_sentiment_range  check (sentiment is null or sentiment between -1 and 1),
  constraint mention_price_band_range check (price_band is null or price_band between 1 and 4),
  constraint mention_excerpt_origin   check (excerpt_origin in ('model', 'repaired', 'dropped'))
);

comment on column mention.excerpt is
  'A VERBATIM span of the post. The spike found the extractor returning excerpts that read '
  'correctly and were not in the post, stitched from non-contiguous lines. A fabricated quote '
  'behind a citation is worse than no citation, so this is enforced by trigger, not convention.';
comment on column mention.excerpt_origin is
  'model = the extractor produced a real substring. repaired = re-anchored on the venue name '
  'after the extractor did not. dropped = neither worked and the citation falls back to the link.';

-- PRD acceptance criterion A2, enforced where it cannot be bypassed. Convention
-- is not enough: the failure is silent and the output reads correctly.
create or replace function mention_excerpt_is_verbatim() returns trigger as $$
declare
  post_body text;
begin
  if new.excerpt is null then
    return new;
  end if;
  select raw_text into post_body from source_post where id = new.post_id;
  if post_body is null or position(new.excerpt in post_body) = 0 then
    raise exception 'excerpt is not a substring of source_post.raw_text (post %)', new.post_id;
  end if;
  return new;
end;
$$ language plpgsql;

drop trigger if exists mention_excerpt_verbatim on mention;
create trigger mention_excerpt_verbatim
  before insert or update of excerpt on mention
  for each row execute function mention_excerpt_is_verbatim();

create index if not exists mention_venue on mention (venue_id);
create index if not exists mention_post  on mention (post_id);

-- -------------------------------------------------------------- venue_embedding
-- n is fixed by the chosen model. text-embedding-v3 on DashScope is 1024.

create table if not exists venue_embedding (
  venue_id   uuid not null references venue(id) on delete cascade,
  model      text not null,
  embedding  vector(1024),
  created_at timestamptz not null default now(),
  primary key (venue_id, model)
);

comment on table venue_embedding is
  'model is part of the key: embeddings from two models never compare, so storing them '
  'in one column keyed only by venue would silently mix incomparable vectors.';

create index if not exists venue_embedding_hnsw
  on venue_embedding using hnsw (embedding vector_cosine_ops);

-- ------------------------------------------------------------------ invariants

create or replace view uncited_venue as
  select v.* from venue v
  where not exists (select 1 from mention m where m.venue_id = v.id);

comment on view uncited_venue is
  'The one invariant, as a query: every ranked result joins to at least one source_post '
  'through mention. Rows here are unrankable and must never reach a response.';
