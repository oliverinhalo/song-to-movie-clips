from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AlignedWord:
    """A single lyric word/token with its timing in the source song."""

    text: str
    start: float  # seconds
    end: float  # seconds

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class YarnResult:
    """One search result returned by the movie-clip finder for a query."""

    query: str
    clip_url: str
    source_title: Optional[str] = None
    quote: Optional[str] = None
    page_url: Optional[str] = None


@dataclass
class TimelineSegment:
    """One slot in the final assembled video: a time range paired with a clip."""

    start: float
    end: float
    word: str
    clip_path: Optional[str]  # local file path, or None if unresolved
    source_query: Optional[YarnResult] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)
