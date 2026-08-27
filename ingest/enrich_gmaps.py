"""Fill coordinates from Google Maps, and take its reviews as a second source.

Two reasons, and the second is the architectural one:

  1. Nominatim resolved 34% of this corpus. OpenStreetMap does not carry
     Chinese-only restaurant names for KL, and those are most of the misses.
  2. **RedNote must not be load-bearing.** AGENTS.md makes that a commitment
     rather than a preference: any one platform can go dark mid-sprint, and a
     data layer with a single point of failure goes dark with it.

Maps reviews get their sentiment from the star rating rather than from a model.
The rating IS the writer's judgement, stated numerically, so asking a model to
infer it from prose would be less accurate and cost a call per review.
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import cdp, gmaps
from makanlah import db

STARS = re.compile(r'([1-5])\s*star')


def star_sentiment(label):
    """1..5 stars -> -1..1. None when the label did not carry a rating."""
    m = STARS.search(label or '')
    if not m:
        return None
    return round((int(m.group(1)) - 3) / 2, 2)


def pending_venues(con, limit=None, only_missing_coords=True):
    sql = """select id, name, area from venue
             where exists (select 1 from mention m where m.venue_id = venue.id)"""
    if only_missing_coords:
        sql += ' and lat is null'
    sql += ' order by (select count(*) from mention m where m.venue_id = venue.id) desc'
    if limit:
        sql += f' limit {int(limit)}'
    return [dict(r) for r in con.execute(sql).fetchall()]


def apply(con, records):
    stats = dict(coords=0, no_coords=0, review_posts=0, review_mentions=0, skipped_short=0)
    run_id = db.start_run(con, 'google_maps')
    for rec in records:
        if rec['coords']:
            lat, lng, address, place_id, _ = rec['coords']
            con.execute(
                """update venue set lat=%s, lng=%s, address=coalesce(%s, address),
                       geocoder='google_maps', geocode_confidence=0.9, place_id=%s
                   where id=%s""",
                (lat, lng, address, place_id, rec['id']),
            )
            stats['coords'] += 1
        else:
            stats['no_coords'] += 1

        for rv in rec['reviews']:
            text = (rv.get('text') or '').strip()
            if len(text) < 25:
                stats['skipped_short'] += 1
                continue
            post_id = db.upsert_post(
                con,
                platform='google_maps',
                platform_post_id=rv['review_id'],
                url=f'https://www.google.com/maps/place/?q=place_id:{rec["id"]}',
                author_handle=None,
                posted_at_raw=rv.get('when') or None,
                langs=['und'],
                raw_text=text,
                media_urls=[],
                raw_payload={'stars': rv.get('stars'), 'venue_name': rec['name']},
            )
            stats['review_posts'] += 1
            # The excerpt is the review itself, so it is a substring by
            # construction and the verbatim trigger cannot fire.
            if db.upsert_mention(
                con,
                post_id=post_id,
                venue_id=rec['id'],
                dishes=[],
                sentiment=star_sentiment(rv.get('stars')),
                price_band=None,
                excerpt=text[:600],
                excerpt_origin='model',
                extractor_model='google_maps_stars',
                confidence=0.85,
            ):
                stats['review_mentions'] += 1
        con.commit()
    db.finish_run(
        con,
        run_id,
        ok=stats['coords'] > 0 or stats['review_posts'] > 0,
        posts_seen=len(records),
        posts_kept=stats['review_posts'],
        error=f'{stats["no_coords"]} venues unresolved' if stats['no_coords'] else None,
    )
    return stats


async def run(limit=None, want_reviews=True, only_missing_coords=True):
    if not cdp.alive():
        raise SystemExit('CDP is not up. Run: scripts/chrome-session.sh start')
    with db.connect(direct=True) as con:
        venues = pending_venues(con, limit, only_missing_coords)
    print(f'{len(venues)} venues to enrich', flush=True)
    if not venues:
        return {}
    records = await gmaps.enrich(venues, want_reviews=want_reviews)
    with db.connect(direct=True) as con:
        return apply(con, records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--no-reviews', action='store_true')
    ap.add_argument('--all-venues', action='store_true', help='not just the ones missing coordinates')
    a = ap.parse_args()
    stats = asyncio.run(run(a.limit, not a.no_reviews, not a.all_venues))
    print(stats)


if __name__ == '__main__':
    main()
