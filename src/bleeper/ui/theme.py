"""'Censor bar' dark theme for the web UI: the only place colors are defined."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import gradio as gr
from gradio.components.dataframe import DataframeData

from bleeper.ui.jobs import JobStatus

BACKGROUND = "#0F1115"
CARD = "#181B22"
TEXT = "#E8EAED"
ACCENT = "#C6FF3D"
ON_ACCENT = "#0F1115"
RUNNING = "#FFB800"
FAILED = "#FF4D4D"
QUEUED = "#8A93A3"
MUTED = QUEUED
BORDER = "#2A2F3A"
ACCENT_HOVER = "#D4FF6B"

# System fonts only: no font file is ever requested.
SYSTEM_FONTS = ["ui-sans-serif", "system-ui", "sans-serif"]
SYSTEM_MONO = ["ui-monospace", "monospace"]

STATUS_COLORS: dict[str, str] = {
    JobStatus.QUEUED.value: QUEUED,
    JobStatus.RUNNING.value: RUNNING,
    JobStatus.DONE.value: ACCENT,
    JobStatus.FAILED.value: FAILED,
}


def _group(value: str, *names: str) -> dict[str, str]:
    return dict.fromkeys(names, value)


THEME_COLORS: dict[str, str] = {
    # Page
    **_group(BACKGROUND, "body_background_fill", "background_fill_primary"),
    # Surfaces
    **_group(
        CARD,
        "background_fill_secondary",
        "block_background_fill",
        "panel_background_fill",
        "block_label_background_fill",
        "block_title_background_fill",
        "code_background_fill",
        "stat_background_fill",
        "table_even_background_fill",
        "table_odd_background_fill",
        "checkbox_label_background_fill",
        "checkbox_label_background_fill_hover",
        "checkbox_label_background_fill_selected",
    ),
    # Text
    **_group(
        TEXT,
        "body_text_color",
        "block_label_text_color",
        "block_title_text_color",
        "table_text_color",
        "checkbox_label_text_color",
        "checkbox_label_text_color_selected",
        "accordion_text_color",
    ),
    **_group(
        MUTED,
        "block_info_text_color",
        "body_text_color_subdued",
        "input_placeholder_color",
    ),
    # Borders
    **_group(
        BORDER,
        "border_color_primary",
        "block_border_color",
        "block_label_border_color",
        "input_border_color",
        "input_border_color_hover",
        "table_border_color",
        "panel_border_color",
        "checkbox_border_color",
        "checkbox_label_border_color",
        "color_accent_soft",
        "table_row_focus",
    ),
    # Accent
    **_group(
        ACCENT,
        "color_accent",
        "border_color_accent",
        "border_color_accent_subdued",
        "input_border_color_focus",
        "checkbox_border_color_focus",
        "checkbox_border_color_selected",
        "checkbox_background_color_selected",
        "checkbox_label_border_color_selected",
        "loader_color",
        "slider_color",
        "link_text_color",
        "link_text_color_active",
        "link_text_color_hover",
        "link_text_color_visited",
    ),
    # Inputs
    **_group(
        BACKGROUND,
        "input_background_fill",
        "input_background_fill_focus",
        "input_background_fill_hover",
        "checkbox_background_color",
        "checkbox_background_color_hover",
        "checkbox_background_color_focus",
    ),
    # Primary button
    "button_primary_background_fill": ACCENT,
    "button_primary_background_fill_hover": ACCENT_HOVER,
    "button_primary_border_color": ACCENT,
    "button_primary_border_color_hover": ACCENT_HOVER,
    "button_primary_text_color": ON_ACCENT,
    "button_primary_text_color_hover": ON_ACCENT,
    # Secondary button
    "button_secondary_background_fill": CARD,
    "button_secondary_background_fill_hover": BORDER,
    "button_secondary_border_color": BORDER,
    "button_secondary_border_color_hover": BORDER,
    "button_secondary_text_color": TEXT,
    "button_secondary_text_color_hover": TEXT,
    # Cancel button ("Delete job"): red on BORDER would be only 4.1:1, so hover fills red
    "button_cancel_background_fill": CARD,
    "button_cancel_background_fill_hover": FAILED,
    "button_cancel_border_color": FAILED,
    "button_cancel_border_color_hover": FAILED,
    "button_cancel_text_color": FAILED,
    "button_cancel_text_color_hover": ON_ACCENT,
    # Errors
    "error_background_fill": CARD,
    "error_border_color": FAILED,
    "error_text_color": FAILED,
    "error_icon_color": FAILED,
}

# Variables Gradio defines once for both modes (no `_dark` twin).
SINGLE_MODE = {"color_accent"}

THEME = gr.themes.Base(font=SYSTEM_FONTS, font_mono=SYSTEM_MONO).set(
    **THEME_COLORS,
    **{f"{name}_dark": value for name, value in THEME_COLORS.items() if name not in SINGLE_MODE},
)

# Native scrollbars and form controls render dark; not expressible as theme variables.
CSS = ":root { color-scheme: dark; }"

WAVEFORM = gr.WaveformOptions(waveform_color=MUTED, waveform_progress_color=ACCENT)


def color_status(
    postprocess: Callable[[Any], DataframeData], column: int
) -> Callable[[Any], DataframeData]:
    """Wrap a Dataframe's postprocess to color the status word in `column`, values unchanged."""

    @wraps(postprocess)
    def wrapper(value: Any) -> DataframeData:  # noqa: ANN401
        result = postprocess(value)
        if result.data:
            result.metadata = {
                "styling": [
                    [
                        f"color: {STATUS_COLORS[row[i]]}"
                        if i == column and row[i] in STATUS_COLORS
                        else ""
                        for i in range(len(row))
                    ]
                    for row in result.data
                ]
            }
        return result

    return wrapper
