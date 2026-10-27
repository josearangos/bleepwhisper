import importlib.util
import json
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
import soundfile as sf

RATE = 8000


def load_script() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "smoke_check.py"
    spec = importlib.util.spec_from_file_location("smoke_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke_check = load_script()


def tone(seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def run(
    tmp_path: Path,
    output: np.ndarray,
    report: list[dict[str, object]] | None = None,
    word: str = "fox",
) -> int:
    sf.write(tmp_path / "in.wav", tone(), RATE, subtype="FLOAT")
    sf.write(tmp_path / "out.wav", output, RATE, subtype="FLOAT")
    entries = [{"word": "Fox.", "start": 0.25, "end": 0.5}] if report is None else report
    (tmp_path / "out.json").write_text(json.dumps(entries))
    args = [str(tmp_path / name) for name in ("in.wav", "out.wav", "out.json")]
    return smoke_check.main([*args, word])


def masked() -> np.ndarray:
    audio = tone()
    audio[2000:4000] = 0.0
    return audio


def test_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, masked()) == 0
    assert "verify: OK" in capsys.readouterr().out


def test_frame_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, masked()[:-10]) == 1
    assert "FAIL: (b)" in capsys.readouterr().err


def test_word_missing_from_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, masked(), report=[{"word": "dog", "start": 0.25, "end": 0.5}]) == 1
    assert "FAIL: (c)" in capsys.readouterr().err


def test_output_equals_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, tone()) == 1
    assert "FAIL: (d)" in capsys.readouterr().err
