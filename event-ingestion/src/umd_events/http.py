"""Shared HTTP client: descriptive User-Agent, on-disk caching, retries with backoff, per-host rate limit."""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings

log = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, settings: Settings, use_cache: bool = True):
        self.settings = settings
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

        if use_cache:
            self.session: requests.Session = requests_cache.CachedSession(
                str(settings.cache_dir / "http_cache"),
                backend="sqlite",
                expire_after=settings.cache_ttl_s,
                allowable_methods=("GET", "POST"),
                allowable_codes=(200,),
                stale_if_error=True,
            )
        else:
            self.session = requests.Session()

        retry = Retry(
            total=3,
            backoff_factor=1.0,  # 1s, 2s, 4s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": settings.user_agent})

    def _throttle(self, url: str) -> None:
        """Reserve the next request slot for this host (thread-safe), then wait for it."""
        host = urlparse(url).netloc
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._last_request.get(host, 0.0) + self.settings.request_interval_s)
            self._last_request[host] = slot
        if slot > now:
            time.sleep(slot - now)

    def request(self, method: str, url: str, *, expire_after: int | None = None, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.settings.request_timeout_s)
        started = time.monotonic()
        response = None
        if isinstance(self.session, requests_cache.CachedSession):
            if expire_after is not None:
                kwargs["expire_after"] = expire_after
            # Serve fresh cache hits without waiting for a rate-limit slot.
            cached = self.session.request(method, url, only_if_cached=True, **kwargs)
            if getattr(cached, "from_cache", False) and cached.status_code != 504 and not getattr(cached, "is_expired", False):
                response = cached
        if response is None:
            self._throttle(url)
            response = self.session.request(method, url, **kwargs)
        log.debug(
            "%s %s -> %s (%.2fs%s)",
            method,
            response.url,
            response.status_code,
            time.monotonic() - started,
            ", cached" if getattr(response, "from_cache", False) else "",
        )
        response.raise_for_status()
        return response

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def get_json(self, url: str, **kwargs):
        return self.get(url, **kwargs).json()

    def cached_text(self, url: str, expire_after: int | None = None) -> str | None:
        """Body of a fresh cached GET response, or None without touching the network."""
        if not isinstance(self.session, requests_cache.CachedSession):
            return None
        kwargs = {"expire_after": expire_after} if expire_after is not None else {}
        cached = self.session.get(url, only_if_cached=True, **kwargs)
        if getattr(cached, "from_cache", False) and cached.status_code == 200 and not getattr(cached, "is_expired", False):
            cached.encoding = cached.encoding or "utf-8"
            return cached.text
        return None

    def get_text(self, url: str, **kwargs) -> str:
        response = self.get(url, **kwargs)
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text
