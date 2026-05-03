"""Shared HTTP helper for delivery modules."""

from __future__ import annotations

import json
from typing import Any
from urllib import request


def post_json(url: str, payload: dict[str, Any], timeout: float) -> None:
    """Synchronous JSON POST using stdlib."""
    raw = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=raw, headers={"content-type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        if response.status >= 400:
            raise RuntimeError(f"webhook failed with status {response.status}")
