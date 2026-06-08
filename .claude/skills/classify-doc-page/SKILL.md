---
model: opus
description: >-
    Classify a single fiscal document PAGE image (Brazilian NF-e / DANFE / NFS-e / boleto / comprovante / recibo) and extract its structured fields, writing the result as JSON next to the image (`<image>.classify.json`). Takes one image path. Use it to transcribe what is on one page — invoke it (often in parallel, one per page) when extracting document fields for the analyze-docs flow.
argument-hint: [file_path]
allowed-tools: Glob, Read, Edit, Write
context: fork
agent: general-purpose
disable-model-invocation: false
hooks:
  PreToolUse:
    - matcher: "Read"
      hooks:
        - type: command
          command: 'uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/skills/classify-doc-page/scripts/validate_image.py"'
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: 'uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/skills/classify-doc-page/scripts/validate_classify.py"'
  Stop:
    - hooks:
        - type: command
          command: "echo 'stop-hook'"
          once: true
---

# Purpose

Read ONE fiscal document page image and transcribe its values into a structured JSON record. This is a pure, single-page vision task: you classify and read exactly what is on the page in front of you — you do not group documents, roll up totals, reconcile, or touch any other file. The output feeds the deterministic `apply-extractions` step downstream, so the field set is frozen and must match the template exactly.

These are Brazilian fiscal documents: nota fiscal (NF-e), DANFE, nota fiscal de serviço (NFS-e), boleto bancário, and payment proofs (comprovante / recibo). A single image is ONE page.

## Input

`$ARGUMENTS` is the path to a **single** page image (e.g. `data/scrape/2025-12/<id>_p1.png`). If more than one path is given, process only the first.

A PreToolUse hook (`scripts/validate_image.py`) checks the file before you read it: it must exist and be a real image (PNG/JPEG/GIF/BMP/TIFF/WEBP). If it blocks the read because the input is missing or not an image, write the error result `{ "error": "<reason>" }` (see step 4) instead.

## Workflow

1. **Read** the image at `$ARGUMENTS` with the Read tool.

2. **Classify the page in front of you.** A multi-page document may bundle an invoice page, a boleto page, and a payment-proof page — this skill sees only one page, so describe only THIS page. Set `papel_artefato` and `tipo_documento` from what the page actually is.

3. **Extract the fields** listed in the template `$CLAUDE_PROJECT_DIR/.claude/skills/classify-doc-page/templates/result.json`. The strings in that template are **field descriptions, not output** — replace each one with the real value you read from the image, or `null`. Rules:
   - **Never fabricate.** If a field is not visible or not legible, use `null`. Do not guess a CNPJ, a document number, or a date.
   - **Amounts** are numbers (e.g. `617.25`); a literal `"R$ 1.234,56"` string is also accepted. For an absent amount use `null`, **not** `0`.
   - **Dates** use `DD/MM/YYYY`.
   - **`nome_emitente` / `cnpj_emitente` are the ISSUER (the party that supplies the goods/service and is paid) — NOT the recipient/payer.** Get this right; it is the most common error:
     - On a **DANFE / NF-e**, the issuer is the **EMITENTE / REMETENTE** (top-left header block), never the **DESTINATÁRIO** (the buyer/recipient). The condominium **"SÃO VICENTE HOME CLUB"** is the customer/payer on these documents — if it appears as DESTINATÁRIO, it is NOT the issuer.
     - On **payroll / holerite / 13º-salário / FGTS-GFD / DARF** and similar, the company in the header is the **employer/payer** (again "SÃO VICENTE HOME CLUB"), not the issuer. The relevant counterparty is the **employee/payee** (e.g. "Nome do Funcionário") or the **tax authority** (Receita Federal / CEF) named as the recipient/favorecido — use that as `nome_emitente`.
     - On a **boleto / comprovante / PIX / TED**, the issuer is the **beneficiário / favorecido** (who receives the money), not the **pagador / sacado**.
     - Prefer the **razão social** (full legal name) for `nome_emitente`. If only a **nome fantasia / trade name / brand** is shown, use that — but never use an **address line, a CEP, or a field label/code** (e.g. the "FRETE POR CONTA DE" value "0- Emitente") as the name; if no real name is legible, use `null`.

4. **Write the result** with the Write tool, next to the input image, replacing the image extension with `.classify.json` (so `<id>_p1.png` → `<id>_p1.classify.json`). The file content is valid JSON and nothing else (no markdown fences, no prose), and is **either**:
   - the filled fields object (every key from the template, with real values or `null`), **or**
   - if the page is missing, unreadable, blank, or illegible: `{ "error": "<short reason>" }`

— never both, and never a partially-filled object alongside an error.

## Output contract (frozen)

The fields object must contain exactly these keys (see the template for per-field meaning): `papel_artefato`, `tipo_documento`, `valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico`.

- `papel_artefato` ∈ `invoice | nfse | boleto | payment_proof | other`
- `tipo_documento` ∈ `NF-e | DANFE | boleto | recibo | comprovante | outro` (or `null`)

Do not add, rename, or drop keys — downstream parsing and the database import depend on this shape.

A PostToolUse hook (`scripts/validate_classify.py`) checks every file you write: it enforces the `.classify.json` naming convention and validates the JSON against this contract. If it reports a problem, fix the file and write it again.
