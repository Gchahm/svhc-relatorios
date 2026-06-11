# Contract: `PATCH /api/alerts/[id]` (existing — resolve/reopen)

Auth-gated (roles `admin`, `member`; else `403`). Sets an alert's resolved state and notes. Already
implemented; this feature invokes it from the detail page and **extends the response to include
`metadata`** (currently omitted) so the client keeps a complete alert object after a mutation.

## Request

```
PATCH /api/alerts/{id}
Content-Type: application/json

{ "resolved": true, "notes": "Confirmed with vendor; legitimate split." }
```

- `resolved` (boolean, required) — new resolved state.
- `notes` (string | null, optional) — free-text notes; `null`/omitted clears them.

## Behavior

- `resolved = body.resolved`
- `resolvedAt = resolved ? now : null`
- `notes = body.notes ?? null`

## Responses

### 200 OK

The updated alert (same shape as `GET /api/alerts/[id]`, including `metadata` after this change).

### 403 Forbidden

```json
{ "error": "Unauthorized" }
```

### 404 Not Found

```json
{ "error": "Alert not found" }
```
