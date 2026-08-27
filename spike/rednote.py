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


async def collect(keywords, limit, on_note=None):
    """Search each keyword, then fetch note bodies until `limit` distinct notes."""
    found, notes = {}, []
    async with Session() as page:
        for kw in keywords:
            if len(found) >= limit * 2:
                break
            try:
                for h in await search(page, kw):
                    found.setdefault(h['note_id'], h)
            except Exception as e:
                print(f'  search failed: {kw}: {e}')
            print(f'  search {kw!r}: {len(found)} distinct notes so far')
            await asyncio.sleep(PAUSE)

        for h in list(found.values()):
            if len(notes) >= limit:
                break
            try:
                d = await fetch_note(page, h['note_id'], h.get('token', ''))
            except Exception as e:
                print(f'  fetch failed {h["note_id"]}: {e}')
                d = None
            if d:
                notes.append(d)
                if on_note:
                    on_note(d)
            else:
                print(f'  empty {h["note_id"]}')
            await asyncio.sleep(PAUSE)
    return notes


def strip_tokens(text):
    """xsec_token is a live request credential. It never reaches a committed file."""
    return re.sub(r'xsec_token=[^&\s"\']+', 'xsec_token=<redacted>', text or '')
