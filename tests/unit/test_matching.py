from bleeper.core.matching import find_matches, normalize
from bleeper.core.models import Match, TranscribedWord
from bleeper.core.words import parse_words


def words(*items: tuple[str, float, float]) -> list[TranscribedWord]:
    return [TranscribedWord(text, start, end) for text, start, end in items]


def test_normalize_lowercases_strips_accents_and_punctuation() -> None:
    assert normalize("Don't!") == ["dont"]
    assert normalize(" señor,") == ["senor"]
    assert normalize("ÁRBOL Ñandú") == ["arbol", "nandu"]
    assert normalize("f-word $") == ["fword"]
    assert normalize("...") == []


def test_matches_after_normalization() -> None:
    transcript = words((" Hola", 0.0, 0.4), (" Señor,", 0.5, 1.0))
    assert find_matches(transcript, parse_words("senor")) == [Match("Señor,", 0.5, 1.0)]


def test_whole_token_only() -> None:
    transcript = words((" class", 0.0, 0.5), (" assess", 0.6, 1.0))
    assert find_matches(transcript, parse_words("ass")) == []


def test_phrase_matches_consecutive_words_only() -> None:
    transcript = words(
        (" shut", 0.0, 0.3),
        (" the", 0.4, 0.5),
        (" door", 0.6, 0.9),
        (" shut", 1.0, 1.2),
        (" up!", 1.3, 1.6),
    )
    assert find_matches(transcript, parse_words("shut up")) == [Match("shut up!", 1.0, 1.6)]


def test_all_occurrences_are_matched_in_order() -> None:
    transcript = words((" heck", 0.0, 0.2), (" darn", 0.3, 0.5), (" heck", 0.6, 0.8))
    assert find_matches(transcript, parse_words("heck\ndarn")) == [
        Match("heck", 0.0, 0.2),
        Match("darn", 0.3, 0.5),
        Match("heck", 0.6, 0.8),
    ]


def test_words_that_normalize_to_empty_are_ignored() -> None:
    transcript = words((" shut", 0.0, 0.3), (" -", 0.35, 0.4), (" up", 0.5, 0.8))
    assert find_matches(transcript, parse_words("shut up")) == [Match("shut up", 0.0, 0.8)]


def test_word_with_inner_space_spans_multiple_tokens() -> None:
    transcript = words(
        (" shut up", 0.0, 0.8),
    )
    assert find_matches(transcript, parse_words("up")) == [Match("shut up", 0.0, 0.8)]
