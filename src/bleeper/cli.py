"""Command-line interface: parse arguments, call the core, print the result."""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from bleeper.core import PRESETS, InvalidInputError, ProcessingError, process_audio

EXIT_CODES = "Exit codes: 0 success, 1 invalid input, 2 processing error."


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """Argument errors are invalid input (exit 1), not argparse's default exit 2."""

    def error(self, message: str) -> NoReturn:
        raise _UsageError(f"{message}. Run 'bleeper --help' for usage.")


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Show `(default: ...)` only for options that have a real default."""

    def _get_help_string(self, action: argparse.Action) -> str | None:
        if action.default is None or action.default is argparse.SUPPRESS:
            return action.help
        return super()._get_help_string(action)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="bleeper",
        description="Mask forbidden words in an audio file, offline, with faster-whisper.",
        epilog=EXIT_CODES,
        formatter_class=_HelpFormatter,
    )
    parser.add_argument("input", metavar="INPUT", help="input audio, .wav or .mp3 (never modified)")
    parser.add_argument(
        "--words",
        required=True,
        metavar="FILE",
        help="UTF-8 text file, one word or phrase per line; blank lines and # comments ignored",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--mask",
        metavar="FILE",
        help="custom mask sound (.wav/.mp3), looped or trimmed to each span",
    )
    source.add_argument(
        "--preset",
        choices=PRESETS,
        help="built-in mask: beep (1 kHz), tone (400 Hz) or noise (white noise)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        metavar="FILE",
        help="output WAV path; replaced if it exists, must differ from INPUT",
    )
    parser.add_argument("--model", default="small", help="faster-whisper model name or local path")
    parser.add_argument(
        "--lang", metavar="CODE", help="spoken language code, e.g. es or en (default: auto-detect)"
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=80,
        metavar="MS",
        help="milliseconds added before and after each match (integer >= 0)",
    )
    parser.add_argument(
        "--report", metavar="FILE", help="JSON report path (default: OUTPUT with .json suffix)"
    )
    return parser


def _show_progress(stage: str, fraction: float) -> None:
    """Overwrite one stderr line with `[stage] NN%`; silent when stderr is not a terminal."""
    if not sys.stderr.isatty():
        return
    end = "\n" if stage == "done" else ""
    print(f"\r[{stage}] {fraction:4.0%}", end=end, file=sys.stderr, flush=True)


def _end_progress_line() -> None:
    if sys.stderr.isatty():
        print(file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except _UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        result = process_audio(
            args.input,
            args.words,
            args.output,
            mask_path=args.mask,
            preset=args.preset,
            model=args.model,
            language=args.lang,
            padding_ms=args.padding,
            report_path=args.report,
            progress=_show_progress,
        )
    except InvalidInputError as exc:
        _end_progress_line()
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ProcessingError as exc:
        _end_progress_line()
        print(f"error: {exc}", file=sys.stderr)
        return 2
    count = len(result.report)
    if count:
        print(f"Masked {count} span{'s' if count != 1 else ''}.")
    else:
        print("No forbidden words found; output is identical to the input.")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
