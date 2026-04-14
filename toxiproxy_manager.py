"""
Toxiproxy manager utilities for local development and testing.
"""

import os
import time
from typing import Any

import requests

TOXIPROXY_API = os.getenv("TOXIPROXY_API", "http://localhost:8474").rstrip("/")
PROXY_NAME = os.getenv("TOXIPROXY_PROXY_NAME", "vbank_api")
PROXY_LISTEN = os.getenv("TOXIPROXY_PROXY_LISTEN", "0.0.0.0:8666")
PROXY_UPSTREAM = os.getenv("TOXIPROXY_PROXY_UPSTREAM", "host.docker.internal:5000")


def _proxy_path(proxy_name: str | None = None) -> str:
    name = proxy_name or PROXY_NAME
    return f"/proxies/{name}"


def _toxics_path(proxy_name: str | None = None) -> str:
    return f"{_proxy_path(proxy_name)}/toxics"


def _url(path: str) -> str:
    return f"{TOXIPROXY_API}{path}"


def list_proxies(timeout: int = 5) -> requests.Response:
    return requests.get(_url("/proxies"), timeout=timeout)


def get_proxy(timeout: int = 5, proxy_name: str | None = None) -> requests.Response:
    return requests.get(_url(_proxy_path(proxy_name)), timeout=timeout)


def create_or_replace_proxy(
    timeout: int = 5,
    proxy_name: str | None = None,
    listen: str | None = None,
    upstream: str | None = None,
) -> requests.Response:
    name = proxy_name or PROXY_NAME
    payload = {
        "name": name,
        "listen": listen or PROXY_LISTEN,
        "upstream": upstream or PROXY_UPSTREAM,
    }

    # Make the operation idempotent for repeated local runs.
    try:
        delete_proxy(timeout=timeout, proxy_name=name)
    except requests.RequestException:
        pass

    return requests.post(_url("/proxies"), json=payload, timeout=timeout)


def delete_proxy(timeout: int = 5, proxy_name: str | None = None) -> requests.Response:
    return requests.delete(_url(_proxy_path(proxy_name)), timeout=timeout)


def add_toxic(
    toxic_type: str,
    stream: str,
    attributes: dict[str, Any],
    timeout: int = 5,
    name: str | None = None,
    proxy_name: str | None = None,
) -> tuple[str, requests.Response]:
    toxic_name = name or f"{toxic_type}_{int(time.time())}"
    payload = {
        "name": toxic_name,
        "type": toxic_type,
        "stream": stream,
        "attributes": attributes,
    }
    response = requests.post(_url(_toxics_path(proxy_name)), json=payload, timeout=timeout)
    return toxic_name, response


def delete_toxic(
    toxic_name: str,
    timeout: int = 5,
    proxy_name: str | None = None,
) -> requests.Response:
    return requests.delete(_url(f"{_toxics_path(proxy_name)}/{toxic_name}"), timeout=timeout)


def clear_toxics(timeout: int = 5, proxy_name: str | None = None) -> list[str]:
    response = get_proxy(timeout=timeout, proxy_name=proxy_name)
    if response.status_code != 200:
        return []

    removed: list[str] = []
    for toxic in response.json().get("toxics", []):
        toxic_name = toxic.get("name")
        if not toxic_name:
            continue
        delete_res = delete_toxic(toxic_name, timeout=timeout, proxy_name=proxy_name)
        if delete_res.status_code in (200, 204):
            removed.append(toxic_name)

    return removed
