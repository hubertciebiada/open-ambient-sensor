"""Manual setup: download the pre-built jlcparts SQLite cache.

Stage 34 (`pipeline/jlcpcb/34_check_lcsc_offline.py`) requires a local
SQLite database at `.tmp/jlcparts/cache.sqlite3` to validate every
LCSC# in `lcsc_mapping.py` against JLCPCB's actual component catalogue.

Upstream `yaqwsx/jlcparts` publishes a pre-built split-ZIP archive on
GitHub Pages at `https://yaqwsx.github.io/jlcparts/data/`:

    cache.zip  cache.z01  cache.z02  ...  cache.z40

A 41-volume archive (~2 GiB compressed) expanding into `cache.sqlite3`
(~250 MiB, regenerated roughly weekly via the upstream Travis CI job).
Downloads all volumes into `.tmp/jlcparts/` then extracts with 7-Zip.

EXTERNAL NETWORK: downloads ~2 GiB compressed → ~250 MiB extracted.
Not auto-triggered by `build.py` — explicit user action only (manual
trigger, like `tools/jlcdfm_upload.py`). Re-run when JLCPCB's catalogue
changes materially.

Prerequisites:
  - 7-Zip command line installed (https://www.7-zip.org/, or
    `winget install 7zip.7zip` on Windows).
  - The split-ZIP format is NOT a 7z archive despite the .z01 ext —
    py7zr cannot extract it; the real 7z.exe handles it natively.

Workflow:
  1. Ensure submodule is initialized:
        git submodule update --init hardware/kicad/third_party/jlcparts
  2. Run this script (resumable — re-runs skip already-downloaded
     parts, just retries any that are missing):
        python hardware/kicad/tools/setup_jlcparts_cache.py
  3. Re-run pipeline:
        python build.py
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KICAD_ROOT = HERE.parent
REPO_ROOT = KICAD_ROOT.parent.parent
CACHE_DIR = REPO_ROOT / ".tmp" / "jlcparts"
CACHE_DB = CACHE_DIR / "cache.sqlite3"
STAMP = CACHE_DIR / "built_at.txt"

UPSTREAM_BASE = "https://yaqwsx.github.io/jlcparts/data"

# upstream publishes a 41-volume split ZIP (cache.zip + cache.z01..z40).
# Total compressed size ~2 GiB; expands to ~250 MiB cache.sqlite3.
ARCHIVE_PARTS = ["cache.zip"] + [f"cache.z{i:02d}" for i in range(1, 41)]


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [cached] {dest.name} ({dest.stat().st_size // (1024*1024)} MiB)")
        return
    print(f"  GET {url}")
    with urllib.request.urlopen(url) as resp:
        dest.write_bytes(resp.read())
    print(f"  -> {dest.name} ({dest.stat().st_size // (1024*1024)} MiB)")


def _find_7z_exe() -> str | None:
    """Locate the 7-Zip command-line binary. py7zr can NOT extract this
    multi-volume archive (it's split-ZIP, not 7z), so we shell out to
    the real 7z.exe — bundled with the 7-Zip installer."""
    candidates = [
        r"C:/Program Files/7-Zip/7z.exe",
        r"C:/Program Files (x86)/7-Zip/7z.exe",
        "7z",
    ]
    import shutil as _shutil
    for c in candidates:
        if Path(c).exists() or _shutil.which(c):
            return c
    return None


def main() -> int:
    seven_zip = _find_7z_exe()
    if seven_zip is None:
        sys.exit(
            "ERROR: 7-Zip is required to extract the split-ZIP archive.\n"
            "       Install from https://www.7-zip.org/ or `winget install 7zip.7zip`"
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"==> downloading {len(ARCHIVE_PARTS)} archive parts -> {CACHE_DIR}")
    print(f"    (total ~2 GiB; resumes from any already-downloaded files)")
    for part in ARCHIVE_PARTS:
        _download(f"{UPSTREAM_BASE}/{part}", CACHE_DIR / part)

    print(f"==> extracting cache.zip + 40 volumes -> {CACHE_DB.name}")
    subprocess.run(
        [seven_zip, "x", "-y", "cache.zip"],
        cwd=str(CACHE_DIR),
        check=True,
    )

    if not CACHE_DB.exists():
        sys.exit(
            f"ERROR: extraction completed but {CACHE_DB} not found.\n"
            "       Inspect contents of .tmp/jlcparts/ manually."
        )

    STAMP.write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
    print(
        f"==> done. cache: {CACHE_DB} "
        f"({CACHE_DB.stat().st_size // (1024*1024)} MiB). "
        "Re-run `python build.py` to enable stage 34 validation."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
