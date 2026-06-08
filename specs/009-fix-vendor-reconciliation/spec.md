# Feature Specification: Vendor reconciliation & issuer roll-up (fix false vendor mismatches)

**Branch**: `fix-vendor-reconciliation-cnpj-rollup`
**Created**: 2026-06-08
**Status**: Draft
**Origin**: Self-improving classification loop — fix step for 63 `false` vendor mismatches in period 2025-12

## Summary

The document-classification analysis compares the extracted document **issuer** to the ledger
**vendor** to flag a `vendor` mismatch (a potential fraud signal: the document does not belong to
the party the condominium claims to have paid). For period 2025-12 the vision-review step judged 63
of the vendor mismatches as **false positives** (system faults, not real findings): in every case the
document and the ledger refer to the **same legal entity**, but the comparison flagged a difference.

The false positives have four fixable sub-causes:

1. **No name normalization.** The same legal entity is flagged because of cosmetic differences:
   abbreviations (`COM.`↔`COMERCIO`, `IND`↔`INDUSTRIA`, `INST.`↔`INSTALACOES`), legal/size suffixes
   (`LTDA`, `ME`, `EIRELI`, `EPP`, `S.A.`), corporate-suffix punctuation (`S/A`↔`S.A.`), commas and
   other punctuation, and internal whitespace (`M G 2`↔`MG 2`).
2. **No CNPJ-aware / cross-page reconciliation.** A document bundles several pages (e.g. invoice +
   boleto + payment proof). The roll-up surfaces ONE issuer name, and if that one differs from the
   ledger the entry is flagged — even when another page in the same document carries the issuer name
   that DOES match the ledger (trade name vs legal name vs payment beneficiary of the same entity).
3. **Wrong issuer field captured.** The reader/roll-up sometimes selects the wrong party as issuer:
   the destinatário/payer (the condominium itself, "SÃO VICENTE HOME CLUB") on DANFEs and tax/payroll
   docs; an NFS-e *nome fantasia* instead of *razão social* (or vice-versa); an address line; or the
   "FRETE POR CONTA DE" field value ("0- Emitente").
4. **Roll-up precedence ignores the payment artifact.** When a boleto / PIX / Sicredi comprovante is
   present, its beneficiário/favorecido (which matches the ledger) should be considered, not only the
   NF header name.

## User Scenarios & Testing

### Primary user story

As a fiscal auditor reviewing the condominium's spending, I want a `vendor` mismatch alert to fire
**only** when the document genuinely belongs to a party other than the ledger vendor, so that the
alert list reflects real anomalies and I am not buried in false positives caused by name formatting,
trade-vs-legal naming, or the reader picking the wrong party off the page.

### Acceptance scenarios

1. **Given** a DANFE whose issuer is `COMERCIAL 3300 EIRELI` and a ledger vendor `COMERCIAL 3300`,
   **when** analyzed, **then** `vendor_match` is true (legal-suffix/normalization equivalence).
2. **Given** a document where the rolled-up issuer differs from the ledger but ANOTHER page of the
   same document carries an issuer name that matches the ledger (e.g. the boleto beneficiary
   `COPAGAZ` while the NF header reads `COPA ENERGIA S.A.`), **when** analyzed, **then** `vendor_match`
   is true (cross-page reconciliation).
3. **Given** a DANFE where the only on-page party matching the ledger is the destinatário/payer
   `SÃO VICENTE HOME CLUB` (the condominium itself), **when** analyzed, **then** that payer name is
   NOT treated as the issuer and does not by itself satisfy `vendor_match`.
4. **Given** an issuer name differing only by abbreviation/punctuation/whitespace from the ledger
   (`ELETRO VOLT COM E INSTALACOES` vs `ELETRO VOLT COMERCIO E INSTALACOES`; `M G 2` vs `MG 2`;
   `TIM S/A` vs `TIM S.A.`), **when** analyzed, **then** `vendor_match` is true.
5. **Given** a document whose issuer is a genuinely different company from the ledger vendor (a real
   finding), **when** analyzed, **then** `vendor_match` remains false and the mismatch still surfaces.

### Edge cases

- The ledger vendor is null/empty → `vendor_match` stays null (no comparison), as today.
- No page yields an issuer name → `vendor_match` stays null, as today.
- The ONLY matching name on any page is the condominium payer → must NOT reconcile to true.
- A short ledger token (e.g. a 2-letter prefix) must not produce spurious substring matches after
  normalization (guard against over-matching on very short normalized strings).

## Requirements

### Functional Requirements

- **FR-001**: The system MUST normalize both the ledger vendor name and each candidate issuer name
  before comparison: case-fold, strip accents, normalize whitespace (collapse runs, and join
  single-letter spacing so `M G 2` ≡ `MG 2`), strip punctuation, expand a fixed set of common
  Portuguese business-name abbreviations (`COM`→`COMERCIO`, `IND`→`INDUSTRIA`, `INST`→`INSTALACOES`,
  `SERV`→`SERVICOS`, `DISTR`→`DISTRIBUIDORA`, `REPR`→`REPRESENTACOES`, etc.), and drop trailing
  legal/size suffix tokens (`LTDA`, `ME`, `EPP`, `EIRELI`, `SA`, `S/A`, `S.A.`).
- **FR-002**: The system MUST reconcile the vendor by comparing the ledger vendor against the issuer
  name of EVERY page record of the document (not only the single rolled-up `issuer_name`); if ANY
  page's normalized issuer name matches the normalized ledger vendor, `vendor_match` is true.
- **FR-003**: When determining the document-level `issuer_name` roll-up, the system MUST prefer a
  payment-artifact (boleto / payment_proof) beneficiary name over an invoice header name when the
  payment-artifact name reconciles with the ledger vendor, so the surfaced issuer reflects the party
  actually paid.
- **FR-004**: The system MUST NOT select the condominium payer (configurable payer denylist, default
  containing "SÃO VICENTE HOME CLUB") as the document issuer, and a payer-name match MUST NOT by
  itself satisfy `vendor_match`.
- **FR-005**: The vendor comparison MUST preserve genuine mismatches: a document whose issuer is a
  different legal entity than the ledger vendor MUST still produce `vendor_match` false.
- **FR-006**: The change MUST apply uniformly to both single-entry documents and shared-NF siblings
  (the fan-out path), and MUST be stdlib-only Python within `scripts/analysis/`.
- **FR-007**: The matcher MUST guard against over-matching: very short normalized names (below a
  minimum token/length threshold) must require a stronger (e.g. equality or token-superset) match
  rather than a bare substring containment, to avoid new false negatives masking real findings.

### Key Entities

- **Ledger vendor name**: the supplier name on the source ledger entry (no CNPJ available on the
  ledger side).
- **Page issuer name** (`nome_emitente`): the issuer/beneficiary captured per page; one document has
  several pages with potentially different names for the same entity.
- **Payer denylist**: names that are the condominium/payer, never the issuer.

## Success Criteria

- **SC-001**: All 63 false vendor mismatches enumerated for period 2025-12 are resolved
  (`vendor_match` becomes true) after re-running the analysis on the affected documents.
- **SC-002**: The 5 genuine (`true`) vendor mismatches for period 2025-12 still surface
  (`vendor_match` false) — no real finding is suppressed.
- **SC-003**: No NEW vendor mismatch appears in scope that was not present before the change.

## Assumptions

- The ledger does not expose a vendor CNPJ; "CNPJ-aware reconciliation" is realized via cross-page
  reconciliation (FR-002) plus normalization (FR-001) — the same legal entity's name appears under a
  form that matches the ledger on at least one page (commonly the payment artifact).
- The condominium payer name is stable enough to be a small configurable denylist.
- Name normalization is a deterministic transform; no external data source is consulted.
