from pathlib import Path

import pytest

from bleeper.core.errors import InvalidInputError
from bleeper.core.words import ForbiddenEntry, load_words, parse_words


def tokens(text: str) -> list[tuple[str, ...]]:
    return [entry.tokens for entry in parse_words(text)]


def test_parses_one_entry_per_line() -> None:
    assert tokens("darn\nheck\n") == [("darn",), ("heck",)]


def test_skips_blank_lines_and_comments() -> None:
    assert tokens("\n   \n# comment\n   # indented comment\nheck\n") == [("heck",)]


def test_trims_whitespace_and_keeps_original() -> None:
    assert parse_words("   heck  \n") == [ForbiddenEntry("heck", ("heck",))]


def test_collapses_duplicates_after_normalization() -> None:
    assert tokens("Heck\nheck\nHECK!\n") == [("heck",)]


def test_normalizes_accents_and_phrases() -> None:
    assert tokens("Señor\nshut up\n") == [("senor",), ("shut", "up")]


def test_skips_punctuation_only_lines() -> None:
    assert tokens("!!!\n...\nheck\n") == [("heck",)]


def test_load_words_reads_utf8(tmp_path: Path) -> None:
    path = tmp_path / "words.txt"
    path.write_text("Señor\n", encoding="utf-8")
    assert [e.tokens for e in load_words(path)] == [("senor",)]


def test_load_words_without_entries_raises(tmp_path: Path) -> None:
    path = tmp_path / "words.txt"
    path.write_text("# only a comment\n\n", encoding="utf-8")
    with pytest.raises(InvalidInputError, match="no forbidden words"):
        load_words(path)


def test_load_words_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="missing.txt"):
        load_words(tmp_path / "missing.txt")


def test_load_words_non_utf8_raises(tmp_path: Path) -> None:
    path = tmp_path / "words.txt"
    path.write_bytes("Señor\n".encode("latin-1"))
    with pytest.raises(InvalidInputError, match="UTF-8"):
        load_words(path)
