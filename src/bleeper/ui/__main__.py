"""Command-line launcher for the web UI: `bleeper-ui` / `python -m bleeper.ui`."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

HOST = "127.0.0.1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bleeper-ui",
        description="Local web UI for Bleeper: mask forbidden words in audio, offline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--port", type=int, default=7860, help="local port to listen on")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("BLEEPER_UI_DATA", "~/.bleeper/ui"),
        metavar="DIR",
        help="where jobs.json and job files live (env: BLEEPER_UI_DATA)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_dir = Path(args.data_dir).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    # Gradio reads these at import time: no analytics, and its upload cache in the data dir.
    cache = data_dir / "tmp"
    shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir()
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    os.environ["GRADIO_TEMP_DIR"] = str(cache)
    try:
        import gradio  # noqa: F401

        from bleeper.ui.app import THEME, build_app
    except ImportError:
        print(
            'error: the web UI needs Gradio. Install it with: pip install "bleeper[ui]"',
            file=sys.stderr,
        )
        return 1
    from bleeper.ui.jobs import JobStore
    from bleeper.ui.worker import JobWorker

    store = JobStore(data_dir)
    store.load()
    worker = JobWorker(store)
    worker.start()
    demo = build_app(store, worker)
    print(f"Bleeper UI running at http://{HOST}:{args.port}")
    try:
        demo.launch(
            server_name=HOST,
            server_port=args.port,
            share=False,
            quiet=True,
            max_file_size="110mb",
            footer_links=["gradio", "settings"],
            allowed_paths=[str(data_dir)],
            theme=THEME,
        )
    except OSError as exc:
        print(
            f"error: cannot listen on port {args.port} ({exc}). "
            "Choose a different port with --port.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
