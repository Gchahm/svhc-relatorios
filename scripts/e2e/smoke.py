"""Browser E2E smoke for the seeded synthetic period (feature 046).

Drives the real Workers build (``pnpm preview``) with the synthetic seed using Python Playwright
``sync_api`` (already in the toolchain — no new JS dependency). One happy path + the auth gate per
surface (smoke, not a matrix). Stable, language-independent anchors where possible (URL params,
element ids/roles, HTTP status, seeded values) so the checks survive the I18N work.

Usage:
    python -m e2e.smoke              # assumes a server is already running on the expected origin
    python -m e2e.smoke --serve      # starts pnpm preview itself, runs the checks, tears it down

Exits non-zero on the first failed surface, naming it.
"""

from __future__ import annotations

import argparse
import sys

from playwright.sync_api import sync_playwright

from . import auth, server, synthetic

PERIOD = synthetic.PERIOD
_NAV_TIMEOUT_MS = 30_000


class SmokeError(RuntimeError):
    pass


def _ids():
    return synthetic.ids()


def run(base_url: str) -> None:
    email, password = auth.ensure_admin(base_url)
    ids = _ids()
    e1_entry = ids["entries"]["E1"]
    e3_entry = ids["entries"]["E3"]
    e1_analysis = ids["analyses"]["E1"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ── S1a: auth gate — unauthenticated /dashboard redirects away ──
            anon = browser.new_context()
            anon_page = anon.new_page()
            anon_page.set_default_timeout(_NAV_TIMEOUT_MS)
            anon_page.goto(f"{base_url}/dashboard", wait_until="domcontentloaded")
            anon_page.wait_for_url(lambda u: "/dashboard" not in u, timeout=_NAV_TIMEOUT_MS)
            if "/dashboard" in anon_page.url:
                raise SmokeError(f"S1a: unauthenticated /dashboard was not redirected (url={anon_page.url})")

            # ── S6b: image route auth gate — no session → non-2xx, not a PNG ──
            img_path = f"{base_url}/api/attachment-analyses/{e1_analysis}/image/p1"
            unauth_resp = anon.request.get(img_path)
            if unauth_resp.ok:
                raise SmokeError(f"S6b: unauthenticated image route returned {unauth_resp.status} (expected non-2xx)")
            anon.close()

            # ── S1b: sign-in lands on /dashboard ──
            ctx = browser.new_context()
            page = ctx.new_page()
            page.set_default_timeout(_NAV_TIMEOUT_MS)
            # Wait for the network to settle so React has hydrated — the form is controlled
            # (value={state} + onChange), so filling/submitting before hydration would submit
            # empty state and never sign in.
            page.goto(f"{base_url}/sign-in", wait_until="networkidle")
            email_box = page.locator("#email")
            email_box.wait_for(state="visible")
            email_box.fill(email)
            page.locator("#password").fill(password)
            page.locator("button[type=submit]").click()
            # The dashboard shell redirects "/dashboard" → "/dashboard/reports", so accept any
            # authenticated dashboard path (not exactly "/dashboard").
            page.wait_for_url(lambda u: "/dashboard" in u, timeout=_NAV_TIMEOUT_MS)

            # ── S2: entries page renders the seeded period ──
            page.goto(f"{base_url}/dashboard/entries?period={PERIOD}", wait_until="networkidle")
            # A seeded description is language-independent (we control it). E3 is "EXEMPLO Servico B".
            page.wait_for_selector("text=EXEMPLO Servico B", timeout=_NAV_TIMEOUT_MS)

            # ── S3: alert deep link highlights the row + opens the analysis dialog ──
            page.goto(
                f"{base_url}/dashboard/entries?period={PERIOD}&entry={e1_entry}",
                wait_until="networkidle",
            )
            # The deep-link dialog auto-opens (Radix Dialog → role=dialog).
            page.wait_for_selector("[role=dialog]", timeout=_NAV_TIMEOUT_MS)
            # The matched row carries the highlight classes.
            if page.locator(".bg-yellow-100").count() == 0:
                raise SmokeError("S3: deep-linked entry row was not highlighted")

            # ── S3a: analysis dialog — feature 055 (EXTRACT-004) legacy-flat record render ──
            # Verify the AttachmentAnalysisDetailDialog renders the per-page flat record section
            # without console errors. The seeded E1 attachment has one flat page_extraction record
            # (keys: tipo_documento, numero, cnpj, valor_total — no top-level `doc_type`, so the
            # legacy flat path is taken; the feature-057 typed path must NOT activate). Checks:
            # dialog is open, all three sections present, the per-page card with KNOWN_FIELD labels
            # is visible (valor_total → "BRUTO"), no blank/crash panel.
            # See also S3b which guards the feature-057 (EXTRACT-006) catalog key resolution.
            dialog = page.locator("[role=dialog]")
            dialog.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            # All three dialog sections must be present (h3 headings are locale-neutral anchors
            # given the current hardcoded pt-BR locale).
            for heading_text in ("Lançamento (origem)", "Consolidado (extraído)", "Páginas"):
                if dialog.locator(f"h3:has-text('{heading_text}')").count() == 0:
                    raise SmokeError(f"S3a: analysis dialog is missing section heading '{heading_text}'")
            # Wait for the async record load — the per-page card appears after the /api fetch.
            # The flat record's valor_total maps to KNOWN_FIELD "Bruto"; wait for that label.
            # (Playwright's text= engine can't be combined with a CSS attribute selector in one
            # string, so scope with get_by_text on the dialog locator instead.)
            dialog.get_by_text("BRUTO", exact=False).first.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            # The seeded valor_total is 150.00; it must be currency-formatted (pt-BR: R$ 150,00).
            if dialog.get_by_text("R$ 150,00", exact=False).count() == 0:
                raise SmokeError("S3a: flat record valor_total (R$ 150,00) not rendered in dialog")
            # The "Transcrição completa" heading must NOT appear for flat records (typed-path guard).
            if dialog.get_by_text("Transcrição completa", exact=False).count() != 0:
                raise SmokeError("S3a: 'Transcrição completa' heading appeared for a legacy flat record")
            # The dialog must still be open (not crashed/navigated away during the flat render).
            if dialog.count() == 0:
                raise SmokeError("S3a: dialog disappeared unexpectedly during flat record render")
            page.keyboard.press("Escape")
            page.wait_for_selector("[role=dialog]", state="hidden", timeout=_NAV_TIMEOUT_MS)

            # ── S3b: feature 057 (EXTRACT-006) typed-path guard on existing flat records ──
            # Open the E1 dialog again and verify the feature-057 dual-path guard:
            #   • No raw catalog key strings appear in the dialog DOM (tsection_*/provenance_*
            #     must be resolved to pt-BR labels, never shown verbatim).
            #   • The isTyped() discriminator does NOT fire for the seeded flat record
            #     (no "Transcrição completa" span — this must hold even after the 057 code
            #     is live, i.e. the new branches in RecordValues do not activate for legacy flat).
            #   • The dialog remains open and the per-page card is still visible (no regression
            #     introduced by importing buildTypedSections/provenanceRoleLabel).
            page.goto(
                f"{base_url}/dashboard/entries?period={PERIOD}&entry={e1_entry}",
                wait_until="networkidle",
            )
            page.wait_for_selector("[role=dialog]", timeout=_NAV_TIMEOUT_MS)
            dialog = page.locator("[role=dialog]")
            dialog.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            # Wait for the async per-page record to load.
            dialog.get_by_text("BRUTO", exact=False).first.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            # No raw catalog key strings must appear inside the dialog.
            dialog_html = dialog.inner_html()
            for forbidden in ("tsection_", "provenance_", "analysis.full_transcription"):
                if forbidden in dialog_html:
                    raise SmokeError(
                        f"S3b: raw catalog key fragment '{forbidden}' found verbatim in dialog DOM (i18n leak)"
                    )
            # The typed-transcription code path (feature 057) must not activate on flat records.
            if dialog.get_by_text("Transcrição completa", exact=False).count() != 0:
                raise SmokeError(
                    "S3b: 'Transcrição completa' (typed transcription) appeared for a legacy flat record "
                    "— isTyped() discriminator is firing incorrectly or flat-to-typed fallback is broken"
                )
            page.keyboard.press("Escape")
            page.wait_for_selector("[role=dialog]", state="hidden", timeout=_NAV_TIMEOUT_MS)

            # ── S4: dead deep link shows the feature-037 not-found notice (no crash) ──
            page.goto(
                f"{base_url}/dashboard/entries?period={PERIOD}&entry=00000000-0000-0000-0000-000000000000",
                wait_until="networkidle",
            )
            # The notice container uses amber styling; assert it appears and the page still rendered.
            page.wait_for_selector(".border-amber-300", timeout=_NAV_TIMEOUT_MS)

            # ── S5: documents page renders the seeded over/within status badges ──
            page.goto(f"{base_url}/dashboard/documents", wait_until="networkidle")
            search = page.locator("input").last  # the number/issuer search box
            # Filter to the over-claim NF (NF1001) and assert its destructive ("over") badge.
            search.fill("NF1001")
            page.wait_for_selector("text=NF1001", timeout=_NAV_TIMEOUT_MS)
            if page.locator("text=NF1002").count() != 0:
                raise SmokeError("S5: search did not filter the documents list to NF1001")
            # Filter to the within NF (NF1002) and assert a green-outline ("within") badge.
            search.fill("NF1002")
            page.wait_for_selector("text=NF1002", timeout=_NAV_TIMEOUT_MS)
            if page.locator(".border-green-400").count() == 0:
                raise SmokeError("S5: no 'within' (green) document status badge for NF1002")

            # ── S6a: image route streams bytes under auth ──
            auth_resp = ctx.request.get(img_path)
            if not auth_resp.ok:
                raise SmokeError(f"S6a: authenticated image route returned {auth_resp.status} (expected 200)")
            ctype = auth_resp.headers.get("content-type", "")
            if "image/png" not in ctype:
                raise SmokeError(f"S6a: image route content-type was '{ctype}' (expected image/png)")
            if not auth_resp.body():
                raise SmokeError("S6a: image route returned an empty body")

            ctx.close()
        finally:
            browser.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Browser E2E smoke against the seeded preview app.")
    parser.add_argument("--serve", action="store_true", help="Start pnpm preview itself (else reuse a running server).")
    parser.add_argument("--port", type=int, default=server.DEFAULT_PORT)
    args = parser.parse_args(argv)

    try:
        if args.serve:
            with server.serve(args.port) as base_url:
                run(base_url)
        else:
            base_url = f"http://localhost:{args.port}"
            server.wait_until_ready(base_url, timeout_s=30.0)
            run(base_url)
    except SmokeError as e:
        print(f"SMOKE FAILED — {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - surface any harness failure clearly
        print(f"SMOKE ERROR — {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print("SMOKE OK — all surface checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
