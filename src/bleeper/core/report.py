"""Build and atomically write the JSON report."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

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
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise ProcessingError(
            f"cannot write report '{path}' ({exc.strerror}). Check free space and permissions."
        ) from exc
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
