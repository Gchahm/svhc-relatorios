"""Shared utilities for the scraper package."""

import uuid
from datetime import datetime

# Fixed namespace for deterministic UUIDs
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "svhc.fiscal")


def det_id(*parts: str) -> str:
    """Generate a deterministic UUID from string parts."""
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)
