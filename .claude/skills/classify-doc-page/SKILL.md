---
model: opus
description: >-
    Classify a single fiscal document PAGE image (Brazilian NF-e / DANFE / NFS-e / boleto / comprovante / recibo) and extract its structured fields, recording the result directly to the database via the `record-classification` CLI (no file is written). Takes one image path plus the page's attachment id and page label. Use it to transcribe what is on one page — invoke it (often in parallel, one per page) when extracting document fields for the analyze-docs flow.
argument-hint: [file_path] [attachment_id] [page_label]
allowed-tools: Read, Bash
context: fork
agent: general-purpose
disable-model-invocation: false
hooks:
  PreToolUse:
    - matcher: "Read"
      hooks:
        - type: command
          command: 'uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/skills/classify-doc-page/scripts/validate_image.py"'
  Stop:
    - hooks:
        - type: command
          command: "echo 'stop-hook'"
          once: true
---

# Purpose

Read ONE fiscal document page image and transcribe its values into a structured JSON record, then **record that record to the database** via the `record-classification` CLI (one row per page in the `page_classifications` staging table — there is no `.classify.json` file). This is a pure, single-page vision task: you classify and read exactly what is on the page in front of you — you do not group documents, roll up totals, reconcile, or touch any other page. Your recorded record feeds the deterministic `apply-extractions` step downstream, so the field set is frozen and must match the template exactly.

These are Brazilian fiscal documents: nota fiscal (NF-e), DANFE, nota fiscal de serviço (NFS-e), boleto bancário, and payment proofs (comprovante / recibo). A single image is ONE page.

## Input

`$ARGUMENTS` is three space-separated tokens:

1. `file_path` — the path to a **single** page image (e.g. `.cache/analysis/<period>/<entry_id>_p1.png`). If more than one path is given, process only the first.
2. `attachment_id` — the attachment this page belongs to (supplied by the orchestrator from the work plan; the image filename is named by *entry*, not attachment, so it does not carry the attachment id).
3. `page_label` — this page's label (e.g. `p1`, `page2`), also from the plan.

An optional trailing `--remote` token (4th) means record to the production database; forward it to the `record-classification` command in step 4. You record the result keyed by `(attachment_id, page_label)`, so the first three tokens are required for the write.

A PreToolUse hook (`scripts/validate_image.py`) checks the file before you read it: it must exist and be a real image (PNG/JPEG/GIF/BMP/TIFF/WEBP). If it blocks the read because the input is missing or not an image, record the error result `{ "error": "<reason>" }` (see step 4) instead.

## Workflow

1. **Read** the image (the first token of `$ARGUMENTS`) with the Read tool.

2. **Classify the page in front of you.** A multi-page document may bundle an invoice page, a boleto page, and a payment-proof page — this skill sees only one page, so describe only THIS page. Set `papel_artefato` and `tipo_documento` from what the page actually is.

3. **Extract the fields** listed in the template `$CLAUDE_PROJECT_DIR/.claude/skills/classify-doc-page/templates/result.json`. The strings in that template are **field descriptions, not output** — replace each one with the real value you read from the image, or `null`. Rules:
   - **Never fabricate.** If a field is not visible or not legible, use `null`. Do not guess a CNPJ, a document number, or a date.
   - **Amounts** are numbers (e.g. `617.25`); a literal `"R$ 1.234,56"` string is also accepted. For an absent amount use `null`, **not** `0`.
   - **Dates** use `DD/MM/YYYY`. `data_emissao` MUST be a date **printed on this page**. **Never
     synthesize, infer, or recompose a date** from partial, ambiguous, or differently-formatted tokens
     — if no full date is legibly printed, use `null`. Do not assemble a date from a day on one line
     and a month/year guessed elsewhere; transcribe only what is actually shown.
     - On a **payroll / holerite / contracheque / payslip / 13º-salário** page, `data_emissao` is the
       **reference month (mês de competência/referência)** or the **payment date (data de pagamento)** —
       NOT the **Data Admissão** (hire date), which is the employee's start date and is unrelated to
       when this payslip belongs. Prefer the payment date; if only the reference month is shown, use it
       (e.g. `01/11/2025` for 11/2025).
   - **`nome_emitente` / `cnpj_emitente` are the ISSUER (the party that supplies the goods/service and is paid) — NOT the recipient/payer.** Get this right; it is the most common error:
     - On a **DANFE / NF-e**, the issuer is the **EMITENTE / REMETENTE** (top-left header block), never the **DESTINATÁRIO** (the buyer/recipient). The condominium **"SÃO VICENTE HOME CLUB"** is the customer/payer on these documents — if it appears as DESTINATÁRIO, it is NOT the issuer.
     - On **payroll / holerite / 13º-salário / FGTS-GFD / DARF** and similar, the company in the header is the **employer/payer** (again "SÃO VICENTE HOME CLUB"), not the issuer. The relevant counterparty is the **employee/payee** (e.g. "Nome do Funcionário") or the **tax authority** (Receita Federal / CEF) named as the recipient/favorecido — use that as `nome_emitente`.
     - On a **boleto / comprovante / PIX / TED**, the issuer is the **beneficiário / favorecido** (who receives the money), not the **pagador / sacado**.
     - Prefer the **razão social** (full legal name) for `nome_emitente`. If only a **nome fantasia / trade name / brand** is shown, use that — but never use an **address line, a CEP, or a field label/code** (e.g. the "FRETE POR CONTA DE" value "0- Emitente") as the name; if no real name is legible, use `null`.

4. **Record the result** by running the `record-classification` CLI from the repo's `scripts/` directory, with the page's `attachment_id` and `page_label` (the 2nd and 3rd tokens of `$ARGUMENTS`), piping the JSON on **stdin** via a quoted heredoc (so accents/quotes in Brazilian names are safe). Forward `--remote` if the orchestrator passed it. The JSON is valid JSON and nothing else (no markdown fences, no prose), and is **either** the filled fields object (every key from the template, with real values or `null`) **or**, if the page is missing/unreadable/blank/illegible, `{ "error": "<short reason>" }` — never both, and never a partially-filled object alongside an error.

   ```bash
   cd scripts && uv run python -m analysis record-classification \
     --attachment-id <attachment_id> --page <page_label> [--page-index <n>] [--remote] <<'JSON'
   { ...the fields object, or {"error": "<reason>"}... }
   JSON
   ```

   The CLI **validates** the JSON against the frozen contract below and writes one row to the `page_classifications` table (`INSERT OR REPLACE` keyed by `(attachment_id, page_label)`, so re-running replaces the prior record). A **non-zero exit** means the JSON was rejected (invalid JSON or a contract violation, reason on stderr) — fix the JSON and run the command again. A zero exit with `Recorded classification for …` means done.

## Output contract (frozen)

The fields object must contain exactly these keys (see the template for per-field meaning): `papel_artefato`, `tipo_documento`, `valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico`.

- `papel_artefato` ∈ `invoice | nfse | boleto | payment_proof | other`
- `tipo_documento` ∈ `NF-e | DANFE | boleto | recibo | comprovante | outro` (or `null`)

Do not add, rename, or drop keys — downstream parsing and the database write depend on this shape. The `record-classification` CLI enforces this contract (it is the validation point — there is no longer a file-write hook).
