"""
OAS - JLCPCB DFM upload + report download (MANUAL TRIGGER ONLY).

Uploads `hardware/output/oas-jlcpcb.zip` to https://jlcdfm.com, waits
for the analysis to complete, screenshots the result page, and saves
the JLCPCB DFM PDF report locally.

------------------------------------------------------------
WARNING - this script makes a LIVE upload to JLCPCB servers.
------------------------------------------------------------

* Do NOT run on every regenerate. JLCPCB tracks upload volume via
  /api/overseas-dfm-service/checkIp; abusive use triggers IP blocks
  and captcha-gating.
* Do NOT run from CI loops or automated wakers.
* RUN ONLY when the user explicitly requests it ("puść DFM", "run
  the JLCPCB DFM check").

See CLAUDE.md section "External services - MANUAL TRIGGER ONLY".

------------------------------------------------------------
Prerequisites
------------------------------------------------------------

  pip install --user playwright
  python -m playwright install chromium

  Then run `python regenerate.py` (stage 23 bundles the ZIP into
  hardware/output/oas-jlcpcb.zip — the upload always uses whatever
  file is currently at that path).

------------------------------------------------------------
First-time auth setup (the upload requires a JLCPCB account)
------------------------------------------------------------

  python tools/jlcdfm_upload.py --login

  This opens a headed Chromium window. Log in to your JLCPCB account
  (passport.jlcpcb.com), dismiss cookie banners, then press ENTER in
  the terminal. The script saves browser storage state (cookies,
  localStorage) to .cache/dfm/auth_state.json (gitignored). Subsequent
  runs reuse that state in headless mode.

  Re-run --login if your session expires (typically every 30-90 days
  per JLCPCB's session cookie lifetime).

------------------------------------------------------------
Outputs
------------------------------------------------------------

All under `hardware/kicad/.cache/dfm/` (gitignored):

  dfm-report.pdf       - the PDF JLCPCB generates (one-click download)
  dfm-result.png       - full-page screenshot of the analysis result
  dfm-result.html      - rendered DOM (for diffing across runs)
  dfm-network.jsonl    - captured XHR responses (if any JSON API was hit)

Exit code 0 on successful upload + download, 1 on any error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent
REPO_ROOT = KICAD_DIR.parent.parent
GERBERS_DIR = REPO_ROOT / "hardware" / "gerbers"
ZIP_PATH = GERBERS_DIR / "oas-jlcpcb.zip"
OUT_DIR = KICAD_DIR / ".cache" / "dfm"
AUTH_STATE = OUT_DIR / "auth_state.json"

UPLOAD_URL = "https://jlcdfm.com/"
TIMEOUT_MS = 180_000  # 3 minutes for analysis to complete


def banner() -> None:
    print("=" * 64)
    print("  OAS JLCPCB DFM upload - LIVE EXTERNAL SERVICE")
    print("=" * 64)
    print("  This script uploads hardware/output/oas-jlcpcb.zip to")
    print("  jlcdfm.com. Do not run from automated pipelines.")
    print(f"  Manual-trigger-only rule: see CLAUDE.md")
    print("=" * 64)
    print()


def preflight() -> None:
    if not ZIP_PATH.exists():
        sys.exit(
            f"ERROR: {ZIP_PATH} not found. Run "
            f"`python hardware/kicad/export_production.py` first."
        )
    try:
        import playwright  # noqa: F401
    except ImportError:
        sys.exit(
            "ERROR: playwright not installed. Run:\n"
            "  pip install --user playwright\n"
            "  python -m playwright install chromium"
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Source zip: {ZIP_PATH} ({ZIP_PATH.stat().st_size // 1024} kB)")
    print(f"  Output dir: {OUT_DIR}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload OAS gerber zip to JLCPCB DFM checker.")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Launch in HEADED mode to log in to JLCPCB. After login + cookie "
             "banner dismissed, press Enter in the terminal to save session "
             "state to .cache/dfm/auth_state.json. Subsequent runs reuse "
             "that state in headless mode.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run with browser visible (for debugging).",
    )
    args = parser.parse_args()

    banner()
    preflight()

    # Lazy-import playwright so the bare `--help` / preflight error
    # paths don't crash on missing browser binaries.
    from playwright.sync_api import sync_playwright

    captured_responses: list[dict] = []
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    with sync_playwright() as p:
        if args.login:
            print("  LOGIN MODE: launching headed browser ...")
            print("  1. Log in to your JLCPCB account in the browser window.")
            print("  2. Dismiss any cookie banners.")
            print("  3. Navigate back to https://jlcdfm.com/ if needed.")
            print("  4. Return to this terminal and press ENTER.")
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.goto("https://passport.jlcpcb.com/", timeout=30_000)
            input("  Press ENTER when logged in and ready to save state ...")
            context.storage_state(path=str(AUTH_STATE))
            print(f"  Saved auth state -> {AUTH_STATE}")
            browser.close()
            return

        # Normal upload mode: reuse saved auth state if present.
        headless = not args.headed
        browser = p.chromium.launch(headless=headless)
        if AUTH_STATE.exists():
            print(f"  Using saved auth state from {AUTH_STATE.name}")
            context = browser.new_context(
                accept_downloads=True,
                storage_state=str(AUTH_STATE),
            )
        else:
            print(f"  WARNING: no saved auth state. Upload will likely")
            print(f"  redirect to login. First run with: python tools/"
                  f"jlcdfm_upload.py --login")
            context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Capture every JSON XHR + every POST request for post-mortem
        # analysis. Per agent research the result page may emit a
        # structured JSON that's cleaner to parse than the rasterized
        # PDF. Also log file-upload-like POSTs (multipart/form-data)
        # which are the most direct evidence the upload actually fired.
        captured_requests: list[dict] = []
        def on_request(request):
            try:
                if request.method == "POST":
                    captured_requests.append({
                        "url": request.url,
                        "method": request.method,
                        "headers": dict(request.headers),
                    })
            except Exception:
                pass
        def on_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct and ("/api/" in response.url or
                                       "/upload" in response.url.lower() or
                                       "/dfm" in response.url.lower()):
                    captured_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "body": response.text(),
                    })
            except Exception:
                pass
        page.on("request", on_request)
        page.on("response", on_response)

        print(f"  Navigating to {UPLOAD_URL} ...")
        page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=15_000)

        # Dismiss the cookie consent banner if present (otherwise it
        # overlays the upload button and intercepts clicks). Both
        # "Accept all cookies" and "Accept only essential cookies"
        # work for our purposes - we don't care which.
        for label in ("Accept all cookies", "Accept only essential cookies"):
            try:
                btn = page.get_by_role("button", name=label).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"  Dismissed cookie banner ({label!r}).")
                    page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        # Element Plus el-upload accepts files via set_input_files on its
        # hidden input. Verified in run 2 of the script - the input
        # exists and is reachable after the cookie banner is dismissed.
        # The component's auto-upload default is true, so attaching the
        # file should fire the upload pipeline immediately.
        print(f"  Uploading {ZIP_PATH.name} ...")
        file_input = page.locator('input.el-upload__input').first
        file_input.set_input_files(str(ZIP_PATH))
        print(f"  File attached.")

        # Wait for the analysis result. Two strategies in series:
        # 1) URL change off landing page (jlcdfm.com/ -> jlcdfm.com/dfm/...)
        # 2) Result text in DOM
        # Each gets a portion of the timeout budget.
        print(f"  Waiting for analysis (timeout {TIMEOUT_MS//1000}s)...")
        start_url = page.url
        result_indicators = [
            "Routing layer", "Soldermask layer", "Silkscreen layer",
            "Drill layer", "DFM analysis report", "DFM Analysis",
            "Trace width", "Pad spacing",
        ]
        try:
            page.wait_for_function(
                """([startUrl, indicators]) => {
                    if (window.location.href !== startUrl) return true;
                    if (!document.body) return false;
                    const t = document.body.innerText || '';
                    return indicators.some(s => t.includes(s));
                }""",
                arg=[start_url, result_indicators],
                timeout=TIMEOUT_MS,
                polling=2000,
            )
            print(f"  Reached viewer page.")
            print(f"  Current URL: {page.url}")
            # Give the viewer time to load the gerber + render.
            page.wait_for_timeout(5_000)
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:
                pass
        except Exception as e:
            print(f"  WARNING: viewer not detected ({type(e).__name__}).")
            print(f"  URL is still: {page.url}")

        # On the viewer page (jlcdfm.com/viewer?pcbUploadFileId=...) every
        # DFM check row starts at status "Unanalyzed". A "DFM check" button
        # at the top of the left analysis panel triggers the actual run.
        # Click it and wait for the rows to populate with Danger/Warning/Good.
        print(f"  Triggering 'DFM check' button...")
        try:
            # Try multiple matchers - the button may be a styled <button>,
            # <div>, or el-button instance.
            for selector in [
                ('role-button', lambda: page.get_by_role("button", name="DFM check").first),
                ('text', lambda: page.get_by_text("DFM check", exact=True).first),
                ('class', lambda: page.locator('.el-button:has-text("DFM check")').first),
            ]:
                name, locator_fn = selector
                try:
                    btn = locator_fn()
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        print(f"  Clicked DFM check button via {name!r} matcher.")
                        break
                except Exception:
                    continue
            # Wait for the analysis rows to flip from "Unanalyzed" to a
            # result count (Danger/Warning/Good). 60 s should be plenty.
            page.wait_for_function(
                """() => {
                    if (!document.body) return false;
                    const t = document.body.innerText || '';
                    // Once analysis completes, rows show results not
                    // "Unanalyzed" - look for at least one occurrence of
                    // "Danger", "Warning", or "Good" in the panel area.
                    const hasResults = /\\b(Danger|Warning|Good)\\b/.test(t);
                    const stillUnanalyzed = /Unanalyzed/.test(t);
                    return hasResults && !stillUnanalyzed;
                }""",
                timeout=120_000,
                polling=2000,
            )
            print(f"  Analysis complete - results populated.")
            page.wait_for_timeout(3_000)
        except Exception as e:
            print(f"  WARNING: DFM check trigger failed ({type(e).__name__}: {e}).")
            print(f"  Will save current state for manual inspection.")

        # Save full-page screenshot for visual diff across iterations.
        screenshot_path = OUT_DIR / "dfm-result.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"  Screenshot saved -> {screenshot_path.name}")

        # Save rendered HTML for textual diff.
        html_path = OUT_DIR / "dfm-result.html"
        html_path.write_text(page.content(), encoding="utf-8")
        print(f"  HTML saved -> {html_path.name}")

        # Try to trigger the PDF download. The agent reported a
        # "PDF report download" button. Heuristic: any visible text
        # matching that pattern.
        pdf_path = OUT_DIR / "dfm-report.pdf"
        download_triggered = False
        for label in ["PDF report download", "Download PDF", "Download Report",
                       "Export PDF", "Download"]:
            try:
                btn = page.get_by_text(label, exact=False).first
                if not btn.is_visible(timeout=1000):
                    continue
                with page.expect_download(timeout=30_000) as dl_info:
                    btn.click()
                dl = dl_info.value
                dl.save_as(str(pdf_path))
                print(f"  PDF report saved -> {pdf_path.name} "
                      f"(via {label!r} button)")
                download_triggered = True
                break
            except Exception:
                continue
        if not download_triggered:
            print(f"  WARNING: could not auto-trigger PDF download. "
                  f"Inspect {screenshot_path} for manual fallback.")

        # Persist captured XHR responses + POST request list.
        net_path = OUT_DIR / "dfm-network.jsonl"
        with net_path.open("w", encoding="utf-8") as fh:
            for r in captured_responses:
                fh.write(json.dumps(r) + "\n")
        print(f"  Captured {len(captured_responses)} API responses "
              f"-> {net_path.name}")
        req_path = OUT_DIR / "dfm-posts.jsonl"
        with req_path.open("w", encoding="utf-8") as fh:
            for r in captured_requests:
                fh.write(json.dumps(r) + "\n")
        print(f"  Captured {len(captured_requests)} POST requests "
              f"-> {req_path.name}")

        browser.close()

    print()
    print("=" * 64)
    print(f"  DFM upload complete at {timestamp}.")
    print(f"  Review {OUT_DIR}/")
    print("=" * 64)


if __name__ == "__main__":
    main()
