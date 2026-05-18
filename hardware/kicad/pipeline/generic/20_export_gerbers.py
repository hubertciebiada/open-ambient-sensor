"""Stage 20: export production gerbers + drill files.

Wipes the output dir (preserving .gitkeep / .gitignore dotfiles) so stale
files from previous board revisions don't sneak into the JLCPCB zip.
Then emits Protel-extension gerbers (X2 attributes, soldermask
subtracted, GND pour filled) and Excellon drill files (mm decimal, PTH +
NPTH separated, drill_map PDFs for human review).

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
from _project import PCB_PATH, FAB_LAYERS, GERBER_OUTPUT_DIR  # noqa: E402

STAGE_NAME = "export_gerbers"


def clean_output_dir() -> None:
    """Wipe GERBER_OUTPUT_DIR but keep dotfiles (.gitkeep / .gitignore)."""
    if GERBER_OUTPUT_DIR.exists():
        for child in GERBER_OUTPUT_DIR.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    else:
        GERBER_OUTPUT_DIR.mkdir(parents=True)


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()

        st.info(f"wiping {GERBER_OUTPUT_DIR.name}/")
        clean_output_dir()

        st.info("kicad-cli pcb export gerbers (Protel, X2, soldermask subtract)")
        run([
            kcli, "pcb", "export", "gerbers",
            "--output", str(GERBER_OUTPUT_DIR) + "/",
            "--layers", FAB_LAYERS,
            "--subtract-soldermask",
            "--check-zones",
            "--use-drill-file-origin",
            str(PCB_PATH),
        ], hide_output=True)
        n_g = len(list(GERBER_OUTPUT_DIR.glob("*.g*")))
        st.ok(f"wrote {n_g} gerber files")

        st.info("kicad-cli pcb export drill (Excellon mm decimal, PTH/NPTH split)")
        run([
            kcli, "pcb", "export", "drill",
            "--output", str(GERBER_OUTPUT_DIR) + "/",
            "--format", "excellon",
            "--excellon-units", "mm",
            "--excellon-zeros-format", "decimal",
            "--excellon-separate-th",
            "--generate-map",
            "--map-format", "pdf",
            "--drill-origin", "absolute",
            str(PCB_PATH),
        ], hide_output=True)
        n_d = len(list(GERBER_OUTPUT_DIR.glob("*.drl")))
        st.ok(f"wrote {n_d} drill files + drill_map PDFs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
