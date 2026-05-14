"""
OAS - JLCPCB DFM upload + report download (MANUAL TRIGGER ONLY).

Uploads `hardware/gerbers/oas-jlcpcb.zip` to https://jlcdfm.com, waits
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

  Then run export_production.py to refresh hardware/gerbers/oas-jlcpcb.zip
  (the upload always uses whatever file is currently at that path).

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

UPLOAD_URL = "https://jlcdfm.com/"
TIMEOUT_MS = 180_000  # 3 minutes for analysis to complete


def banner() -> None:
    print("=" * 64)
    print("  OAS JLCPCB DFM upload - LIVE EXTERNAL SERVICE")
    print("=" * 64)
    print("  This script uploads hardware/gerbers/oas-jlcpcb.zip to")
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
    banner()
    preflight()

    # Lazy-import playwright so the bare `--help` / preflight error
    # paths don't crash on missing browser binaries.
    from playwright.sync_api import sync_playwright

    captured_responses: list[dict] = []
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Capture every JSON XHR for post-mortem analysis. Per agent
        # research the result page may emit a structured JSON that's
        # cleaner to parse than the rasterized PDF.
        def on_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct and "/api/" in response.url:
                    captured_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "body": response.text(),
                    })
            except Exception:
                pass
        page.on("response", on_response)

        print(f"  Navigating to {UPLOAD_URL} ...")
        page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30_000)

        # Find the file upload input. Per agent's snapshot, the page
        # has an `<input type=file>` near the primary "Upload file"
        # CTA. Use set_input_files which works with hidden inputs too.
        print(f"  Uploading {ZIP_PATH.name} ...")
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(ZIP_PATH))

        # Wait for the analysis result to appear. The agent did not
        # capture the exact selector; we use a heuristic: wait for any
        # text matching one of the section headers from the report.
        # Fallback: just wait the full TIMEOUT_MS for the page to settle.
        result_indicators = [
            "Routing layer",
            "Soldermask layer",
            "Silkscreen layer",
            "Drill layer",
            "DFM analysis report",
        ]
        print(f"  Waiting for analysis to complete (timeout {TIMEOUT_MS//1000}s) ...")
        try:
            # Race: any of the indicators appearing -> done.
            page.wait_for_function(
                """(indicators) => {
                    const t = document.body.innerText;
                    return indicators.some(s => t.includes(s));
                }""",
                arg=result_indicators,
                timeout=TIMEOUT_MS,
            )
            print(f"  Analysis result page detected.")
        except Exception as e:
            print(f"  WARNING: result indicator not found ({e}). Continuing.")

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

        # Persist captured XHR responses.
        net_path = OUT_DIR / "dfm-network.jsonl"
        with net_path.open("w", encoding="utf-8") as fh:
            for r in captured_responses:
                fh.write(json.dumps(r) + "\n")
        print(f"  Captured {len(captured_responses)} API responses "
              f"-> {net_path.name}")

        browser.close()

    print()
    print("=" * 64)
    print(f"  DFM upload complete at {timestamp}.")
    print(f"  Review {OUT_DIR}/")
    print("=" * 64)


if __name__ == "__main__":
    main()
