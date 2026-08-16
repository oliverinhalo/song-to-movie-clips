from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .models import YarnResult

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://getyarn.io"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class YarnBlockedError(RuntimeError):
    """Raised when getyarn.io's bot protection rejects a request.

    getyarn.io is fronted by Cloudflare and returns an HTTP 403 challenge
    page to plain scripted requests (verified directly while building this
    tool - every request path, including the homepage, was blocked). This
    client does not attempt to defeat that challenge: no headless-browser
    automation, no CAPTCHA solving, no proxy rotation. If you have solved
    the challenge yourself in an ordinary browser, you can copy the
    resulting cookies (e.g. `cf_clearance`) and pass them to `YarnClient`
    via `cookies=` so your own already-authorized session is reused.
    """


@dataclass
class YarnClient:
    base_url: str = DEFAULT_BASE_URL
    user_agent: str = DEFAULT_USER_AGENT
    cookies: Optional[Dict[str, str]] = None
    timeout: float = 15.0
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.session.headers.setdefault("User-Agent", self.user_agent)
        if self.cookies:
            self.session.cookies.update(self.cookies)

    def search(self, query: str, limit: int = 5) -> List[YarnResult]:
        """Search getyarn.io's movie/TV clip finder for `query`."""
        url = f"{self.base_url}/yarn-find"
        response = self.session.get(url, params={"text": query}, timeout=self.timeout)
        if response.status_code == 403 or "cf-error-details" in response.text:
            raise YarnBlockedError(
                f"getyarn.io rejected the search for {query!r} "
                f"(HTTP {response.status_code}). See YarnBlockedError.__doc__."
            )
        response.raise_for_status()
        results = parse_search_results(response.text, query=query, base_url=self.base_url)
        return results[:limit]


def _find_by_class_hint(container, hint: str):
    """Return the first descendant whose class list contains `hint`."""
    for el in container.find_all(class_=True):
        classes = el.get("class") or []
        if any(hint in c.lower() for c in classes):
            return el
    return None


def parse_search_results(
    html: str, query: str, base_url: str = DEFAULT_BASE_URL
) -> List[YarnResult]:
    """Parse a getyarn.io search-results page into `YarnResult` objects.

    NOTE: this environment could not fetch a live page to confirm
    getyarn.io's exact markup - every request, including a plain GET to the
    homepage, was blocked by Cloudflare (see `YarnBlockedError`). The parser
    below therefore uses a deliberately generic strategy: any `<video>` /
    `<source>` element on the page is treated as a clip result, with the
    nearest enclosing link/container searched for a title/quote by class
    name, rather than hard-coded site-specific selectors that could be
    wrong. It is covered by `tests/test_yarn_client.py` against a
    synthetic fixture, not a real captured page. If it doesn't line up with
    getyarn.io's actual structure, save a real results page with
    `YarnClient(...).session.get(...)` from your own browser session and
    adjust the selectors here - the rest of the pipeline only depends on
    the `YarnResult` objects this function returns, not on its internals.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[YarnResult] = []
    seen_urls = set()

    for video in soup.find_all("video"):
        clip_url = video.get("src")
        if not clip_url:
            source = video.find("source")
            clip_url = source.get("src") if source else None
        if not clip_url or clip_url in seen_urls:
            continue
        seen_urls.add(clip_url)

        if clip_url.startswith("//"):
            clip_url = "https:" + clip_url
        elif clip_url.startswith("/"):
            clip_url = base_url + clip_url

        link_el = video.find_parent("a", href=True)
        page_url = link_el["href"] if link_el else None
        if page_url and page_url.startswith("/"):
            page_url = base_url + page_url

        container = link_el or video.find_parent(["div", "li", "article"]) or video

        quote_el = _find_by_class_hint(container, "quote")
        quote = quote_el.get_text(strip=True) if quote_el else None
        title_el = _find_by_class_hint(container, "title")
        source_title = title_el.get_text(strip=True) if title_el else None

        results.append(
            YarnResult(
                query=query,
                clip_url=clip_url,
                source_title=source_title,
                quote=quote,
                page_url=page_url,
            )
        )

    if not results:
        log.warning("no <video> clip results parsed for query %r", query)
    return results
