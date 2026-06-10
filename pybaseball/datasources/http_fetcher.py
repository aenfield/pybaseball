import logging
import os
import time
from typing import Optional
from urllib.parse import urlencode

from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 15
_DEFAULT_BACKOFF_ENABLED = True
_MAX_BACKOFF_SECONDS = 120


def fetch_url(url: str, params: Optional[dict] = None) -> bytes:
    api_key = os.environ.get("SCRAPE_DO_API_KEY")
    if api_key:
        return _fetch_via_scrape_do(url, params, api_key)
    return _fetch_via_curl_cffi(url, params)


def _get_max_retries() -> int:
    raw = os.environ.get("SCRAPE_DO_MAX_RETRIES", "")
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_MAX_RETRIES


def _get_backoff_enabled() -> bool:
    raw = os.environ.get("SCRAPE_DO_BACKOFF_ENABLED", "").strip().lower()
    if raw in ("false", "0", "no"):
        return False
    if raw in ("true", "1", "yes"):
        return True
    return _DEFAULT_BACKOFF_ENABLED


def get_scrape_do_config() -> dict:
    return {
        "max_retries": _get_max_retries(),
        "backoff_enabled": _get_backoff_enabled(),
    }


def _fetch_via_scrape_do(url: str, params: Optional[dict], api_key: str) -> bytes:
    full_url = f"{url}?{urlencode(params)}" if params else url
    max_retries = _get_max_retries()
    backoff_enabled = _get_backoff_enabled()

    for attempt in range(max_retries):
        logger.debug(f"scrape.do attempt {attempt + 1}/{max_retries} for '{full_url}'")
        response = cffi_requests.get(
            "https://api.scrape.do",
            params={"token": api_key, "url": full_url, "render": "true"},
            timeout=90,
        )
        if response.status_code == 200:
            if attempt > 0:
                logger.warning(f"scrape.do succeeded on attempt {attempt + 1}/{max_retries}")
            return response.content
        if response.status_code == 502:
            # Transient proxy error from scrape.do — does not consume a credit
            if attempt < max_retries - 1:
                wait = min(2**attempt, _MAX_BACKOFF_SECONDS) if backoff_enabled else 0
                if wait > 0:
                    logger.warning(
                        f"scrape.do returned 502 on attempt {attempt + 1}/{max_retries}"
                        f" — waiting {wait}s before retry"
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        f"scrape.do returned 502 on attempt {attempt + 1}/{max_retries}"
                        f" — retrying immediately"
                    )
            continue
        raise cffi_requests.exceptions.HTTPError(
            f"scrape.do returned {response.status_code} for '{full_url}'"
        )
    raise cffi_requests.exceptions.HTTPError(
        f"scrape.do returned 502 after {max_retries} attempts for '{full_url}'"
    )


def _fetch_via_curl_cffi(url: str, params: Optional[dict]) -> bytes:
    response = cffi_requests.get(url, params=params, impersonate="chrome")
    if response.status_code > 399:
        raise cffi_requests.exceptions.HTTPError(
            f"Error accessing '{url}'. Received status code {response.status_code}"
        )
    return response.content
