# song_to_movie

Turn a song into a video made of movie/TV clips - one clip per lyric word,
timed to when that word is actually sung - while keeping the song's vocal
and instrumental as separate stems you can blend against the clips'
own audio.

```
song.mp3 + lyrics.txt
   │
   ├─ separation.py   → vocals.wav, instrumental.wav        (Demucs)
   ├─ alignment.py     → per-word start/end times             (torchaudio forced alignment)
   ├─ yarn_client.py   → one movie-clip match per word         (getyarn.io)
   ├─ clip_cache.py    → downloads + caches those clips
   ├─ timeline.py       → lines the clips up against the word timings
   ├─ video_assembly.py → trims/stretches + concatenates the clips
   └─ mixer.py + webapp → blend clip audio / vocals / instrumental → final.mp4
```

## Before you use this

- Only run this on audio and lyrics **you have the rights to use** - your
  own recording, something licensed for remixing, or material in the
  public domain. This tool does not source or embed any copyrighted song
  or movie content itself; it operates on a song file and lyrics transcript
  you supply, and fetches movie clips at run time into a local, gitignored
  cache - nothing copyrighted is checked into this repository.
- The resulting video is built from third-party movie/TV clips. Treat it as
  a personal/parody project, not something to redistribute or monetize
  without checking the rights situation yourself.

## Important: getyarn.io blocks scripted requests

While building this, every request to `getyarn.io` from this environment -
including a plain `GET /` - came back as an HTTP 403 Cloudflare challenge
page ("Sorry, you have been blocked"), not a search result. `yarn_client.py`
detects this and raises `YarnBlockedError` rather than pretending to
succeed. This tool does **not** attempt to defeat that protection (no
headless-browser automation, no CAPTCHA solving, no proxy rotation/IP
rotation).

If you want to use getyarn.io as the clip source:

1. Open `https://getyarn.io` in an ordinary browser yourself and let it
   pass Cloudflare's check.
2. Copy the resulting cookies (e.g. `cf_clearance`) from your browser's dev
   tools.
3. Pass them through: `YarnClient(cookies={"cf_clearance": "..."})`, or
   plug a different clip-search backend into `yarn_client.py` -
   `parse_search_results()` is the only function the rest of the pipeline
   depends on, so any source that can return a list of `YarnResult`s (a
   clip URL + optional title/quote) will work.

`yarn_client.py`'s HTML parser was written against a synthetic fixture
(`tests/fixtures/synthetic_search_results.html`), not a real captured page,
since no page could be fetched to verify the exact markup. It uses a
generic "find any `<video>`/`<source>` tag" strategy rather than
site-specific class names for that reason. If it doesn't match the real
page structure, save a page from your own authorized session and adjust
the selectors in `parse_search_results()`.

## Setup

```bash
cd song_to_movie
python -m venv .venv && source .venv/bin/activate
pip install -e ".[alignment,separation,dev]"
```

You'll also need `ffmpeg`/`ffprobe` on your PATH (system package, e.g.
`apt install ffmpeg` / `brew install ffmpeg`) - they're not pip-installable.

`alignment` and `separation` are optional extras (they pull in PyTorch) -
omit them if you only want to run the parser/timeline unit tests, or if
you'll use `--no-forced-alignment`'s dependency-free fallback aligner.

## Usage

```bash
song-to-movie path/to/song.mp3 path/to/lyrics.txt --out output/ -v
```

This will:

1. Separate `song.mp3` into `vocals.wav` and `instrumental.wav` with Demucs.
2. Force-align `lyrics.txt`'s words against the vocal track.
3. Look up a movie clip per word via `YarnClient` and download it.
4. Build a timeline, filling any unmatched word with the nearest earlier
   clip (freeze-frame) so playback never has a hard gap.
5. Trim/stretch each clip to its word's duration and concatenate them.
6. Mix the clip audio with the vocal/instrumental stems (`--vocals-vol`,
   `--instrumental-vol`, `--clips-vol`) into `output/final.mp4`.

To blend interactively instead of picking fixed volumes up front:

```bash
song-to-movie path/to/song.mp3 path/to/lyrics.txt --out output/ --no-default-mix
python -m song_to_movie.webapp output/
```

Then open `http://localhost:5000` - it previews the clip video, vocal
track, and instrumental track together with a volume slider each, and an
**Export mix** button that renders `output/final_mix.mp4` with ffmpeg at
whatever levels you chose (sliders can go above 1x in the exported file,
even though live browser preview is capped at unity gain).

## Tests

The alignment fallback, timeline-building, and clip-search HTML parser are
pure logic with no network/ffmpeg/torch dependency, and are covered by
unit tests:

```bash
pip install -e ".[dev]"
pytest
```
