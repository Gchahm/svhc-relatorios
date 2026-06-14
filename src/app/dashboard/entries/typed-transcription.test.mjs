/**
 * Unit tests for the type-aware extraction builder (feature 057 / EXTRACT-006).
 *
 * Pins:
 *  - per-type section grouping + value completeness ("show all the text" — FR-003, SC-001);
 *  - the RECONCILIATION_PROVENANCE map against contracts/provenance.md and that the total+issuer
 *    rows are tagged for each type (FR-004/FR-005, SC-002), mirroring scripts/analysis/type_mappers.py;
 *  - absent/null provenance target → no role tag, no throw (FR-006, SC-004);
 *  - malformed/partial typed shapes → no throw (SC-004);
 *  - canonicalDocType alias resolution + unknown→outro.
 *
 * Imports the REAL builder + the REAL catalog (role labels must resolve), per the repo's
 * `node --test "src/**\/*.test.mjs"` convention.
 *
 * Run: `pnpm test:ts`
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
    buildTypedSections,
    canonicalDocType,
    provenanceRoleLabel,
    RECONCILIATION_PROVENANCE,
} from "./typed-transcription.ts";
import { catalog } from "../../../lib/i18n/catalog.ts";

// A translator that resolves a deep catalog key against pt-BR (asserts the keys exist + are strings).
function makeT(locale = "pt-BR") {
    return key => {
        const parts = key.split(".");
        let v = catalog[locale];
        for (const p of parts) v = v?.[p];
        assert.equal(typeof v, "string", `catalog key ${key} must resolve to a string`);
        return v;
    };
}
const t = makeT();
const locale = "pt-BR";

// Collect every (path → value) leaf the builder produced, for completeness assertions.
function rowsByPath(sections) {
    const map = new Map();
    for (const s of sections) for (const r of s.rows) map.set(r.path, r);
    return map;
}
function roleForPath(sections, path) {
    return rowsByPath(sections).get(path)?.provenanceRole;
}

// ─── canonicalDocType ───────────────────────────────────────────────────────────────────────────

test("canonicalDocType resolves canonical, aliases, and unknown→outro", () => {
    assert.equal(canonicalDocType("danfe"), "danfe");
    assert.equal(canonicalDocType("NF-e"), "danfe");
    assert.equal(canonicalDocType("nfe"), "danfe");
    assert.equal(canonicalDocType("nfs-e"), "nfse");
    assert.equal(canonicalDocType("DANFSe"), "nfse");
    assert.equal(canonicalDocType("comprovante"), "comprovante_pagamento");
    assert.equal(canonicalDocType("PIX"), "comprovante_pagamento");
    assert.equal(canonicalDocType("ted"), "comprovante_pagamento");
    assert.equal(canonicalDocType("recibo"), "recibo");
    assert.equal(canonicalDocType("boleto bancario"), "boleto");
    assert.equal(canonicalDocType("something weird"), "outro");
    assert.equal(canonicalDocType(undefined), "outro");
    assert.equal(canonicalDocType(null), "outro");
    assert.equal(canonicalDocType(42), "outro");
});

// ─── Provenance map matches the contract (mirrors type_mappers.py) ───────────────────────────────

test("RECONCILIATION_PROVENANCE matches contracts/provenance.md exactly", () => {
    assert.deepEqual(RECONCILIATION_PROVENANCE.danfe, {
        total: "totais.valor_total_nota",
        issuer_name: "emitente.nome",
        issuer_cnpj: "emitente.cnpj",
        number: "numero",
        date: "data_emissao",
        service: "itens.0.descricao",
    });
    assert.deepEqual(RECONCILIATION_PROVENANCE.nfse, {
        total: "valores.valor_liquido",
        issuer_name: "prestador.nome",
        issuer_cnpj: "prestador.cnpj",
        number: "numero",
        date: "data_emissao",
        service: "discriminacao_servico",
    });
    assert.deepEqual(RECONCILIATION_PROVENANCE.boleto, {
        total: "valor_documento",
        issuer_name: "beneficiario.nome",
        issuer_cnpj: "beneficiario.cnpj_cpf",
        number: "numero_documento",
        date: "data_documento",
    });
    assert.deepEqual(RECONCILIATION_PROVENANCE.recibo, {
        total: "valor",
        issuer_name: "recebedor.nome",
        issuer_cnpj: "recebedor.cnpj_cpf",
        number: "numero",
        date: "data",
        service: "referente_a",
    });
    assert.deepEqual(RECONCILIATION_PROVENANCE.comprovante_pagamento, {
        total: "valor",
        issuer_name: "recebedor.nome",
        issuer_cnpj: "recebedor.cnpj_cpf",
        number: "identificador",
        date: "data",
    });
    assert.deepEqual(RECONCILIATION_PROVENANCE.outro, {
        total: "valores_identificados.0.valor",
        service: "descricao",
    });
});

test("provenanceRoleLabel resolves every role to a non-empty pt-BR + en string", () => {
    for (const lc of ["pt-BR", "en"]) {
        const tt = makeT(lc);
        for (const role of ["total", "issuer_name", "issuer_cnpj", "number", "date", "service"]) {
            const label = provenanceRoleLabel(role, tt);
            assert.ok(typeof label === "string" && label.length > 0, `role ${role} label in ${lc}`);
        }
    }
});

// ─── Per-type: grouping + completeness + total/issuer provenance ─────────────────────────────────

test("nfse: grouped sections, all values visible, total←valor_liquido and issuer←prestador tagged", () => {
    const nfse = {
        doc_type: "nfse",
        schema_version: "1",
        raw_text: "PREFEITURA ... NFS-e ...",
        numero: "123",
        data_emissao: "2025-03-10",
        prestador: { nome: "ACME Servicos", cnpj: "11222333000181" },
        tomador: { nome: "Condominio SVHC", cnpj_cpf: "99888777000166" },
        discriminacao_servico: "Manutencao predial mensal",
        valores: { valor_servico: 320.0, deducoes: 0, valor_liquido: 320.0 },
    };
    const sections = buildTypedSections(nfse, t, locale);
    const byPath = rowsByPath(sections);

    // doc_type / schema_version hidden; raw_text kept.
    assert.equal(byPath.has("doc_type"), false);
    assert.equal(byPath.has("schema_version"), false);
    assert.ok(byPath.has("raw_text"));

    // Grouped: prestador / tomador / valores are their own sections (not "general").
    const sectionKeys = sections.map(s => s.key);
    assert.ok(sectionKeys.includes("prestador"));
    assert.ok(sectionKeys.includes("tomador"));
    assert.ok(sectionKeys.includes("valores"));

    // Every non-empty scalar visible.
    assert.equal(byPath.get("prestador.nome").value, "ACME Servicos");
    assert.equal(byPath.get("discriminacao_servico").value, "Manutencao predial mensal");
    assert.ok(byPath.has("valores.valor_liquido"));

    // Provenance: total ← valores.valor_liquido (the 757dedb0 fix target), issuer ← prestador.
    assert.equal(roleForPath(sections, "valores.valor_liquido"), "total");
    assert.equal(roleForPath(sections, "prestador.nome"), "issuer_name");
    assert.equal(roleForPath(sections, "prestador.cnpj"), "issuer_cnpj");
    assert.equal(roleForPath(sections, "numero"), "number");
    assert.equal(roleForPath(sections, "discriminacao_servico"), "service");
    // The tomador is NOT the issuer.
    assert.equal(roleForPath(sections, "tomador.nome"), undefined);
});

test("danfe: total←totais.valor_total_nota, issuer←emitente, service←itens.0.descricao", () => {
    const danfe = {
        doc_type: "danfe",
        schema_version: "1",
        raw_text: "DANFE ...",
        numero: "55",
        data_emissao: "2025-01-02",
        emitente: { nome: "Fornecedor LTDA", cnpj: "11222333000181" },
        destinatario: { nome: "Condominio SVHC" },
        itens: [{ descricao: "Item A", valor_unitario: 100 }],
        totais: { valor_total_nota: 100.0 },
    };
    const sections = buildTypedSections(danfe, t, locale);
    assert.equal(roleForPath(sections, "totais.valor_total_nota"), "total");
    assert.equal(roleForPath(sections, "emitente.nome"), "issuer_name");
    assert.equal(roleForPath(sections, "emitente.cnpj"), "issuer_cnpj");
    assert.equal(roleForPath(sections, "itens.0.descricao"), "service");
    // Array item value rendered.
    assert.equal(rowsByPath(sections).get("itens.0.descricao").value, "Item A");
});

test("boleto: total←valor_documento, issuer←beneficiario", () => {
    const boleto = {
        doc_type: "boleto",
        schema_version: "1",
        beneficiario: { nome: "Banco do Servico", cnpj_cpf: "11222333000181" },
        pagador: { nome: "Condominio" },
        valor_documento: 540.5,
        data_documento: "2025-02-01",
        numero_documento: "BOL-9",
    };
    const sections = buildTypedSections(boleto, t, locale);
    assert.equal(roleForPath(sections, "valor_documento"), "total");
    assert.equal(roleForPath(sections, "beneficiario.nome"), "issuer_name");
    assert.equal(roleForPath(sections, "numero_documento"), "number");
});

test("recibo: total←valor, issuer←recebedor, service←referente_a", () => {
    const recibo = {
        doc_type: "recibo",
        schema_version: "1",
        numero: "R-1",
        data: "2025-04-01",
        recebedor: { nome: "Prestador X", cnpj_cpf: "11222333000181" },
        pagador: { nome: "Condominio" },
        valor: 200,
        referente_a: "Servico de limpeza",
    };
    const sections = buildTypedSections(recibo, t, locale);
    assert.equal(roleForPath(sections, "valor"), "total");
    assert.equal(roleForPath(sections, "recebedor.nome"), "issuer_name");
    assert.equal(roleForPath(sections, "referente_a"), "service");
});

test("comprovante_pagamento: total←valor, issuer←recebedor, number←identificador", () => {
    const comp = {
        doc_type: "comprovante_pagamento",
        schema_version: "1",
        tipo: "PIX",
        data: "2025-05-01",
        recebedor: { nome: "Prestador X", cnpj_cpf: "11222333000181" },
        valor: 750,
        identificador: "E12345",
    };
    const sections = buildTypedSections(comp, t, locale);
    assert.equal(roleForPath(sections, "valor"), "total");
    assert.equal(roleForPath(sections, "recebedor.nome"), "issuer_name");
    assert.equal(roleForPath(sections, "identificador"), "number");
});

test("outro: total←valores_identificados.0.valor (best-effort), service←descricao, generic", () => {
    const outro = {
        doc_type: "outro",
        schema_version: "1",
        descricao: "Documento diverso",
        valores_identificados: [{ rotulo: "Total", valor: 99.9 }],
    };
    const sections = buildTypedSections(outro, t, locale);
    assert.equal(roleForPath(sections, "valores_identificados.0.valor"), "total");
    assert.equal(roleForPath(sections, "descricao"), "service");
});

// ─── Robustness ──────────────────────────────────────────────────────────────────────────────────

test("absent/null provenance target → no role tag, no throw", () => {
    const nfse = {
        doc_type: "nfse",
        schema_version: "1",
        numero: "1",
        // no `valores` at all, no prestador → total/issuer targets absent
    };
    const sections = buildTypedSections(nfse, t, locale);
    // number is present and tagged; total/issuer simply have no row → no tag, no error.
    assert.equal(roleForPath(sections, "numero"), "number");
    assert.equal(roleForPath(sections, "valores.valor_liquido"), undefined);
    assert.equal(roleForPath(sections, "prestador.nome"), undefined);
});

test("malformed / partial typed shapes never throw and drop nothing present", () => {
    const cases = [
        { doc_type: "nfse", schema_version: "1", valores: null, prestador: null },
        { doc_type: "danfe", schema_version: "1", itens: [], totais: {} },
        { doc_type: "weird-unknown-type", schema_version: "1", foo: "bar", nested: { a: 1, b: null } },
        { doc_type: "outro", schema_version: "1", valores_identificados: "not-an-array" },
        { doc_type: "nfse", schema_version: "1" },
    ];
    for (const c of cases) {
        let sections;
        assert.doesNotThrow(() => {
            sections = buildTypedSections(c, t, locale);
        });
        assert.ok(Array.isArray(sections));
    }
    // The unknown-type case still surfaces its scalar + nested scalar.
    const unknown = buildTypedSections(
        { doc_type: "weird-unknown-type", schema_version: "1", foo: "bar", nested: { a: 1, b: null } },
        t,
        locale
    );
    const byPath = rowsByPath(unknown);
    assert.equal(byPath.get("foo").value, "bar");
    assert.equal(byPath.get("nested.a").value, "1");
    assert.equal(byPath.has("nested.b"), false); // null dropped
    assert.equal(byPath.has("doc_type"), false); // discriminator hidden even for unknown types
});

test("amount leaves are currency-formatted per locale (pt-BR BRL / en USD)", () => {
    const recibo = { doc_type: "recibo", schema_version: "1", valor: 1234.5, recebedor: { nome: "X" } };
    const ptRows = rowsByPath(buildTypedSections(recibo, makeT("pt-BR"), "pt-BR"));
    const enRows = rowsByPath(buildTypedSections(recibo, makeT("en"), "en"));
    // pt-BR uses R$ (BRL); en uses $ (USD). Exact glyphs vary by ICU, so assert the currency marker.
    assert.match(ptRows.get("valor").value, /R\$/);
    assert.match(enRows.get("valor").value, /\$/);
});

test("empty string values are omitted (no empty noise)", () => {
    const sections = buildTypedSections(
        { doc_type: "recibo", schema_version: "1", numero: "", valor: 10, recebedor: { nome: "", cnpj_cpf: "X1" } },
        t,
        locale
    );
    const byPath = rowsByPath(sections);
    assert.equal(byPath.has("numero"), false); // "" omitted
    assert.equal(byPath.has("recebedor.nome"), false); // "" omitted
    assert.ok(byPath.has("recebedor.cnpj_cpf")); // present
    assert.ok(byPath.has("valor"));
});
