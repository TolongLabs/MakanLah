"""Corpus access. The only module that speaks SQL.

ingest/ writes through here, api/ reads through here, and neither holds a
connection the other can see.
"""

import json
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from makanlah import config

_pool = None


@contextmanager
def connect(direct=False):
    """Pooled for the API, direct for migrations and long ingestion batches.

    pgbouncer in transaction mode does not support the session-level statements
    DDL and some long transactions issue.
    """
    s = config.settings()
    dsn = (s.database_url_direct if direct else s.database_url) or s.database_url
    if not dsn:
        raise RuntimeError('DATABASE_URL is not set')
    with psycopg.connect(dsn, row_factory=dict_row) as con:
        yield con


def upsert_post(
    con, *, platform, platform_post_id, url, author_handle, posted_at_raw, langs, raw_text, media_urls, raw_payload
):
    """Idempotent on (platform, platform_post_id) — the dedup key across re-ingestion."""
    row = con.execute(
        """insert into source_post (platform, platform_post_id, url, author_handle,
                                    posted_at_raw, langs, raw_text, media_urls, raw_payload)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (platform, platform_post_id) do update
             set raw_text = excluded.raw_text,
                 raw_payload = excluded.raw_payload
           returning id""",
        (
            platform,
            platform_post_id,
            url,
            author_handle,
            posted_at_raw,
            langs,
            raw_text,
            media_urls,
            json.dumps(raw_payload, ensure_ascii=False),
        ),
    ).fetchone()
    return row['id']


def upsert_venue(con, *, name, name_normalized, aliases, area, city='Kuala Lumpur'):
    """Ambiguity creates a new venue. Merging later is safe; a wrong merge is not."""
    row = con.execute('select id, aliases from venue where name_normalized = %s', (name_normalized,)).fetchone()
    if row:
        merged = sorted(set(row['aliases']) | {a for a in aliases if a and a != name})
        if merged != sorted(row['aliases']):
            con.execute('update venue set aliases = %s where id = %s', (merged, row['id']))
        return row['id']
    return con.execute(
        """insert into venue (name, name_normalized, aliases, area, city)
           values (%s,%s,%s,%s,%s) returning id""",
        (name, name_normalized, sorted(set(aliases)), area, city),
    ).fetchone()['id']


def upsert_mention(
    con, *, post_id, venue_id, dishes, sentiment, price_band, excerpt, excerpt_origin, extractor_model, confidence
):
    return con.execute(
        """insert into mention (post_id, venue_id, dishes, sentiment, price_band, excerpt,
                                excerpt_origin, extractor_model, confidence)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (post_id, venue_id) do nothing
           returning id""",
        (post_id, venue_id, dishes, sentiment, price_band, excerpt, excerpt_origin, extractor_model, confidence),
    ).fetchone()


def set_coords(con, venue_id, lat, lng, address, geocoder, confidence):
    con.execute(
        """update venue set lat=%s, lng=%s, address=%s, geocoder=%s, geocode_confidence=%s
           where id=%s""",
        (lat, lng, address, geocoder, confidence, venue_id),
    )


def upsert_embedding(con, venue_id, model, vector):
    con.execute(
        """insert into venue_embedding (venue_id, model, embedding) values (%s,%s,%s)
           on conflict (venue_id, model) do update set embedding = excluded.embedding""",
        (venue_id, model, str(vector)),
    )


def venue_documents(con, only_missing_for=None):
    """The composite a venue is embedded from: name, aliases, dishes, excerpts.

    Not the raw posts. The retrievable unit is a venue; posts are evidence
    attached to it (docs/TRD.md).
    """
    sql = """
      select v.id,
             v.name || ' ' || coalesce(array_to_string(v.aliases, ' '), '') || '. ' ||
             coalesce(v.area, '') || ' ' || coalesce(v.city, '') || '. ' ||
             coalesce((select string_agg(distinct d, ', ')
                       from mention m2, unnest(m2.dishes) d
                       where m2.venue_id = v.id), '') || '. ' ||
             coalesce((select string_agg(m3.excerpt, ' ')
                       from (select excerpt from mention
                             where venue_id = v.id and excerpt is not null
                             order by confidence desc nulls last limit 4) m3), '') as document
      from venue v
      where exists (select 1 from mention m where m.venue_id = v.id)
    """
    params = ()
    if only_missing_for:
        sql += """ and not exists (select 1 from venue_embedding e
                                   where e.venue_id = v.id and e.model = %s)"""
        params = (only_missing_for,)
    return con.execute(sql, params).fetchall()


# ------------------------------------------------------------------ ranking


def filter_candidates(con, *, lat=None, lng=None, radius_m=None, limit=400):
    """Stage 1. Distance in SQL before the vector index is touched.

    Filtering after retrieval wastes the index and returns a great match forty
    minutes away. Venues without coordinates are included only when no distance
    bound was given — they stay rankable by preference, never deleted.
    """
    if lat is None or lng is None or not radius_m:
        # Ordered by evidence, not arbitrarily: `limit` truncates, and an
        # unordered truncation returns a different 400 venues between calls,
        # which makes a ranking complaint impossible to reproduce.
        rows = con.execute(
            """select v.id
               from venue v
               join (select venue_id, count(*) as n from mention group by venue_id) m
                 on m.venue_id = v.id
               order by m.n desc, v.id
               limit %s""",
            (limit,),
        ).fetchall()
        return [r['id'] for r in rows]
    # The spherical law of cosines needs the query latitude TWICE and the query
    # longitude once. The distance is computed in a subquery so the bound and the
    # ordering can both reference it without restating it, and so the placeholder
    # count is obvious: three for the position, one for the bound, one for limit.
    rows = con.execute(
        """select id from (
             select v.id,
                    6371000 * acos(least(1, greatest(-1,
                        cos(radians(%s)) * cos(radians(v.lat)) * cos(radians(v.lng) - radians(%s))
                      + sin(radians(%s)) * sin(radians(v.lat))))) as dist
             from venue v
             where v.lat is not null and v.lng is not null
               and exists (select 1 from mention m where m.venue_id = v.id)
           ) t
           where t.dist <= %s
           order by t.dist
           limit %s""",
        (lat, lng, lat, radius_m, limit),
    ).fetchall()
    return [r['id'] for r in rows]


def retrieve(con, query_vector, candidate_ids, model, k=50):
    """Stage 2. pgvector cosine over the already-filtered candidate set."""
    if not candidate_ids:
        return []
    return con.execute(
        """select e.venue_id, 1 - (e.embedding <=> %s::vector) as score
           from venue_embedding e
           where e.model = %s and e.venue_id = any(%s)
           order by e.embedding <=> %s::vector
           limit %s""",
        (str(query_vector), model, list(candidate_ids), str(query_vector), k),
    ).fetchall()


def venues_with_citations(con, venue_ids, per_venue=3):
    """Stage 4. Citations come from the database, never from the model.

    A model asked to produce a URL produces a plausible one.
    """
    if not venue_ids:
        return {}
    rows = con.execute(
        """select v.id as venue_id, v.name, v.area, v.city, v.lat, v.lng, v.place_id,
                  m.excerpt, m.dishes, m.sentiment, m.confidence,
                  p.url as post_url, p.platform, p.author_handle, p.posted_at_raw
           from venue v
           join mention m on m.venue_id = v.id
           join source_post p on p.id = m.post_id
           where v.id = any(%s)
           order by v.id, m.confidence desc nulls last""",
        (list(venue_ids),),
    ).fetchall()
    out, pool = {}, {}
    for r in rows:
        v = out.setdefault(
            r['venue_id'],
            {
                'id': r['venue_id'],
                'name': r['name'],
                'area': r['area'],
                'city': r['city'],
                'lat': r['lat'],
                'lng': r['lng'],
                'place_id': r['place_id'],
                'dishes': [],
                'citations': [],
            },
        )
        for d in r['dishes'] or []:
            if d not in v['dishes']:
                v['dishes'].append(d)
        pool.setdefault(r['venue_id'], []).append(
            {
                'post_url': r['post_url'],
                'excerpt': r['excerpt'],
                'platform': r['platform'],
                'author_handle': r['author_handle'],
                'posted_at': r['posted_at_raw'],
            }
        )

    for venue_id, cites in pool.items():
        out[venue_id]['citations'] = diverse_citations(cites, per_venue)
    return out


def diverse_citations(citations, limit):
    """Take one citation from each platform before taking a second from any.

    Ordering purely by confidence hands every slot to whichever source the
    extractor is most sure about, which was RedNote across the whole corpus, so
    Google Maps evidence existed and never appeared. Two sources the user cannot
    see is the same as one source, and showing both is what makes "neither is
    load-bearing" legible rather than a claim in a design document.

    `citations` arrives already ordered best-first within each platform.
    """
    by_platform = {}
    for c in citations:
        by_platform.setdefault(c['platform'], []).append(c)

    picked = []
    while len(picked) < limit and any(by_platform.values()):
        for p in list(by_platform):
            if not by_platform[p]:
                continue
            picked.append(by_platform[p].pop(0))
            if len(picked) >= limit:
                break
    return picked


# ------------------------------------------------------------ source health

# Platforms the corpus is meant to carry. A platform listed here that has never
# ingested, or whose last run failed, is a degraded state the UI must state
# plainly rather than hide (docs/PRD.md FR6).
EXPECTED_PLATFORMS = ('rednote', 'google_maps')

# These strings render straight to a user, so they follow docs/DESIGN.md: plain
# sentence case, no internal identifiers. "rednote has never ingested" is
# accurate and is not something anyone outside this repo can read.
PLATFORM_NAMES = {'rednote': 'RedNote', 'google_maps': 'Google Maps', 'instagram': 'Instagram'}


def platform_name(p):
    return PLATFORM_NAMES.get(p, p.replace('_', ' ').title())


# How stale the newest capture may get before the corpus counts as degraded.
# Freshness is a background concern, so this is generous: a day of failed
# ingestion is meant to be invisible to a user, a week is not.
STALE_AFTER_HOURS = 168


def start_run(con, platform):
    row = con.execute('insert into ingest_run (platform) values (%s) returning id', (platform,)).fetchone()
    con.commit()
    return row['id']


def finish_run(con, run_id, *, ok, posts_seen=0, posts_kept=0, error=None):
    con.execute(
        """update ingest_run set finished_at = now(), ok = %s, posts_seen = %s,
               posts_kept = %s, error = %s where id = %s""",
        (ok, posts_seen, posts_kept, (error or None), run_id),
    )
    con.commit()


def source_health(con):
    """Returns (degraded, sources_ok, reasons). Never raises: a health check that
    fails closed would make every request look degraded."""
    reasons, ok_sources = [], []
    try:
        rows = {r['platform']: r for r in con.execute('select * from source_status').fetchall()}
    except Exception:
        return False, list(EXPECTED_PLATFORMS), []

    for p in EXPECTED_PLATFORMS:
        r, name = rows.get(p), platform_name(p)
        if r is None:
            reasons.append(f'we have no record of a {name} refresh')
        elif r['ok'] is False:
            reasons.append(f'the last {name} refresh failed')
        elif r['ok'] is None:
            reasons.append(f'the last {name} refresh did not finish')
        else:
            ok_sources.append(p)

    fresh = con.execute(
        'select max(captured_at) > now() - make_interval(hours => %s) as fresh from source_post',
        (STALE_AFTER_HOURS,),
    ).fetchone()
    if fresh and fresh['fresh'] is False:
        reasons.append('nothing new has been collected in a while')

    return bool(reasons), ok_sources, reasons


def already_extracted(con, post_id, model):
    """True when this post was last extracted by this exact model.

    "Has no mentions" is not the same as "not extracted": a video-first post
    that genuinely names no venue is correctly empty, and 16 of the spike's
    first 50 were exactly that. Without the marker those posts are re-extracted
    on every run, forever.
    """
    row = con.execute('select extracted_with from source_post where id = %s', (post_id,)).fetchone()
    return bool(row and row['extracted_with'] == model)


def mark_extracted(con, post_id, model):
    con.execute(
        'update source_post set extracted_with = %s, extracted_at = now() where id = %s',
        (model, post_id),
    )
