-- Which model last extracted a post, so a re-run does not re-spend a call on
-- every post it already understands.
--
-- Needed because "has no mentions" is not the same as "not extracted": a
-- video-first post that genuinely names no venue is correctly empty, and 16 of
-- the spike's first 50 were exactly that. Without this column those posts are
-- re-extracted forever.

alter table source_post add column if not exists extracted_with text;
alter table source_post add column if not exists extracted_at timestamptz;

comment on column source_post.extracted_with is
  'The extractor model that last ran over this post. Null means never extracted. '
  'Changing the model or the prompt is a re-extraction, and clearing this column is how.';

create index if not exists source_post_extracted on source_post (extracted_with);
