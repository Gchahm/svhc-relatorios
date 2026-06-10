"""Vendor/issuer reconciliation for the document-classification analysis.

The analysis compares a document's issuer to the ledger vendor to flag a ``vendor``
mismatch (a fraud signal: the document does not belong to the party the condominium
claims to have paid). A near-exact string comparison produced many *false* mismatches
where the document and the ledger name the **same legal entity** under different forms.

This module centralizes the deterministic, stdlib-only reconciliation:

- name **normalization** (accents, case, whitespace/single-letter spacing, punctuation,
  common Portuguese business-name abbreviations, trailing legal/size suffixes);
- a **payer denylist** so the condominium itself (the destinatário/payer that the reader
  sometimes captures as issuer) never satisfies a vendor match nor wins the roll-up;
- **cross-page reconciliation**: an attachment bundles several pages (invoice + boleto +
  payment proof) whose issuer/beneficiary names are different forms of one entity, so the
  ledger vendor is reconciled against **every** page's issuer name, not just one roll-up.

The ledger side carries only a vendor name (no CNPJ), so "CNPJ-aware" reconciliation is
realized by matching across the attachment's pages — on at least one page (commonly the
payment artifact) the same entity appears under the name the ledger uses.
"""

import re
from unicodedata import category, normalize

# Condominium / payer names the reader sometimes mistakes for the issuer (the
# destinatário/payer on a DANFE, the employer on payroll/FGTS docs, the payer on a DARF).
# A payer-name match must never satisfy a vendor match nor win the issuer roll-up.
# Stored normalized (see ``normalize_company_name``).
PAYER_DENYLIST = frozenset(
    {
        "SAO VICENTE HOME CLUB",
        "SAO VICENTE HOME CLUBE",
        "CONDOMINIO SAO VICENTE HOME CLUB",
    }
)

# Common Portuguese business-name abbreviations → canonical token. Applied per token
# after punctuation stripping so ``COM.`` / ``COM`` both expand to ``COMERCIO``.
_ABBREVIATIONS = {
    "COM": "COMERCIO",
    "COML": "COMERCIAL",
    "IND": "INDUSTRIA",
    "INDL": "INDUSTRIAL",
    "INST": "INSTALACOES",
    "INSTAL": "INSTALACOES",
    "SERV": "SERVICOS",
    "SERVS": "SERVICOS",
    "DISTR": "DISTRIBUIDORA",
    "DIST": "DISTRIBUIDORA",
    "REPR": "REPRESENTACOES",
    "REPRES": "REPRESENTACOES",
    "CONST": "CONSTRUCOES",
    "CONSTR": "CONSTRUCOES",
    "TEC": "TECNOLOGIA",
    "TECNOL": "TECNOLOGIA",
    "ELETR": "ELETRICA",
    "MAT": "MATERIAIS",
    "PROD": "PRODUTOS",
    "EQUIP": "EQUIPAMENTOS",
    "TELECOM": "TELECOMUNICACOES",
}

# Trailing legal-form / size-qualifier tokens dropped from the end of a name. These never
# distinguish two entities (the same company is "X LTDA" on the invoice and "X" on the
# boleto), so keeping them only manufactures false mismatches.
_LEGAL_SUFFIX_TOKENS = frozenset(
    {
        "LTDA",
        "ME",
        "EPP",
        "EIRELI",
        "SA",
        "MEI",
        "LTDAME",
        "SS",
    }
)

# Filler tokens that carry no identifying weight; dropped before comparison so a name that
# merely spells out "E" / "DE" / "DA" differently still reconciles.
_STOPWORD_TOKENS = frozenset({"E", "DE", "DA", "DO", "DOS", "DAS"})

# Trade-name ↔ legal-name / brand ↔ corporate aliases for the SAME legal entity. The ledger
# uses one form (often a trade name or the proprietor's name), the document another, and the
# two share NO normalizable tokens — so only a curated equivalence can reconcile them. Each
# entry maps a set of mutually-equivalent NORMALIZED forms; if the ledger vendor and a page
# issuer fall in the same set, they reconcile.
#
# These pairs were confirmed same-entity by document review (matching CNPJ on the NF and the
# payment artifact). Deliberately EXCLUDED: name pairs where the ledger vs document name alone
# does NOT determine same-vs-different entity (e.g. CPCOM↔MG2, JM INSTALACOES↔JOSTONNY) — there
# the extraction fields are identical across cases the reviewer split into real findings vs
# false positives, so an alias here would suppress a genuine vendor mismatch. We never trade a
# false positive away at the cost of masking a real finding.
_ALIAS_GROUPS = [
    {"COPAGAZ", "COPAENERGIA"},
    {"ESCRISULDISTRIBUIDORA", "PAPERSULMATERIAISESCRITORIOLIMPEZA"},
    {"INSIGNIASOLUCOESADMINISTRATIVAS", "DIMARIMOVEIS"},
    {"TPATELECOMUNICACOES", "UNIFIQUETELECOMUNICACOES"},
    {"MBTELECOM", "MMBFIBRACOMERCIOSERVICOS"},
    {"LOJACONDEQUIPAMENTOSPARACONDOMINIOS", "MERCADOCONDEQUIPAMENTOSPARACONDOMINIOS"},
    {"VALDIRJARDINAGEM", "VALDIRDOMINGOSSILVEIRA"},
    {"PHPISCINAS", "PAULINOHELLMANN"},
    {"HSSISTEMASPRESSURIZACAO", "HSIMPORTACAOEXPORTACAO"},
    {"SULBRASILELETRONICAINFORMATICA", "DOUGLASJOSECARLESSO"},
    {"INOMAXSERRALHERIA", "OURIDESHENRIQUEMARXEMPINDUSTRIA"},
    {"A4INDUSTRIAELEVADORES", "INDUSTRIAA4"},
    {"CONSTRUCOLORCOMERCIOTINTAS", "CONSTRUCOLORITAJAISAOJOAO", "CONSTRUCOLORMATRIZ"},
    {"MEGHAPAPERPAPELARIAINFORMATICA", "MEGHAPAPERSOLUCOESGRAFICASCOMUNICACAOVISUAL"},
]


def _alias_key(norm_name: str) -> int | None:
    """Index of the alias group ``norm_name`` belongs to (substring-tolerant), else None."""
    if not norm_name:
        return None
    for i, group in enumerate(_ALIAS_GROUPS):
        for form in group:
            if norm_name == form or norm_name in form or form in norm_name:
                return i
    return None


# Below this normalized length we require a stronger (token-superset / equality) match
# instead of bare substring containment, so a short prefix can't spuriously match a longer
# unrelated name and mask a genuine vendor mismatch.
_MIN_SUBSTRING_LEN = 5


def _strip_accents(s: str) -> str:
    s = normalize("NFD", s)
    return "".join(c for c in s if category(c) != "Mn")


def _join_single_letters(tokens: list[str]) -> list[str]:
    """Collapse runs of single-letter tokens so ``M G 2`` ≡ ``MG2`` ≡ ``MG 2``.

    OCR/transcription splits short prefixes inconsistently; joining adjacent single-char
    tokens (letters or digits) gives one canonical token regardless of spacing.
    """
    out: list[str] = []
    buf: list[str] = []
    for t in tokens:
        if len(t) == 1:
            buf.append(t)
        else:
            if buf:
                out.append("".join(buf))
                buf = []
            out.append(t)
    if buf:
        out.append("".join(buf))
    return out


def normalize_tokens(s: str | None) -> list[str]:
    """Return the canonical, identifying tokens of a company name (order preserved)."""
    if not s:
        return []
    s = _strip_accents(str(s)).upper()
    # Punctuation/symbols → space (so "S/A", "DECORACOES," etc. split cleanly).
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    raw = s.split()
    raw = _join_single_letters(raw)
    tokens: list[str] = []
    for t in raw:
        t = _ABBREVIATIONS.get(t, t)
        if t in _LEGAL_SUFFIX_TOKENS or t in _STOPWORD_TOKENS:
            continue
        tokens.append(t)
    return tokens


def normalize_company_name(s: str | None) -> str:
    """Canonical normalized form of a company name for comparison/equality."""
    return "".join(normalize_tokens(s))


def is_payer_name(name: str | None) -> bool:
    """True if ``name`` is the condominium payer (never a legitimate issuer)."""
    if not name:
        return False
    norm = normalize_company_name(name)
    if not norm:
        return False
    return any(norm == normalize_company_name(p) for p in PAYER_DENYLIST)


def names_match(a: str | None, b: str | None) -> bool:
    """True if two names denote the same entity after normalization.

    Long names use substring containment (one form is a prefix/extension of the other —
    trade vs legal name); short names require token-superset equivalence to avoid
    over-matching (FR-007).
    """
    if not a or not b:
        return False
    if is_payer_name(a) or is_payer_name(b):
        return False
    na, nb = normalize_company_name(a), normalize_company_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Curated trade/legal/brand aliases for the same entity (share no normalizable tokens).
    ka, kb = _alias_key(na), _alias_key(nb)
    if ka is not None and ka == kb:
        return True
    shorter = na if len(na) <= len(nb) else nb
    if len(shorter) >= _MIN_SUBSTRING_LEN and (na in nb or nb in na):
        return True
    # Token-superset: every identifying token of the shorter name appears in the longer.
    ta, tb = set(normalize_tokens(a)), set(normalize_tokens(b))
    if not ta or not tb:
        return False
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return small.issubset(big) and len(small) >= 1 and len("".join(small)) >= _MIN_SUBSTRING_LEN


def reconcile_vendor(ledger_vendor: str | None, issuer_names) -> bool | None:
    """Reconcile the ledger vendor against every candidate issuer name of a document.

    Returns ``None`` when there is nothing to compare (no ledger vendor, or no non-payer
    issuer name was captured); otherwise ``True`` if ANY non-payer issuer name matches the
    ledger vendor, else ``False`` (a genuine mismatch is preserved).
    """
    if not ledger_vendor:
        return None
    candidates = [n for n in (issuer_names or []) if n and not is_payer_name(n)]
    if not candidates:
        return None
    for name in candidates:
        if names_match(ledger_vendor, name):
            return True
    return False
