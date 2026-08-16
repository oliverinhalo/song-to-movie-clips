from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MixLevels:
    """Relative volume for each of the three blendable elements.

    1.0 is unity gain; ffmpeg's `volume` filter accepts values above 1.0
    to amplify a track, unlike an HTML `<audio>`/`<video>` element's
    `.volume` property, which is clamped to the 0.0-1.0 range in-browser.
    """

    vocals: float = 1.0
    instrumental: float = 1.0
    clips: float = 1.0


def render_mix(
    clip_video: Path,
    vocals: Path,
    instrumental: Path,
    output_path: Path,
    levels: MixLevels = MixLevels(),
) -> Path:
    """Blend the assembled clip video's own audio with the song's vocal and
    instrumental stems at independently adjustable volumes, producing one
    final video with the clip video's picture.
    """
    filter_complex = (
        f"[0:a]volume={levels.clips}[a0];"
        f"[1:a]volume={levels.vocals}[a1];"
        f"[2:a]volume={levels.instrumental}[a2];"
        f"[a0][a1][a2]amix=inputs=3:duration=first:dropout_transition=0[aout]"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(clip_video),
            "-i",
            str(vocals),
            "-i",
            str(instrumental),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path
