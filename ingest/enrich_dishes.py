"""Pull dish names out of Google Maps reviews for venues that have none.

43% of venues carried no dish at all, because a RedNote listicle often gives a
verdict without naming a dish ("老字号小店，饭点必排"). A venue with no dishes has
none in its embedding document, so it is retrievable by name and area but not by
what it serves, and "what do I feel like eating" is a dish-shaped question.

Reviews name dishes constantly. Extraction is per review rather than per venue,
batched into one call, so a dish stays attached to the mention whose excerpt
actually contains it. Writing a venue-level dish list onto an arbitrary mention
would be cheaper and would decouple the dish from its evidence.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import config, db, models

BATCH = 6

SYSTEM = """You list dishes named in restaurant reviews.

Reviews mix English, Malay and Chinese, often inside one sentence. Handle all
three identically, and never translate: record the dish as the writer wrote it.

You receive numbered reviews. Return ONLY a json object:
  {"reviews": [{"index": <number>, "dishes": ["...", "..."]}]}

Rules:
- A dish is something you order and eat. "nasi lemak", "肉骨茶", "kaya toast".
- NOT a dish: cuisine types ("Chinese food"), meals ("breakfast"), drinks unless
  the venue is known for them, adjectives, or the restaurant's own name.
- A review naming no dish gets an empty list. Empty is correct and is far better
  than a guess; most reviews are about service or queues.
- Return an entry for every index you were given."""


def pending(con, limit=None):
    """Maps mentions belonging to venues that currently have no dish anywhere."""
    sql = """
      select m.id, m.excerpt
      from mention m
      join source_post p on p.id = m.post_id
      join venue v on v.id = m.venue_id
      where p.platform = 'google_maps'
        and m.excerpt is not null
        and m.dishes = '{}'
        and not exists (select 1 from mention d where d.venue_id = v.id and d.dishes <> '{}')
      order by m.confidence desc nulls last
    """
    if limit:
        sql += f' limit {int(limit)}'
    return con.execute(sql).fetchall()


def extract_batch(rows):
    body = '\n\n'.join(f'[{i}] {r["excerpt"][:700]}' for i, r in enumerate(rows))
    s = config.settings()
    payload = {
        'model': s.extract_model,
        'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': body}],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    got = models._json_object(
        models._content(models._post(f'{s.extract_base_url}/chat/completions', payload, s.extract_api_key))
    )
    out = {}
    for r in got.get('reviews', []):
        i = r.get('index')
        if isinstance(i, int) and 0 <= i < len(rows):
            # Case-insensitive dedupe, first spelling wins. The model repeats a
            # dish when the review does ("savoury pork ... so good ... pork").
            seen, dishes = set(), []
            for d in r.get('dishes') or []:
                if not isinstance(d, str) or not d.strip():
                    continue
                d = d.strip()
                if d.casefold() in seen:
                    continue
                seen.add(d.casefold())
                dishes.append(d)
            out[i] = dishes
    return out


def run(limit=None):
    stats = dict(mentions_seen=0, mentions_updated=0, dishes_written=0, embeddings_invalidated=0, batches_failed=0)
    with db.connect(direct=True) as con:
        rows = pending(con, limit)
        print(f'{len(rows)} maps mentions on venues with no dish', flush=True)
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            stats['mentions_seen'] += len(batch)
            try:
                found = extract_batch(batch)
            except Exception as e:
                stats['batches_failed'] += 1
                print(f'  batch {i // BATCH} failed: {str(e)[:90]}', flush=True)
                continue
            for idx, dishes in found.items():
                if not dishes:
                    continue
                con.execute('update mention set dishes = %s where id = %s', (dishes, batch[idx]['id']))
                # The venue's embedding document is built from its dishes, so the
                # stored vector now describes text that has changed. Drop it and
                # let the pipeline rebuild: venue_documents() only embeds venues
                # that have none, so a stale vector would otherwise survive
                # forever and rank the venue on what it used to say.
                con.execute(
                    """delete from venue_embedding
                       where venue_id = (select venue_id from mention where id = %s)""",
                    (batch[idx]['id'],),
                )
                stats['mentions_updated'] += 1
                stats['dishes_written'] += len(dishes)
                stats['embeddings_invalidated'] += 1
            con.commit()
            print(
                f'  [{min(i + BATCH, len(rows))}/{len(rows)}] '
                f'{stats["mentions_updated"]} updated, {stats["dishes_written"]} dishes',
                flush=True,
            )
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=None)
    a = ap.parse_args()
    print(json.dumps(run(a.limit), indent=2))
    print('re-run `python ingest/pipeline.py --skip-geocode` to rebuild embeddings')


if __name__ == '__main__':
    main()
