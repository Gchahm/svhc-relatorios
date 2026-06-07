"""Shared leaf used by both the scraper and the analysis packages.

The ONLY code shared across the two subsystems: deterministic UUID minting
(`det_id`/`NAMESPACE`) and a millisecond timestamp (`now_ms`). Kept in one place so
ids stay byte-identical across both — the `NAMESPACE` constant must never change.
"""

import uuid
from datetime import datetime

# Fixed namespace for deterministic UUIDs
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "svhc.fiscal")


def det_id(*parts: str) -> str:
    """Generate a deterministic UUID from string parts."""
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)
