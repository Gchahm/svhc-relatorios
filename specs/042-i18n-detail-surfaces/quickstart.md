# Quickstart: verifying I18N-004

## Build / test

```bash
# catalog completeness + new-key coverage (Node's built-in test runner via the project script)
node_modules/.bin/next lint            # if `pnpm lint` fails on ignored builds in the sandbox
node_modules/.bin/prettier --check .   # or: pnpm format
node --test src/lib/i18n/catalog.test.mjs   # i18n catalog tests (native TS type-stripping)
```

## Manual verification (running app, local D1 prod-like data)

Use the `ui-login` skill to authenticate the Playwright MCP browser, then:

1. **Alert detail (US1)** — open `/dashboard/alerts`, click into any alert.
   - Confirm: headings "Resolução"/"Evidências"/"Lançamentos afetados"; field labels in pt-BR; the
     Type field shows a Portuguese alert-type label (e.g. `document_overpayment` → catalog label),
     never raw `snake_case`; currency `R$ x.xxx,xx`; timestamps `dd/mm/aaaa hh:mm`.
   - Resolve then reopen an alert → writeback still works; button labels Portuguese in idle + in-flight.
2. **Document detail (US2)** — open `/dashboard/documents`, click into a document.
   - Confirm: header labels, the four section headings, both table headers, page badges, and the
     "no image available" placeholder are pt-BR; document number/issuer/CNPJ verbatim; the "Abrir"
     deep link still navigates to the entry.
3. **Analysis dialog + viewer (US3)** — from an entry with an analysis (or via the alert detail "Ver
   anexo" button), open the dialog.
   - Confirm: title "Análise do anexo"; section headings; extracted-field labels (Bruto/Líquido/
     Pago/…); match pills read "OK"/"divergência"/"—"; the page viewer shows images or the Portuguese
     "Imagem indisponível" placeholder on error; the enlarge control aria/alt are Portuguese;
     extracted values (CNPJ, NF number, issuer) stay verbatim.
4. **Deep-link notice (US4)** — navigate to
   `/dashboard/entries?period=<p>&entry=<nonexistent-id>`; confirm the notice is Portuguese with the
   short id + period interpolated.
```
