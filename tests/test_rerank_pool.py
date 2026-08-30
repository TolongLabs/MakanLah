"""The re-ranker was handed fewer candidates than it was allowed to return.

`RERANK_CANDIDATES` was 16 and `/recommend` accepts `limit` up to 20, so a
request for 20 could never be filled: the pool decided the answer before the
model did. Nobody noticed while the corpus was small enough that few queries had
16 plausible matches.

Measured across 46 real queries by @makanlah-92, the symptom was a total result
count that did not move: 192 slots filled at 1,507 posts, 198 at 4,523, 187
after the candidate ceiling was raised. Tripling the corpus changed which venues
came back and not how many. Median 2.5 results against a limit of 20.

Measured directly on eight queries: raising the pool to 40 took total results
from 36 to 60, and median re-rank latency from 1.4s to 1.9s.
"""

from makanlah.models import RERANK_CANDIDATES


def test_the_pool_exceeds_the_largest_answer_the_api_will_return():
    """`RecommendRequest.limit` is capped at 20. A pool at or below that lets the
    truncation, rather than the model, decide how many results exist."""
    from api.main import RecommendRequest

    max_limit = RecommendRequest.model_fields['limit'].metadata[-1].le
    assert max_limit == 20
    assert 2 * max_limit <= RERANK_CANDIDATES, (
        f'pool {RERANK_CANDIDATES} must give the model real choice above the {max_limit} it may return'
    )


def test_the_pool_is_still_bounded():
    """It is a prompt, and every candidate costs tokens and latency. Unbounded
    would trade a measured 0.5s for candidates the model will not reach."""
    assert RERANK_CANDIDATES <= 60
