"""Check a masked output against its input and report. Runs inside the image.

Usage: python smoke_check.py INPUT OUTPUT REPORT WORD
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def _fail(check: str, detail: str) -> int:
    print(f"FAIL: {check}: {detail}", file=sys.stderr)
    return 1


def _normalize(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Bleeper smoke-test result.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("word")
    args = parser.parse_args(argv)

    for path in (args.output, args.report):
        if not path.is_file():
            return _fail("(a) files exist", f"{path} is missing")

    before, after = sf.info(str(args.input)), sf.info(str(args.output))
    for field in ("frames", "samplerate", "channels"):
        if getattr(before, field) != getattr(after, field):
            return _fail(
                "(b) audio format preserved",
                f"{field} {getattr(before, field)} != {getattr(after, field)}",
            )

    entries = json.loads(args.report.read_text(encoding="utf-8"))
    wanted = _normalize(args.word)
    matches = [e for e in entries if _normalize(str(e.get("word", ""))) == wanted]
    if not matches:
        found = [e.get("word") for e in entries]
        return _fail("(c) word reported", f"'{args.word}' not in report entries {found}")

    entry = matches[0]
    rate = before.samplerate
    start, end = int(entry["start"] * rate), int(entry["end"] * rate)
    in_seg, _ = sf.read(str(args.input), start=start, stop=end, always_2d=True)
    out_seg, _ = sf.read(str(args.output), start=start, stop=end, always_2d=True)
    if np.array_equal(in_seg, out_seg):
        return _fail("(d) span masked", f"audio is unchanged in {entry['start']}-{entry['end']} s")

    print("verify: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
