"""song_to_movie: turn a song's lyrics into a video of movie clips.

Pipeline: separate vocals/instrumental -> align lyrics to the vocal track ->
find a movie clip per word -> assemble a clip video timed to the original ->
mix the clip audio with the vocal/instrumental stems (independently
adjustable) into a final video.
"""

from .models import AlignedWord, TimelineSegment, YarnResult

__all__ = ["AlignedWord", "TimelineSegment", "YarnResult"]
__version__ = "0.1.0"
