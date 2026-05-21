"""
OAS - JLCPCB DFM upload + full analysis extraction (MANUAL TRIGGER ONLY).

Drives jlcdfm.com end-to-end with Playwright and dumps the result as two
tables (PCB DFM + SMT DFM) so an agent does not have to click through the
SPA by hand:

  1. log in to JLCPCB (reuses a saved session; --login to (re)create it)
  2. upload hardware/output/jlcpcb/oas-jlcpcb.zip       -> the viewer
  3. run the PCB DFM check
  4. BOM match: upload oas-BOM.csv + oas-top-CPL.csv, process, save
  5. run the SMT DFM check
  6. for every check with Danger/Warning, open its Details panel and
     scrape the per-row severity + affected objects
  7. print two tables + write .cache/dfm/dfm-results.json

------------------------------------------------------------
WARNING - this script makes a LIVE upload to JLCPCB servers.
------------------------------------------------------------
* Do NOT run on every build. JLCPCB tracks upload volume via
  /api/overseas-dfm-service/checkIp; abusive use triggers IP blocks.
* Do NOT run from CI loops or automated wakers.
* RUN ONLY when the user explicitly requests it.
See CLAUDE.md section "External services - MANUAL TRIGGER ONLY".

------------------------------------------------------------
Prerequisites
------------------------------------------------------------
  pip install --user playwright
  python -m playwright install chromium
  python build.py        # stages 31/32 emit the BOM + CPL + ZIP

------------------------------------------------------------
Auth - fully automatic, no manual step
------------------------------------------------------------
  Drop a credentials file at .cache/dfm/credentials.json (gitignored,
  NEVER committed):
      {"email": "you@example.com", "password": "..."}

  The script detects whether the saved session is still valid and, if
  not, signs in by itself: it opens the JLCPCB passport form, types the
  credentials (human-paced so reCAPTCHA v3 - invisible, score-based -
  passes), and persists the resulting httpOnly session cookies to
  .cache/dfm/auth_state.json. Later runs reuse that token; a login only
  happens again once it expires (~30-90 days).

------------------------------------------------------------
Outputs (all under hardware/kicad/.cache/dfm/, gitignored)
------------------------------------------------------------
  dfm-results.json   - structured PCB + SMT findings
  dfm-pcb.png        - full-page screenshot, PCB DFM tab
  dfm-smt.png        - full-page screenshot, SMT DFM tab

Exit 0 on success, 1 on any error.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent
# v0.40-vendor-split: build.py stages 31/32 write the JLCPCB deliverables
# to hardware/output/jlcpcb/ (KICAD_DIR.parent == hardware).
_JLC_OUT = KICAD_DIR.parent / "output" / "jlcpcb"
ZIP_PATH = _JLC_OUT / "oas-jlcpcb.zip"
BOM_PATH = _JLC_OUT / "oas-BOM.csv"
CPL_PATH = _JLC_OUT / "oas-top-CPL.csv"

OUT_DIR = KICAD_DIR / ".cache" / "dfm"
# Persistent Chromium profile. Holds the JLCPCB session between runs
# (so a login happens once, not every run) AND accumulates the device
# trust that keeps reCAPTCHA from escalating to an image challenge.
PROFILE_DIR = OUT_DIR / "profile"
# Optional credentials file for unattended login. NEVER committed:
# .cache/ is gitignored (`**/.cache/` rule). Format:
#   {"email": "you@example.com", "password": "..."}
CREDENTIALS = OUT_DIR / "credentials.json"

UPLOAD_URL = "https://jlcdfm.com/"
RESULTS_JSON = OUT_DIR / "dfm-results.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _rsleep(lo: float = 0.0, hi: float = 1.0) -> None:
    """Random human-like pause. Sprinkled between UI steps so JLCPCB's
    reCAPTCHA v3 (score-based, invisible) does not flag the run as a bot -
    instant scripted clicks score badly and trip a challenge / block."""
    time.sleep(random.uniform(lo, hi))


def _load_credentials() -> dict | None:
    """Read JLCPCB login credentials from the gitignored creds file."""
    if not CREDENTIALS.exists():
        return None
    try:
        data = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if isinstance(data, dict) and data.get("email") and data.get("password"):
        return {"email": str(data["email"]), "password": str(data["password"])}
    return None


def _dismiss_cookie_banner(page) -> None:
    """Click whichever cookie-consent button is showing, if any."""
    for label in ("Accept all cookies", "Accept only essential cookies"):
        try:
            btn = page.get_by_role("button", name=label).first
            if btn.is_visible(timeout=2500):
                btn.click()
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def banner() -> None:
    print("=" * 64)
    print("  OAS JLCPCB DFM - LIVE EXTERNAL SERVICE (manual trigger only)")
    print("=" * 64)


def preflight() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        sys.exit(
            "ERROR: playwright not installed. Run:\n"
            "  pip install --user playwright\n"
            "  python -m playwright install chromium"
        )
    for label, fp in (("ZIP", ZIP_PATH), ("BOM", BOM_PATH), ("CPL", CPL_PATH)):
        if not fp.exists():
            sys.exit(
                f"ERROR: {label} not found at {fp}\n"
                f"       Run `python hardware/kicad/build.py` first."
            )
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _attach_file(page, opener, path: Path, label: str) -> None:
    """Click `opener()` (which triggers a file chooser) and attach `path`."""
    with page.expect_file_chooser(timeout=20_000) as fc:
        opener().click()
    fc.value.set_files(str(path))
    print(f"  attached {label}: {path.name}")
    page.wait_for_timeout(1500)


# ---------------------------------------------------------------------------
# login - fully automatic (detect session, sign in if needed)
# ---------------------------------------------------------------------------
def _logged_in(page) -> bool:
    """True if the jlcdfm.com nav shows a signed-in state (no 'Sign In').

    Waits for the nav to actually render first - checking too early sees
    zero 'Sign In' nodes and would wrongly report 'logged in'.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    return page.get_by_text("Sign In", exact=True).count() == 0


def _go_to_passport(page) -> None:
    """Open the JLCPCB passport login form from the jlcdfm.com nav.

    jlcdfm.com carries several 'Sign In' text nodes (the nav item plus
    the popover it reveals); rather than guess the right index, click
    every visible candidate until the URL changes to passport.
    """
    for _ in range(8):
        if "passport.jlcpcb.com" in page.url:
            return
        try:
            cands = page.get_by_text("Sign In", exact=True)
            for i in range(min(cands.count(), 6)):
                try:
                    el = cands.nth(i)
                    if not el.is_visible():
                        continue
                    el.hover()
                    _rsleep(0.2, 0.5)
                    el.click(timeout=3000)
                    _rsleep(0.5, 0.9)
                    if "passport.jlcpcb.com" in page.url:
                        return
                except Exception:
                    continue
        except Exception:
            pass
        # the popover may now expose a real <button> - try it too
        try:
            page.get_by_role("button", name="Sign In").first.click(timeout=3000)
        except Exception:
            pass
        try:
            page.wait_for_url("**passport.jlcpcb.com/**", timeout=5000)
            return
        except Exception:
            _rsleep(0.6, 1.2)
    shot = OUT_DIR / "dfm-login-error.png"
    try:
        page.screenshot(path=str(shot), full_page=True)
    except Exception:
        pass
    raise RuntimeError(f"could not reach the JLCPCB passport login - see {shot}")


def _click_recaptcha_checkbox(page) -> bool:
    """Click the reCAPTCHA v2 'I'm not a robot' checkbox if a Security
    Verification modal appeared. Returns True if a checkbox was clicked.

    Locates the reCAPTCHA anchor iframe by frame URL (robust against the
    iframe's CSS attributes / localised title). A clean, human-paced
    session usually passes on the checkbox alone; an image challenge
    cannot be solved here - the caller leaves a wide wait window so a
    human can solve it once in the headed browser.
    """
    page.wait_for_timeout(3000)  # let the modal + iframe load
    for _ in range(12):
        for fr in page.frames:
            url = fr.url or ""
            if "recaptcha" in url and "anchor" in url:
                try:
                    box = fr.locator("#recaptcha-anchor")
                    box.wait_for(state="visible", timeout=3000)
                    _rsleep(0.6, 1.3)
                    box.click()
                    print("  reCAPTCHA checkbox clicked.")
                    return True
                except Exception:
                    pass
        page.wait_for_timeout(1000)
    print("  (no reCAPTCHA anchor frame found)")
    return False


def _ensure_logged_in(page, creds: dict | None) -> None:
    """Detect the JLCPCB session; sign in automatically when it is absent.

    The persistent browser profile (PROFILE_DIR) keeps the session
    between runs, so a login normally happens only on the first run or
    after expiry. Paced with random pauses + per-character typing so
    reCAPTCHA scores the run as human; the profile's accumulated device
    trust keeps it from escalating to an image challenge.
    """
    if _logged_in(page):
        print("  session OK - profile already signed in.")
        return
    if not creds:
        sys.exit(
            "ERROR: not signed in and no .cache/dfm/credentials.json present.\n"
            '       Create it with {"email": "...", "password": "..."}'
        )
    print(f"  not signed in - logging in as {creds['email']} ...")
    _go_to_passport(page)
    page.wait_for_load_state("domcontentloaded")
    _rsleep(0.7, 1.3)
    email = page.get_by_role("textbox", name="Username or Email")
    email.click()
    _rsleep()
    email.press_sequentially(creds["email"], delay=random.randint(45, 150))
    _rsleep()
    pwd = page.get_by_role("textbox", name="Password")
    pwd.click()
    _rsleep()
    pwd.press_sequentially(creds["password"], delay=random.randint(45, 150))
    _rsleep(0.6, 1.2)
    page.get_by_role("button", name="Sign In", exact=True).click()
    _rsleep(1.5, 2.5)
    # A 'Security Verification' modal with a reCAPTCHA v2 checkbox may
    # appear on a low score. Click the checkbox; the modal does NOT
    # auto-submit, so re-press Sign In. If reCAPTCHA escalates to an
    # image challenge the long wait below leaves time to solve it once
    # in the visible window - the persistent profile then avoids it.
    if _click_recaptcha_checkbox(page):
        for _ in range(4):
            if "passport.jlcpcb.com" not in page.url:
                break
            _rsleep(0.6, 1.2)
            try:
                page.get_by_role(
                    "button", name="Sign In", exact=True).click(timeout=6000)
            except Exception:
                pass
            try:
                page.wait_for_url("**jlcdfm.com/**", timeout=30_000)
                break
            except Exception:
                pass
    # success == OAuth redirect back to jlcdfm.com
    if "passport.jlcpcb.com" in page.url:
        print()
        print("  " + "=" * 58)
        print("  >> If the browser window shows a reCAPTCHA IMAGE challenge,")
        print("  >> solve it now (just click the pictures - no typing).")
        print("  >> This is a ONE-TIME step; the profile is reused afterwards.")
        print("  >> Waiting up to 4 minutes for the login to complete ...")
        print("  " + "=" * 58)
        print()
    try:
        page.wait_for_url("**jlcdfm.com/**", timeout=240_000)
    except Exception:
        pass
    page.wait_for_load_state("domcontentloaded")
    _rsleep(1.5, 2.5)
    if not _logged_in(page):
        shot = OUT_DIR / "dfm-login-error.png"
        try:
            page.screenshot(path=str(shot), full_page=True)
        except Exception:
            pass
        sys.exit(
            "ERROR: login did not complete - reCAPTCHA most likely showed an\n"
            "       image challenge. Re-running reuses the persistent profile\n"
            f"       (higher score); else solve it once in the window. See {shot}"
        )
    print("  signed in - persistent profile keeps the session for next runs.")


# ---------------------------------------------------------------------------
# analysis flow
# ---------------------------------------------------------------------------
def _wait_results(page, timeout_ms: int = 180_000) -> None:
    """Wait until a DFM check has produced results in the active tab."""
    try:
        page.wait_for_function(
            """() => {
                const t = document.body.innerText || '';
                if (t.includes('Unanalyzed')) return false;
                const btns = [...document.querySelectorAll('button')]
                    .filter(b => (b.innerText || '').trim() === 'Details');
                return btns.length > 0 && btns.some(b => !b.disabled);
            }""",
            timeout=timeout_ms,
            polling=2000,
        )
    except Exception:
        print("  WARN: result-wait timed out; scraping whatever is present.")
    page.wait_for_timeout(2500)


def _scrape_detail(page) -> list[dict]:
    """Scrape the currently-open Details panel table.

    Detail rows are identified by the 2nd cell being a severity word -
    the check-list rows carry an "N, N, N" statistics string there.
    """
    raw = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('tr').forEach(tr => {
                const tds = [...tr.querySelectorAll('td')]
                    .map(td => (td.innerText || '').trim());
                if (tds.length >= 2 && /^(Danger|Warning|Good)$/.test(tds[1]))
                    out.push(tds);
            });
            return out;
        }"""
    )
    rows: list[dict] = []
    for tds in raw:
        sev = tds[1]
        if sev == "Good":
            continue
        value = tds[2] if len(tds) > 2 else ""
        objects = [t for t in tds[3:] if t and t.lower() != "null"]
        rows.append({"severity": sev, "value": value, "objects": objects})
    return rows


def _collect_tab(page) -> list[dict]:
    """Walk every check row of the active DFM tab; open Details for the
    ones with Danger/Warning and scrape the per-row findings."""
    findings: list[dict] = []
    detail_btns = page.get_by_role("button", name="Details")
    total = detail_btns.count()
    for i in range(total):
        btn = detail_btns.nth(i)
        try:
            row = btn.locator("xpath=ancestor::tr[1]")
            tds = row.locator("td")
            name = tds.nth(0).inner_text().strip()
            stat = tds.nth(1).inner_text().strip()
        except Exception:
            continue
        m = re.match(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", stat)
        if not m:
            continue
        danger, warning, good = int(m[1]), int(m[2]), int(m[3])
        if danger == 0 and warning == 0:
            continue
        try:
            btn.scroll_into_view_if_needed(timeout=5000)
            btn.click()
        except Exception as e:
            print(f"  WARN: could not open Details for {name!r} ({type(e).__name__}).")
            findings.append({"check": name, "danger": danger,
                             "warning": warning, "good": good, "details": []})
            continue
        page.wait_for_timeout(1400)
        # expand pagination so every row is in the DOM
        try:
            all_btn = page.get_by_role("button", name="All", exact=True)
            if all_btn.count() and all_btn.first.is_visible(timeout=800):
                all_btn.first.click()
                page.wait_for_timeout(800)
        except Exception:
            pass
        details = _scrape_detail(page)
        if len(details) < danger + warning:   # stale / still loading -> retry
            page.wait_for_timeout(2000)
            details = _scrape_detail(page)
        print(f"  {name}: D={danger} W={warning} -> {len(details)} detail row(s)")
        findings.append({"check": name, "danger": danger, "warning": warning,
                         "good": good, "details": details})
    return findings


def _bom_match(page, context):
    """Run the BOM match flow: upload BOM + CPL in the spawned tab.

    Returns the viewer page that now carries the matched BOM. 'BOM match'
    opens a second tab; after 'Save & Close' THAT tab navigates to the
    viewer with the BOM associated, while the original viewer tab stays
    BOM-less. So this returns the post-save tab and drops the stale one.

    Each step waits for the NEXT control to appear rather than sleeping
    a fixed time - 'Process BOM & CPL' can take well over the old 4 s
    budget, and a too-early click left the BOM unsaved.
    """
    print("  BOM match: uploading BOM + CPL ...")
    with context.expect_page(timeout=20_000) as new_info:
        page.get_by_role("button", name="BOM match").click()
    bom = new_info.value
    bom.wait_for_load_state("domcontentloaded")
    bom.wait_for_timeout(2000)
    _rsleep()
    _attach_file(bom, lambda: bom.get_by_role("button", name="Add BOM File"),
                 BOM_PATH, "BOM")
    _rsleep()
    _attach_file(bom, lambda: bom.get_by_role("button", name="Add CPL File"),
                 CPL_PATH, "CPL")
    _rsleep()
    proc = bom.get_by_role("button", name="Process BOM & CPL")
    proc.wait_for(state="visible", timeout=10_000)
    proc.click()
    print("  processing BOM/CPL match ...")
    # the matched-parts view is reached once 'Next' shows up
    nxt = bom.get_by_role("button", name="Next")
    nxt.wait_for(state="visible", timeout=90_000)
    _rsleep(0.8, 1.5)
    nxt.click()
    # the Component Placements view is reached once 'Save & Close' shows up
    save = bom.get_by_role("button", name="Save & Close")
    save.wait_for(state="visible", timeout=45_000)
    _rsleep(0.8, 1.5)
    save.click()
    # After 'Save & Close' the BOM-match tab navigates to the viewer that
    # now carries the BOM. Poll for that navigation, then adopt that tab
    # (a context.pages scan also catches a freshly spawned viewer tab).
    for _ in range(24):
        bom.wait_for_timeout(1000)
        try:
            if not bom.is_closed() and "/viewer" in (bom.url or ""):
                try:
                    page.close()
                except Exception:
                    pass
                bom.bring_to_front()
                print("  BOM match saved (adopted post-save viewer tab).")
                return bom
        except Exception:
            break
        # also check for any other viewer tab the save may have opened
        for other in list(context.pages):
            try:
                if (other not in (page, bom) and not other.is_closed()
                        and "/viewer" in (other.url or "")):
                    print("  BOM match saved (adopted spawned viewer tab).")
                    other.bring_to_front()
                    return other
            except Exception:
                pass
        if bom.is_closed():
            break
    # fallback: reload the original viewer
    try:
        if not bom.is_closed():
            bom.close()
    except Exception:
        pass
    page.bring_to_front()
    page.reload(wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(3000)
    print("  BOM match saved (reloaded original viewer).")
    return page


def _format_table(title: str, findings: list[dict]) -> str:
    """Render findings as an aligned text table: Check | Severity | Affected."""
    rows: list[tuple[str, str, str]] = []
    for c in findings:
        for sev in ("Danger", "Warning"):
            count = c["danger"] if sev == "Danger" else c["warning"]
            if count == 0:
                continue
            objs: list[str] = []
            vals: set[str] = set()
            for d in c["details"]:
                if d["severity"] != sev:
                    continue
                objs.extend(d["objects"] or ["(no ref)"])
                if d["value"] and d["value"].lower() != "null":
                    vals.add(d["value"])
            tally = Counter(objs)
            aff = ", ".join(f"{k}x{v}" if v > 1 else k
                            for k, v in sorted(tally.items()))
            if vals:
                aff = (aff + "  ") if aff else ""
                aff += f"[val: {', '.join(sorted(vals))}]"
            rows.append((c["check"], f"{sev} ({count})", aff or "-"))

    hdr = ("Check", "Severity", "Affected elements")
    if not rows:
        body = [("(no Danger / Warning findings)", "", "")]
    else:
        body = rows
    w0 = max(len(hdr[0]), *(len(r[0]) for r in body))
    w1 = max(len(hdr[1]), *(len(r[1]) for r in body))
    w2 = max(len(hdr[2]), *(len(r[2]) for r in body))
    line = f"+-{'-'*w0}-+-{'-'*w1}-+-{'-'*w2}-+"
    out = [f"\n  === {title} ===", "  " + line,
           f"  | {hdr[0]:<{w0}} | {hdr[1]:<{w1}} | {hdr[2]:<{w2}} |",
           "  " + line]
    for r in body:
        out.append(f"  | {r[0]:<{w0}} | {r[1]:<{w1}} | {r[2]:<{w2}} |")
    out.append("  " + line)
    return "\n".join(out)


def run(headless: bool) -> int:
    from playwright.sync_api import sync_playwright

    creds = _load_credentials()
    print(f"  ZIP: {ZIP_PATH.name} ({ZIP_PATH.stat().st_size // 1024} kB)")
    print(f"  BOM: {BOM_PATH.name}   CPL: {CPL_PATH.name}")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Persistent context: the profile dir holds the JLCPCB session
        # between runs and accumulates the reCAPTCHA device trust.
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            accept_downloads=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("  opening jlcdfm.com ...")
        page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30_000)
        _dismiss_cookie_banner(page)
        # detect the session and sign in automatically if it is missing
        _ensure_logged_in(page, creds)
        page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30_000)
        _dismiss_cookie_banner(page)
        _rsleep(0.5, 1.0)

        # upload the gerber ZIP -> viewer
        print("  uploading gerber ZIP ...")
        _attach_file(page, lambda: page.get_by_role("button", name="Upload file"),
                     ZIP_PATH, "ZIP")
        page.wait_for_url("**/viewer**", timeout=60_000)
        page.wait_for_timeout(6000)
        print(f"  viewer: {page.url}")
        _rsleep()

        # ---- PCB DFM ----
        print("  running PCB DFM check ...")
        page.get_by_role("button", name="DFM check").first.click()
        _wait_results(page)
        _rsleep()
        pcb = _collect_tab(page)
        try:
            page.screenshot(path=str(OUT_DIR / "dfm-pcb.png"), full_page=True)
        except Exception:
            pass

        # ---- SMT DFM ----
        print("  switching to SMT DFM ...")
        page.get_by_role("button", name="SMT DFM").click()
        page.wait_for_timeout(1500)
        _rsleep()
        page = _bom_match(page, context)
        _dismiss_cookie_banner(page)
        page.wait_for_timeout(6000)
        print("  running SMT DFM check ...")
        page.get_by_role("button", name="SMT DFM").click()
        page.wait_for_timeout(2500)
        _rsleep()
        page.get_by_role("button", name="DFM check").first.click()
        _wait_results(page)
        _rsleep()
        smt = _collect_tab(page)
        try:
            page.screenshot(path=str(OUT_DIR / "dfm-smt.png"), full_page=True)
        except Exception:
            pass

        context.close()

    # ---- dump ----
    stamp = datetime.now().isoformat(timespec="seconds")
    RESULTS_JSON.write_text(
        json.dumps({"timestamp": stamp, "pcb": pcb, "smt": smt}, indent=2),
        encoding="utf-8",
    )
    print(_format_table("PCB DFM", pcb))
    print(_format_table("SMT DFM", smt))

    def _tally(rows: list[dict]) -> tuple[int, int]:
        return (sum(r["danger"] for r in rows), sum(r["warning"] for r in rows))

    pd, pw = _tally(pcb)
    sd, sw = _tally(smt)
    print(f"\n  TOTAL  PCB: {pd} Danger / {pw} Warning"
          f"   SMT: {sd} Danger / {sw} Warning")
    print(f"  json -> {RESULTS_JSON}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload OAS to jlcdfm.com and extract the DFM report "
                    "(fully automatic: signs in if the session is missing).")
    parser.add_argument("--headless", action="store_true",
                        help="Run with no visible browser window. Only safe "
                             "once a fresh session token exists - reCAPTCHA "
                             "scores headless logins poorly.")
    args = parser.parse_args()

    banner()
    preflight()
    return run(headless=args.headless)


if __name__ == "__main__":
    sys.exit(main())
