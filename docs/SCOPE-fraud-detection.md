# Fraud & Forgery Detection — Future Scope

## Overview

Extend the document analysis module to detect forged, altered, or suspicious fiscal documents attached to condominium expense entries.

## Phase 1: Visual Forgery Detection (VLM)

Extend the VLM prompt to assess document authenticity:

- **Font consistency**: flag documents with mixed/inconsistent fonts
- **Layout validation**: compare against known NF-e/DANFE/boleto templates
- **Digital alteration signs**: detect editing artifacts, misaligned text, resolution inconsistencies
- **Confidence score**: 0-100 authenticity confidence per document
- **Output**: new fields in `document_analyses` (e.g. `authenticity_score`, `forgery_flags`)

## Phase 2: Cross-Reference Validation

- **CNPJ lookup**: validate extracted CNPJs against Receita Federal public API
    - Check if company exists and is active
    - Compare registered business name vs document issuer name
    - Flag CNPJs belonging to shell companies or recently created entities
- **Document number sequences**: detect gaps or duplicates in invoice numbers from the same vendor
- **Cross-vendor duplicate detection**: same document image attached to different entries

## Phase 3: Pattern-Based Fraud Indicators

- **Round number bias**: flag entries where amounts are suspiciously round (R$ 5,000.00 exact)
- **Just-below-threshold expenses**: cluster of expenses just under approval limits
- **Weekend/holiday dating**: documents dated on non-business days
- **Vendor relationship analysis**: graph of vendor connections (shared CNPJ roots, addresses)
- **Split transaction detection**: single large expense broken into multiple smaller entries to avoid oversight

## Phase 4: Historical & Statistical Analysis

- **Price benchmarking**: compare unit prices against market rates for common services (cleaning, security, maintenance)
- **Vendor rotation anomalies**: same service alternating between vendors without bidding
- **Ghost vendor detection**: vendors that only appear in this condominium's records
- **Approval pattern analysis**: which approvers sign off on flagged transactions

## Technical Notes

- VLM model: Qwen2.5-VL-7B (local, Apple Silicon) — may need larger model for forgery detection
- CNPJ API: `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` (free, rate-limited)
- New DB tables may be needed for CNPJ cache, vendor graph, benchmark data
- All new checks should generate alerts with appropriate severity levels
