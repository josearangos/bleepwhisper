"""Build and atomically write the JSON report."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from bleeper.core.atomic import temp_file_for
from bleeper.core.errors import ProcessingError
from bleeper.core.models import ReportEntry, Span


def to_report(spans: Sequence[Span], sample_rate: int) -> list[ReportEntry]:
    return [
        ReportEntry(
            " ".join(span.words),
            round(span.start / sample_rate, 3),
            round(span.end / sample_rate, 3),
        )
        for span in sorted(spans, key=lambda s: s.start)
    ]


def write_report(path: Path, entries: Sequence[ReportEntry]) -> None:
    path = Path(path)
    text = json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False) + "\n"
    tmp = temp_file_for(path)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise ProcessingError(
            f"cannot write report '{path}' ({exc.strerror}). Check free space and permissions."
        ) from exc
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
