"""SQLite mirror of the corpus schema in docs/TRD.md.

SQLite is the spike store only; TRD picks Neon for the real corpus. Arrays and
jsonb become TEXT holding JSON, which is the one place this diverges from the
Postgres DDL the corpus phase will write.
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime

DDL = """
create table if not exists source_post (
  id text primary key,
  platform text not null,
  platform_post_id text not null,
  url text not null,
  author_handle text,
  posted_at text,
  captured_at text not null,
  langs text not null default '[]',
  raw_text text,
  media_urls text not null default '[]',
  raw_payload text not null default '{}',
  unique (platform, platform_post_id)
);

create table if not exists venue (
  id text primary key,
  name text not null,
  name_normalized text not null,
  aliases text not null default '[]',
  lat real, lng real,
  geohash text,
  address text, area text,
  city text,
  geocoder text,
  geocode_confidence real,
  place_id text
);
create index if not exists venue_norm on venue (name_normalized);

create table if not exists mention (
  id text primary key,
  post_id text not null references source_post(id) on delete cascade,
  venue_id text not null references venue(id),
  dishes text not null default '[]',
  sentiment real,
  price_band integer,
  excerpt text,
  extractor_model text,
  extracted_at text,
  confidence real,
  unique (post_id, venue_id)
);
"""


def now():
    return datetime.now(UTC).isoformat()


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    return con


def upsert_post(
    con, *, platform, platform_post_id, url, author_handle, posted_at, langs, raw_text, media_urls, raw_payload
):
    row = con.execute(
        'select id from source_post where platform=? and platform_post_id=?', (platform, platform_post_id)
    ).fetchone()
    if row:
        return row['id']
    pid = str(uuid.uuid4())
    con.execute(
        'insert into source_post (id, platform, platform_post_id, url, author_handle,'
        ' posted_at, captured_at, langs, raw_text, media_urls, raw_payload)'
        ' values (?,?,?,?,?,?,?,?,?,?,?)',
        (
            pid,
            platform,
            platform_post_id,
            url,
            author_handle,
            posted_at,
            now(),
            json.dumps(langs, ensure_ascii=False),
            raw_text,
            json.dumps(media_urls, ensure_ascii=False),
            json.dumps(raw_payload, ensure_ascii=False),
        ),
    )
    return pid


def normalize(name):
    import re
    import unicodedata

    s = unicodedata.normalize('NFKC', name or '').casefold()
    s = re.sub(r'\b(restoran|restaurant|kedai|cafe|café|kopitiam|餐厅|餐廳)\b', ' ', s)
    s = re.sub(r'[^\w一-鿿]+', ' ', s)
    return ' '.join(s.split())


def upsert_venue(con, *, name, aliases=None, area=None, city='Kuala Lumpur'):
    """Ambiguity creates a new venue — merging later is safe, a wrong merge is not."""
    norm = normalize(name)
    if not norm:
        return None
    row = con.execute('select id, aliases from venue where name_normalized=?', (norm,)).fetchone()
    if row:
        if aliases:
            have = set(json.loads(row['aliases']))
            merged = sorted(have | {a for a in aliases if a and a != name})
            con.execute('update venue set aliases=? where id=?', (json.dumps(merged, ensure_ascii=False), row['id']))
        return row['id']
    vid = str(uuid.uuid4())
    con.execute(
        'insert into venue (id, name, name_normalized, aliases, area, city) values (?,?,?,?,?,?)',
        (vid, name, norm, json.dumps(sorted(set(aliases or [])), ensure_ascii=False), area, city),
    )
    return vid


def upsert_mention(con, *, post_id, venue_id, dishes, sentiment, price_band, excerpt, extractor_model, confidence):
    row = con.execute('select id from mention where post_id=? and venue_id=?', (post_id, venue_id)).fetchone()
    if row:
        return row['id']
    mid = str(uuid.uuid4())
    con.execute(
        'insert into mention (id, post_id, venue_id, dishes, sentiment, price_band,'
        ' excerpt, extractor_model, extracted_at, confidence) values (?,?,?,?,?,?,?,?,?,?)',
        (
            mid,
            post_id,
            venue_id,
            json.dumps(dishes or [], ensure_ascii=False),
            sentiment,
            price_band,
            excerpt,
            extractor_model,
            now(),
            confidence,
        ),
    )
    return mid
