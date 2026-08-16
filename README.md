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

The web app (`song_to_movie/webapp/`) runs the whole pipeline itself from an
upload - it's the easiest way to use this from a phone, with the actual
processing happening on a machine that has ffmpeg/Demucs/torch installed
(a Raspberry Pi, a desktop, whatever you run it on).

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

### Option A: command line

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

### Option B: the web app (upload from your phone, process elsewhere)

```bash
python -m song_to_movie.webapp runs/ --host 0.0.0.0 --port 5000
```

Open `http://<the-machine's-address>:5000` in a browser (see below for
reaching it from your phone). From there you can:

1. Upload a song file and paste its lyrics - no CLI/SSH access needed.
2. Watch it process (the page polls status and shows the current stage).
3. Once done, preview the clip video against the vocal/instrumental stems
   with an independent volume slider each, and hit **Export mix** to render
   the blend with ffmpeg (sliders can go above 1x in the exported file,
   even though live browser preview is capped at unity gain - a browser
   limitation, not this app's).
4. Download the result from the link the export gives you.

Each run's uploads and output live under `runs/<run_id>/`; the run list on
the home page survives a server restart (it's reconstructed from what's on
disk), though progress on a run that was still processing when the server
stopped is lost.

## Running it from your phone (Raspberry Pi + Tailscale)

This is the right setup for phone use: the pipeline needs ffmpeg, Demucs
(PyTorch), and real disk space for clip downloads, none of which a phone
can do - so run the web app on the Pi and just reach it from your phone's
browser.

**You don't need nginx or a Cloudflare tunnel for this.** Tailscale already
gives your phone a private, encrypted connection straight to the Pi; a
public-facing reverse proxy would only be needed if you wanted this
reachable from the open internet, which isn't necessary for personal use -
and this tool operates on copyrighted movie/song material as input, so
keeping it off the public internet entirely is also the safer default. (If
"nginx + Cloudflare" was about a *different*, unrelated self-hosting setup
you already run on the Pi - e.g. Cloudflare Tunnel for other services - note
that's a separate thing from the Cloudflare bot-protection getyarn.io itself
uses, described above; you don't need to combine the two.)

1. Install Tailscale on the Pi and on your phone, and sign in to the same
   Tailscale account on both (`https://tailscale.com/download`).
2. On the Pi, run the web app bound to all interfaces so Tailscale can
   reach it:
   ```bash
   python -m song_to_movie.webapp runs/ --host 0.0.0.0 --port 5000
   ```
3. On your phone (with the Tailscale app connected), open
   `http://<pi-tailscale-name>:5000` - the Tailscale app shows the Pi's
   MagicDNS name (or `tailscale ip` on the Pi gives its Tailscale IP if you
   prefer that).
4. Optional: for HTTPS without any extra infrastructure, `tailscale serve
   https / 5000` on the Pi puts the app behind Tailscale's own MagicDNS
   HTTPS certificate - still tailnet-only, nothing exposed publicly.

Keep the web app itself off the public internet (no Funnel, no port
forwarding, no public reverse proxy) - Tailscale's private network is all
you need for phone access, and it avoids exposing a tool that downloads
copyrighted media to anyone but you.

## Tests

The alignment fallback, timeline-building, and clip-search HTML parser are
pure logic with no network/ffmpeg/torch dependency, and are covered by
unit tests:

```bash
pip install -e ".[dev]"
pytest
```
