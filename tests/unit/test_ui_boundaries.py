"""Layering rules: Gradio stays in app.py; no audio logic in the UI package."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

UI_DIR = Path(__file__).parents[2] / "src/bleeper/ui"
FORBIDDEN = {"soundfile", "numpy.fft", "subprocess"}


@pytest.mark.parametrize(
    "module",
    ["bleeper.ui.jobs", "bleeper.ui.submit", "bleeper.ui.worker", "bleeper.core", "bleeper.cli"],
)
def test_module_does_not_import_gradio(module: str) -> None:
    code = f"import sys, {module}; sys.exit('gradio' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("path", sorted(UI_DIR.glob("*.py")), ids=lambda p: p.name)
def test_no_audio_logic_in_ui(path: Path) -> None:
    names = imported_names(path)
    assert not {n for n in names if n in FORBIDDEN or n.startswith("numpy.fft")}
    assert "ffmpeg" not in path.read_text(encoding="utf-8")
    if path.name != "app.py":
        assert not {n for n in names if n == "numpy" or n.startswith("numpy.")}
