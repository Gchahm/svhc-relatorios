# Contracts: I18N-004

**No API or data contract change.**

This is a presentation-layer feature. It adds no routes, changes no request/response shapes, reads no
new data, and writes nothing. The existing endpoints the in-scope components call — `GET
/api/alerts/[id]` (+ PATCH), `GET /api/documents/[id]`, `GET /api/attachment-analyses/[id]` (+
`/pages`, `/image/[page]`) — are untouched. The only changed module is the i18n catalog
(`src/lib/i18n/catalog.ts`), whose "contract" is the typed `CatalogShape` enforced at compile time
and by `catalog.test.mjs`.
