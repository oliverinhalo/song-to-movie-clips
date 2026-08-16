from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List

from .models import TimelineSegment

MIN_CLIP_DURATION = 0.15


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} is not installed or not on PATH.")


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float(result.stdout.strip() or 0.0)
    if duration <= 0:
        raise RuntimeError(f"could not read duration of {path}")
    return duration


def _fit_clip_duration(src: Path, dest: Path, target_duration: float) -> None:
    """Trim or gently time-stretch `src` so its duration matches
    `target_duration` as closely as possible, writing the result to `dest`.
    """
    target_duration = max(target_duration, MIN_CLIP_DURATION)
    src_duration = _probe_duration(src)

    if src_duration >= target_duration:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-t",
            f"{target_duration:.3f}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(dest),
        ]
    else:
        # Clip is shorter than its slot: slow it down (capped at 2x) rather
        # than looping, to avoid a jarring repeat.
        speed = max(0.5, src_duration / target_duration)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-filter:v",
            f"setpts={1 / speed:.6f}*PTS",
            "-filter:a",
            f"atempo={speed:.6f}",
            "-t",
            f"{target_duration:.3f}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(dest),
        ]
    subprocess.run(cmd, check=True, capture_output=True)


def assemble_video(
    segments: List[TimelineSegment], work_dir: Path, output_path: Path
) -> Path:
    """Fit each segment's clip to its slot duration and concatenate them in
    order into a single video at `output_path`.

    Segments with `clip_path is None` are skipped; run
    `timeline.resolve_missing_clips` first if every word needs a clip.
    """
    _require_tool("ffmpeg")
    _require_tool("ffprobe")
    work_dir.mkdir(parents=True, exist_ok=True)
    fitted_paths: List[Path] = []

    for i, seg in enumerate(segments):
        if seg.clip_path is None:
            continue
        fitted = work_dir / f"seg_{i:04d}.mp4"
        _fit_clip_duration(Path(seg.clip_path), fitted, seg.duration)
        fitted_paths.append(fitted)

    if not fitted_paths:
        raise RuntimeError("no segments had a clip to assemble")

    concat_list = work_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for p in fitted_paths:
            f.write(f"file '{p.resolve()}'\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path
