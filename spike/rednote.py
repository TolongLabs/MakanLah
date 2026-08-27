"""RedNote (rednote.com) search and note capture over CDP.

rednote.com is the international host for the same content as xiaohongshu.com and
carries a separate session. The .com session was live when xiaohongshu.com's was
not, which is why the source adapter targets the host rather than the brand.

Collection is deliberately modest: one note at a time, a pause between fetches,
and everything cached to disk so a re-run costs no requests.
"""

import asyncio
import json
import re
import urllib.parse

from cdp import Session

BASE = 'https://www.rednote.com'
PAUSE = 2.5

SEARCH_JS = """JSON.stringify((() => {
  const seen = {};
  for (const a of document.querySelectorAll('a[href*="/search_result/"], a[href*="/explore/"]')) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/\\/(?:search_result|explore)\\/([0-9a-f]{8,})/);
    if (!m) continue;
    const tok = (href.match(/xsec_token=([^&]+)/) || [])[1] || '';
    if (!seen[m[1]] || (!seen[m[1]].token && tok)) {
      const card = a.closest('section, div.note-item') || a;
      seen[m[1]] = {
        note_id: m[1],
        token: tok,
        title: ((card.querySelector('.title') || {}).innerText || '').trim()
      };
    }
  }
  return Object.values(seen);
})())"""

NOTE_JS = """JSON.stringify((() => {
  const t = s => ((document.querySelector(s) || {}).innerText || '').trim();
  return {
    url: location.href,
    title: t('#detail-title') || t('.title'),
    desc: t('#detail-desc') || t('.desc'),
    author: t('.username') || t('.author-wrapper .name'),
    date: t('.date') || t('.bottom-container .date'),
    tags: [...document.querySelectorAll('#detail-desc a, a.tag')]
            .map(a => a.innerText.trim()).filter(x => x.startsWith('#')),
    likes: t('.like-wrapper .count') || t('.interact-container .count'),
    image_count: document.querySelectorAll('.swiper-slide img, img.note-slider-img').length,
    body_len: document.body.innerText.length
  };
})())"""


async def search(page, keyword, settle=11.0):
    url = f'{BASE}/search_result?keyword={urllib.parse.quote(keyword)}'
    await page.goto(url, settle=settle)
    raw = await page.js(SEARCH_JS)
    hits = json.loads(raw) if raw else []
    return [h for h in hits if h.get('note_id')]


async def fetch_note(page, note_id, token, settle=9.0):
    q = f'?xsec_token={token}&xsec_source=pc_search' if token else ''
    await page.goto(f'{BASE}/explore/{note_id}{q}', settle=settle)
    raw = await page.js(NOTE_JS)
    if not raw:
        return None
    d = json.loads(raw)
    # A note that rendered nothing is a failed fetch, not an empty note.
    if not (d.get('title') or d.get('desc')):
        return None
    d['note_id'] = note_id
    return d


async def collect(keywords, limit, on_note=None, tab_every=8, skip=()):
    """Search each keyword, then fetch note bodies until `limit` distinct notes.

    The tab is recycled every `tab_every` notes. A long-lived RedNote tab
    accumulates service workers and detached execution contexts, and the failure
    mode is a navigate that never returns rather than an error.
    """
    found = {}
    notes = []

    async with Session() as page:
        for kw in keywords:
            if len(found) >= limit * 3:
                break
            try:
                for h in await search(page, kw):
                    found.setdefault(h['note_id'], h)
            except Exception as e:
                print(f'  search failed {kw!r}: {str(e)[:100]}')
            print(f'  search {kw!r}: {len(found)} distinct notes so far', flush=True)
            await asyncio.sleep(PAUSE)

    # Already-cached notes must not be re-fetched. Without this a rerun spends its
    # whole budget re-reading what it already has and the cache never grows.
    seen = set(skip)
    todo = [h for h in found.values() if h.get('token') and h['note_id'] not in seen]
    print(f'  {len(found)} found, {len(seen)} already cached, {len(todo)} to fetch', flush=True)

    i = 0
    while i < len(todo) and len(notes) < limit:
        batch = todo[i : i + tab_every]
        i += tab_every
        try:
            async with Session() as page:
                for h in batch:
                    if len(notes) >= limit:
                        break
                    try:
                        # Bound the whole note, not just each CDP call: a page can
                        # answer every call slowly and still never finish.
                        d = await asyncio.wait_for(fetch_note(page, h['note_id'], h.get('token', '')), timeout=60.0)
                    except TimeoutError:
                        print(f'  timeout {h["note_id"]}', flush=True)
                        d = None
                    except Exception as e:
                        print(f'  failed {h["note_id"]}: {str(e)[:90]}', flush=True)
                        d = None
                    if d:
                        notes.append(d)
                        if on_note:
                            on_note(d)
                        print(f'  [{len(notes)}/{limit}] {h["note_id"]}', flush=True)
                    else:
                        print(f'  empty {h["note_id"]}', flush=True)
                    await asyncio.sleep(PAUSE)
        except Exception as e:
            print(f'  tab batch failed: {str(e)[:100]}', flush=True)

    return notes


def strip_tokens(text):
    """xsec_token is a live request credential. It never reaches a committed file."""
    return re.sub(r'xsec_token=[^&\s"\']+', 'xsec_token=<redacted>', text or '')
