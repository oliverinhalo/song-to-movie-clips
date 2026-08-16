from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Stems:
    vocals: Path
    instrumental: Path


def separate_stems(song_path: Path, out_dir: Path, model: str = "htdemucs") -> Stems:
    """Split a song into vocal and instrumental stems using Demucs.

    Requires the `demucs` package (`pip install -e ".[separation]"`), which
    in turn needs a working PyTorch install. It is invoked as a subprocess
    rather than imported directly so this module - and anything that only
    needs the `Stems` type - can be imported without pulling in torch.
    """
    if shutil.which("demucs") is None:
        raise RuntimeError(
            "demucs is not installed or not on PATH. Install it with "
            'pip install -e ".[separation]" (see pyproject.toml).'
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "demucs",
            "-n",
            model,
            "--two-stems",
            "vocals",
            "-o",
            str(out_dir),
            str(song_path),
        ],
        check=True,
    )
    stem_dir = out_dir / model / song_path.stem
    vocals = stem_dir / "vocals.wav"
    instrumental = stem_dir / "no_vocals.wav"
    if not vocals.exists() or not instrumental.exists():
        raise RuntimeError(f"demucs did not produce expected output in {stem_dir}")
    return Stems(vocals=vocals, instrumental=instrumental)
