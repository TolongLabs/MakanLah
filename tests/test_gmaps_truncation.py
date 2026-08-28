"""Google Maps collapses long reviews behind its own "… More" control.

Reading `innerText` without clicking it captured the platform's chrome inside a
verbatim citation AND silently lost the rest of the review. 1036 of 1388 stored
Google Maps excerpts ended in the marker before this was fixed -- 74.6% of one
whole source, cut mid-sentence, shown to users as the writer's words.
"""

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

GMAPS = (pathlib.Path(__file__).resolve().parents[1] / 'ingest' / 'gmaps.py').read_text()

MARKER = re.compile(r'(?:…|\.\.\.)\s*More\s*$')


class TestTheScraperExpandsBeforeReading:
    def test_there_is_an_expand_step(self):
        assert 'EXPAND_JS' in GMAPS, 'nothing clicks the "See more" control'

    def test_the_expand_step_runs_before_the_read(self):
        body = GMAPS[GMAPS.index('async def reviews') : GMAPS.index('async def enrich')]
        assert 'EXPAND_JS' in body, 'reviews() never expands'
        assert body.index('EXPAND_JS') < body.index('REVIEWS_JS'), 'reviews are read before being expanded'

    def test_the_extractor_also_strips_the_marker(self):
        """Defence in depth: a click that does not land must not put scrape
        chrome inside a verbatim excerpt."""
        assert 'More' in GMAPS and 'replace(' in GMAPS


class TestTheMarkerPattern:
    """The pattern used to backfill, asserted directly so a future change to it
    cannot silently start eating real words."""

    def test_it_matches_the_real_shapes(self):
        for s in ['great food … More', 'great food... More', 'great food …  More  ']:
            assert MARKER.search(s), s

    def test_it_leaves_ordinary_sentences_alone(self):
        for s in ['I want more', 'More salt needed', 'nothing more to say', 'the More the merrier']:
            assert not MARKER.search(s), s

    def test_stripping_preserves_the_writers_words(self):
        assert MARKER.sub('', 'The pizza was excellent … More').strip() == 'The pizza was excellent'
