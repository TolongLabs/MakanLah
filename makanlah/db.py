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


def venue_dishes(con, venue_ids):
    """{venue_id: [dish, ...]} for a candidate set.

    Canonicalisation stays in makanlah/dishes.py rather than being rewritten as
    SQL. Two implementations of "is this the same dish" would drift, and the
    eval ground truth depends on the answer matching exactly.
    """
    if not venue_ids:
        return {}
    rows = con.execute(
        """select m.venue_id, array_agg(distinct d) as dishes
           from mention m, unnest(m.dishes) d
           where m.venue_id = any(%s) group by m.venue_id""",
        (list(venue_ids),),
    ).fetchall()
    return {r['venue_id']: r['dishes'] for r in rows}


# Which excerpt leads, and why not confidence.
#
# Confidence measures how easy the text was to extract, which is close to the
# opposite of whether it is worth reading. Measured on this corpus: the >=0.95 band
# averages 75 characters against 180 for the band below it, and is nearly twice as
# likely to carry no opinion at all. A postal address is trivially extractable, so
# it wins every time -- 82 of 243 venues led with one.
#
# So rank on what the excerpt says. First, does it argue anything: an opinion with
# enough text to be a sentence. Then, is it representative -- closest to what this
# venue's own mentions average, so the lead is neither the angriest review nor the
# most flattering one. Ties break on id so the same query returns the same excerpt
# twice running.
EXCERPT_ORDER = """
  (m.sentiment <> 0 and length(m.excerpt) >= 60) desc,
  abs(m.sentiment - avg(m.sentiment) over (partition by m.venue_id)) asc,
  m.id
"""


def venue_evidence(con, venue_id, limit=40):
    """Everything the corpus actually says about one venue.

    The copilot answers from these rows and nothing else. Ordered by confidence
    so the strongest evidence survives a truncation rather than whatever the
    planner happened to return first.
    """
    rows = con.execute(
        """select m.excerpt, m.dishes, m.sentiment, m.confidence,
                  p.id as post_id, p.url as post_url, p.platform, p.author_handle, p.posted_at_raw,
                  case when p.dead_at is not null then true else null end as dead
           from mention m join source_post p on p.id = m.post_id
           where m.venue_id = %s and m.excerpt is not null
           order by """
        + EXCERPT_ORDER
        + """
           limit %s""",
        (venue_id, limit),
    ).fetchall()
    return rows


def venue_by_id(con, venue_id):
    return con.execute(
        'select id, name, area, city, lat, lng, place_id from venue where id = %s', (venue_id,)
    ).fetchone()


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
                  p.id as post_id, p.url as post_url, p.platform, p.author_handle, p.posted_at_raw,
                  case when p.dead_at is not null then true else null end as dead
           from venue v
           join mention m on m.venue_id = v.id
           join source_post p on p.id = m.post_id
           where v.id = any(%s)
           order by v.id, """
        + EXCERPT_ORDER
        + """""",
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
                'sentiment': {'positive': 0, 'mixed': 0, 'negative': 0},
            },
        )
        for d in r['dishes'] or []:
            if d not in v['dishes']:
                v['dishes'].append(d)
        pool.setdefault(r['venue_id'], []).append(
            {
                # Identity and address are different things, and the client needs both.
                # Google Maps has no per-review URL, so review_url() returns the venue
                # page and three reviewers share one address. Deduping on post_url
                # collapsed them into one citation and denied the corroboration stamp
                # to venues that had genuinely earned it (#153).
                'post_id': str(r['post_id']),
                'post_url': r['post_url'],
                'excerpt': r['excerpt'],
                'platform': r['platform'],
                'author_handle': r['author_handle'],
                'posted_at': r['posted_at_raw'],
                'dead': r['dead'],
            }
        )

    kept = {}
    for venue_id, cites in pool.items():
        shown = diverse_citations(cites, per_venue)
        out[venue_id]['citations'] = shown
        kept[venue_id] = {c['post_id'] for c in shown if not c.get('dead')}
    for venue_id, counts in tally_sentiment(rows, kept).items():
        out[venue_id]['sentiment'] = counts
    return out


def tally_sentiment(rows, kept=None):
    """Bucket counts per venue, one vote per POST, over posts the card can show.

    Three separate things had to be true before this number meant anything, and the
    first two were fixed a commit apart:

    - One vote per post. Counting mention rows made a card read "1 post" and "All 9
      posts positive" at once.
    - No dead posts. Counting them repeats #111 -- a breakdown that cannot be traced
      to an openable post is the unverifiable assertion this product exists not to
      make.
    - The same posts corroboration counts. `citations` is trimmed to per_venue before
      it ships, and add_corroboration counts what survives that trim. Tallying every
      live post in the corpus instead gave Village Park 7 sentiment against 3 posts:
      four of those seven were real, and none of them were on the card. `kept` is the
      set of post_urls that survived, so every counted post is one a reader can open.

    Several mentions behind one identity are averaged, not reduced to the worst.
    That rule was written for one author's own disagreeing sentences and it is wrong
    here, because `post_url` is not one author: Google Maps has no per-review URL, so
    `review_url()` returns the venue's page and all 1,388 Maps mentions share just 178
    URLs -- about eight reviews each. Taking the worst turned one 1-star review into a
    verdict on all eight (#149). 王美记 read "2 of 2 posts critical" with a mean of
    +0.19 and no complaint in any excerpt shown.
    """
    by_venue = {}
    for r in rows:
        if r['dead']:
            continue
        if kept is not None and str(r['post_id']) not in kept.get(r['venue_id'], ()):
            continue
        if r['sentiment'] is None:
            continue
        by_venue.setdefault(r['venue_id'], {}).setdefault(str(r['post_id']), []).append(float(r['sentiment']))
    out = {}
    for venue_id, by_post in by_venue.items():
        counts = {'positive': 0, 'mixed': 0, 'negative': 0}
        for scores in by_post.values():
            counts[sentiment_bucket(sum(scores) / len(scores))] += 1
        out[venue_id] = counts
    return out


def sentiment_bucket(score):
    """Three buckets, on the star scale that produces most of these scores.

    star_sentiment is (stars - 3) / 2, so the cut points are stars: 4 and 5 are
    positive, 3 is mixed, 1 and 2 are critical. Naming a 4-star review "mixed" to
    manufacture spread would be inventing a reservation the reviewer did not have.

    The negative cut is -0.4 rather than -0.5, and the two platforms decide it
    separately. Maps scores are quantised to {-1, -0.5, 0, 0.5, 1}, so any cut in
    (-0.5, 0) treats Maps identically -- 1-2 stars critical, 3 mixed. RedNote is
    scored continuously by the extraction model and is the only thing the exact
    value moves.

    -0.4 is where its negative population actually separates, read by hand across
    all 14 negative RedNote mentions: at -0.4 and below sit 避雷 (avoid), 别去
    (don't go) and 强烈不推荐; at -0.3 and above sit 可吃可不吃 (take it or leave
    it) and 确实好吃，但要排40分钟. -0.5 filed 王美记's "不推荐" twice and "性价比
    很低" as mixed (#155); -0.2 filed a queue complaint as critical (#149).
    """
    if score is None:
        return None
    s = float(score)
    if s >= 0.5:
        return 'positive'
    if s <= -0.4:
        return 'negative'
    return 'mixed'


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


# --- Accounts, sessions and preferences (docs/TRD.md "API Contract") ----------
#
# Auth persists preferences; it never gates /recommend. Nothing below returns a
# password hash or a raw token to a caller.

SESSION_DAYS = 30
GUEST_SESSION_HOURS = 12  # the guest credential is effectively public, so it expires fast


def create_user(con, *, email, password_hash):
    """None when the address is already taken, rather than raising: a duplicate
    signup is an expected outcome of a public form, not an exceptional one."""
    row = con.execute(
        """insert into app_user (email, password_hash, is_guest) values (%s, %s, false)
           on conflict (email) do nothing
           returning id, email, is_guest, created_at""",
        (email.strip().lower(), password_hash),
    ).fetchone()
    return row


def user_by_email(con, email):
    return con.execute(
        'select id, email, password_hash, is_guest from app_user where email = %s',
        (email.strip().lower(),),
    ).fetchone()


def guest_user(con):
    return con.execute('select id, email, is_guest from app_user where is_guest limit 1').fetchone()


def open_session(con, user_id, *, hours):
    """Stores only the fingerprint. The caller holds the single copy of the token."""
    from makanlah import auth

    token = auth.new_token()
    con.execute(
        """insert into user_session (user_id, token_hash, expires_at)
           values (%s, %s, now() + make_interval(hours => %s))""",
        (user_id, auth.token_fingerprint(token), hours),
    )
    return token


def user_for_token(con, token):
    """None for absent, unknown or expired. The caller cannot tell which, deliberately."""
    from makanlah import auth

    if not token:
        return None
    return con.execute(
        """select u.id, u.email, u.is_guest
           from user_session s join app_user u on u.id = s.user_id
           where s.token_hash = %s and s.expires_at > now()""",
        (auth.token_fingerprint(token),),
    ).fetchone()


def close_session(con, token):
    from makanlah import auth

    con.execute('delete from user_session where token_hash = %s', (auth.token_fingerprint(token),))


def purge_expired_sessions(con):
    return con.execute('delete from user_session where expires_at <= now()').rowcount


def get_prefs(con, user_id):
    row = con.execute('select prefs from user_pref where user_id = %s', (user_id,)).fetchone()
    return (row or {}).get('prefs') or {}


def set_prefs(con, user_id, prefs):
    row = con.execute(
        """insert into user_pref (user_id, prefs, updated_at) values (%s, %s, now())
           on conflict (user_id) do update set prefs = excluded.prefs, updated_at = now()
           returning prefs""",
        (user_id, json.dumps(prefs)),
    ).fetchone()
    return row['prefs']


def popular_dishes(con, limit=24):
    """The dishes the corpus actually has the most posts about.

    The suggestion chips on /discover are built from this and nothing else, so a
    chip can never lead to an empty result page: every string offered is a dish
    somebody wrote about, ordered by how many people did.

    Canonicalisation already happened at extraction time (makanlah/dishes.py), so
    this counts what is stored rather than trying to fold variants here.
    """
    rows = con.execute(
        """select d as dish, count(distinct m.post_id) as posts, count(distinct m.venue_id) as venues
             from mention m, unnest(m.dishes) d
            where length(trim(d)) > 1
            group by d
           having count(distinct m.post_id) >= 2
            order by posts desc, venues desc
            limit %s""",
        (limit,),
    ).fetchall()
    return [{'dish': r['dish'], 'posts': r['posts'], 'venues': r['venues']} for r in rows]
