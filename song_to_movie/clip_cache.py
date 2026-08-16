from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import requests

from .models import YarnResult


def cache_key(result: YarnResult) -> str:
    return hashlib.sha1(result.clip_url.encode("utf-8")).hexdigest()[:16]


def download_clip(
    result: YarnResult,
    cache_dir: Path,
    session: Optional[requests.Session] = None,
    timeout: float = 30.0,
) -> Path:
    """Download a clip's source video into `cache_dir`, reusing any cached copy.

    Returns the local file path. Downloads are content-addressed by the
    clip URL, so re-running the pipeline on the same song does not
    re-fetch clips it already has.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{cache_key(result)}.mp4"
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    sess = session or requests.Session()
    tmp = dest.with_suffix(".part")
    with sess.get(result.clip_url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    tmp.rename(dest)
    return dest
