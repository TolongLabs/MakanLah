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

MARKER = re.compile(r'(?:\s*(?:…|\.\.\.)\s*|\s+)More\s*$')


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
    cannot silently start eating real words.

    The first version required an ellipsis and left 295 excerpts marked -- and
    reported success, because it counted with the same pattern it stripped with.
    Google Maps emits the control after an ellipsis, after a full stop, and after
    a bare word with no punctuation at all.
    """

    def test_it_matches_every_shape_the_platform_emits(self):
        for s in [
            'great food … More',
            'great food... More',
            'great food …  More  ',
            'perfect flavour. More',
            'Atmosphere is ok. More',
            'Pricing ok More',
            'the broths are flavorful More',
            'Will come back again More',
        ]:
            assert MARKER.search(s), s

    def test_it_leaves_ordinary_sentences_alone(self):
        for s in ['I want more', 'nothing more to say', 'give me more']:
            assert not MARKER.search(s), s

    def test_it_is_case_sensitive(self):
        """One excerpt in the corpus genuinely ends in lower-case "more"."""
        assert not MARKER.search('I would like some more')

    def test_a_capitalised_more_carrying_punctuation_is_a_real_word(self):
        """The control never carries punctuation; a real word at a sentence end does."""
        for s in ['Would I go again? More!', 'Give me More.', 'and then some More?']:
            assert not MARKER.search(s), s

    def test_stripping_preserves_the_writers_words(self):
        assert MARKER.sub('', 'The pizza was excellent … More').strip() == 'The pizza was excellent'
        assert MARKER.sub('', 'Pricing ok More').strip() == 'Pricing ok'


class TestTheBackfillVerifiesWithADifferentPattern:
    """Counting with the pattern you strip with proves nothing.

    The first pass reported "0 markers left" while 295 excerpts still ended in
    the marker, because both numbers came from the same too-narrow regex.
    """

    def test_the_script_does_not_verify_with_its_own_strip_pattern(self):
        src = (pathlib.Path(__file__).resolve().parents[1] / 'ingest' / 'strip_truncation.py').read_text()
        after = src[src.index('remaining marked excerpts') - 1200 :]
        assert "'[[:space:]]More[[:space:]]*$'" in after, 'the completeness check reuses PATTERN'

    def test_the_backfill_is_scoped_to_the_platform_that_emits_the_marker(self):
        src = (pathlib.Path(__file__).resolve().parents[1] / 'ingest' / 'strip_truncation.py').read_text()
        assert "PLATFORM = 'google_maps'" in src
        assert src.count('platform = %s') >= 2, 'raw_text or excerpt updates are not platform-scoped'
