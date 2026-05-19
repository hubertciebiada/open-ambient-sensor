"""Stage 20: export production gerbers + drill files.

Wipes hardware/build/gerbers/ so stale files from previous board revisions
don't sneak into a vendor ZIP. Emits Protel-extension gerbers (X2
attributes, soldermask subtracted, GND pour filled) and Excellon drill
files (mm decimal, PTH + NPTH separated, drill_map PDFs for human review).

Output is vendor-neutral raw fab data. Each vendor's pipeline subdirectory
(stages 30+ in pipeline/<vendor>/) consumes these files and packages them
into vendor-specific deliverables under hardware/output/<vendor>/.

kicad-cli flags worth knowing:
  --subtract-soldermask : keeps silkscreen text off exposed pads
  --check-zones         : refills zones before plotting (GND pour solid)
  --use-drill-file-origin : aligns gerber coords with drill file origin
                            so gerbers / drill / pos / BOM share one frame
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli  # noqa: E402
from _project import PCB_PATH, FAB_LAYERS, GERBERS_BUILD_DIR  # noqa: E402

STAGE_NAME = "export_gerbers"


def clean_output_dir() -> None:
    """Wipe GERBERS_BUILD_DIR fresh (it's an intermediate build artifact,
    gitignored, so we don't need to preserve any dotfiles)."""
    if GERBERS_BUILD_DIR.exists():
        shutil.rmtree(GERBERS_BUILD_DIR)
    GERBERS_BUILD_DIR.mkdir(parents=True)


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()

        st.info(f"wiping {GERBERS_BUILD_DIR}/")
        clean_output_dir()

        st.info("kicad-cli pcb export gerbers (Protel, X2, soldermask subtract)")
        run([
            kcli, "pcb", "export", "gerbers",
            "--output", str(GERBERS_BUILD_DIR) + "/",
            "--layers", FAB_LAYERS,
            "--subtract-soldermask",
            "--check-zones",
            "--use-drill-file-origin",
            str(PCB_PATH),
        ], hide_output=True)
        n_g = len(list(GERBERS_BUILD_DIR.glob("*.g*")))
        st.ok(f"wrote {n_g} gerber files")

        st.info("kicad-cli pcb export drill (Excellon mm decimal, PTH/NPTH split)")
        run([
            kcli, "pcb", "export", "drill",
            "--output", str(GERBERS_BUILD_DIR) + "/",
            "--format", "excellon",
            "--excellon-units", "mm",
            "--excellon-zeros-format", "decimal",
            "--excellon-separate-th",
            "--generate-map",
            "--map-format", "pdf",
            "--drill-origin", "absolute",
            str(PCB_PATH),
        ], hide_output=True)
        n_d = len(list(GERBERS_BUILD_DIR.glob("*.drl")))
        st.ok(f"wrote {n_d} drill files + drill_map PDFs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
