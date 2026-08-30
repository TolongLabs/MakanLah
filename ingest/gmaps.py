"""Google Maps as the second source, over CDP. No API key, no billing.

Two jobs, and the second is why this exists at all:

  1. Resolve a venue to coordinates. Nominatim managed 33% on this corpus
     because OpenStreetMap does not carry Chinese-only restaurant names for KL.
     A Maps place URL embeds them as !3d<lat>!4d<lng>.
  2. Carry reviews as source_posts, so RedNote is not load-bearing.

The second is an architectural commitment, not an optimisation: AGENTS.md says
no single source may be load-bearing, for uptime rather than legal cover. With
one source the app goes dark when that source does.

Collection is modest and cached: one venue at a time, a pause between, and
nothing re-fetched that the corpus already has.
"""

import asyncio
import json
import re
import urllib.parse

from ingest.cdp import Session

PAUSE = 2.0

# The place URL carries coordinates inline: .../data=!4m7!3m6!1s0x...!8m2!3d3.1468!4d101.7125
COORDS = re.compile(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)')
PLACE_ID = re.compile(r'!1s(0x[0-9a-f]+:0x[0-9a-f]+)')

PLACE_JS = """JSON.stringify((() => {
  const a = document.querySelector('a[href*="/maps/place/"]');
  const h1 = document.querySelector('h1');
  const addr = [...document.querySelectorAll('button[data-item-id="address"]')]
                 .map(b => b.getAttribute('aria-label') || '')[0] || '';
  return {
    href: a ? a.getAttribute('href') : '',
    url: location.href,
    name: h1 ? h1.innerText.trim() : '',
    address: addr.replace(/^Address:\\s*/, '')
  };
})())"""

# Google Maps collapses a long review and appends its own "… More" control.
# Reading innerText without clicking that captures the platform's chrome AND
# loses the rest of the review: 1008 of 1388 captured posts were truncated this
# way, and the marker reached users inside a verbatim citation.
EXPAND_JS = """(() => {
  const buttons = [...document.querySelectorAll(
    'button[aria-label="See more"], button[jsaction*="review.expandReview"], .w8nwRe'
  )];
  buttons.forEach((b) => { try { b.click() } catch (e) {} });
  return buttons.length;
})()"""

REVIEWS_JS = """JSON.stringify((() => {
  const seen = {};
  for (const n of document.querySelectorAll('div[data-review-id]')) {
    const id = n.getAttribute('data-review-id');
    const body = n.querySelector('.MyEned, span[class*="wiI7pd"]');
    if (!id || !body) continue;
    // Defence in depth: strip the control's label if a click did not land.
    const txt = (body.innerText || '').replace(/(?:\s*(?:…|\.\.\.)\s*|\s+)More\s*$/, '').trim();
    if (txt.length < 25) continue;
    const stars = n.querySelector('span[role="img"][aria-label*="star"]');
    seen[id] = {
      review_id: id,
      text: txt,
      stars: stars ? (stars.getAttribute('aria-label') || '') : '',
      when: (n.querySelector('span[class*="rsqaWe"]') || {}).innerText || ''
    };
  }
  return Object.values(seen);
})())"""


def _coords_from(href):
    m = COORDS.search(href or '')
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def _place_id_from(href):
    m = PLACE_ID.search(href or '')
    return m.group(1) if m else None


# The results feed of a Maps search. `resolve` reads querySelector -- the FIRST
# result -- because it exists to turn a known name into a place. Discovery needs
# the whole list, which is the difference between enriching a venue and finding one.
LIST_JS = """JSON.stringify([...document.querySelectorAll('a[href*="/maps/place/"]')]
  .map(a => ({
    href: a.getAttribute('href') || '',
    name: (a.getAttribute('aria-label') || '').trim()
  }))
  .filter(x => x.name && x.href))"""

# Maps renders about seven results and loads the rest only as the feed scrolls.
# Measured on 'nasi lemak Bangsar': 7 anchors on arrival, 47 after six scrolls and
# still climbing. Reading the feed without this collects a seventh of the page.
SCROLL_JS = """(() => {
  const f = document.querySelector('div[role="feed"]');
  if (!f) return 0;
  f.scrollTop = f.scrollHeight;
  return document.querySelectorAll('a[href*="/maps/place/"]').length;
})()"""

# Klang Valley. Same bound resolve() applies, for the same reason: a hit outside
# it matched the wrong place, and a wrong coordinate is worse than a null one.
KLANG_VALLEY = (2.6, 3.6, 101.2, 102.1)


def parse_feed(items, limit=60):
    """Anchor dicts from LIST_JS -> [{name, place_id, lat, lng}], deduped.

    Kept separate from the navigation so the discard rules are testable without a
    browser. Every rule here throws a row away, and each one is a row that would
    otherwise enter the corpus as a venue nobody can verify.
    """
    out, seen = [], set()
    for d in items or []:
        if not isinstance(d, dict):
            continue
        name = (d.get('name') or '').strip()
        href = d.get('href') or ''
        if not name:
            continue
        lat, lng = _coords_from(href)
        place_id = _place_id_from(href)
        if lat is None or not place_id or place_id in seen:
            continue
        lo_lat, hi_lat, lo_lng, hi_lng = KLANG_VALLEY
        if not (lo_lat <= lat <= hi_lat and lo_lng <= lng <= hi_lng):
            continue
        seen.add(place_id)
        out.append({'name': name, 'place_id': place_id, 'lat': lat, 'lng': lng})
        if len(out) >= limit:
            break
    return out


async def discover(page, query, limit=60, scrolls=8):
    """Search Maps and return every place the results feed will give up.

    The only path by which a venue can enter the corpus without a RedNote post
    naming it first (#157). Returns [] rather than raising when the feed is not
    there -- a query with no results is a normal outcome, not an error.
    """
    await page.goto(f'https://www.google.com/maps/search/{urllib.parse.quote(query)}/?hl=en', settle=9)
    seen_count = 0
    for _ in range(scrolls):
        n = await page.js(SCROLL_JS)
        try:
            n = int(n)
        except (TypeError, ValueError):
            break
        if n <= seen_count:
            break
        seen_count = n
        if n >= limit:
            break
        await asyncio.sleep(2.5)
    raw = await page.js(LIST_JS)
    if not raw:
        return []
    return parse_feed(json.loads(raw), limit=limit)


async def resolve(page, name, area=None, city='Kuala Lumpur'):
    """Name -> (lat, lng, address, place_id, resolved_name) or None.

    A search that lands on a place page gives coordinates in location.href; one
    that lands on a result list gives them in the first result's link.
    """
    q = ' '.join(x for x in [name, area, city, 'Malaysia'] if x)
    await page.goto(f'https://www.google.com/maps/search/{urllib.parse.quote(q)}/?hl=en', settle=9)
    raw = await page.js(PLACE_JS)
    if not raw:
        return None
    import json as _json

    d = _json.loads(raw)
    lat, lng = _coords_from(d.get('url'))
    if lat is None:
        lat, lng = _coords_from(d.get('href'))
    if lat is None:
        return None
    # Klang Valley. A hit outside it matched the wrong place entirely, and a
    # wrong coordinate is worse than a null one.
    if not (2.6 <= lat <= 3.6 and 101.2 <= lng <= 102.1):
        return None
    place_id = _place_id_from(d.get('url')) or _place_id_from(d.get('href'))
    return lat, lng, d.get('address') or None, place_id, d.get('name') or name


async def reviews(page, limit=8):
    """Read reviews from the place page already open. Returns [] if the tab is
    not on one, which is a normal outcome, not an error."""
    opened = await page.js("""(() => {
      const b = [...document.querySelectorAll('button[role="tab"]')]
        .find(x => /^Reviews/i.test(x.getAttribute('aria-label') || ''));
      if (!b) return false;
      b.click();
      return true;
    })()""")
    if not opened:
        return []
    await asyncio.sleep(6)
    for _ in range(2):
        await page.js("""(() => {
          const d = [...document.querySelectorAll('div')]
            .filter(e => e.scrollHeight > e.clientHeight + 200 && e.clientHeight > 300);
          if (d.length) d[d.length - 1].scrollTop = d[d.length - 1].scrollHeight;
        })()""")
        await asyncio.sleep(3)
    # Expand every collapsed review BEFORE reading, then let the DOM settle.
    # Without this the capture keeps Google's own "… More" control and loses
    # everything after it.
    await page.js(EXPAND_JS)
    await asyncio.sleep(2)

    raw = await page.js(REVIEWS_JS)
    if not raw:
        return []
    import json as _json

    return _json.loads(raw)[:limit]


async def enrich(venues, want_reviews=True, tab_every=6, on_record=None):
    """venues: [{'id', 'name', 'area'}] -> [{'id', 'coords', 'reviews'}].

    The tab is recycled: a long-lived Maps tab accumulates state and starts
    answering navigations that never complete.

    `on_record` is called as each venue resolves, so the caller can persist
    incrementally. Without it a crash at venue 90 of 93 throws away half an hour
    of scraping, which is the expensive thing here.
    """
    out = []
    for i in range(0, len(venues), tab_every):
        batch = venues[i : i + tab_every]
        try:
            async with Session() as page:
                for v in batch:
                    rec = {'id': v['id'], 'name': v['name'], 'coords': None, 'reviews': []}
                    try:
                        rec['coords'] = await asyncio.wait_for(resolve(page, v['name'], v.get('area')), timeout=70)
                        if rec['coords'] and want_reviews:
                            rec['reviews'] = await asyncio.wait_for(reviews(page), timeout=70)
                    except TimeoutError:
                        print(f'  timeout {v["name"]!r}', flush=True)
                    except Exception as e:
                        print(f'  failed {v["name"]!r}: {str(e)[:80]}', flush=True)
                    out.append(rec)
                    if on_record:
                        try:
                            on_record(rec)
                        except Exception as e:
                            print(f'  persist failed {v["name"]!r}: {str(e)[:80]}', flush=True)
                    hit = 'ok' if rec['coords'] else 'miss'
                    print(
                        f'  [{len(out)}/{len(venues)}] {v["name"][:28]!r} {hit} {len(rec["reviews"])} review(s)',
                        flush=True,
                    )
                    await asyncio.sleep(PAUSE)
        except Exception as e:
            print(f'  tab batch failed: {str(e)[:90]}', flush=True)
    return out
