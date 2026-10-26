"""Temp files for atomic writes (write to a temp file, then `os.replace` onto the target)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def temp_file_for(path: Path) -> Path:
    """Create an empty temp file next to `path` with the permissions a new file would get.

    `mkstemp` creates files as 0600; after `os.replace` that mode would stick to the output,
    so it is widened to the default `0666 & ~umask`.
    """
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(name, 0o666 & ~umask)
    return Path(name)
