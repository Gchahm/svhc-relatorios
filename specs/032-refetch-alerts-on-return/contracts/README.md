# Contracts: Refetch alerts list after resolve/reopen on the detail page

**N/A — no API contract change.**

This feature reuses the existing, unchanged endpoints:

- `GET /api/alerts` — returns the full alerts list (incl. `resolved` status). The fix only changes
  how often the client calls it; request and response shapes are unchanged.
- `PATCH /api/alerts/[id]` — already used by the detail page to resolve/reopen; unchanged.

No new endpoint, no request/response shape change, no auth change.
