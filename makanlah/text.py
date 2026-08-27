"""Text normalization shared by ingestion and ranking.

Lives here rather than in ingest/ because both runtimes need it and they share
nothing else: api/ must never import from ingest/, which carries the browser
session and the scrapers.
"""

import re
import unicodedata

CJK = re.compile(r'[一-鿿]')
MS = re.compile(r'\b(nasi|makan|sedap|kedai|restoran|jalan|murah|enak|ayam|ikan|daun)\b', re.I)
EN = re.compile(r'\b(the|and|food|restaurant|best|good|really|place|try|with)\b', re.I)

# Latin generics need a word boundary; CJK ones must not have one. \b sits between
# a word and a non-word character, and every CJK glyph is a word character, so
# \b(酒家)\b never matches inside 适苑酒家 -- which silently split one restaurant
# into two venue rows.
LATIN_GENERIC = re.compile(r'\b(restoran|restaurant|kedai|cafe|café|coffee shop|kopitiam)\b', re.I)
CJK_GENERIC = re.compile(r'(餐厅|餐廳|酒家|茶室|茶餐厅|美食|小吃|餐馆|餐館)')

# Districts and malls are not venues. The extractor is told to skip them; this is
# the belt to that braces, because one bad row poisons a whole area's ranking.
NOT_A_VENUE = {
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
