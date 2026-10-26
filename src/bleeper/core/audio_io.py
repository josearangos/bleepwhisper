"""Audio decoding (soundfile, ffmpeg for mp3) and atomic WAV writing."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from bleeper.core.atomic import temp_file_for
from bleeper.core.errors import InvalidInputError, ProcessingError

_PCM_SUBTYPES = {"PCM_S8", "PCM_U8", "PCM_16", "PCM_24", "PCM_32"}
_FLOAT_DTYPES = {"FLOAT": "float32", "DOUBLE": "float64"}
_EXTENSIONS = {".wav", ".mp3"}


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    subtype: str

    @property
    def n_samples(self) -> int:
        return int(self.samples.shape[0])

    @property
    def channels(self) -> int:
        return int(self.samples.shape[1])


def load_audio(path: Path, tmp_dir: Path) -> tuple[AudioData, Path]:
    """Decode `path`; return the samples and the file the transcriber should read."""
    path = Path(path)
    if not path.is_file():
        raise InvalidInputError(f"audio file '{path}' not found. Check the path.")
    suffix = path.suffix.lower()
    if suffix not in _EXTENSIONS:
        raise InvalidInputError(
            f"unsupported audio format '{suffix or path.name}' for '{path}'. "
            "Use a .wav or .mp3 file."
        )
    if suffix == ".wav":
        try:
            subtype = sf.info(str(path)).subtype
        except (sf.LibsndfileError, RuntimeError):
            raise InvalidInputError(
                f"cannot read '{path}': not a valid WAV file. Check that the file is not corrupt."
            ) from None
        if subtype in _PCM_SUBTYPES or subtype in _FLOAT_DTYPES:
            return _read_wav(path, subtype), path
    decoded = _ffmpeg_decode(path, Path(tmp_dir))
    return _read_wav(decoded, "PCM_16"), decoded


def _read_wav(path: Path, subtype: str) -> AudioData:
    dtype = _FLOAT_DTYPES.get(subtype, "int32")
    try:
        samples, sample_rate = sf.read(str(path), dtype=dtype, always_2d=True)
    except (sf.LibsndfileError, RuntimeError):
        raise InvalidInputError(
            f"cannot read '{path}': the audio data is corrupt. Check the file."
        ) from None
    return AudioData(samples, int(sample_rate), subtype)


def require_ffmpeg(path: Path) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise InvalidInputError(
            f"ffmpeg is required to read '{path}'. Please install ffmpeg (e.g. `brew install "
            "ffmpeg`) and make sure it is on PATH."
        )
    return ffmpeg


def run_ffmpeg(path: Path, args: list[str], tmp_dir: Path) -> Path:
    """Run ffmpeg on `path` writing a 16-bit WAV into `tmp_dir`; return the new file."""
    ffmpeg = require_ffmpeg(path)
    fd, name = tempfile.mkstemp(suffix=".wav", dir=tmp_dir)
    os.close(fd)
    target = Path(name)
    command = [ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(path), *args, str(target)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        target.unlink(missing_ok=True)
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown"
        if "Invalid data" in result.stderr or "could not find codec" in result.stderr.lower():
            raise InvalidInputError(
                f"cannot decode '{path}': not a valid audio file ({detail}). Check the file."
            )
        raise ProcessingError(f"ffmpeg failed on '{path}' ({detail}). Try re-encoding the file.")
    return target


def _ffmpeg_decode(path: Path, tmp_dir: Path) -> Path:
    return run_ffmpeg(path, ["-acodec", "pcm_s16le", "-f", "wav"], tmp_dir)


def write_wav(path: Path, audio: AudioData) -> None:
    """Write atomically: temp file in the destination directory, then rename."""
    path = Path(path)
    tmp = temp_file_for(path)
    try:
        sf.write(str(tmp), audio.samples, audio.sample_rate, subtype=audio.subtype, format="WAV")
        os.replace(tmp, path)
    except (OSError, sf.LibsndfileError, RuntimeError) as exc:
        tmp.unlink(missing_ok=True)
        raise ProcessingError(
            f"cannot write output '{path}' ({exc}). Check free space and permissions."
        ) from exc
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load_mask(path: Path, sample_rate: int, tmp_dir: Path) -> np.ndarray:
    """Load a custom mask as mono float64 at `sample_rate` (resampled with ffmpeg if needed)."""
    mask, _ = load_audio(path, tmp_dir)
    if mask.sample_rate != sample_rate:
        resampled = run_ffmpeg(
            Path(path), ["-ar", str(sample_rate), "-acodec", "pcm_s16le", "-f", "wav"], tmp_dir
        )
        try:
            mask = _read_wav(resampled, "PCM_16")
        finally:
            resampled.unlink(missing_ok=True)
    samples = mask.samples.astype(np.float64)
    if np.issubdtype(mask.samples.dtype, np.integer):
        samples /= 2.0**31
    return samples.mean(axis=1)
