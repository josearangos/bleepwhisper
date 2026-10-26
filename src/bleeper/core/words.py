"""Parse the forbidden-words file into normalized entries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bleeper.core.errors import InvalidInputError
from bleeper.core.matching import normalize


@dataclass(frozen=True)
class ForbiddenEntry:
    original: str
    tokens: tuple[str, ...]


def parse_words(text: str) -> list[ForbiddenEntry]:
    """One entry per line; skip blanks, `#` comments, empty normalizations and duplicates."""
    entries: list[ForbiddenEntry] = []
    seen: set[tuple[str, ...]] = set()
    for line in text.splitlines():
        original = line.strip()
        if not original or original.startswith("#"):
            continue
        tokens = tuple(normalize(original))
        if tokens and tokens not in seen:
            seen.add(tokens)
            entries.append(ForbiddenEntry(original, tokens))
    return entries


def load_words(path: Path) -> list[ForbiddenEntry]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise InvalidInputError(
            f"words file '{path}' not found. Check the path passed to --words."
        ) from None
    except UnicodeDecodeError:
        raise InvalidInputError(
            f"cannot read words file '{path}': the words file must be UTF-8. "
            "Re-save it with UTF-8 encoding."
        ) from None
    except OSError as exc:
        raise InvalidInputError(
            f"cannot read words file '{path}' ({exc.strerror}). Check that it is a readable file."
        ) from None
    entries = parse_words(text)
    if not entries:
        raise InvalidInputError(
            f"no forbidden words found in {path}. Add one word or phrase per line."
        )
    return entries
