from song_to_movie.models import AlignedWord, YarnResult
from song_to_movie.timeline import build_timeline, coverage_ratio, resolve_missing_clips


def make_words():
    return [
        AlignedWord("hello", 0.0, 0.5),
        AlignedWord("world", 0.5, 1.0),
        AlignedWord("again", 1.0, 1.5),
    ]


def test_build_timeline_matches_words_to_clips():
    words = make_words()
    lookup = {
        "hello": YarnResult(query="hello", clip_url="http://x/hello.mp4"),
        "world": None,
        "again": YarnResult(query="again", clip_url="http://x/again.mp4"),
    }
    segments = build_timeline(
        words, lookup, clip_path_for=lambda r: f"/cache/{r.query}.mp4" if r else None
    )

    assert [s.word for s in segments] == ["hello", "world", "again"]
    assert segments[0].clip_path == "/cache/hello.mp4"
    assert segments[1].clip_path is None
    assert segments[2].clip_path == "/cache/again.mp4"
    assert segments[0].duration == 0.5


def test_build_timeline_skips_zero_duration_words():
    words = [AlignedWord("oops", 1.0, 1.0), AlignedWord("ok", 1.0, 1.2)]
    segments = build_timeline(words, {}, clip_path_for=lambda r: None)
    assert [s.word for s in segments] == ["ok"]


def test_resolve_missing_clips_hold_previous_fills_gap():
    words = make_words()
    lookup = {
        "hello": YarnResult(query="hello", clip_url="u"),
        "world": None,
        "again": None,
    }
    segments = build_timeline(
        words, lookup, clip_path_for=lambda r: "/cache/hello.mp4" if r else None
    )
    resolved = resolve_missing_clips(segments, strategy="hold_previous")
    assert [s.clip_path for s in resolved] == ["/cache/hello.mp4"] * 3


def test_resolve_missing_clips_backfills_leading_gap():
    words = make_words()
    lookup = {"hello": None, "world": None, "again": YarnResult(query="again", clip_url="u")}
    segments = build_timeline(
        words, lookup, clip_path_for=lambda r: "/cache/again.mp4" if r else None
    )
    resolved = resolve_missing_clips(segments, strategy="hold_previous")
    assert [s.clip_path for s in resolved] == ["/cache/again.mp4"] * 3


def test_resolve_missing_clips_leave_blank_keeps_none():
    words = make_words()
    segments = build_timeline(words, {}, clip_path_for=lambda r: None)
    resolved = resolve_missing_clips(segments, strategy="leave_blank")
    assert all(s.clip_path is None for s in resolved)


def test_resolve_missing_clips_rejects_unknown_strategy():
    segments = build_timeline(make_words(), {}, clip_path_for=lambda r: None)
    try:
        resolve_missing_clips(segments, strategy="bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown strategy")


def test_coverage_ratio():
    words = make_words()
    lookup = {
        "hello": YarnResult(query="hello", clip_url="u"),
        "world": None,
        "again": None,
    }
    segments = build_timeline(words, lookup, clip_path_for=lambda r: "/x.mp4" if r else None)
    assert coverage_ratio(segments) == 1 / 3


def test_coverage_ratio_empty():
    assert coverage_ratio([]) == 0.0
