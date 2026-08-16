from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .models import AlignedWord, TimelineSegment, YarnResult


def build_timeline(
    words: List[AlignedWord],
    clip_lookup: Dict[str, Optional[YarnResult]],
    clip_path_for: Callable[[Optional[YarnResult]], Optional[str]],
) -> List[TimelineSegment]:
    """Turn aligned lyric words into an ordered list of video timeline segments.

    `clip_lookup` maps each word's lowercased text to the best-matching
    YarnResult found for it (or None if no result was found). `clip_path_for`
    resolves a YarnResult to a locally downloaded/trimmed clip file, so this
    function stays pure and network/ffmpeg-free and is safe to unit test.
    Words with zero duration (alignment artifacts) are dropped.
    """
    segments: List[TimelineSegment] = []
    for word in words:
        if word.duration <= 0:
            continue
        result = clip_lookup.get(word.text.lower())
        clip_path = clip_path_for(result)
        segments.append(
            TimelineSegment(
                start=word.start,
                end=word.end,
                word=word.text,
                clip_path=clip_path,
                source_query=result,
            )
        )
    return segments


def resolve_missing_clips(
    segments: List[TimelineSegment], strategy: str = "hold_previous"
) -> List[TimelineSegment]:
    """Fill segments with no matched clip using a fallback strategy.

    - "hold_previous": reuse the nearest earlier clip (or the nearest later
      one, for a gap at the very start), producing a freeze-frame effect.
    - "leave_blank": leave clip_path as None; the video assembler should
      then render a placeholder for these segments instead of skipping them.
    """
    if strategy not in ("hold_previous", "leave_blank"):
        raise ValueError(f"unknown strategy: {strategy!r}")
    if strategy == "leave_blank":
        return segments

    resolved = list(segments)

    last_clip: Optional[str] = None
    for i, seg in enumerate(resolved):
        if seg.clip_path is not None:
            last_clip = seg.clip_path
        elif last_clip is not None:
            resolved[i] = TimelineSegment(
                start=seg.start,
                end=seg.end,
                word=seg.word,
                clip_path=last_clip,
                source_query=seg.source_query,
            )

    # Backfill any leading gap (no earlier clip existed yet) using the
    # nearest clip that appears later in the timeline.
    next_clip: Optional[str] = None
    for i in range(len(resolved) - 1, -1, -1):
        seg = resolved[i]
        if seg.clip_path is not None:
            next_clip = seg.clip_path
        elif next_clip is not None:
            resolved[i] = TimelineSegment(
                start=seg.start,
                end=seg.end,
                word=seg.word,
                clip_path=next_clip,
                source_query=seg.source_query,
            )

    return resolved


def coverage_ratio(segments: List[TimelineSegment]) -> float:
    """Fraction of segments that matched a real clip (not just a fallback)."""
    if not segments:
        return 0.0
    matched = sum(1 for s in segments if s.source_query is not None)
    return matched / len(segments)
