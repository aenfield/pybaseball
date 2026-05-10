import os
from typing import Optional
from urllib.parse import urlencode

from curl_cffi import requests as cffi_requests


def fetch_url(url: str, params: Optional[dict] = None) -> bytes:
    api_key = os.environ.get("SCRAPE_DO_API_KEY")
    if api_key:
        return _fetch_via_scrape_do(url, params, api_key)
    return _fetch_via_curl_cffi(url, params)


def _fetch_via_scrape_do(url: str, params: Optional[dict], api_key: str) -> bytes:
    full_url = f"{url}?{urlencode(params)}" if params else url
    for attempt in range(3):
        response = cffi_requests.get(
            "https://api.scrape.do",
            params={"token": api_key, "url": full_url, "render": "true"},
            timeout=90,
        )
        if response.status_code == 200:
            return response.content
        if response.status_code == 502:
            # Transient proxy error from scrape.do — does not consume a credit
            continue
        raise cffi_requests.exceptions.HTTPError(
            f"scrape.do returned {response.status_code} for '{full_url}'"
        )
    raise cffi_requests.exceptions.HTTPError(
        f"scrape.do returned 502 after 3 attempts for '{full_url}'"
    )


def _fetch_via_curl_cffi(url: str, params: Optional[dict]) -> bytes:
    response = cffi_requests.get(url, params=params, impersonate="chrome")
    if response.status_code > 399:
        raise cffi_requests.exceptions.HTTPError(
            f"Error accessing '{url}'. Received status code {response.status_code}"
        )
    return response.content
