"""The three-language retrieval test from docs/TRD.md.

  "a held-out set of KL venues, queried in each of the three languages, checking
   whether the same venue is retrieved regardless of query language. A model that
   scores well in English and poorly in Malay has failed, not partly passed."

This is the test that decides the embedding row. It is here rather than in the
test suite because it costs API calls and measures a model, not our code.

Run: uv run python makanlah/research/embedding_language_test.py
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from makanlah import config

# Venue documents in the shape the corpus actually stores: name, aliases, dishes
# and excerpt text, in whatever script the writer used. Deliberately mixed — an
# all-English fixture set would not test the thing that fails.
VENUES = {
    'village_park': 'Village Park Restaurant. Damansara Uptown, Petaling Jaya. 椰浆饭天花板。'
    'nasi lemak ayam goreng, sambal, rendang. Queue is long but moves fast.',
    'hing_kee': '兴记肉骨茶 Hing Kee Bakuteh. Jalan Ipoh, Kuala Lumpur. 汤头浓郁，本地人回头率高。'
    'bak kut teh, herbal soup, yau char kwai.',
    'sek_yuen': '适苑酒家 Sek Yuen Restaurant. Pudu, Kuala Lumpur. 78年历史老牌粤餐馆，家庭聚餐友好。'
    'roast duck, kaus yuk, Cantonese banquet, charcoal stove.',
    'ho_kow': '何九海南茶店 Ho Kow Hainam Kopitiam. Jalan Balai Polis, Bukit Bintang. '
    '海南咖啡+早餐组合，老派茶室氛围。kaya toast, half boiled eggs, kopi O.',
    'ss15_satay': 'Sate Kajang Haji Samuri. SS15 Subang Jaya. Satay daging, satay ayam, kuah kacang. '
    '沙爹很嫩。Best eaten late at night with ketupat.',
    'chow_kit': 'Nasi Kandar Pelita Chow Kit. Jalan Tuanku Abdul Rahman. Nasi kandar, kari kepala ikan, '
    'ayam goreng berempah. 咖喱鱼头很够味。Open 24 hours.',
    'yut_kee': 'Yut Kee Restaurant 镒记. Jalan Kamunting, Chow Kit. Hainanese chicken chop, roti babi, '
    'marble cake. 海南鸡扒是招牌，老店气氛。',
    'kanna_curry': 'Kanna Curry House. Section 17, Petaling Jaya. Banana leaf rice, fish head curry, '
    'crab masala. Nasi daun pisang yang sedap. 香蕉叶饭。',
}

# Three queries per venue, one per language, each describing what the venue offers
# WITHOUT naming it. Naming it would test string matching, not retrieval.
QUERIES = {
    'village_park': {
        'en': 'famous nasi lemak with crispy fried chicken in Petaling Jaya',
        'ms': 'nasi lemak ayam goreng paling sedap di Damansara',
        'zh': '八打灵最好吃的椰浆饭配炸鸡',
    },
    'hing_kee': {
        'en': 'rich herbal pork rib soup for breakfast in KL',
        'ms': 'sup tulang babi herba yang pekat di Kuala Lumpur',
        'zh': '吉隆坡汤头浓郁的肉骨茶',
    },
    'sek_yuen': {
        'en': 'old Cantonese restaurant for a family banquet with roast duck',
        'ms': 'restoran Kantonis lama untuk jamuan keluarga dengan itik panggang',
        'zh': '适合家庭聚餐的老字号粤菜烧鸭',
    },
    'ho_kow': {
        'en': 'traditional kopitiam breakfast with kaya toast and soft boiled eggs',
        'ms': 'sarapan kopitiam tradisional roti bakar kaya dan telur separuh masak',
        'zh': '传统茶室早餐咖椰吐司和半熟蛋',
    },
    'ss15_satay': {
        'en': 'grilled skewers with peanut sauce late at night in Subang',
        'ms': 'satay bakar dengan kuah kacang waktu malam di Subang',
        'zh': '梳邦深夜沙爹配花生酱',
    },
    'chow_kit': {
        'en': 'twenty four hour indian muslim rice with fish head curry',
        'ms': 'nasi kandar 24 jam dengan kari kepala ikan',
        'zh': '二十四小时营业的印度咖喱鱼头饭',
    },
    'yut_kee': {
        'en': 'hainanese chicken chop at an old coffee shop',
        'ms': 'chicken chop Hainan di kedai kopi lama',
        'zh': '老店的海南鸡扒',
    },
    'kanna_curry': {
        'en': 'banana leaf rice with crab and fish head curry in PJ',
        'ms': 'nasi daun pisang dengan ketam dan kari kepala ikan di PJ',
        'zh': '八打灵的香蕉叶饭配螃蟹咖喱',
    },
}


# DashScope rejects a batch larger than 10 for text-embedding-v3 with a bare
# HTTP 400, so batching is a correctness concern, not a throughput one.
BATCH = 10


def embed(texts, s):
    out = []
    for i in range(0, len(texts), BATCH):
        chunk = texts[i : i + BATCH]
        req = urllib.request.Request(
            f'{s.embed_base_url}/embeddings',
            data=json.dumps({'model': s.embed_model, 'input': chunk, 'encoding_format': 'float'}).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {s.embed_api_key}'},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)['data']
        out.extend(d['embedding'] for d in sorted(data, key=lambda d: d['index']))
    return out


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def main():
    s = config.settings()
    if not s.embed_api_key:
        raise SystemExit('no embedding key configured')

    keys = list(VENUES)
    doc_vecs = dict(zip(keys, embed([VENUES[k] for k in keys], s), strict=True))

    langs = ('en', 'ms', 'zh')
    flat = [(k, lang) for k in keys for lang in langs]
    q_vecs = dict(zip(flat, embed([QUERIES[k][lang] for k, lang in flat], s), strict=True))

    per_lang = dict.fromkeys(langs, 0)
    misses = []
    for k, lang in flat:
        ranked = sorted(keys, key=lambda c: -cosine(q_vecs[(k, lang)], doc_vecs[c]))
        if ranked[0] == k:
            per_lang[lang] += 1
        else:
            misses.append((lang, k, ranked[0]))

    n = len(keys)
    print(f'model: {s.embed_model}  dim: {len(next(iter(doc_vecs.values())))}  venues: {n}\n')
    for lang in langs:
        print(f'  {lang}  top-1 {per_lang[lang]}/{n}  ({100 * per_lang[lang] / n:.0f}%)')

    # Cross-language agreement: does the SAME venue come back regardless of the
    # language the question was asked in? This is the property the product needs.
    agree = sum(
        1
        for k in keys
        if len({sorted(keys, key=lambda c: -cosine(q_vecs[(k, lang)], doc_vecs[c]))[0] for lang in langs}) == 1
    )
    print(f'\n  same venue retrieved in all three languages: {agree}/{n} ({100 * agree / n:.0f}%)')

    if misses:
        print('\n  misses:')
        for lang, want, got in misses:
            print(f'    [{lang}] {want} -> {got}')

    worst = min(per_lang.values())
    print(f'\n  VERDICT: weakest language {100 * worst / n:.0f}%. ', end='')
    print('PASS' if worst == n else 'a language is behind — see misses above')


if __name__ == '__main__':
    main()
