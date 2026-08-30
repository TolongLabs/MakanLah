"""Narration must not talk over itself.

Built from the real launch cut, where three of six lines were mixed on top of
the line before them. The overlap is inaudible to every mechanical check the
pipeline runs -- level, clipping, silence and dynamics are all normal while two
voices speak at once -- so it reached the owner and he caught it by listening.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'demo'))

from schedule import deconflict


def lines_at(*ms):
    return [{'ms': m, 'text': f'line {i}'} for i, m in enumerate(ms)]


def test_the_real_launch_cut_had_three_overlaps():
    # Beat-derived starts and measured durations from the 2026-08-30 capture.
    lines = lines_at(3681, 12496, 30651, 37994, 45013, 50013)
    durations = [6300, 8100, 9800, 9200, 10600, 3700]
    shifted, _ = deconflict(lines, durations)
    assert shifted == 3
    assert all(a['ms'] + a['dur_ms'] <= b['ms'] for a, b in zip(lines, lines[1:], strict=False))


def test_a_line_that_fits_is_left_exactly_where_the_beat_put_it():
    # Beats stay authoritative for the earliest a line may start.
    lines = lines_at(1000, 20000, 40000)
    durations = [3000, 3000, 3000]
    shifted, _ = deconflict(lines, durations)
    assert shifted == 0
    assert [x['ms'] for x in lines] == [1000, 20000, 40000]


def test_a_pushed_line_pushes_the_ones_after_it():
    # Cascading matters: fixing only the first collision leaves the rest colliding.
    lines = lines_at(0, 1000, 2000)
    durations = [5000, 5000, 5000]
    deconflict(lines, durations, gap_ms=0)
    assert [x['ms'] for x in lines] == [0, 5000, 10000]


def test_it_never_moves_a_line_earlier():
    lines = lines_at(0, 30000)
    durations = [1000, 1000]
    deconflict(lines, durations)
    assert lines[1]['ms'] == 30000


def test_the_gap_is_applied_between_lines():
    lines = lines_at(0, 100)
    durations = [1000, 1000]
    deconflict(lines, durations, gap_ms=260)
    assert lines[1]['ms'] == 1260
