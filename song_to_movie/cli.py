from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional

from .alignment import even_split_alignment, forced_align, tokenize_lyrics
from .clip_cache import download_clip
from .mixer import MixLevels, render_mix
from .models import YarnResult
from .separation import separate_stems
from .timeline import build_timeline, coverage_ratio, resolve_missing_clips
from .video_assembly import assemble_video
from .yarn_client import YarnBlockedError, YarnClient

log = logging.getLogger("song_to_movie")


def _audio_duration(path: Path) -> float:
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
    return float(result.stdout.strip())


def run_pipeline(
    song_path: Path,
    lyrics_path: Path,
    out_dir: Path,
    demucs_model: str = "htdemucs",
    use_forced_alignment: bool = True,
    yarn_cookies: Optional[Dict[str, str]] = None,
    mix_levels: MixLevels = MixLevels(),
    render_default_mix: bool = True,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Path:
    """Run the full song -> movie-clip video pipeline.

    Returns the path to the final mixed video (or, if `render_default_mix`
    is False, the path to the clip-only assembly, so a caller such as the
    interactive web mixer can produce the final mix itself once the user
    has chosen volume levels). `on_progress`, if given, is called with a
    short human-readable stage description at each major step - the web
    app uses this to show live progress for a run kicked off from a phone.
    """

    def report(stage: str) -> None:
        log.info(stage)
        if on_progress:
            on_progress(stage)

    out_dir.mkdir(parents=True, exist_ok=True)
    lyrics_text = lyrics_path.read_text()
    words = tokenize_lyrics(lyrics_text)
    if not words:
        raise ValueError(f"no words found in {lyrics_path}")

    report(f"separating vocals/instrumental with demucs ({demucs_model})...")
    stems = separate_stems(song_path, out_dir / "stems", model=demucs_model)

    report(f"aligning {len(words)} lyric words to the vocal track...")
    if use_forced_alignment:
        aligned = forced_align(stems.vocals, words)
    else:
        aligned = even_split_alignment(words, _audio_duration(stems.vocals))

    report("searching getyarn.io for a movie clip per word...")
    client = YarnClient(cookies=yarn_cookies)
    clip_cache_dir = out_dir / "clip_cache"
    clip_lookup: Dict[str, Optional[YarnResult]] = {}
    clip_paths: Dict[str, Optional[str]] = {}
    for word in {w.lower() for w in words}:
        try:
            results = client.search(word, limit=1)
        except YarnBlockedError as exc:
            log.warning("skipping %r: %s", word, exc)
            results = []
        if not results:
            clip_lookup[word] = None
            clip_paths[word] = None
            continue
        best = results[0]
        clip_lookup[word] = best
        try:
            local_path = download_clip(best, clip_cache_dir, session=client.session)
            clip_paths[word] = str(local_path)
        except Exception as exc:  # noqa: BLE001 - keep the pipeline going
            log.warning("failed to download clip for %r: %s", word, exc)
            clip_paths[word] = None

    segments = build_timeline(
        aligned,
        clip_lookup,
        clip_path_for=lambda result: clip_paths.get(result.query) if result else None,
    )
    segments = resolve_missing_clips(segments, strategy="hold_previous")
    report(f"matched clips for {coverage_ratio(segments) * 100:.0f}% of lyric words")

    report("assembling clip video...")
    clip_video = assemble_video(segments, out_dir / "assembly", out_dir / "clips_only.mp4")

    if not render_default_mix:
        report("ready to mix")
        return clip_video

    report("rendering final mix...")
    final_path = render_mix(
        clip_video,
        stems.vocals,
        stems.instrumental,
        out_dir / "final.mp4",
        levels=mix_levels,
    )
    report("done")
    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Turn a song into movie clips: one clip per lyric word, timed to "
            "the original vocal, with the song's vocal and instrumental kept "
            "as separately mixable stems."
        )
    )
    parser.add_argument("song", type=Path, help="path to a song audio file you have rights to use")
    parser.add_argument(
        "lyrics", type=Path, help="path to a plain-text lyrics file (your own transcript)"
    )
    parser.add_argument("--out", type=Path, default=Path("output"), help="output directory")
    parser.add_argument("--demucs-model", default="htdemucs")
    parser.add_argument(
        "--no-forced-alignment",
        action="store_true",
        help=(
            "use a fast, dependency-free proportional alignment instead of "
            "torchaudio forced alignment"
        ),
    )
    parser.add_argument(
        "--no-default-mix",
        action="store_true",
        help="skip rendering a default mix; use the webapp mixer afterward instead",
    )
    parser.add_argument("--vocals-vol", type=float, default=1.0)
    parser.add_argument("--instrumental-vol", type=float, default=1.0)
    parser.add_argument("--clips-vol", type=float, default=1.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    run_pipeline(
        song_path=args.song,
        lyrics_path=args.lyrics,
        out_dir=args.out,
        demucs_model=args.demucs_model,
        use_forced_alignment=not args.no_forced_alignment,
        render_default_mix=not args.no_default_mix,
        mix_levels=MixLevels(
            vocals=args.vocals_vol,
            instrumental=args.instrumental_vol,
            clips=args.clips_vol,
        ),
    )


if __name__ == "__main__":
    main()
