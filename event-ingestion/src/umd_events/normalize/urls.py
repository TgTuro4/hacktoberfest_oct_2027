from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")


def clean_url(url: str | None, base: str | None = None) -> str | None:
    """Make a URL absolute and drop tracking parameters and fragments."""
    if not url:
        return None
    url = url.strip()
    if url.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    if base:
        url = urljoin(base, url)
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith(_TRACKING_PREFIXES)]
    return urlunparse(parts._replace(query=urlencode(query), fragment=""))
