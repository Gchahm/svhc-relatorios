"""Start/stop the real Workers build (``pnpm preview``) for the browser smoke (feature 046).

``pnpm preview`` builds with OpenNext and serves via ``wrangler dev`` against local Miniflare.
We serve on a port that better-auth already trusts (``.dev.vars`` lists ``http://localhost:3000``
and ``:3001``), so the smoke's browser origin is accepted without editing committed config.

If a server is already answering on the port (e.g. a developer's running instance), ``serve()``
reuses it instead of starting a second one. Otherwise it launches ``pnpm preview --port <port>`` as
its own process group and tears it down on exit. All waits are bounded (FR-012).
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 3001  # matches the .dev.vars BETTER_AUTH_URL origin (and is a trusted origin)
_DEV_VARS = _REPO_ROOT / ".dev.vars"
# A throwaway, local-only better-auth secret. The Workers build (unlike `next dev`) refuses the
# default secret; this is injected into the gitignored .dev.vars at serve time, never committed.
_TEST_SECRET = "e2e-smoke-synthetic-secret-do-not-use-in-prod"


def ensure_dev_vars(port: int = DEFAULT_PORT) -> None:
    """Ensure .dev.vars carries the auth vars the Workers build needs to start (idempotent).

    wrangler dev injects .dev.vars into the Worker runtime (process env is NOT inherited), so this
    is the sanctioned way to supply them. The file is gitignored — the synthetic secret never
    reaches the repo. Each key is ADDED only if absent, so a developer's existing values
    (BETTER_AUTH_URL / trusted origins) are left untouched; in a fresh CI checkout (no .dev.vars)
    all three are written, with the serve origin trusted.
    """
    base_url = f"http://localhost:{port}"
    lines = _DEV_VARS.read_text().splitlines() if _DEV_VARS.exists() else []
    present = {line.split("=", 1)[0].strip() for line in lines if "=" in line}
    if "BETTER_AUTH_SECRET" not in present:
        lines.append(f"BETTER_AUTH_SECRET={_TEST_SECRET}")
    if "BETTER_AUTH_URL" not in present:
        lines.append(f"BETTER_AUTH_URL={base_url}")
    if "BETTER_AUTH_TRUSTED_ORIGINS" not in present:
        lines.append(
            f"BETTER_AUTH_TRUSTED_ORIGINS={base_url},http://127.0.0.1:{port}"
        )
    _DEV_VARS.write_text("\n".join(lines) + "\n")


def _http_status(url: str, timeout: float = 3.0) -> int | None:
    """Return the HTTP status for a GET (following no redirects), or None on connection error."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: D401 - suppress auto-follow
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code  # 3xx/4xx still tells us the server is up
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None


def _is_up(base_url: str) -> bool:
    # The root is an auth route; an up server returns 200 (unauth) or a redirect — any HTTP status.
    return _http_status(base_url + "/") is not None


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_until_ready(base_url: str, timeout_s: float = 240.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _is_up(base_url):
            return
        time.sleep(2.0)
    raise TimeoutError(f"server did not become ready at {base_url} within {timeout_s:.0f}s")


@contextlib.contextmanager
def serve(port: int = DEFAULT_PORT, build_timeout_s: float = 240.0):
    """Yield the base URL of a running preview server, starting one if needed.

    Reuses an already-running server on the port; otherwise launches ``pnpm preview`` and kills
    its process group on exit.
    """
    base_url = f"http://localhost:{port}"

    if _is_up(base_url):
        # Reuse a server a developer already has running on this port.
        yield base_url
        return

    if not _port_free(port):
        raise RuntimeError(f"port {port} is in use but not serving the app; free it or pick another port")

    # wrangler dev injects .dev.vars into the Worker runtime; ensure the auth vars are present.
    ensure_dev_vars(port)

    # `pnpm preview` passes flags after `--` through to `wrangler dev`.
    proc = subprocess.Popen(
        ["pnpm", "preview", "--", "--port", str(port)],
        cwd=_REPO_ROOT,
        env=dict(os.environ),
        start_new_session=True,  # own process group so we can kill children (the build + wrangler)
    )
    try:
        wait_until_ready(base_url, timeout_s=build_timeout_s)
        yield base_url
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        with contextlib.suppress(Exception):
            proc.wait(timeout=30)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
