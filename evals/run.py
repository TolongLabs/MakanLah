"""Measure ranking quality against pinned ground truth.

NOT part of the pytest suite: it needs the live corpus and spends model quota,
and docs/TRD.md rules out a CI suite that depends on either. Run it deliberately,
before and after a ranking change, and paste the table into the issue.

Two metrics, because they fail differently:
  precision@5  how much of the shortlist is right
  fp@5         venues whose tagged dishes are entirely the OPPOSITE cuisine.
               Unambiguous, and near-useless: the reported failure was `bak kut
               teh` returning 首都茶室 and 何九茶室, which are Malaysian, so this
               metric scores that 0.000 and calls the ranker perfect.
  wd@5         venues with >=2 tagged dishes, NONE of them the one asked for.
               This is the metric that sees the actual complaint.

Every case runs REPEATS times. The re-ranker returned 2, 10 and 10 results for
three identical calls, so a single run measures the roll rather than the ranker.
"""

import argparse
import json
import pathlib
import statistics
import time

from makanlah import rank

TRUTH = json.loads((pathlib.Path(__file__).parent / 'truth.json').read_text())
REPEATS = 3
K = 5

# KLCC, the centre of the corpus.
LAT, LNG = 3.1390, 101.6869

QUERIES = {
    'bak kut teh': ['bak kut teh', '肉骨茶'],
    'nasi lemak': ['nasi lemak', '椰浆饭'],
    'char kway teow': ['char kway teow', '炒粿条'],
    'laksa': ['laksa', '叻沙'],
    'kaya toast': ['kaya toast'],
    'satay': ['satay'],
    'roti canai': ['roti canai'],
    'curry mee': ['curry mee'],
    'chicken rice': ['chicken rice'],
    'pasta': ['pasta'],
    'pizza': ['pizza'],
    'steak': ['steak'],
    'tiramisu': ['tiramisu'],
    'matcha': ['matcha'],
}

# No dish ground truth exists for these, so they are reported, never scored.
# Silently scoring them against dish labels would invent a number.
MOOD = ['somewhere light for breakfast', '想吃辣的东西', 'tempat makan yang sedap dan murah']


def _p95(values):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def score_one(query, truth, limit=10):
    t = time.perf_counter()
    out = rank.recommend(query, lat=LAT, lng=LNG, limit=limit)
    dt = time.perf_counter() - t
    ids = [r['venue']['id'] for r in out['results']]
    top = ids[:K]
    correct = {v['id'] for v in truth['correct']}
    wrong_cuisine = {v['id'] for v in truth['wrong_cuisine']}
    wrong_dish = {v['id'] for v in truth['wrong_dish']}
    denom = max(1, len(top))
    return {
        'sec': dt,
        'n': len(ids),
        'p_at_k': sum(1 for i in top if i in correct) / denom,
        'fp_at_k': sum(1 for i in top if i in wrong_cuisine) / denom,
        'wd_at_k': sum(1 for i in top if i in wrong_dish) / denom,
        'top1_ok': bool(top) and top[0] in correct,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', default='baseline')
    ap.add_argument('--repeats', type=int, default=REPEATS)
    ap.add_argument('--quick', action='store_true', help='one repeat, dish queries only (~43k tokens)')
    args = ap.parse_args()
    repeats = 1 if args.quick else args.repeats

    # This is not free. One full run is ~134k tokens against a 1,000,000-token
    # free quota that does not refill until it expires, so a careless afternoon
    # of re-runs is most of a month's allowance. Print the bill BEFORE spending it.
    queries = sum(len(v) for k, v in QUERIES.items() if k in TRUTH)
    calls = queries * repeats + (0 if args.quick else len(MOOD))
    print(f'{calls} model calls, roughly {calls * 2500:,} tokens. Ctrl-C now if that is not intended.\n')

    print(f'{"query":26} {"lang":5} {"p@5":>12} {"fp@5":>6} {"wd@5":>6} {"top1":>6} {"n":>7} {"sec":>6}')
    print('-' * 82)
    all_p, all_fp, all_wd, all_top1, all_sec = [], [], [], [], []
    for dish, queries in QUERIES.items():
        if dish not in TRUTH:
            continue
        for q in queries:
            lang = 'zh' if any('一' <= c <= '鿿' for c in q) else 'en'
            runs = [score_one(q, TRUTH[dish]) for _ in range(repeats)]
            p = [r['p_at_k'] for r in runs]
            fp = [r['fp_at_k'] for r in runs]
            wd = [r['wd_at_k'] for r in runs]
            t1 = [r['top1_ok'] for r in runs]
            ns = [r['n'] for r in runs]
            sec = [r['sec'] for r in runs]
            all_p += p
            all_fp += fp
            all_wd += wd
            all_top1 += t1
            all_sec += sec
            print(
                f'{q[:24]:26} {lang:5} {statistics.mean(p):6.2f} ±{max(p) - min(p):4.2f} '
                f'{statistics.mean(fp):6.2f} {statistics.mean(wd):6.2f} '
                f'{sum(t1)}/{len(t1):<4} {min(ns)}-{max(ns):<4} {statistics.mean(sec):6.2f}'
            )

    print('-' * 82)
    print(
        f'{args.label}:\n  mean p@5  {statistics.mean(all_p):.3f}\n'
        f'  mean fp@5 {statistics.mean(all_fp):.3f}  (opposite cuisine -- blind to the reported bug)\n'
        f'  mean wd@5 {statistics.mean(all_wd):.3f}  (tagged, but not with the dish asked for)\n'
        f'  top1 correct {sum(all_top1)}/{len(all_top1)}\n'
        # PRD.md states p95 < 3s. Reporting a median against a p95 target hides
        # the tail, which is the only part that target is about.
        f'  latency median {statistics.median(all_sec):.2f}s  p95 {_p95(all_sec):.2f}s  max {max(all_sec):.2f}s'
    )
    print()
    if args.quick:
        return
    print('unscored (no dish ground truth; reported so a regression in shape is visible):')
    for q in MOOD:
        t = time.perf_counter()
        out = rank.recommend(q, lat=LAT, lng=LNG, limit=10)
        print(f'  {q[:34]:36} n={len(out["results"]):2}  {time.perf_counter() - t:5.2f}s')


if __name__ == '__main__':
    main()
