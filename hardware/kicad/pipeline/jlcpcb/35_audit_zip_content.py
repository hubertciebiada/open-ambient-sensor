"""Stage 35: audit oas-jlcpcb.zip content (Gap D).

Opens the bundled ZIP and asserts:
  - The expected file inventory (9 gerber layers + 2 drill files = 11)
    is present, in any order.
  - No unexpected files (no leftover .bak, .log, .DS_Store, etc.).
  - Every file is > 0 bytes — a zero-byte gerber in the upload silently
    drops a copper layer at JLCPCB without raising an obvious flag.

The stage 32 bundler glob is `BUNDLE_GLOBS` in pipeline/_project.py;
this audit independently re-checks the resulting ZIP so a future
glob-list edit that drops a layer (e.g. accidentally removes "*.gbp"
from the bundle list) gets caught before the order is placed.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage  # noqa: E402
from _project import JLCPCB_OUTPUT_DIR, BUNDLE_NAME  # noqa: E402

STAGE_NAME = "audit_zip_content"

ZIP_PATH = JLCPCB_OUTPUT_DIR / BUNDLE_NAME

# Files JLCPCB expects to find in the ZIP for a 2-layer SMT order:
#   F.Cu / B.Cu                 — copper layers
#   F.Mask / B.Mask             — solder mask
#   F.Silkscreen / B.Silkscreen — silkscreen
#   F.Paste / B.Paste           — stencil paste
#   Edge.Cuts                   — board outline
#   PTH / NPTH                  — Excellon drill files
EXPECTED_FILES = {
    "oas-F_Cu.gtl",
    "oas-B_Cu.gbl",
    "oas-F_Mask.gts",
    "oas-B_Mask.gbs",
    "oas-F_Silkscreen.gto",
    "oas-B_Silkscreen.gbo",
    "oas-F_Paste.gtp",
    "oas-B_Paste.gbp",
    "oas-Edge_Cuts.gm1",
    "oas-PTH.drl",
    "oas-NPTH.drl",
}


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if not ZIP_PATH.exists():
            st.fail(f"{ZIP_PATH} not found — stage 32 bundle did not produce the ZIP")

        with zipfile.ZipFile(ZIP_PATH) as z:
            members = z.infolist()

        present = {m.filename for m in members}
        missing = EXPECTED_FILES - present
        unexpected = present - EXPECTED_FILES
        zero_byte = [m.filename for m in members if m.file_size == 0]

        errors: list[str] = []
        if missing:
            errors.append(
                f"{len(missing)} expected file(s) missing from ZIP: "
                f"{sorted(missing)}"
            )
        if unexpected:
            errors.append(
                f"{len(unexpected)} unexpected file(s) in ZIP: "
                f"{sorted(unexpected)}"
            )
        if zero_byte:
            errors.append(
                f"{len(zero_byte)} zero-byte file(s): {zero_byte}"
            )

        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            st.fail("ZIP content audit found anomalies")

        st.ok(
            f"{len(members)} files in {ZIP_PATH.name}, "
            f"all expected and non-empty"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
