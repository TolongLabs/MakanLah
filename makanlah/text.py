"""Text normalization shared by ingestion and ranking.

Lives here rather than in ingest/ because both runtimes need it and they share
nothing else: api/ must never import from ingest/, which carries the browser
session and the scrapers.
"""

import re
import unicodedata

from opencc import OpenCC

CJK = re.compile(r'[一-鿿]')
MS = re.compile(r'\b(nasi|makan|sedap|kedai|restoran|jalan|murah|enak|ayam|ikan|daun)\b', re.I)
EN = re.compile(r'\b(the|and|food|restaurant|best|good|really|place|try|with)\b', re.I)

# Latin generics need a word boundary; CJK ones must not have one. \b sits between
# a word and a non-word character, and every CJK glyph is a word character, so
# \b(酒家)\b never matches inside 适苑酒家 -- which silently split one restaurant
# into two venue rows.
LATIN_GENERIC = re.compile(r'\b(restoran|restaurant|kedai|cafe|café|coffee shop|kopitiam)\b', re.I)
# Malaysian-Chinese restaurant suffixes. 茶餐室 and 冰室 were missing, so 华阳 and
# 华阳冰室 stayed two venues for one kopitiam. Longest alternatives come first:
# 茶餐室 must match before 餐室, or the leading 茶 survives and the key differs.
#
# Dish names are deliberately NOT stripped. 兴记 and 兴记肉骨茶 may well be one
# place, but 肉骨茶 is a dish, and stripping dishes from names would collapse
# genuinely different businesses that happen to share a speciality.
CJK_GENERIC = re.compile(
    r'(茶餐厅|茶餐廳|茶餐室|大排档|大排檔|小食店|快餐店|餐厅|餐廳|餐室|冰室|茶室|酒家|酒楼|酒樓|飯店|饭店|美食|小吃|餐馆|餐館)'
)

# Districts and malls are not venues. The extractor is told to skip them; this is
# the belt to that braces, because one bad row poisons a whole area's ranking.
NOT_A_VENUE = {
    # Pronouns and deictics. A post says 他们家 ("their place") meaning a venue it
    # named earlier, and the extractor takes the phrase as the name. Found in the
    # corpus as a real venue row with one mention behind it.
    '他们家',
    '他們家',
    '这家',
    '這家',
    '那家',
    '这间',
    '那间',
    '这里',
    '那里',
    'this place',
    'that place',
    # Districts and malls.
    'kuala lumpur',
    'kl',
    'malaysia',
    'selangor',
    'petaling jaya',
    'pj',
    'bukit bintang',
    'bangsar',
    'cheras',
    'subang jaya',
    'mont kiara',
    'damansara',
    'klang valley',
    'pavilion',
    'mid valley',
    'klcc',
    'trx',
    'sunway pyramid',
}


def detect_langs(text):
    """Plural by design. A single-language column would erase the code-switching
    that is the whole point of this corpus."""
    langs = []
    if CJK.search(text or ''):
        langs.append('zh')
    if MS.search(text or ''):
        langs.append('ms')
    if EN.search(text or ''):
        langs.append('en')
    return langs or ['und']


def normalize(name):
    """The join key for venue dedup. Case-folded, generics stripped, punctuation gone."""
    s = unicodedata.normalize('NFKC', name or '').casefold()
    s = LATIN_GENERIC.sub(' ', s)
    s = CJK_GENERIC.sub(' ', s)
    s = re.sub(r'[^\w一-鿿]+', ' ', s)
    return ' '.join(s.split())


_T2S = OpenCC('t2s')


def fold_variants(name):
    """A join key that ignores simplified/traditional CJK variants.

    The same shop may be written 興记 or 兴记; a row may also carry an English
    gloss after the Chinese name. When CJK is present, the Latin text is the
    gloss and is dropped so the variants still collide. Latin-only names pass
    through unchanged.
    """
    s = normalize(name)
    if not s:
        return ''
    s = _T2S.convert(s)
    if CJK.search(s):
        s = re.sub(r'[^一-鿿]+', ' ', s)
        s = ' '.join(s.split())
    return s
