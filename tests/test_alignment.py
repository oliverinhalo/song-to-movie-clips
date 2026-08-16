from song_to_movie.alignment import even_split_alignment, tokenize_lyrics


def test_tokenize_lyrics_splits_on_words_and_ignores_punctuation():
    assert tokenize_lyrics("Hello, world! It's fine.") == ["Hello", "world", "It's", "fine"]


def test_tokenize_lyrics_empty_string():
    assert tokenize_lyrics("") == []


def test_even_split_alignment_covers_full_duration_in_order():
    words = ["a", "bb", "ccc"]
    aligned = even_split_alignment(words, total_duration=6.0)

    assert [w.text for w in aligned] == words
    assert aligned[0].start == 0.0
    assert aligned[-1].end == 6.0
    for earlier, later in zip(aligned, aligned[1:]):
        assert earlier.end == later.start

    # Longer words get a proportionally longer slot.
    assert aligned[2].duration > aligned[0].duration


def test_even_split_alignment_empty_words():
    assert even_split_alignment([], total_duration=10.0) == []
