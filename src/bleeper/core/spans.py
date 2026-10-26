"""Turn matches into padded, clamped, merged sample spans (pure)."""

from __future__ import annotations

from collections.abc import Sequence

from bleeper.core.models import Match, Span


def build_spans(
    matches: Sequence[Match], sample_rate: int, n_samples: int, padding_ms: int
) -> list[Span]:
    pad = round(padding_ms * sample_rate / 1000)
    raw = sorted(
        (
            max(0, round(m.start * sample_rate) - pad),
            min(n_samples, round(m.end * sample_rate) + pad),
            index,
            m.text,
        )
        for index, m in enumerate(matches)
    )
    spans: list[Span] = []
    for start, end, _, text in raw:
        if end <= start:
            continue
        if spans and start <= spans[-1].end:
            last = spans[-1]
            spans[-1] = Span(last.start, max(last.end, end), (*last.words, text))
        else:
            spans.append(Span(start, end, (text,)))
    return spans
