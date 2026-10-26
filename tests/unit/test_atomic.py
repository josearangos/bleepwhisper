import os
import stat
from pathlib import Path

from bleeper.core.atomic import temp_file_for


def test_temp_file_is_created_next_to_target_with_default_mode(tmp_path: Path) -> None:
    previous = os.umask(0o022)
    try:
        tmp = temp_file_for(tmp_path / "out.wav")
    finally:
        os.umask(previous)
    assert tmp.parent == tmp_path
    assert tmp.name.startswith(".out.wav.") and tmp.suffix == ".tmp"
    assert tmp.read_bytes() == b""
    assert stat.S_IMODE(tmp.stat().st_mode) == 0o644
