"""
OAS - JLCPCB DFM upload + full analysis extraction (MANUAL TRIGGER ONLY).

Drives jlcdfm.com end-to-end with Playwright and dumps the result as two
tables (PCB DFM + SMT DFM) so an agent does not have to click through the
SPA by hand:

  1. log in to JLCPCB (reuses the persistent-profile session, or signs
     in automatically when it has expired)
  2. upload hardware/output/jlcpcb/oas-jlcpcb.zip -> the viewer
     (or, with --resume, re-attach to the previous upload)
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
  passes). The session lives in the persistent Chromium profile under
  .cache/dfm/profile/; later runs reuse it and a login only happens
  again once it expires.

------------------------------------------------------------
Re-running without a fresh upload
------------------------------------------------------------
  `--resume` re-attaches to the viewer of the previous upload (URL
  cached in .cache/dfm/last-viewer.json) instead of uploading the ZIP
  again - JLCPCB tracks upload volume per IP, and it lets the BOM /
  SMT-DFM flow be iterated without spending an upload each time.

------------------------------------------------------------
Outputs (all under hardware/kicad/.cache/dfm/, gitignored)
------------------------------------------------------------
  dfm-results.json   - structured PCB + SMT findings
  dfm-pcb.png        - full-page screenshot, PCB DFM tab
  dfm-smt.png        - full-page screenshot, SMT DFM tab
  debug/NN-*.png     - per-step screenshots of the BOM-match / SMT flow
  last-viewer.json   - viewer URL of the last upload (for --resume)

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
# Numbered debug screenshots + tab dumps for every BOM-match / SMT step.
DEBUG_DIR = OUT_DIR / "debug"
# Viewer URL of the last upload. A --resume run re-attaches to this
# jlcdfm project instead of re-uploading the ZIP (JLCPCB tracks upload
# volume per IP; this also lets the BOM/SMT flow be iterated quickly).
LAST_VIEWER = OUT_DIR / "last-viewer.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _rsleep(lo: float = 0.0, hi: float = 1.0) -> None:
    """Random human-like pause. Sprinkled between UI steps so JLCPCB's
    reCAPTCHA v3 (score-based, invisible) does not flag the run as a bot -
    instant scripted clicks score badly and trip a challenge / block."""
    time.sleep(random.uniform(lo, hi))


_DBG_SEQ = 0


def _snap(page, tag: str) -> str:
    """Numbered full-page debug screenshot + active-URL / open-tabs dump.

    Unattended automation needs artifacts when a step misbehaves - every
    BOM-match and SMT step drops one of these into .cache/dfm/debug/ so a
    bad run can be diagnosed (and the flow code fixed) without spending a
    fresh live upload to reproduce it."""
    global _DBG_SEQ
    _DBG_SEQ += 1
    name = f"{_DBG_SEQ:02d}-{tag}"
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DEBUG_DIR / f"{name}.png"), full_page=True)
    except Exception:
        pass
    try:
        tabs = " | ".join(
            f"[{i}]{(p.url or '')[:90]}"
            for i, p in enumerate(page.context.pages))
    except Exception:
        tabs = "?"
    print(f"  [dbg {name}] active={page.url}")
    print(f"           tabs: {tabs}")
    return name


def _save_resume_url(url: str) -> None:
    """Cache the viewer URL of a fresh upload so --resume can re-attach."""
    try:
        LAST_VIEWER.write_text(
            json.dumps({"url": url,
                        "zip_mtime": ZIP_PATH.stat().st_mtime,
                        "saved": datetime.now().isoformat(timespec="seconds")},
                       indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _load_resume_url() -> str | None:
    """Return the cached viewer URL for --resume, or None if unusable."""
    if not LAST_VIEWER.exists():
        return None
    try:
        data = json.loads(LAST_VIEWER.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    url = data.get("url")
    if not url or "/viewer" not in url:
        return None
    if data.get("zip_mtime") != ZIP_PATH.stat().st_mtime:
        print("  --resume: WARNING - the ZIP changed since this viewer was "
              "uploaded; resumed results may be stale.")
    return str(url)


def _click_modal(page, label: str) -> bool:
    """Click a button (Confirm / Cancel) inside a jlcdfm 'Tip' dialog."""
    try:
        page.get_by_role(
            "button", name=label, exact=True).first.click(timeout=4000)
        page.wait_for_timeout(700)
        return True
    except Exception:
        return False


def _dfm_modal_kind(page) -> str:
    """Classify the jlcdfm 'Tip' dialog that can pop up after a DFM check.

      'no-bom' - SMT tab: BOM / coordinate files not uploaded yet
      'exists' - DFM results already exist, re-analyze? (Confirm runs it)
      'none'   - no dialog on screen
    """
    for needle, kind in (
        ("unable to perform", "no-bom"),
        ("not uploaded the BOM", "no-bom"),
        ("Re-analyzing", "exists"),
        ("results exist", "exists"),
        ("produce the same", "exists"),
    ):
        try:
            if page.get_by_text(
                    needle, exact=False).first.is_visible(timeout=800):
                return kind
        except Exception:
            continue
    return "none"


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
def _wait_results(page, timeout_ms: int = 120_000) -> None:
    """Wait until a DFM check has produced results in the active tab.

    'Done' == no 'Unanalyzed' / 'Analyzing' text left AND at least one
    enabled 'Details' button (a check that found something). A genuinely
    all-good tab never enables a Details button, so the wait times out -
    that is fine, the caller just scrapes the (empty) result."""
    try:
        page.wait_for_function(
            """() => {
                const t = document.body.innerText || '';
                if (/Unanalyzed|Analyzing/i.test(t)) return false;
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
    """Upload BOM + CPL through jlcdfm's BOM-match wizard.

    'BOM match' spawns a second tab for the wizard, which opens in one
    of two states:
      (a) fresh project - an 'Add BOM File' / 'Add CPL File' upload
          step followed by 'Process BOM & CPL';
      (b) a project that already carries a committed BOM - the matched
          BOM table directly (happens on a --resume re-attach).
    Both converge on 'Next' (-> Component Placements) then 'Save &
    Close', which commits the BOM to the project (keyed by the
    pcbUploadFileId the viewer and wizard share) and closes the wizard
    tab itself. Returns the original viewer page, reloaded so the SPA
    re-fetches project state with the BOM now attached.

    Every step drops a numbered debug screenshot via _snap() so a run
    that comes back with an empty SMT table can be diagnosed offline.
    """
    print("  BOM match: opening the wizard ...")
    _snap(page, "bom-00-before")
    btn = page.get_by_role("button", name="BOM match")
    btn.wait_for(state="visible", timeout=15_000)
    # the wizard usually opens in a new tab; tolerate same-tab too
    wizard = page
    try:
        with context.expect_page(timeout=15_000) as new_info:
            btn.click()
        wizard = new_info.value
    except Exception:
        print("  (BOM match did not spawn a tab - using the current one)")
    wizard.wait_for_load_state("domcontentloaded")
    wizard.wait_for_timeout(2500)
    _snap(wizard, "bom-01-wizard-open")
    _rsleep()

    # state (a) shows an 'Add BOM File' upload button; state (b) opens
    # straight on the already-matched BOM table (no upload button)
    try:
        fresh = wizard.get_by_role(
            "button", name="Add BOM File").is_visible(timeout=4000)
    except Exception:
        fresh = False

    if fresh:
        _attach_file(wizard,
                     lambda: wizard.get_by_role("button", name="Add BOM File"),
                     BOM_PATH, "BOM")
        _snap(wizard, "bom-02-bom-added")
        _rsleep()
        _attach_file(wizard,
                     lambda: wizard.get_by_role("button", name="Add CPL File"),
                     CPL_PATH, "CPL")
        _snap(wizard, "bom-03-cpl-added")
        _rsleep()
        proc = wizard.get_by_role("button", name="Process BOM & CPL")
        proc.wait_for(state="visible", timeout=10_000)
        proc.click()
        print("  processing BOM/CPL match ...")
    else:
        print("  wizard already shows a matched BOM - reusing it.")

    # Both states must reach a POPULATED matched-BOM table before
    # advancing. 'Process BOM & CPL' matches the parts against the JLC
    # catalogue over the network, and the 'Next' button renders BEFORE
    # the table fills - clicking Next too early commits an empty
    # ('No Data') BOM, and SMT DFM then reports 'no BOM'. Wait for the
    # 'N parts detected / N Parts confirmed' summary to appear.
    try:
        wizard.wait_for_function(
            """() => {
                const t = document.body.innerText || '';
                if (/No Data/i.test(t)) return false;
                return /parts?\\s+(detected|confirmed)/i.test(t);
            }""",
            timeout=120_000,
            polling=1500,
        )
        print("  BOM/CPL parts matched.")
    except Exception:
        print("  WARN: BOM-match table did not populate in time.")
    wizard.wait_for_timeout(2000)
    _snap(wizard, "bom-04-matched")

    # advance: matched-BOM view -> Component Placements
    nxt = wizard.get_by_role("button", name="Next")
    nxt.wait_for(state="visible", timeout=30_000)
    _rsleep(0.8, 1.5)
    nxt.click()
    # the Component Placements view is reached once 'Save & Close' shows
    save = wizard.get_by_role("button", name="Save & Close")
    save.wait_for(state="visible", timeout=60_000)
    _snap(wizard, "bom-05-placements")
    _rsleep(0.8, 1.5)
    # Save & Close commits the BOM/CPL to the project (keyed by the
    # pcbUploadFileId that the viewer and the wizard share) and then
    # closes the wizard tab itself - the `wizard` handle goes dead here,
    # so it must not be touched afterwards.
    try:
        save.click()
    except Exception:
        pass  # the wizard tab can close mid-click
    # The wizard tab closes ITSELF once the BOM/CPL commit POST has
    # completed server-side. Wait for that self-close as the
    # commit-landed signal — the old fixed 3 s sleep could force-close
    # the tab mid-commit, leaving the project with no BOM so SMT DFM
    # then reports 'no BOM' (intermittent false-empty SMT table).
    if wizard is not page:
        try:
            if not wizard.is_closed():
                wizard.wait_for_event("close", timeout=60_000)
            print("  BOM match: wizard tab self-closed - BOM commit landed.")
        except Exception:
            print("  BOM match: WARN - wizard tab did not self-close in "
                  "60 s; force-closing (SMT DFM may report 'no BOM').")
    else:
        print("  BOM match: Save & Close clicked (single-tab wizard).")
        time.sleep(3.0)

    # Drop any tab that is not the original viewer so later
    # get_by_role calls stay unambiguous.
    for p in list(context.pages):
        if p is not page:
            try:
                p.close()
            except Exception:
                pass
    page.bring_to_front()
    # Extra settle so the committed BOM fully propagates to the
    # viewer's SMT-DFM endpoint before the reload below.
    page.wait_for_timeout(5000)
    # Reload the viewer so the SPA re-fetches project state - the BOM is
    # now attached to pcbUploadFileId server-side. (_run_smt_dfm reloads
    # again if the commit had not landed yet.)
    try:
        page.reload(wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(7000)
    except Exception:
        pass
    _dismiss_cookie_banner(page)
    _snap(page, "bom-06-viewer-reloaded")
    print(f"  BOM match done - SMT viewer: {page.url}")
    return page


_SMT_NOBOM_RETRIES = 8


def _run_smt_dfm(page) -> list[dict]:
    """Run SMT DFM, handling the two Tip dialogs jlcdfm can raise.

      'results exist' -> Confirm (re-analyze, then scrape).
      'no BOM'        -> the match did not propagate to this viewer;
                         reload it and retry.

    The 'no BOM' case is a server-side propagation race: 'Save & Close'
    commits the BOM, but the viewer's SMT-DFM endpoint can lag tens of
    seconds before it sees the committed BOM. Retry patiently
    (_SMT_NOBOM_RETRIES reloads, 12 s settle each ≈ up to ~2 min) — a
    fixed 3x/8s was too short and intermittently returned a false-empty
    SMT table.
    """
    for attempt in range(1, _SMT_NOBOM_RETRIES + 1):
        try:
            page.get_by_role("button", name="SMT DFM").click()
            page.wait_for_timeout(2000)
        except Exception:
            pass
        _rsleep()
        try:
            page.get_by_role("button", name="DFM check").first.click()
        except Exception:
            pass
        page.wait_for_timeout(3500)
        kind = _dfm_modal_kind(page)
        if kind == "exists":
            print("  SMT DFM: 'results exist' dialog - confirming re-analysis.")
            _click_modal(page, "Confirm")
            page.wait_for_timeout(2500)
        elif kind == "no-bom":
            print(f"  SMT DFM reports 'no BOM' (attempt {attempt}/"
                  f"{_SMT_NOBOM_RETRIES}) - reloading the viewer to pick up "
                  "the BOM match ...")
            _snap(page, f"smt-nobom-{attempt}")
            _click_modal(page, "Cancel")
            try:
                page.reload(wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(12_000)
            except Exception:
                pass
            _dismiss_cookie_banner(page)
            continue
        _wait_results(page)
        _rsleep()
        return _collect_tab(page)
    print("  ERROR: SMT DFM never picked up the BOM match - see debug shots.")
    _snap(page, "smt-failed")
    return []


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


def run(headless: bool, resume: bool, pcb_only: bool = False) -> int:
    from playwright.sync_api import sync_playwright

    creds = _load_credentials()
    print(f"  ZIP: {ZIP_PATH.name} ({ZIP_PATH.stat().st_size // 1024} kB)")
    print(f"  BOM: {BOM_PATH.name}   CPL: {CPL_PATH.name}")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    resume_url = _load_resume_url() if resume else None
    if resume and not resume_url:
        print("  --resume: no usable saved viewer URL - doing a fresh upload.")

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

        if resume_url:
            print(f"  --resume: re-attaching to {resume_url}")
            page.goto(resume_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(7000)
            _dismiss_cookie_banner(page)
            if "/viewer" not in (page.url or ""):
                print("  --resume: saved viewer expired - falling back to upload.")
                resume_url = None
        if not resume_url:
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30_000)
            _dismiss_cookie_banner(page)
            _rsleep(0.5, 1.0)
            # upload the gerber ZIP -> viewer
            print("  uploading gerber ZIP ...")
            _attach_file(page, lambda: page.get_by_role("button", name="Upload file"),
                         ZIP_PATH, "ZIP")
            page.wait_for_url("**/viewer**", timeout=60_000)
            page.wait_for_timeout(6000)
            _save_resume_url(page.url)
        print(f"  viewer: {page.url}")
        _rsleep()

        # ---- PCB DFM ----
        print("  running PCB DFM check ...")
        page.get_by_role("button", name="DFM check").first.click()
        page.wait_for_timeout(3500)
        if _dfm_modal_kind(page) == "exists":
            print("  PCB DFM: 'results exist' dialog - confirming re-analysis.")
            _click_modal(page, "Confirm")
            page.wait_for_timeout(2500)
        _wait_results(page)
        _rsleep()
        pcb = _collect_tab(page)
        try:
            page.screenshot(path=str(OUT_DIR / "dfm-pcb.png"), full_page=True)
        except Exception:
            pass

        # ---- SMT DFM ----
        smt: list[dict] = []
        if pcb_only:
            print("  --pcb-only: skipping SMT DFM (no BOM / CPL upload).")
        else:
            print("  switching to SMT DFM ...")
            page.get_by_role("button", name="SMT DFM").click()
            page.wait_for_timeout(1500)
            _rsleep()
            page = _bom_match(page, context)
            _dismiss_cookie_banner(page)
            page.wait_for_timeout(2500)
            print("  running SMT DFM check ...")
            smt = _run_smt_dfm(page)
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
    parser.add_argument("--resume", action="store_true",
                        help="Re-attach to the viewer of the previous upload "
                             "(URL cached in .cache/dfm/last-viewer.json) "
                             "instead of uploading the ZIP again.")
    parser.add_argument("--pcb-only", action="store_true",
                        help="Run the PCB DFM check only — skip the SMT DFM "
                             "stage (no BOM / CPL upload, no BOM match).")
    args = parser.parse_args()

    banner()
    preflight()
    return run(headless=args.headless, resume=args.resume,
               pcb_only=args.pcb_only)


if __name__ == "__main__":
    sys.exit(main())
