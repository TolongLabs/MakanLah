"""Derive labelled ground truth from the corpus, once, into evals/truth.json.

Pinned to a file rather than recomputed at eval time so a ranking change is
measured against a fixed target. Re-run deliberately when the corpus grows.

Labelling rule, and its limit: dish coverage is 486/1705 mentions, so a venue
WITHOUT a dish tag is unknown, not negative. Only venues carrying >= 2 tagged
dishes entirely from a disjoint cuisine group are labelled wrong. That keeps
the negative set small and honest instead of large and wrong.
"""

import contextlib
import json
import pathlib

from evals.aliases import MALAYSIAN, WESTERN, canonical
from makanlah import db

OUT = pathlib.Path(__file__).parent / 'truth.json'


def main():
    stack = contextlib.ExitStack()
    con = stack.enter_context(db.connect())
    rows = con.execute("""
        select v.id, v.name, coalesce(array_agg(distinct d) filter (where d is not null), '{}') as dishes
        from venue v
        left join mention m on m.venue_id = v.id
        left join unnest(m.dishes) d on true
        group by v.id, v.name
    """).fetchall()
    stack.close()

    venues = []
    for r in rows:
        keys = {c for c in (canonical(d) for d in r['dishes']) if c}
        venues.append({'id': str(r['id']), 'name': r['name'], 'keys': keys, 'n_tags': len(r['dishes'])})

    truth = {}
    for dish in sorted(MALAYSIAN | WESTERN):
        other = WESTERN if dish in MALAYSIAN else MALAYSIAN
        correct = [v for v in venues if dish in v['keys']]
        # Two negative classes, because they catch different failures.
        #
        # `wrong_cuisine` -- >=2 canonical tags, all from the opposite cuisine.
        # Unambiguous, and it turned out to be USELESS for the reported bug: the
        # complaint was `bak kut teh` returning 首都茶室 and 何九茶室, and those
        # canonicalise to char kway teow / kaya toast / laksa / curry mee, all
        # Malaysian. An opposite-cuisine rule scores that failure 0.000 and
        # reports the ranker as perfect.
        #
        # `wrong_dish` -- >=2 canonical tags, none of them the dish asked for.
        # Weaker evidence per venue, but it is the class the owner actually
        # complained about, so it is the one that has to be measured.
        wrong_cuisine = [v for v in venues if len(v['keys']) >= 2 and v['keys'] <= other and dish not in v['keys']]
        wrong_dish = [v for v in venues if len(v['keys']) >= 2 and dish not in v['keys']]
        if len(correct) >= 2:
            truth[dish] = {
                'correct': [{'id': v['id'], 'name': v['name']} for v in correct],
                'wrong_cuisine': [{'id': v['id'], 'name': v['name']} for v in wrong_cuisine][:12],
                'wrong_dish': [{'id': v['id'], 'name': v['name']} for v in wrong_dish],
            }
    OUT.write_text(json.dumps(truth, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(truth)} dishes with ground truth -> {OUT}')
    for d, t in truth.items():
        print(
            f'  {d:16} correct={len(t["correct"]):3}  '
            f'wrong-cuisine={len(t["wrong_cuisine"]):3}  wrong-dish={len(t["wrong_dish"]):3}'
        )


if __name__ == '__main__':
    main()
