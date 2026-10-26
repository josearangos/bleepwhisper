from bleeper.core.models import Match
from bleeper.core.spans import build_spans

SR = 16000


def test_padding_and_time_conversion() -> None:
    spans = build_spans([Match("heck", 2.0, 2.5)], SR, 5 * SR, padding_ms=80)
    assert [(s.start, s.end, s.words) for s in spans] == [(30720, 41280, ("heck",))]


def test_padding_rounds_to_samples() -> None:
    spans = build_spans([Match("a", 1.0, 1.0001)], 44100, 44100 * 2, padding_ms=1)
    assert (spans[0].start, spans[0].end) == (44100 - 44, round(1.0001 * 44100) + 44)


def test_zero_padding_gives_exact_word_bounds() -> None:
    spans = build_spans([Match("heck", 2.0, 2.5)], SR, 5 * SR, padding_ms=0)
    assert (spans[0].start, spans[0].end) == (32000, 40000)


def test_clamps_to_audio_bounds() -> None:
    spans = build_spans([Match("a", 0.01, 0.2), Match("b", 4.9, 5.0)], SR, 5 * SR, padding_ms=80)
    assert (spans[0].start, spans[-1].end) == (0, 5 * SR)


def test_overlapping_and_touching_spans_merge() -> None:
    matches = [Match("c", 3.0, 3.1), Match("a", 1.0, 1.1), Match("b", 1.2, 1.3)]
    spans = build_spans(matches, SR, 5 * SR, padding_ms=80)
    assert [(s.start, s.end, s.words) for s in spans] == [
        (14720, 22080, ("a", "b")),
        (46720, 50880, ("c",)),
    ]
    touching = build_spans([Match("a", 1.0, 1.5), Match("b", 1.5, 2.0)], SR, 5 * SR, 0)
    assert [(s.start, s.end, s.words) for s in touching] == [(16000, 32000, ("a", "b"))]


def test_non_touching_spans_stay_separate() -> None:
    spans = build_spans([Match("a", 1.0, 1.5), Match("b", 1.5001, 2.0)], SR, 5 * SR, 0)
    assert len(spans) == 2


def test_zero_length_spans_are_dropped() -> None:
    assert build_spans([Match("a", 6.0, 7.0)], SR, 5 * SR, padding_ms=0) == []
    assert build_spans([Match("a", 1.0, 1.0)], SR, 5 * SR, padding_ms=0) == []
