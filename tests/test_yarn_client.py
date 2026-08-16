from pathlib import Path

from song_to_movie.yarn_client import parse_search_results

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_search_results.html"


def test_parse_search_results_extracts_clip_urls():
    html = FIXTURE.read_text()
    results = parse_search_results(html, query="example", base_url="https://getyarn.io")

    assert len(results) == 2

    first = results[0]
    assert first.clip_url == "https://cdn.example.test/yarn-clip/mp4/abc123.mp4"
    assert first.source_title == "Example Movie (2000)"
    assert first.quote == "placeholder quote text"
    assert first.page_url == "https://getyarn.io/yarn-clip/abc123"

    second = results[1]
    assert second.clip_url == "https://getyarn.io/yarn-clip/mp4/def456.mp4"


def test_parse_search_results_handles_no_matches():
    assert parse_search_results("<html><body>no clips here</body></html>", query="x") == []


def test_parse_search_results_dedupes_repeated_clip_urls():
    html = f"""
    <video src="/a.mp4"></video>
    <video src="/a.mp4"></video>
    """
    results = parse_search_results(html, query="dup", base_url="https://getyarn.io")
    assert len(results) == 1
