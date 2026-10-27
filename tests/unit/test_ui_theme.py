"""Tests for the Censor bar theme: palette in one place, always dark, accessible, status colors."""

from __future__ import annotations

import re
from pathlib import Path

import gradio as gr
import pytest

from bleeper.ui import theme
from bleeper.ui.jobs import JobStatus

UI_DIR = Path(theme.__file__).parent
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_colors_are_defined_only_in_theme_module() -> None:
    offenders = [
        path.name
        for path in UI_DIR.glob("*.py")
        if path.name != "theme.py" and HEX.search(path.read_text())
    ]
    assert offenders == []


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("TEXT", "BACKGROUND"),
        ("TEXT", "CARD"),
        ("ACCENT", "CARD"),
        ("RUNNING", "CARD"),
        ("QUEUED", "CARD"),
        ("FAILED", "CARD"),
        ("ON_ACCENT", "ACCENT"),
        ("ON_ACCENT", "ACCENT_HOVER"),
        ("TEXT", "BORDER"),
        ("ON_ACCENT", "FAILED"),
    ],
)
def test_text_contrast_meets_wcag_aa(foreground: str, background: str) -> None:
    assert contrast(getattr(theme, foreground), getattr(theme, background)) >= 4.5


def test_light_and_dark_values_are_identical() -> None:
    for name in theme.THEME_COLORS:
        if name in theme.SINGLE_MODE:
            continue
        assert getattr(theme.THEME, name) == getattr(theme.THEME, f"{name}_dark"), name


def test_no_gradio_orange_in_theme() -> None:
    orange = {
        getattr(gr.themes.colors.orange, f"c{n}").lower()
        for n in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)
    }
    for name, value in vars(theme.THEME).items():
        if ("color" in name or "fill" in name) and isinstance(value, str):
            assert value.lower() not in orange, name


def test_fonts_are_plain_system_strings() -> None:
    assert all(isinstance(font, str) for font in theme.THEME._font)
    assert all(isinstance(font, str) for font in theme.THEME._font_mono)


def test_css_is_inline_dark_and_offline() -> None:
    assert "color-scheme: dark" in theme.CSS
    for forbidden in ("url(", "@import", "http"):
        assert forbidden not in theme.CSS


def test_primary_button_is_lime() -> None:
    assert theme.THEME.button_primary_background_fill == theme.ACCENT
    assert theme.THEME.button_primary_text_color == theme.ON_ACCENT


def test_status_colors_cover_every_status() -> None:
    assert theme.STATUS_COLORS == {
        "queued": theme.QUEUED,
        "running": theme.RUNNING,
        "done": theme.ACCENT,
        "failed": theme.FAILED,
    }
    assert set(theme.STATUS_COLORS) == {status.value for status in JobStatus}


def test_color_status_styles_only_the_status_cell() -> None:
    df = gr.Dataframe(headers=["ID", "Status"], interactive=False)
    styled = theme.color_status(df.postprocess, 1)
    rows = [[f"id{i}", s] for i, s in enumerate(theme.STATUS_COLORS)]
    hint = ["", "No jobs yet. Submit an audio file above."]
    out = styled(rows + [hint])
    assert out.data == rows + [hint]
    styling = out.metadata["styling"]
    for r, (_, status) in enumerate(rows):
        assert styling[r] == ["", f"color: {theme.STATUS_COLORS[status]}"]
    assert styling[-1] == ["", ""]


def test_color_status_handles_empty_table() -> None:
    df = gr.Dataframe(headers=["ID", "Status"], interactive=False)
    assert theme.color_status(df.postprocess, 1)([]).metadata is None


def test_waveform_uses_accent_for_progress() -> None:
    assert theme.WAVEFORM.waveform_progress_color == theme.ACCENT
    assert theme.WAVEFORM.waveform_color == theme.MUTED
