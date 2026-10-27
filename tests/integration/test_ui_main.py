"""`bleeper-ui` launcher: options, missing Gradio, and a local-only, offline launch."""

import os
import sys
from pathlib import Path
from typing import Any

import gradio as gr
import pytest

from bleeper.ui import __main__ as launcher
from bleeper.ui.worker import JobWorker


@pytest.fixture
def launches(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record `launch()` kwargs instead of serving; never start the worker thread."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(gr.Blocks, "launch", lambda self, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(JobWorker, "start", lambda self: None)
    for name in ("GRADIO_ANALYTICS_ENABLED", "GRADIO_TEMP_DIR"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    return calls


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        launcher.main(["--help"])
    assert info.value.code == 0
    out = capsys.readouterr().out
    assert "--port" in out
    assert "--data-dir" in out


def test_missing_gradio(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "gradio", None)
    monkeypatch.setenv("BLEEPER_UI_DATA", str(tmp_path / "data"))
    for name in ("GRADIO_ANALYTICS_ENABLED", "GRADIO_TEMP_DIR"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    assert launcher.main([]) == 1
    assert capsys.readouterr().err.strip() == (
        'error: the web UI needs Gradio. Install it with: pip install "bleeper[ui]"'
    )


def test_env_data_dir(
    monkeypatch: pytest.MonkeyPatch, launches: list[dict[str, Any]], tmp_path: Path
) -> None:
    data = tmp_path / "from-env"
    monkeypatch.setenv("BLEEPER_UI_DATA", str(data))
    assert launcher.main([]) == 0
    assert data.is_dir()
    assert (data / "jobs.json").is_file()
    assert launches[0]["server_port"] == 7860


def test_launch_is_local_and_offline(
    launches: list[dict[str, Any]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stale = tmp_path / "tmp" / "old-upload.wav"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")

    assert launcher.main(["--data-dir", str(tmp_path), "--port", "7999"]) == 0

    (kwargs,) = launches
    assert kwargs["server_name"] == "127.0.0.1"
    assert kwargs["server_port"] == 7999
    assert kwargs["share"] is False
    assert kwargs["quiet"] is True
    assert kwargs["max_file_size"] == "110mb"
    assert "api" not in kwargs["footer_links"]
    assert str(tmp_path) in kwargs["allowed_paths"]
    assert os.environ["GRADIO_ANALYTICS_ENABLED"] == "False"
    assert os.environ["GRADIO_TEMP_DIR"] == str(tmp_path / "tmp")
    assert not stale.exists()
    theme = kwargs["theme"]
    fonts = [*theme._font, *theme._font_mono]
    assert not [font for font in fonts if isinstance(font, gr.themes.GoogleFont)]
    assert all(isinstance(font, str) for font in fonts)
    assert capsys.readouterr().out.strip() == "Bleeper UI running at http://127.0.0.1:7999"


def test_busy_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def busy(self: gr.Blocks, **kwargs: Any) -> None:  # noqa: ANN401
        raise OSError("Cannot find empty port in range: 7860-7860.")

    monkeypatch.setattr(gr.Blocks, "launch", busy)
    monkeypatch.setattr(JobWorker, "start", lambda self: None)
    for name in ("GRADIO_ANALYTICS_ENABLED", "GRADIO_TEMP_DIR"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    assert launcher.main(["--data-dir", str(tmp_path)]) == 1
    assert "--port" in capsys.readouterr().err


def test_defaults_without_env(
    monkeypatch: pytest.MonkeyPatch, launches: list[dict[str, Any]], tmp_path: Path
) -> None:
    for name in ("BLEEPER_UI_HOST", "BLEEPER_UI_PORT", "BLEEPER_UI_MAX_UPLOAD_MB"):
        monkeypatch.delenv(name, raising=False)
    assert launcher.main(["--data-dir", str(tmp_path)]) == 0
    (kwargs,) = launches
    assert kwargs["server_name"] == "127.0.0.1"
    assert kwargs["server_port"] == 7860
    assert kwargs["max_file_size"] == "110mb"


def test_env_sets_host_port_and_limit(
    monkeypatch: pytest.MonkeyPatch,
    launches: list[dict[str, Any]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("BLEEPER_UI_HOST", "0.0.0.0")
    monkeypatch.setenv("BLEEPER_UI_PORT", "8081")
    monkeypatch.setenv("BLEEPER_UI_MAX_UPLOAD_MB", "5")
    assert launcher.main(["--data-dir", str(tmp_path)]) == 0
    (kwargs,) = launches
    assert kwargs["server_name"] == "0.0.0.0"
    assert kwargs["server_port"] == 8081
    assert kwargs["max_file_size"] == "15mb"
    assert capsys.readouterr().out.strip() == "Bleeper UI running at http://0.0.0.0:8081"


def test_explicit_port_beats_env(
    monkeypatch: pytest.MonkeyPatch, launches: list[dict[str, Any]], tmp_path: Path
) -> None:
    monkeypatch.setenv("BLEEPER_UI_PORT", "8081")
    assert launcher.main(["--data-dir", str(tmp_path), "--port", "9000"]) == 0
    assert launches[0]["server_port"] == 9000


def test_invalid_env_port(
    monkeypatch: pytest.MonkeyPatch,
    launches: list[dict[str, Any]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("BLEEPER_UI_PORT", "abc")
    assert launcher.main(["--data-dir", str(tmp_path)]) == 1
    assert "error:" in capsys.readouterr().err
    assert not launches
