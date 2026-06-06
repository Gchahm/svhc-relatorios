"""Agent-driven document extraction: plan -> (Claude vision agent) -> apply.

This module replaces the local-VLM extraction step. The flow is three touchpoints
around a Claude vision subagent (`.claude/agents/analyze-docs.md`):

1. ``plan_extractions`` selects + groups the documents to analyze (reusing
   ``select_work``) and writes a work manifest ``<period>.extract-todo.json``.
2. The agent reads that manifest, views each representative page image, and writes
   a per-page ``<period>.extractions.json`` mapping a page ``path`` to its parsed
   fields (or ``{"error": ...}``).
3. ``apply_extractions`` consumes the manifest + extractions and runs the existing
   deterministic roll-up / group reconciliation / sibling fan-out / entry
   validation / write-back, producing ``document_analyses`` identical in shape to
   the old flow.

The contracts for the two files live under
``specs/006-analyze-docs-agent/contracts/``.
"""

import json
import logging
from pathlib import Path

from .documentos import (
    DocAnalysisResult,
    _apply_group_amount_match,
    _fanout_result,
    _merge_and_write,
    _page_label_from_path,
    _parse_json_blob,
    build_document_analysis,
    select_work,
    summarize_results,
)
from .loader import load_all_periods

logger = logging.getLogger(__name__)


def extract_todo_path(data_dir: str, period: str) -> Path:
    """Path of the work manifest for a period."""
    return Path(data_dir) / f"{period}.extract-todo.json"


def extractions_path(data_dir: str, period: str) -> Path:
    """Path of the agent-produced extractions file for a period."""
    return Path(data_dir) / f"{period}.extractions.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class FileExtractionProvider:
    """Extraction provider backed by an agent-written extractions map.

    Maps a page ``path`` to ``(fields, None)`` for a fields object, ``(None,
    reason)`` for an ``{"error": ...}`` object, and ``(None, "no extraction for
    page")`` when the path is absent — matching the ``ExtractionProvider`` seam in
    ``documentos.build_document_analysis``.
    """

    def __init__(self, extractions: dict | None):
        self._ex = extractions or {}

    def __call__(self, path: str) -> tuple[dict | None, str | None]:
        val = self._ex.get(path)
        if val is None:
            return None, "no extraction for page"
        # Tolerate a string-wrapped JSON object just in case.
        if isinstance(val, str):
            val = _parse_json_blob(val)
            if val is None:
                return None, "unparseable extraction entry"
        if not isinstance(val, dict):
            return None, "invalid extraction entry"
        if "error" in val:
            return None, str(val.get("error") or "extraction error")
        return val, None


def plan_extractions(
    data_dir: str,
    periods_filter: list[str] | None = None,
    *,
    min_amount: float | None = None,
    limit: int | None = None,
    reanalyze: bool = False,
    document_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
) -> None:
    """Write the work manifest(s) the analyze-docs agent consumes.

    One ``<period>.extract-todo.json`` per period with documents to analyze. Each
    shared-NF group lists its representative document's pages (with an absolute
    ``read_path`` for the agent's Read tool) plus the full member list.
    """
    periods, refs = load_all_periods(data_dir, periods_filter)
    if not periods:
        logger.info("No periods to plan")
        return

    work = select_work(
        periods,
        min_amount=min_amount,
        limit=limit,
        reanalyze=reanalyze,
        document_ids=document_ids,
        entry_ids=entry_ids,
    )
    if not work:
        logger.info("No documents to plan")
        print("\nNothing to extract (no matching documents).")
        return

    # Group selected items by period then NF group, preserving the amount-desc
    # order from select_work so items[0] is the highest-amount representative.
    by_period: dict[str, dict[str, list]] = {}
    for item in work:
        by_period.setdefault(item.period, {}).setdefault(item.group_key, []).append(item)

    total_groups = 0
    total_pages = 0
    for period, groups in by_period.items():
        out_groups = []
        for gkey, items in groups.items():
            rep = items[0]
            tokens = [p.strip() for p in rep.document["file_path"].split(";") if p.strip()]
            pages = [
                {
                    "page_index": idx,
                    "page_label": _page_label_from_path(token, idx),
                    "path": token,
                    "read_path": str(Path(token).resolve()),
                }
                for idx, token in enumerate(tokens)
            ]
            members = []
            for it in items:
                vendor_name = refs.vendor_name(it.entry["vendor_id"]) if it.entry.get("vendor_id") else None
                members.append(
                    {
                        "document_id": it.document["id"],
                        "entry_id": it.entry["id"],
                        "entry_amount": it.entry["amount"],
                        "vendor_name": vendor_name,
                        "is_representative": it is rep,
                    }
                )
            out_groups.append(
                {
                    "group_key": gkey,
                    "representative_document_id": rep.document["id"],
                    "group_size": rep.group_size,
                    "sibling_sum": rep.sibling_sum,
                    "pages": pages,
                    "members": members,
                }
            )
            total_groups += 1
            total_pages += len(pages)

        manifest = {
            "period": period,
            "data_dir": data_dir,
            "generated_for": {
                "min_amount": min_amount,
                "limit": limit,
                "reanalyze": reanalyze,
                "document_ids": document_ids,
                "entry_ids": entry_ids,
            },
            "groups": out_groups,
        }
        path = extract_todo_path(data_dir, period)
        _write_json(path, manifest)
        logger.info("Wrote %s: %d group(s), %d page(s) to extract", path, len(out_groups), total_pages)

    print(f"\nPlanned {total_groups} group(s), {total_pages} representative page(s) across {len(by_period)} period(s).")
    print("Next: run the analyze-docs agent to produce <period>.extractions.json, then `apply-extractions`.")


def _periods_with_manifests(data_dir: str) -> list[str]:
    suffix = ".extract-todo.json"
    return sorted(p.name[: -len(suffix)] for p in Path(data_dir).glob(f"*{suffix}"))


def apply_extractions(
    data_dir: str,
    periods_filter: list[str] | None = None,
) -> None:
    """Merge agent extractions into period JSON(s) as ``document_analyses``.

    For each period with a manifest, reads the extractions file, rebuilds the
    representative document's analysis via the deterministic pipeline, reconciles
    shared-NF groups, fans the extraction out to sibling members, and writes the
    results back — the same output the old VLM runner produced.
    """
    data_path = Path(data_dir)
    target_periods = periods_filter or _periods_with_manifests(data_dir)
    if not target_periods:
        logger.info("No manifests found; run docs-plan first")
        return

    all_results: list[DocAnalysisResult] = []
    for period in target_periods:
        todo_path = extract_todo_path(data_dir, period)
        if not todo_path.exists():
            logger.warning("No manifest for %s (%s); run docs-plan first", period, todo_path)
            continue
        ex_path = extractions_path(data_dir, period)
        if not ex_path.exists():
            logger.warning("No extractions for %s (%s); run the analyze-docs agent first", period, ex_path)
            continue

        manifest = _read_json(todo_path)
        provider = FileExtractionProvider(_read_json(ex_path))
        period_json = data_path / f"{period}.json"
        raw = json.loads(period_json.read_text(encoding="utf-8"))

        results: list[DocAnalysisResult] = []
        for group in manifest.get("groups", []):
            gsize = group["group_size"]
            sibling_sum = group["sibling_sum"]
            members = group["members"]
            rep_member = next((m for m in members if m.get("is_representative")), members[0] if members else None)
            if rep_member is None:
                continue

            rep_file_path = ";".join(p["path"] for p in group["pages"])
            rep_result = build_document_analysis(
                rep_file_path,
                rep_member["entry_amount"],
                rep_member.get("vendor_name"),
                period,
                rep_member["document_id"],
                rep_member["entry_id"],
                provider,
            )
            if gsize > 1 and not rep_result.error:
                _apply_group_amount_match(rep_result, sibling_sum)
            results.append(rep_result)
            _merge_and_write(data_path, period, raw, rep_result)

            for m in members:
                if m.get("is_representative"):
                    continue
                if rep_result.error:
                    sib = DocAnalysisResult(
                        document_id=m["document_id"],
                        entry_id=m["entry_id"],
                        entry_amount=m["entry_amount"],
                    )
                    sib.error = rep_result.error
                else:
                    sib = _fanout_result(
                        rep_result, m["document_id"], m["entry_id"], m["entry_amount"], m.get("vendor_name"), period
                    )
                    if gsize > 1:
                        _apply_group_amount_match(sib, sibling_sum)
                results.append(sib)
                _merge_and_write(data_path, period, raw, sib)

        logger.info("Applied %d analysis row(s) for %s", len(results), period)
        all_results.extend(results)

    if not all_results:
        logger.info("No extractions applied")
        return
    summarize_results(all_results)
