"""Agent-driven attachment extraction: plan -> (Claude vision) -> apply.

This module replaces the local-VLM extraction step. The flow is three touchpoints
around a Claude vision skill (`.claude/skills/classify-doc-page`, usually driven
per period by `.claude/skills/classify-period`):

1. ``plan_extractions`` selects + groups the attachments to analyze (reusing
   ``select_work``) and **prints** the work plan as JSON to stdout — the
   ``classify-period`` skill parses that, no file is written. Each plan page carries a
   ``recorded`` flag (whether its extraction is already in D1) so the skill can
   re-dispatch only the pages still missing one.
2. The vision skill views each representative page image and **records** that page's
   parsed fields (or ``{"error": ...}``) directly to the D1 ``page_classifications``
   staging table, via the ``record-classification`` CLI (feature 017 — there is no
   ``.classify.json`` file).
3. ``apply_extractions`` re-derives the identical plan from D1 (the plan is a pure
   function of D1 + materialized images via ``build_plan``), reads each page's recorded
   extraction from D1 (via ``D1ExtractionProvider``), and runs the existing
   deterministic roll-up / group reconciliation / sibling fan-out / entry
   validation / write-back, producing the authoritative ``attachment_analyses``.

The plan is derived from the database (feature 016): the shared-NF grouping key lives
in ``attachments.content_hash`` (written at scrape time), so there is no longer a
``<period>.extract-todo.json`` manifest. The per-page classification contract is
``.claude/skills/classify-doc-page``; the staging-table seam is
``.page_classifications`` (``record_classification`` / ``D1ExtractionProvider``).
"""

import json
import logging
from pathlib import Path

from common import d1
from common.d1 import Target

from .attachments import (
    AttachmentAnalysisResult,
    _apply_group_amount_match,
    _fanout_result,
    _merge_and_write,
    _page_label_from_path,
    build_attachment_analysis,
    select_work,
    summarize_results,
)
from .images import attachments_needing_hash_backfill, materialize_period_images
from .loader import load_all_periods
from .mismatches import KIND_AMOUNT, KIND_DATE, KIND_PAGE_ERROR, KIND_VENDOR, detect_attachment_mismatches
from .page_classifications import D1ExtractionProvider

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "../.cache/analysis"


def build_plan(
    periods,
    refs,
    *,
    cache_dir: str = DEFAULT_CACHE_DIR,
    min_amount: float | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Derive the per-period extraction plan from loaded D1 data (no file).

    Pure function of the already-loaded ``periods`` + ``refs`` (and the materialized
    page images they point at): selects + groups the **pending** attachments (those with
    ``classified_at IS NULL``) via ``select_work`` and returns one plan envelope per
    period — ``{period, cache_dir, generated_for, groups: [...]}`` — where each group
    lists its representative attachment's pages and the full member list. This is the same
    structure the old ``<period>.extract-todo.json`` manifest held, so both
    ``plan_extractions`` (prints it) and ``apply_extractions`` (applies it) build it the
    same way and stay consistent without a shared file. Which attachments are pending is
    controlled in D1 (``mark-pending``), not by id arguments here.
    """
    work = select_work(periods, min_amount=min_amount, limit=limit)

    # Group selected items by period then NF group, preserving the amount-desc
    # order from select_work so items[0] is the highest-amount representative.
    by_period: dict[str, dict[str, list]] = {}
    for item in work:
        by_period.setdefault(item.period, {}).setdefault(item.group_key, []).append(item)

    generated_for = {"min_amount": min_amount, "limit": limit}

    envelopes: list[dict] = []
    for period, groups in by_period.items():
        # Pages already recorded in the staging table (so classify-period can re-dispatch
        # only the ones still missing — the DB-derived completeness check). Keyed by
        # (attachment_id, page_label), matching the record/lookup key.
        recorded_keys = {
            (r["attachment_id"], r["page_label"]) for r in periods[period].raw.get("page_classifications", [])
        }
        out_groups = []
        for gkey, items in groups.items():
            rep = items[0]
            tokens = [p.strip() for p in rep.attachment["file_path"].split(";") if p.strip()]
            pages = [
                {
                    "page_index": idx,
                    "page_label": _page_label_from_path(token, idx),
                    "path": token,
                    "read_path": str(Path(token).resolve()),
                    "recorded": (rep.attachment["id"], _page_label_from_path(token, idx)) in recorded_keys,
                }
                for idx, token in enumerate(tokens)
            ]
            members = []
            for it in items:
                vendor_name = refs.vendor_name(it.entry["vendor_id"]) if it.entry.get("vendor_id") else None
                members.append(
                    {
                        "attachment_id": it.attachment["id"],
                        "entry_id": it.entry["id"],
                        "entry_amount": it.entry["amount"],
                        "vendor_name": vendor_name,
                        "is_representative": it is rep,
                    }
                )
            out_groups.append(
                {
                    "group_key": gkey,
                    "representative_attachment_id": rep.attachment["id"],
                    "group_size": rep.group_size,
                    "sibling_sum": rep.sibling_sum,
                    "pages": pages,
                    "members": members,
                }
            )
        envelopes.append(
            {
                "period": period,
                "cache_dir": cache_dir,
                "generated_for": generated_for,
                "groups": out_groups,
            }
        )
    return envelopes


def plan_extractions(
    target: Target = "local",
    periods_filter: list[str] | None = None,
    *,
    cache_dir: str = DEFAULT_CACHE_DIR,
    min_amount: float | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Print the DB-derived work plan to stdout (no manifest file).

    Materializes the period's page images from R2 into the cache (so each page's
    ``read_path`` points at a local file the vision skill can read and grouping can hash
    legacy rows), derives the plan of **pending** attachments via ``build_plan``, and
    prints it as a JSON list of per-period envelopes to **stdout** — which the
    ``classify-period`` skill parses. All human/progress text goes to the log (stderr),
    keeping stdout pure JSON. Returns the envelopes too (for in-process callers/tests).
    """
    periods, refs = load_all_periods(target, periods_filter)
    if not periods:
        logger.info("No periods to plan")
        print("[]")
        return []

    # Bring the period's images local (R2 -> cache) so read_paths/grouping work.
    # docs-plan is read-only: it does NOT backfill content_hash (a D1 write would stream
    # the wrangler banner onto stdout and corrupt the JSON the skill parses). The backfill
    # happens in apply-extractions instead.
    materialize_period_images(periods, cache_dir, target, backfill_hash=False)

    envelopes = build_plan(periods, refs, cache_dir=cache_dir, min_amount=min_amount, limit=limit)

    total_groups = sum(len(env["groups"]) for env in envelopes)
    total_pages = sum(len(g["pages"]) for env in envelopes for g in env["groups"])
    if not total_groups:
        logger.info("Nothing to extract (no matching attachments).")
        print("[]")
        return []

    logger.info(
        "Planned %d group(s), %d representative page(s) across %d period(s). "
        "Next: classify each page (classify-doc-page records each to D1), then apply-extractions.",
        total_groups, total_pages, len(envelopes),
    )
    # stdout is pure JSON so the classify-period skill can parse it directly.
    print(json.dumps(envelopes, ensure_ascii=False, indent=2))
    return envelopes


def apply_extractions(
    target: Target = "local",
    periods_filter: list[str] | None = None,
    *,
    cache_dir: str = DEFAULT_CACHE_DIR,
    min_amount: float | None = None,
    limit: int | None = None,
) -> None:
    """Merge per-page classifications into ``attachment_analyses`` in D1.

    Re-derives the same plan ``docs-plan`` produced (via ``build_plan`` from D1 +
    materialized images — no manifest file), rebuilds each representative attachment's
    analysis from each page's extraction recorded in the ``page_classifications`` staging
    table (via ``D1ExtractionProvider``), reconciles shared-NF groups, fans the extraction
    out to sibling members, and writes each result to D1 (delete-then-insert), then stamps
    ``attachments.classified_at`` so each leaves the pending set. A page with no recorded
    classification is recorded as a per-page error and does not abort the attachment.

    The per-page extractions come from D1, not a cache file, so a re-run depends only on
    D1 state (clearing the cache cannot lose recorded vision work). There are no id
    arguments: the set of attachments processed is exactly the **pending** set
    (``classified_at IS NULL``), controlled in D1 via ``mark-pending``. So a scoped re-run
    is "mark those attachments pending, then run this" — deterministic and file-free.

    Apply reads **no image bytes** itself (per-page extractions come from D1, page labels
    are parsed from ``file_path`` tokens, and grouping prefers the persisted
    ``attachments.content_hash`` column), so materialization is now **conditional**: it runs
    only to hash + backfill the attachments whose ``content_hash`` is still NULL. When every
    page-bearing attachment is already keyed (the normal case post-scrape), the R2 round-trip
    is skipped entirely. The classify (``docs-plan``) and review (``mismatches``) paths are
    unaffected — they keep materializing their images.
    """
    periods, refs = load_all_periods(target, periods_filter)
    if not periods:
        logger.info("No periods to apply")
        return

    # Only attachments still missing a content_hash need their images (to hash + backfill);
    # everything else groups from the stored column, and apply reads no image bytes. So skip
    # the R2 round-trip when there's nothing to backfill (scope the fetch to what needs it).
    needing = attachments_needing_hash_backfill(periods)
    if needing:
        materialize_period_images(periods, cache_dir, target, attachment_ids=needing)
    else:
        logger.info("All page-bearing attachments already have content_hash; skipping R2 image materialization")

    envelopes = build_plan(periods, refs, cache_dir=cache_dir, min_amount=min_amount, limit=limit)

    all_results: list[AttachmentAnalysisResult] = []
    for env in envelopes:
        period = env["period"]
        # Per-page extractions for this period come from the D1 staging table (loaded into
        # the period's raw dict), keyed by (attachment_id, page_label) — no cache file.
        provider = D1ExtractionProvider(periods[period].raw.get("page_classifications", []))
        results: list[AttachmentAnalysisResult] = []
        for group in env["groups"]:
            gsize = group["group_size"]
            sibling_sum = group["sibling_sum"]
            members = group["members"]
            rep_member = next((m for m in members if m.get("is_representative")), members[0] if members else None)
            if rep_member is None:
                continue

            # The page tokens only drive page count + page_label derivation here (the
            # per-page extractions are looked up in D1 by (attachment_id, page_label)).
            rep_file_path = ";".join(p.get("read_path") or p["path"] for p in group["pages"])
            rep_result = build_attachment_analysis(
                rep_file_path,
                rep_member["entry_amount"],
                rep_member.get("vendor_name"),
                period,
                rep_member["attachment_id"],
                rep_member["entry_id"],
                provider,
            )
            if gsize > 1 and not rep_result.error:
                _apply_group_amount_match(rep_result, sibling_sum)
            results.append(rep_result)
            _merge_and_write(rep_result, target=target)

            for m in members:
                if m.get("is_representative"):
                    continue
                if rep_result.error:
                    sib = AttachmentAnalysisResult(
                        attachment_id=m["attachment_id"],
                        entry_id=m["entry_id"],
                        entry_amount=m["entry_amount"],
                    )
                    sib.error = rep_result.error
                else:
                    sib = _fanout_result(
                        rep_result, m["attachment_id"], m["entry_id"], m["entry_amount"], m.get("vendor_name"), period
                    )
                    if gsize > 1:
                        _apply_group_amount_match(sib, sibling_sum)
                results.append(sib)
                _merge_and_write(sib, target=target)

        logger.info("Applied %d analysis row(s) for %s", len(results), period)
        all_results.extend(results)

    if not all_results:
        logger.info("No extractions applied")
        return
    summarize_results(all_results)


def mark_pending(
    target: Target,
    period: str | None = None,
    *,
    attachment_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
) -> int:
    """Clear ``attachment_state.classified_at`` for the given attachments/entries (re-queue them).

    The deterministic, SQL-controlled way to request re-classification: a marked
    attachment becomes **pending** again, so the next ``docs-plan``/``apply-extractions``
    picks it up — without threading id lists through the classify pipeline. The state lives
    in the analysis-owned ``attachment_state`` table; this never writes the mirror table
    ``attachments`` (BUG-002 / issue #33). Scoping is by attachment id and/or entry id (ids
    are globally unique deterministic UUIDs); an entry-id scope is resolved to attachment ids
    via ``attachments`` (read-only). ``period`` is accepted for symmetry/logging and is not
    required for the match. Returns the number of ids requested (0 when none are given).

    An attachment with no ``attachment_state`` row is already pending (no row ⇒ pending), so
    the UPDATE only needs to clear rows that exist; nothing is created to "mark pending".
    """
    clauses = []
    if attachment_ids:
        ids = ",".join("'" + str(i).replace("'", "''") + "'" for i in attachment_ids)
        clauses.append(f"attachment_id IN ({ids})")
    if entry_ids:
        eids = ",".join("'" + str(i).replace("'", "''") + "'" for i in entry_ids)
        # Resolve entry ids to attachment ids without touching the mirror table for writes:
        # the SELECT against `attachments` is read-only; only `attachment_state` is updated.
        clauses.append(f"attachment_id IN (SELECT id FROM attachments WHERE entry_id IN ({eids}))")
    if not clauses:
        logger.info("mark-pending: no attachment/entry ids given; nothing to do")
        return 0
    where = " OR ".join(clauses)
    d1.execute_sql(f"UPDATE attachment_state SET classified_at = NULL WHERE {where};", target=target)
    n = len(attachment_ids or []) + len(entry_ids or [])
    logger.info("mark-pending: requested re-classification for %d id(s)%s", n, f" in {period}" if period else "")
    return n


def _page_refs_for_doc(doc: dict | None) -> list[dict]:
    """Page references for a attachment's image(s): ``{attachment_id, page_label, read_path}``.

    Derives from the attachment's ``file_path`` tokens (the same source ``docs-plan``
    uses), resolving each to an absolute ``read_path`` for the review worker's Read
    tool. Included in the mismatch summary so FR-004 (page reference(s) in the
    summary) holds literally.
    """
    if not doc:
        return []
    tokens = [p.strip() for p in (doc.get("file_path") or "").split(";") if p.strip()]
    return [
        {
            "attachment_id": doc["id"],
            "page_label": _page_label_from_path(token, idx),
            "read_path": str(Path(token).resolve()),
        }
        for idx, token in enumerate(tokens)
    ]


def summarize_mismatches(
    target: Target = "local",
    periods_filter: list[str] | None = None,
    *,
    cache_dir: str = DEFAULT_CACHE_DIR,
    attachment_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
) -> list[dict]:
    """Terse, machine-readable list of classification mismatches for a caller/loop.

    Read-only (no model, no writes): joins the persisted ``attachment_analyses``
    (amount / vendor / date / page-error) and ``document_overpayment`` alerts with the
    ledger entries, optionally scoped to specific attachment or entry ids. Each row
    carries ``page_refs`` (the attachment's page image(s)) so the review worker can
    open the evidence directly (FR-004). This is the concise hand-back the vision
    step returns instead of dumping page images or full artifacts. Run after
    ``apply_extractions`` (for the analyses) and ``analyze`` (for the alerts).
    """
    periods, refs = load_all_periods(target, periods_filter)
    # Bring images local so each page_ref's read_path points at a cache file the
    # review worker can open (scoped to the attachments under review when given).
    materialize_period_images(periods, cache_dir, target, attachment_ids=attachment_ids)
    doc_filter = set(attachment_ids) if attachment_ids else None
    entry_filter = set(entry_ids) if entry_ids else None

    out: list[dict] = []
    for period, pd in periods.items():
        doc_map = {d["id"]: d for d in pd.attachments}

        # Per-attachment mismatches come from the shared detector (single source of truth
        # with check_attachment_mismatches — FR-004), then get page_refs + scoping added here.
        for mm in detect_attachment_mismatches(pd, refs):
            if doc_filter is not None and mm.attachment_id not in doc_filter:
                continue
            if entry_filter is not None and mm.entry_id not in entry_filter:
                continue
            base = {
                "period": period,
                "attachment_id": mm.attachment_id,
                "entry_id": mm.entry_id,
                "page_refs": _page_refs_for_doc(doc_map.get(mm.attachment_id)),
            }
            if mm.kind == KIND_PAGE_ERROR:
                out.append({**base, "kind": "page-error", "detail": mm.detail})
            elif mm.kind == KIND_AMOUNT:
                out.append(
                    {**base, "kind": "amount", "ledger_amount": mm.ledger_value, "extracted_amount": mm.extracted_value}
                )
            elif mm.kind == KIND_VENDOR:
                out.append(
                    {**base, "kind": "vendor", "ledger_vendor": mm.ledger_value, "extracted_issuer": mm.extracted_value}
                )
            elif mm.kind == KIND_DATE:
                out.append(
                    {**base, "kind": "date", "expected_period": period, "extracted_date": mm.extracted_value}
                )

        # document_overpayment (feature 020) — the entity-backed successor to the retired
        # duplicate_billing over-claim signal. Its metadata carries entry_ids (no
        # attachment_ids), so page_refs are resolved via the entries' attachments.
        entry_to_doc = {a["entry_id"]: a["id"] for a in pd.attachments}
        for al in pd.raw.get("alerts", []):
            if al.get("type") != "document_overpayment":
                continue
            meta = {}
            if al.get("metadata"):
                try:
                    meta = json.loads(al["metadata"])
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            entids = meta.get("entry_ids", []) or []
            docids = [entry_to_doc[e] for e in entids if e in entry_to_doc]
            if doc_filter is not None and not (set(docids) & doc_filter):
                continue
            if entry_filter is not None and not (set(entids) & entry_filter):
                continue
            over_page_refs: list[dict] = []
            for did in docids:
                over_page_refs.extend(_page_refs_for_doc(doc_map.get(did)))
            out.append(
                {
                    "period": period,
                    "kind": "document_overpayment",
                    "document_id": meta.get("document_id"),
                    "document_number": meta.get("document_number"),
                    "attachment_ids": docids,
                    "entry_ids": entids,
                    "total_value": meta.get("total_value"),
                    "sum_entries": meta.get("sum_entries"),
                    "over_amount": meta.get("over_amount"),
                    "page_refs": over_page_refs,
                }
            )
    return out
