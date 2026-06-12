# Contract: `parse_brl` (currency parser)

Module: `scripts/scraper/extractors/demonstrativo.py`

## Signature

```python
def parse_brl(text: str) -> float | None
```

## Behavior

| Input                | Output    | Notes |
|----------------------|-----------|-------|
| `"R$ 1.234,56"`      | `1234.56` | strip `R$`/whitespace, `.`→thousands, `,`→decimal |
| `"443.995,17"`       | `443995.17` | no currency symbol |
| `"0,00"`             | `0.0`     | zero is valid |
| `"-50,00"` / `"(50,00)"` | parsed numeric if `float()` accepts after cleaning, else `None` | sign handled by `float()`; parenthesized → likely `None` (no digits-only after cleaning) |
| `""` / `"   "`       | `None`    | empty / whitespace-only |
| `"R$ --,--"` / `"abc"` | `None`  | unparseable junk |
| value parsing to `NaN` / `inf` | `None` | rejected via `math.isfinite` |

- MUST NOT raise for any `str` input — all failure modes return `None`.
- MUST be a pure function (no I/O, no logging) — callers own logging/severity.

## Caller contracts

### Entry rows — `extractors/lancamentos.py` + `runner.py`

- Each extracted lancamento carries the raw amount text (`valor_raw`) and the parsed value
  (`valor`, possibly `None`).
- In `runner.py` entry build: if `valor is None`, **skip the row** (do not append to `entries_out`),
  log a warning quoting `valor_raw` + the description, and collect a non-fatal note.
- A skipped entry produces no attachment rows either (the attachment build is gated on the entry).

### Subtotals — `extractors/lancamentos.py`

- Subtotal rows likewise parse via `parse_brl`; a `None` subtotal is skipped with a warning (subtotals
  are not user-entry rows, but the same fail-soft rule applies so one bad subtotal cell can't abort the
  period). Out-of-scope to add raw provenance to subtotals (spec Assumptions).

### Demonstrativo report totals — `extractors/demonstrativo.py`

- The 5 summary values are **required**; a `None` for any is fatal for the period (raise a clear
  `RuntimeError` naming the title + raw text), preserving today's "Missing financial data" abort
  semantics for a genuinely broken summary.

## Unit tests (`scripts/tests/test_parse_brl.py`)

- valid BRL strings → expected floats
- empty / whitespace / junk → `None`
- NaN / inf source strings → `None`
- well-formed zero and large values → exact expected float
