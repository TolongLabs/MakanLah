"""Give venues their evidence through the Places API instead of a browser.

Same job as `enrich_gmaps`, one HTTP call per venue instead of a driven tab.
Measured on the same venues: ~1s against ~25s, review text whole rather than cut
off at Google's "… More" (#15), and a `priceRange` in ringgit that the scraper
never had access to at all.

The citation invariant is unchanged and is the reason this is a swap and not a
rewrite: a review still becomes a `source_post` with its own id, the mention
still carries a verbatim excerpt, and a venue with no usable review text stays
unrecommendable rather than being returned with a caveat.

Dishes are tagged from the review text against the corpus's own vocabulary, so a
Maps-only venue is findable by what it serves -- the gap that made `roti canai`
return nothing city-wide.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import places_api
from ingest.enrich_gmaps import pending_venues
from makanlah import db
from makanlah.dishes import dishes_in_text
from makanlah.text import detect_langs

MIN_REVIEW_CHARS = 25


def apply_place(con, venue, place, vocab, stats):
    """Persist one venue's details. Returns the number of mentions written."""
    loc = place.get('location') or {}
    band = places_api.place_price_band(place)
    if loc.get('latitude') is not None:
        con.execute(
            """update venue set lat=%s, lng=%s, address=coalesce(%s, address),
                   geocoder='google_places', geocode_confidence=0.95,
                   place_id=%s
               where id=%s""",
            (loc['latitude'], loc['longitude'], place.get('formattedAddress'), place.get('id'), venue['id']),
        )
        stats['coords'] += 1

    written = 0
    for rv in place.get('reviews') or []:
        post = places_api.review_to_post(rv, place.get('id') or '', venue['name'])
        if not post or len(post['raw_text']) < MIN_REVIEW_CHARS:
            stats['skipped_short'] += 1
            continue
        post_id = db.upsert_post(
            con,
            platform='google_maps',
            platform_post_id=post['platform_post_id'],
            url=post['url'],
            author_handle=post['author_handle'],
            posted_at_raw=post['posted_at_raw'],
            # #133: the scraper hardcoded 'und' here and made 1,388 posts invisible
            # to language-aware retrieval.
            langs=detect_langs(post['raw_text']),
            raw_text=post['raw_text'],
            media_urls=[],
            raw_payload={'rating': rv.get('rating'), 'venue_name': venue['name'], 'source': 'places_api'},
        )
        stats['review_posts'] += 1
        if db.upsert_mention(
            con,
            post_id=post_id,
            venue_id=venue['id'],
            # The dish tags the scraper never wrote, so a Maps-only venue is
            # findable by what it serves rather than only by embedding.
            dishes=dishes_in_text(post['raw_text'], vocab),
            sentiment=post['sentiment'],
            price_band=band,
            excerpt=post['raw_text'][:600],
            excerpt_origin='model',
            extractor_model='places_api_stars',
            confidence=0.9,
        ):
            stats['review_mentions'] += 1
            written += 1
    if band is not None:
        stats['priced'] += 1
    return written


def run(limit=None, discovered_only=False, offset=0, pause=0.15, dry_run=False):
    key = places_api.api_key()
    with db.connect(direct=True) as con:
        venues = pending_venues(con, limit, True, offset, discovered_only=discovered_only)
        vocab = [d for d in db.dish_vocabulary(con) if d]
        print(f'{len(venues)} venues to enrich, {len(vocab)} dish terms in vocabulary', flush=True)
        if dry_run:
            print(f'DRY RUN: would cost {len(venues)} Place Details calls (Enterprise SKU)')
            return {}
        if not venues:
            return {}

        stats = dict(coords=0, review_posts=0, review_mentions=0, skipped_short=0, priced=0, no_place=0, calls=0)
        run_id = db.start_run(con, 'google_maps')
        for i, v in enumerate(venues, start=1):
            pid = v.get('place_id')
            if not places_api.is_api_place_id(pid):
                pid = None
            if not pid:
                found = places_api.search(f'{v["name"]} {v.get("area") or ""} Kuala Lumpur', key, pages=1)
                stats['calls'] += 1
                pid = found[0]['place_id'] if found else None
            if not pid:
                stats['no_place'] += 1
                print(f'  [{i}/{len(venues)}] {v["name"][:30]!r} no place', flush=True)
                continue
            place = places_api.details(pid, key)
            stats['calls'] += 1
            if not place:
                stats['no_place'] += 1
                continue
            n = apply_place(con, v, place, vocab, stats)
            con.commit()
            print(
                f'  [{i}/{len(venues)}] {v["name"][:28]!r} {n} review(s) price={places_api.place_price_band(place)}',
                flush=True,
            )
            time.sleep(pause)
        db.finish_run(
            con, run_id, ok=stats['review_posts'] > 0, posts_seen=len(venues), posts_kept=stats['review_posts']
        )
    return stats


def main():
    ap = argparse.ArgumentParser(description='Enrich venues via the Places API (#157/#158/#15)')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--discovered-only', action='store_true')
    ap.add_argument('--dry-run', action='store_true', help='report the call count without spending it')
    a = ap.parse_args()
    stats = run(a.limit, a.discovered_only, a.offset, dry_run=a.dry_run)
    print(stats)


if __name__ == '__main__':
    main()
