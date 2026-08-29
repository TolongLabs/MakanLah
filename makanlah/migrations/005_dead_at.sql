-- Liveness of a source post. Set by a background prober; request-time code
-- never fetches. Null means not known dead; a timestamp means the post was
-- found unreachable at that time.

alter table source_post add column if not exists dead_at timestamptz;

comment on column source_post.dead_at is
  'Timestamp when the post was found to be unreachable. Null means not known dead; '
  'a background prober sets this, and request-time code never fetches.';
