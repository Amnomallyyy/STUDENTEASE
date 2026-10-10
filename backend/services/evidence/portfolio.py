"""Portfolio evidence from the user's own personal website (a URL they give us, fetched once per run).

    fetch_portfolio(url)            -> str          visible text of the page plus up to MAX_PAGES same-site pages
    skills_from_portfolio(text)     -> ExtractedCV  M1's extractor run on that text, every skill stamped "portfolio"

Only public http(s) pages the user points at; private and loopback addresses are refused so the server
cannot be used to probe its own network. Pages linked from the first one on the same host whose link text
or path looks like projects / work / about are read too, since portfolios often split their content.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from backend.schemas import ExtractedCV
from backend.services.extractor import extract_from_text

USER_AGENT = "CareerLens/0.1 (AICON'26 hackathon project; reading the portfolio its owner submitted)"
TIMEOUT = 12
MAX_BYTES = 1_500_000
MAX_PAGES = 4
MAX_CHARS = 20_000
_FOLLOW = re.compile(r"project|work|portfolio|about|experience|skill|resume|cv", re.IGNORECASE)
_SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "template"}


class PortfolioError(ValueError):
    """User-safe reason the portfolio could not be read."""


class _Text(HTMLParser):
    """Visible text of an HTML document, one line per block, plus same-site links."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []  # (href, text)
        self._skip = 0
        self._link: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            self._link = [href or ""]
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "section", "article", "tr", "td"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag == "a" and self._link is not None:
            self.links.append((self._link[0], " ".join(self._link[1:]).strip()))
            self._link = None

    def handle_data(self, data):
        if self._skip:
            return
        self.parts.append(data)
        if self._link is not None:
            self._link.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def fetch_portfolio(url: str) -> str:
    """Visible text of the portfolio (first page plus a few same-site content pages)."""
    start = _check_url(url)
    seen: set[str] = set()
    queue = [start]
    chunks: list[str] = []
    while queue and len(seen) < MAX_PAGES:
        page = queue.pop(0)
        if page in seen:
            continue
        seen.add(page)
        html = _get(page)
        parser = _Text()
        parser.feed(html)
        chunks.append(parser.text())
        if page == start:
            host = urlparse(start).netloc
            for href, label in parser.links:
                target = urljoin(start, href).split("#", 1)[0]
                parsed = urlparse(target)
                if parsed.scheme in ("http", "https") and parsed.netloc == host and target not in seen:
                    if _FOLLOW.search(label or "") or _FOLLOW.search(parsed.path or ""):
                        queue.append(target)
    text = "\n\n".join(c for c in chunks if c)[:MAX_CHARS]
    if len(text.strip()) < 40:
        raise PortfolioError("The portfolio page has no readable text (is it a single-page app that needs JavaScript?).")
    return text


def skills_from_portfolio(text: str) -> ExtractedCV:
    """Skills, projects and experience from the portfolio text, with `sources=["portfolio"]` on each skill."""
    result = extract_from_text(text)
    for skill in result.skills:
        skill.sources = ["portfolio"]
    return result


def _check_url(url: str) -> str:
    url = url.strip()
    if url and "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise PortfolioError("Give the portfolio as an http(s) address, e.g. https://yourname.github.io.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise PortfolioError(f"Could not resolve {parsed.hostname}.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise PortfolioError("That address points at a private network, which the analyzer will not read.")
    return url


def _get(url: str) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        body = response.raw.read(MAX_BYTES + 1, decode_content=True)
    except requests.RequestException as exc:
        raise PortfolioError(f"Could not fetch the portfolio: {exc}") from exc
    if len(body) > MAX_BYTES:
        raise PortfolioError("The portfolio page is larger than 1.5 MB; point at a lighter page.")
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        raise PortfolioError(f"The portfolio address returned {content_type or 'a non-text file'}, not a web page.")
    return body.decode(response.encoding or "utf-8", errors="replace")
