# Tasks: Vendor reconciliation & issuer roll-up

- [x] T001 New module `scripts/analysis/vendor_match.py`: `normalize_tokens` /
  `normalize_company_name` (accents, case, whitespace, single-letter join, abbreviation map,
  legal-suffix/stopword drop), `PAYER_DENYLIST` + `is_payer_name`, `names_match` (substring for long
  names, token-superset/equality for short — FR-001/FR-007), curated `_ALIAS_GROUPS` trade/legal
  aliases (excluding pairs that collide with true findings), `reconcile_vendor` across all page
  issuer names (FR-002).
- [x] T002 `documentos.py`: import the helpers; add `_issuer_names_of` and `_pick_issuer_name`
  (payment-artifact-preferred, payer-excluded — FR-003/FR-004); replace the substring vendor
  comparison in `build_document_analysis` and `_fanout_result` with `reconcile_vendor` over all page
  issuer names (FR-002/FR-006); remove the now-unused `_normalize_name`.
- [x] T003 `.claude/skills/classify-doc-page/SKILL.md`: add issuer-disambiguation guidance so the
  reader never captures the destinatário/payer (condominium), the address line, or the
  "FRETE POR CONTA DE" code as `nome_emitente`, and prefers razão social (addresses the `reading`
  sub-cause on the next re-classify).
- [x] T004 Verify against persisted 2025-12 extractions: 51/63 false vendor mismatches reconcile via
  code with zero regressions (all 126 docs); all 5 genuine `true` findings preserved (SC-002/SC-003).
  Remaining 9 are `reading` cases (the correct issuer name is not in the extraction data — fixed by
  T003 on re-classify) and 3 are name-pairs whose extraction data is identical to a true finding, so
  they are intentionally left as mismatches to avoid suppressing a real finding.
