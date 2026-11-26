import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bleeper.core import InvalidInputError, ProcessingError, pipeline, process_audio
from bleeper.core.models import ReportEntry, TranscribedWord

SR = 16000
HECK = [TranscribedWord(" heck", 2.0, 2.5)]


def read(path: Path) -> tuple[np.ndarray, int]:
    return sf.read(path, dtype="int32", always_2d=True)


def changed_indices(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.any(a != b, axis=1))


def test_masks_only_the_padded_word(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    src = make_tone()
    out = tmp_path / "out.wav"
    result = process_audio(
        src, words_file(["heck"]), out, preset="beep", transcriber=fake_transcriber(HECK)
    )
    original, _ = read(src)
    masked, sr = read(out)
    assert sr == SR and masked.shape == original.shape
    diff = changed_indices(original, masked)
    assert diff.min() >= round(1.92 * SR) and diff.max() < round(2.58 * SR)
    assert len(diff) > 0.9 * (round(2.58 * SR) - round(1.92 * SR))
    assert result.report == [ReportEntry("heck", 1.92, 2.58)]
    assert result.report_path == out.with_suffix(".json")
    assert result.language == "en"
    assert json.loads(out.with_suffix(".json").read_text()) == [
        {"word": "heck", "start": 1.92, "end": 2.58}
    ]


def test_no_matches_output_identical(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    src = make_tone()
    out = tmp_path / "out.wav"
    words = [TranscribedWord(" hello", 1.0, 1.4)]
    result = process_audio(
        src, words_file(["heck"]), out, preset="noise", transcriber=fake_transcriber(words)
    )
    np.testing.assert_array_equal(read(src)[0], read(out)[0])
    assert result.report == []
    assert json.loads(result.report_path.read_text()) == []


def test_input_is_never_modified(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    src = make_tone()
    before = (src.read_bytes(), os.stat(src).st_mtime_ns)
    process_audio(
        src,
        words_file(["heck"]),
        tmp_path / "o.wav",
        preset="tone",
        transcriber=fake_transcriber(HECK),
    )
    assert (src.read_bytes(), os.stat(src).st_mtime_ns) == before


def test_existing_output_and_report_are_replaced(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    out, report = tmp_path / "o.wav", tmp_path / "r.json"
    out.write_bytes(b"old")
    report.write_text("old")
    process_audio(
        make_tone(),
        words_file(["heck"]),
        out,
        preset="beep",
        report_path=report,
        transcriber=fake_transcriber(HECK),
    )
    assert sf.info(out).frames == 5 * SR
    assert json.loads(report.read_text())[0]["word"] == "heck"


def test_stereo_pcm24_is_preserved(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    src = make_tone(sr=44100, channels=2, subtype="PCM_24")
    out = tmp_path / "out.wav"
    process_audio(src, words_file(["heck"]), out, preset="beep", transcriber=fake_transcriber(HECK))
    info = sf.info(out)
    assert (info.samplerate, info.channels, info.frames, info.subtype) == (
        44100,
        2,
        5 * 44100,
        "PCM_24",
    )
    diff = changed_indices(read(src)[0], read(out)[0])
    assert diff.min() >= round(1.92 * 44100) and diff.max() < round(2.58 * 44100)


def test_transcriber_receives_input_path_and_language(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    src = make_tone()
    fake = fake_transcriber(HECK)
    result = process_audio(
        src,
        words_file(["heck"]),
        tmp_path / "o.wav",
        preset="beep",
        language="es",
        transcriber=fake,
    )
    assert fake.calls == [(src, "es")]
    assert result.language == "es"


def write_mask(path: Path, seconds: float, sr: int = SR, channels: int = 1) -> Path:
    rng = np.random.default_rng(7)
    sf.write(path, rng.uniform(-0.5, 0.5, (round(seconds * sr), channels)), sr, subtype="FLOAT")
    return path


@pytest.mark.parametrize("mask_seconds", [0.2, 2.0])
def test_custom_mask_fills_exactly_the_span(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
    mask_seconds: float,
) -> None:
    src = make_tone()
    out = tmp_path / "out.wav"
    mask = write_mask(tmp_path / "mask.wav", mask_seconds)
    process_audio(
        src, words_file(["heck"]), out, mask_path=mask, transcriber=fake_transcriber(HECK)
    )
    start, end = round(1.92 * SR), round(2.58 * SR)
    original, masked = read(src)[0], read(out)[0]
    np.testing.assert_array_equal(original[:start], masked[:start])
    np.testing.assert_array_equal(original[end:], masked[end:])
    diff = changed_indices(original, masked)
    assert diff.min() == start and diff.max() == end - 1  # 660 ms, 0-sample difference
    assert masked[start, 0] == 0 and masked[end - 1, 0] == 0  # fades reach zero


def test_mask_rate_and_channels_follow_the_input(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    src = make_tone()
    out = tmp_path / "out.wav"
    mask = write_mask(tmp_path / "mask.wav", 0.3, sr=44100, channels=2)
    process_audio(
        src, words_file(["heck"]), out, mask_path=mask, transcriber=fake_transcriber(HECK)
    )
    info = sf.info(out)
    assert (info.samplerate, info.channels, info.frames) == (SR, 1, 5 * SR)


class RaisingTranscriber:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def transcribe(self, *args: object) -> None:
        raise self.error


def listing(directory: Path) -> set[str]:
    return {p.name for p in directory.iterdir()}


@pytest.mark.parametrize("error", [ProcessingError("model broke"), RuntimeError("boom")])
def test_processing_failure_leaves_nothing_behind(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    tmp_path: Path,
    error: Exception,
) -> None:
    src = make_tone()
    words = words_file(["heck"])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    before_src = src.read_bytes()
    before_tmp = listing(Path(tempfile.gettempdir()))
    with pytest.raises(ProcessingError):
        process_audio(
            src, words, out_dir / "o.wav", preset="beep", transcriber=RaisingTranscriber(error)
        )
    assert listing(out_dir) == set()
    assert not {n for n in listing(Path(tempfile.gettempdir())) - before_tmp if "bleeper" in n}
    assert src.read_bytes() == before_src


def test_report_write_failure_removes_new_wav(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def broken(path: Path, entries: object) -> None:
        raise ProcessingError("cannot write report")

    monkeypatch.setattr(pipeline, "write_report", broken)
    with pytest.raises(ProcessingError):
        process_audio(
            make_tone(),
            words_file(["heck"]),
            out_dir / "o.wav",
            preset="beep",
            transcriber=fake_transcriber(HECK),
        )
    assert listing(out_dir) == set()


def test_invalid_options_fail_before_transcription(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    fake = fake_transcriber(HECK)
    src, words = make_tone(), words_file(["heck"])
    for kwargs in (
        {"preset": "beep", "padding_ms": -1},
        {"preset": "beep", "mask_path": tmp_path / "m.wav"},
        {},
        {"preset": "quack"},
    ):
        with pytest.raises(InvalidInputError):
            process_audio(src, words, tmp_path / "o.wav", transcriber=fake, **kwargs)
    assert fake.calls == []


STAGES = ["loading", "transcribing", "masking", "writing", "done"]


def test_progress_is_monotonic_and_ends_done(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, float]] = []
    process_audio(
        make_tone(),
        words_file(["heck"]),
        tmp_path / "o.wav",
        preset="beep",
        transcriber=fake_transcriber(HECK),
        progress=lambda s, f: calls.append((s, f)),
    )
    fractions = [f for _, f in calls]
    assert fractions == sorted(fractions)
    assert all(0.0 <= f <= 1.0 for f in fractions)
    stages = list(dict.fromkeys(s for s, _ in calls))
    assert stages == STAGES
    assert all(0.05 <= f <= 0.85 for s, f in calls if s == "transcribing")
    assert calls[-1] == ("done", 1.0)


def test_runs_without_progress_callback(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    result = process_audio(
        make_tone(),
        words_file(["heck"]),
        tmp_path / "o.wav",
        preset="beep",
        transcriber=fake_transcriber(HECK),
        progress=None,
    )
    assert result.output_path.exists()


def test_callback_exception_aborts_without_output(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    class Cancelled(Exception):
        pass

    def cancel(stage: str, fraction: float) -> None:
        if stage == "masking":
            raise Cancelled

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with pytest.raises(Cancelled):
        process_audio(
            make_tone(),
            words_file(["heck"]),
            out_dir / "o.wav",
            preset="beep",
            transcriber=fake_transcriber(HECK),
            progress=cancel,
        )
    assert listing(out_dir) == set()


# --- song styles ---------------------------------------------------------------------------

WORD_AT_1S = [TranscribedWord(" heck", 0.9, 1.1)]
NOTE_MONO = "vocal-dropout needs stereo audio; this file is mono, so dip was used instead."
NOTE_DIP_DB = "--dip-db was ignored: this file is stereo, so vocal-dropout was applied."


def run_style(
    src: Path, words: Path, tmp_path: Path, fake_transcriber: type, **options: object
) -> tuple[object, np.ndarray, np.ndarray]:
    out = tmp_path / "out.wav"
    result = process_audio(src, words, out, transcriber=fake_transcriber(WORD_AT_1S), **options)  # type: ignore[arg-type]
    original, _ = read(src)
    masked, _ = read(out)
    return result, original, masked


def level(x: np.ndarray, freq: float, start: int, end: int) -> float:
    seg = x[start:end].astype(np.float64)
    t = np.arange(len(seg)) / SR
    return abs(np.mean(seg * np.exp(-2j * np.pi * freq * t)))


def test_vocal_dropout_end_to_end(
    song_file: Path, words_file: Callable[..., Path], fake_transcriber: type, tmp_path: Path
) -> None:
    result, original, masked = run_style(
        song_file, words_file(["heck"]), tmp_path, fake_transcriber, style="vocal-dropout"
    )
    start, end = round(0.82 * SR), round(1.18 * SR)  # padded span 0.82-1.18 s
    changed = changed_indices(original, masked)
    assert changed.min() >= start - 1 and changed.max() <= end
    assert masked.shape == original.shape
    a, b = round(0.85 * SR), round(1.15 * SR)
    drop = 20 * np.log10(level(original[:, 0], 1000, a, b) / level(masked[:, 0], 1000, a, b))
    assert drop >= 30
    bass = level(masked[:, 0], 60, a, b) / level(original[:, 0], 60, a, b)
    assert 0.89 <= bass <= 1.12
    assert result.report[0].to_dict()["style"] == "vocal-dropout"  # type: ignore[attr-defined]
    assert result.notes == ()  # type: ignore[attr-defined]


def test_vocal_dropout_falls_back_to_dip_on_mono_and_dual_mono(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    for channels in (1, 2):
        src = make_tone(f"m{channels}.wav", seconds=2.0, channels=channels)
        result, _, masked = run_style(
            src, words_file(["heck"]), tmp_path, fake_transcriber, style="vocal-dropout"
        )
        a, b = round(0.85 * SR), round(1.15 * SR)
        assert np.all(masked[a:b] == 0)
        assert result.report[0].to_dict()["style"] == "dip"  # type: ignore[attr-defined]
        assert result.report[0].to_dict()["requested_style"] == "vocal-dropout"  # type: ignore[attr-defined]
        assert result.notes == (NOTE_MONO,)  # type: ignore[attr-defined]


def test_dip_db_ignored_on_stereo_vocal_dropout(
    song_file: Path, words_file: Callable[..., Path], fake_transcriber: type, tmp_path: Path
) -> None:
    result, _, masked = run_style(
        song_file,
        words_file(["heck"]),
        tmp_path,
        fake_transcriber,
        style="vocal-dropout",
        dip_db=20,
    )
    a, b = round(0.85 * SR), round(1.15 * SR)
    assert np.any(masked[a:b] != 0)  # not a dip
    assert result.report[0].to_dict()["style"] == "vocal-dropout"  # type: ignore[attr-defined]
    assert result.notes == (NOTE_DIP_DB,)  # type: ignore[attr-defined]


@pytest.mark.parametrize("options", [{"style": "reverse"}, {"style": "dip", "dip_db": 20}])
def test_reverse_and_dip_end_to_end(
    options: dict[str, object],
    song_file: Path,
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    result, original, masked = run_style(
        song_file, words_file(["heck"]), tmp_path, fake_transcriber, **options
    )
    changed = changed_indices(original, masked)
    assert changed.min() >= round(0.82 * SR) - 1 and changed.max() <= round(1.18 * SR)
    assert masked.shape == original.shape
    entry = result.report[0].to_dict()  # type: ignore[attr-defined]
    assert entry["style"] == options["style"] and "requested_style" not in entry


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"style": "dip", "preset": "beep"}, "--style"),
        ({"style": "karaoke"}, "unknown style 'karaoke'"),
        ({"style": "dip", "dip_db": 0}, "--dip-db must be greater than 0"),
        ({"style": "dip", "dip_db": -3}, "--dip-db must be greater than 0"),
        ({"preset": "beep", "dip_db": 10}, "--dip-db only applies"),
        ({"style": "reverse", "dip_db": 10}, "--dip-db only applies"),
    ],
)
def test_style_option_validation(
    options: dict[str, object],
    message: str,
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    with pytest.raises(InvalidInputError, match=message):
        process_audio(
            make_tone(),
            words_file(["heck"]),
            tmp_path / "o.wav",
            transcriber=fake_transcriber(HECK),
            **options,  # type: ignore[arg-type]
        )


def test_style_with_mask_path_rejected(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    with pytest.raises(InvalidInputError, match="--style"):
        process_audio(
            make_tone(),
            words_file(["heck"]),
            tmp_path / "o.wav",
            mask_path=make_tone("mask.wav"),
            style="dip",
            transcriber=fake_transcriber(HECK),
        )
