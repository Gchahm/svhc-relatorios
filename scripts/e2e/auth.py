"""Provision the synthetic admin user for the browser smoke (feature 046).

A new better-auth sign-up gets ``role='pending'`` (it cannot reach the role-gated surfaces), so
after creating the user we elevate it to ``admin`` directly in local D1 (the ``ui-login`` skill's
mechanism). Idempotent: a duplicate sign-up is tolerated, and the role UPDATE is safe to repeat.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from common import d1

from .synthetic import ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD


def _sign_up(base_url: str) -> None:
    payload = json.dumps({"name": ADMIN_NAME, "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).encode()
    req = urllib.request.Request(
        base_url + "/api/auth/sign-up/email",
        data=payload,
        headers={"Content-Type": "application/json", "Origin": base_url},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        # A duplicate (USER_ALREADY_EXISTS) returns 4xx — tolerate it (idempotent provision).
        body = e.read().decode("utf-8", "replace")
        if e.code >= 500:
            raise RuntimeError(f"sign-up failed ({e.code}): {body}") from e


def ensure_admin(base_url: str) -> tuple[str, str]:
    """Ensure the synthetic admin exists with role='admin'. Returns (email, password)."""
    _sign_up(base_url)
    d1.execute_sql(
        f"UPDATE users SET role = 'admin' WHERE email = '{ADMIN_EMAIL}';",
        target="local",
    )
    return ADMIN_EMAIL, ADMIN_PASSWORD
