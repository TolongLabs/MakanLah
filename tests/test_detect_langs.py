"""Language tagging, which the Maps half of the corpus never had (#133).

`enrich_gmaps.py` hardcoded `langs=['und']`, so 1,388 of 1,507 posts were invisible
to language-aware retrieval. Fixing the ingest path exposed a second gap: the EN
detector was ten keywords, and short English reviews using none of them stayed 'und'.
"""

from makanlah.text import detect_langs


def test_a_short_english_review_using_none_of_the_topic_words_is_still_english():
    # Verbatim from the corpus. Under the ten-keyword pattern these were 'und'.
    assert detect_langs('Decent coffee.\nNice sandwiches.') == ['en']
    assert detect_langs("It's already closed; I made a wasted trip.") == ['en']
    assert detect_langs('Chicken rice a bit dry, chicken is ok.') == ['en']


def test_the_tag_is_plural_because_the_corpus_code_switches():
    # A real RedNote post: Chinese review, Malay dish, English aside. A
    # single-language column would erase what makes this corpus worth having.
    got = detect_langs('来吉隆坡一定要去这家店，nasi lemak 很好吃 BUT 面本身有点普通')
    assert set(got) == {'zh', 'ms', 'en'}


def test_a_latin_proper_noun_is_not_evidence_of_english():
    # "Ho Kaw Hainan Kopitiam" is a name and a loanword, not English prose. Tagging
    # every RedNote post 'en' because venue names are Latin would make the tag
    # meaningless for retrieval.
    assert detect_langs('来吉隆坡一定要去 Ho Kaw Hainan Kopitiam 这家店') == ['zh']


def test_malay_is_not_swallowed_by_the_wider_english_list():
    assert 'ms' in detect_langs('Nasi lemak sedap, harga murah, tempat bersih')


def test_chinese_alone_stays_chinese():
    assert detect_langs('汤头浓郁，本地人回头率高') == ['zh']


def test_text_with_no_signal_is_und_not_a_guess():
    # 2 of 1507 land here, both English in fact. Inventing a tag for them would put
    # a wrong language on a post, which is worse for retrieval than admitting none.
    assert detect_langs('unreal. perfect. amazing.') == ['und']
    assert detect_langs('') == ['und']
    assert detect_langs(None) == ['und']


def test_widening_a_detector_never_removes_a_language():
    # The property that made the corpus-wide re-tag safe: 0 of 1507 rows lost a tag.
    zh = detect_langs('汤头浓郁 the food is good')
    assert 'zh' in zh and 'en' in zh
