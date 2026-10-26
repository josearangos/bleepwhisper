"""Text normalization and whole-token matching of forbidden entries (pure)."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from typing import TYPE_CHECKING

from bleeper.core.models import Match, TranscribedWord

if TYPE_CHECKING:
    from bleeper.core.words import ForbiddenEntry


def normalize(text: str) -> list[str]:
    """Lowercase, strip accents, delete punctuation/symbols and split into tokens."""
    decomposed = unicodedata.normalize("NFKD", text)
    no_marks = "".join(c for c in decomposed if unicodedata.category(c) != "Mn").casefold()
    kept = "".join(c for c in no_marks if unicodedata.category(c)[0] not in "PS")
    return kept.split()


def find_matches(
    words: Sequence[TranscribedWord], entries: Sequence[ForbiddenEntry]
) -> list[Match]:
    """Return every occurrence of every entry in transcript order."""
    tokens: list[tuple[str, int]] = [
        (token, index) for index, word in enumerate(words) for token in normalize(word.text)
    ]
    texts = [token for token, _ in tokens]
    found: list[tuple[int, int, Match]] = []
    for entry in entries:
        size = len(entry.tokens)
        for i in range(len(texts) - size + 1):
            if tuple(texts[i : i + size]) != entry.tokens:
                continue
            indices = list(dict.fromkeys(index for _, index in tokens[i : i + size]))
            text = " ".join(words[index].text.strip() for index in indices)
            first, last = words[indices[0]], words[indices[-1]]
            found.append((i, size, Match(text, first.start, last.end)))
    found.sort(key=lambda item: (item[0], item[1]))
    return [match for _, _, match in found]
