"""Stage 23: JLCPCB ZIP bundle.

Packs the fab deliverables (gerbers + drill) into a single ZIP for
JLCPCB upload. Excludes drill map PDFs (human-only review), position
files and BOM (separate upload to JLCPCB SMT quoting page).
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage  # noqa: E402
from _project import GERBER_OUTPUT_DIR, BUNDLE_NAME, BUNDLE_GLOBS  # noqa: E402

STAGE_NAME = "bundle_jlcpcb"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        GERBER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = GERBER_OUTPUT_DIR / BUNDLE_NAME
        if zip_path.exists():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for pattern in BUNDLE_GLOBS:
                for f in sorted(GERBER_OUTPUT_DIR.glob(pattern)):
                    zf.write(f, arcname=f.name)

        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            n = len(zf.namelist())
        if bad is not None:
            st.fail(f"{BUNDLE_NAME} corrupted: {bad}")
        size_kb = zip_path.stat().st_size / 1024
        st.ok(f"wrote {BUNDLE_NAME} ({n} files, {size_kb:.1f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
