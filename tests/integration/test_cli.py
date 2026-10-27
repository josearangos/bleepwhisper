import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bleeper import cli
from bleeper.core import pipeline
from bleeper.core.models import TranscribedWord

HECK = [TranscribedWord(" heck", 2.0, 2.5)]


@pytest.fixture
def use_fake(monkeypatch: pytest.MonkeyPatch, fake_transcriber: type) -> Callable[..., list[str]]:
    """Replace the default faster-whisper transcriber; returns the list of requested models."""
    models: list[str] = []

    def install(words: list[TranscribedWord]) -> list[str]:
        fake = fake_transcriber(words)

        def factory(model: str) -> object:
            models.append(model)
            return fake

        monkeypatch.setattr(pipeline, "WhisperTranscriber", factory)
        return models

    return install


def test_preset_run_prints_summary(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    use_fake: Callable[..., list[str]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_fake(HECK)
    out = tmp_path / "out.wav"
    code = cli.main(
        [str(make_tone()), "--words", str(words_file(["heck"])), "--preset", "beep", "-o", str(out)]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Masked 1 span" in captured.out
    assert f"Output: {out}" in captured.out
    assert f"Report: {out.with_suffix('.json')}" in captured.out
    assert "heck" not in captured.out + captured.err


def test_no_match_run_says_so(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    use_fake: Callable[..., list[str]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_fake([TranscribedWord(" secretword", 1.0, 1.5)])
    code = cli.main(
        [
            str(make_tone()),
            "--words",
            str(words_file(["heck"])),
            "--preset",
            "beep",
            "-o",
            str(tmp_path / "out.wav"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "No forbidden words found" in captured.out
    assert "secretword" not in captured.out + captured.err
    assert "heck" not in captured.out + captured.err


def test_custom_mask_run(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    use_fake: Callable[..., list[str]],
    tmp_path: Path,
) -> None:
    use_fake(HECK)
    mask = make_tone("mask.wav", seconds=0.2, freq=880.0)
    code = cli.main(
        [
            str(make_tone()),
            "--words",
            str(words_file(["heck"])),
            "--mask",
            str(mask),
            "-o",
            str(tmp_path / "out.wav"),
        ]
    )
    assert code == 0


def run_error(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = cli.main(argv)
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ")
    return code, lines[0]


@pytest.fixture
def base(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    use_fake: Callable[..., list[str]],
    tmp_path: Path,
) -> dict[str, str]:
    use_fake(HECK)
    return {
        "input": str(make_tone()),
        "words": str(words_file(["heck"])),
        "output": str(tmp_path / "out.wav"),
    }


def test_missing_words_file(
    base: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nowords.txt"
    code, message = run_error(
        [base["input"], "--words", str(missing), "--preset", "beep", "-o", base["output"]], capsys
    )
    assert code == 1 and "nowords.txt" in message


def test_words_file_without_entries(
    base: dict[str, str],
    words_file: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = words_file(["", "# nothing", "   "], name="empty.txt")
    code, message = run_error(
        [base["input"], "--words", str(empty), "--preset", "beep", "-o", base["output"]], capsys
    )
    assert code == 1 and "no forbidden words found" in message and "empty.txt" in message


@pytest.mark.parametrize(
    "extra",
    [
        ["--preset", "beep", "--mask", "m.wav"],
        [],
        ["--preset", "quack"],
        ["--preset", "beep", "--padding", "-5"],
        ["--preset", "beep", "--padding", "abc"],
        ["--preset", "beep", "--unknown"],
    ],
    ids=["both", "neither", "unknown-preset", "negative-padding", "bad-padding", "unknown-arg"],
)
def test_argument_errors_exit_1(
    base: dict[str, str], extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    code, _ = run_error(
        [base["input"], "--words", base["words"], "-o", base["output"], *extra], capsys
    )
    assert code == 1


def test_output_equal_to_input(
    base: dict[str, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    src = Path(base["input"])
    before = src.read_bytes()
    code, message = run_error(
        [base["input"], "--words", base["words"], "--preset", "beep", "-o", base["input"]], capsys
    )
    assert code == 1 and "overwrite the input" in message
    monkeypatch.chdir(src.parent)
    code, _ = run_error(
        [base["input"], "--words", base["words"], "--preset", "beep", "-o", f"./x/../{src.name}"],
        capsys,
    )
    assert code == 1
    assert src.read_bytes() == before


@pytest.mark.parametrize("target", ["output", "input"])
def test_report_colliding_with_output_or_input(
    base: dict[str, str], target: str, capsys: pytest.CaptureFixture[str]
) -> None:
    Path(base["input"]).parent.joinpath("x").mkdir(exist_ok=True)
    code, _ = run_error(
        [
            base["input"],
            "--words",
            base["words"],
            "--preset",
            "beep",
            "-o",
            base["output"],
            "--report",
            base[target],
        ],
        capsys,
    )
    assert code == 1
    assert not Path(base["output"]).exists()


def test_missing_output_directory(
    base: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, message = run_error(
        [
            base["input"],
            "--words",
            base["words"],
            "--preset",
            "beep",
            "-o",
            str(tmp_path / "nodir" / "out.wav"),
        ],
        capsys,
    )
    assert code == 1 and "nodir" in message


def test_missing_input(
    base: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, message = run_error(
        [
            str(tmp_path / "ghost.wav"),
            "--words",
            base["words"],
            "--preset",
            "beep",
            "-o",
            base["output"],
        ],
        capsys,
    )
    assert code == 1 and "ghost.wav" in message


def test_missing_mask_file(
    base: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, message = run_error(
        [
            base["input"],
            "--words",
            base["words"],
            "--mask",
            str(tmp_path / "quack.wav"),
            "-o",
            base["output"],
        ],
        capsys,
    )
    assert code == 1 and "quack.wav" in message


def test_processing_error_exit_2(
    base: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Broken:
        def transcribe(self, *args: object) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "WhisperTranscriber", lambda model: Broken())
    code, _ = run_error(
        [base["input"], "--words", base["words"], "--preset", "beep", "-o", base["output"]], capsys
    )
    assert code == 2
    assert not Path(base["output"]).exists()


def test_zero_padding_masks_exact_word(
    base: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli.main(
            [
                base["input"],
                "--words",
                base["words"],
                "--preset",
                "beep",
                "-o",
                base["output"],
                "--padding",
                "0",
            ]
        )
        == 0
    )
    original = sf.read(base["input"], dtype="int32")[0]
    masked = sf.read(base["output"], dtype="int32")[0]
    diff = np.flatnonzero(original != masked)
    assert diff.min() >= 32000 and diff.max() < 40000
    report = json.loads(Path(base["output"]).with_suffix(".json").read_text())
    assert report == [{"word": "heck", "start": 2.0, "end": 2.5}]


def test_custom_report_path(
    base: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "custom.json"
    assert (
        cli.main(
            [
                base["input"],
                "--words",
                base["words"],
                "--preset",
                "beep",
                "-o",
                base["output"],
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert json.loads(report.read_text())[0]["word"] == "heck"
    assert not Path(base["output"]).with_suffix(".json").exists()
    assert f"Report: {report}" in capsys.readouterr().out


def test_lang_and_model_reach_the_transcriber(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    fake_transcriber: type,
    tmp_path: Path,
) -> None:
    fake = fake_transcriber(HECK)
    models: list[str] = []
    monkeypatch.setattr(pipeline, "WhisperTranscriber", lambda model: models.append(model) or fake)
    assert (
        cli.main(
            [
                str(make_tone()),
                "--words",
                str(words_file(["heck"])),
                "--preset",
                "beep",
                "-o",
                str(tmp_path / "o.wav"),
                "--lang",
                "es",
                "--model",
                "tiny",
            ]
        )
        == 0
    )
    assert models == ["tiny"]
    assert fake.calls[0][1] == "es"


def test_help_documents_options_defaults_and_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    for option in (
        "--words",
        "--mask",
        "--preset",
        "--output",
        "--model",
        "--lang",
        "--padding",
        "--report",
    ):
        assert option in text
    assert "small" in text and "80" in text
    assert "Exit codes: 0 success, 1 invalid input, 2 processing error" in text


@pytest.mark.parametrize("source", ["preset", "mask"])
def test_cli_and_api_outputs_are_byte_identical(
    make_tone: Callable[..., Path],
    words_file: Callable[..., Path],
    fake_transcriber: type,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: str,
) -> None:
    words = [TranscribedWord(" heck", 1.0, 1.4), TranscribedWord(" heck", 3.0, 3.3)]
    src, wordlist = make_tone(channels=2), words_file(["heck"])
    mask = make_tone("mask.wav", seconds=0.15, freq=660.0)
    option = {"preset": ["--preset", "noise"], "mask": ["--mask", str(mask)]}[source]
    kwargs = {"preset": {"preset": "noise"}, "mask": {"mask_path": mask}}[source]
    monkeypatch.setattr(pipeline, "WhisperTranscriber", lambda model: fake_transcriber(words))
    cli_out, api_out = tmp_path / "cli.wav", tmp_path / "api.wav"
    assert cli.main([str(src), "--words", str(wordlist), *option, "-o", str(cli_out)]) == 0
    pipeline.process_audio(src, wordlist, api_out, transcriber=fake_transcriber(words), **kwargs)
    assert cli_out.read_bytes() == api_out.read_bytes()
    assert cli_out.with_suffix(".json").read_bytes() == api_out.with_suffix(".json").read_bytes()


def test_model_default_comes_from_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["in.wav", "--words", "w.txt", "--preset", "beep", "-o", "out.wav"]
    monkeypatch.delenv("BLEEPER_MODEL", raising=False)
    assert cli.build_parser().parse_args(args).model == "small"
    monkeypatch.setenv("BLEEPER_MODEL", "base")
    assert cli.build_parser().parse_args(args).model == "base"
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--help"])
    assert "--model" in capsys.readouterr().out
