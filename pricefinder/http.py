"""Polite HTTP helper: browser-like headers, timeouts, small delay between requests."""
from __future__ import annotations

import time

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

_session = requests.Session()
_session.headers.update(HEADERS)
_last_request = 0.0
MIN_INTERVAL = 1.0  # seconds between requests, to be a good citizen


class BlockedError(RuntimeError):
    """The site refused the request (bot protection, captcha, 403/503...)."""


def get(url: str, **kwargs) -> requests.Response:
    global _last_request
    wait = MIN_INTERVAL - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    kwargs.setdefault("timeout", 20)
    resp = _session.get(url, **kwargs)
    _last_request = time.time()
    if resp.status_code in (403, 429, 503):
        raise BlockedError(f"{resp.status_code} from {url.split('?')[0]}")
    lowered = resp.text[:5000].lower()
    if "captcha" in lowered or "robot or human" in lowered:
        raise BlockedError(f"captcha page from {url.split('?')[0]}")
    resp.raise_for_status()
    return resp
