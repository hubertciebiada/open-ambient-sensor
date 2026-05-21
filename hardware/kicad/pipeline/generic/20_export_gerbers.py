"""Stage 20: export production gerbers + drill files.

Wipes hardware/build/gerbers/ so stale files from previous board revisions
don't sneak into a vendor ZIP. Emits Protel-extension gerbers (X2
attributes, soldermask subtracted, GND pour filled) and Excellon drill
files (mm decimal, PTH + NPTH separated, drill_map PDFs for human review).

Gerbers are plotted from a silk-stripped WORKING COPY of the PCB (when
STRIP_SILK_NEAR_PADS is set) — footprint body-outline silk within the
DFM clearance of a pad is removed there, so oas.kicad_pcb itself stays
library-faithful (an in-place footprint edit would trip KiCad's
lib_footprint_mismatch DRC). STRIP_FOOTPRINT_SILK additionally drops
DFM-hostile silk that the near-pad pass cannot reach (SW1's body-outline
brackets, the CP_Radial polarity hatch fill) from named footprints on
that same copy. The drill files are exported from the original PCB
(drill geometry has no silkscreen).

Output is vendor-neutral raw fab data. Each vendor's pipeline subdirectory
(stages 30+ in pipeline/<vendor>/) consumes these files and packages them
into vendor-specific deliverables under hardware/output/<vendor>/.

kicad-cli flags worth knowing:
  --subtract-soldermask : keeps silkscreen text off exposed pads
  --check-zones         : refills zones before plotting (GND pour solid)
  --use-drill-file-origin : aligns gerber coords with drill file origin
                            so gerbers / drill / pos / BOM share one frame
  --drill-origin plot   : emits drill coords in that SAME aux-origin frame.
                          The default ("absolute") puts the drill file in
                          the page frame — offset from the gerbers by the
                          aux origin (148.5, 105 mm here), so every THT
                          hole lands away from its pad and JLCPCB DFM
                          flags "Missing plated through-hole" board-wide.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import (  # noqa: E402
    Stage, run, find_kicad_cli,
    strip_silk_near_pads, strip_footprint_silk, expand_thru_hole_mask_margin,
)
from _project import (  # noqa: E402
    PCB_PATH, FAB_LAYERS, GERBERS_BUILD_DIR,
    STRIP_SILK_NEAR_PADS, SILK_PAD_MIN_CLEARANCE_MM, STRIP_FOOTPRINT_SILK,
    EXPAND_THT_MASK_MARGIN, THT_MASK_MARGIN_MM,
)

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

        # Plot gerbers from a DFM-tuned working copy so oas.kicad_pcb
        # stays library-faithful. The copy keeps the same basename so the
        # emitted gerbers are named oas-*.g* as the downstream stages
        # expect. The .kicad_pro is copied alongside in case kicad-cli
        # looks for project plot settings.
        gerber_src = PCB_PATH
        tmpdir: Path | None = None
        if STRIP_SILK_NEAR_PADS or STRIP_FOOTPRINT_SILK or EXPAND_THT_MASK_MARGIN:
            tmpdir = Path(tempfile.mkdtemp(prefix="oas-fab-"))
            gerber_src = tmpdir / PCB_PATH.name
            shutil.copy2(PCB_PATH, gerber_src)
            pro = PCB_PATH.with_suffix(".kicad_pro")
            if pro.exists():
                shutil.copy2(pro, tmpdir / pro.name)
        if STRIP_SILK_NEAR_PADS:
            n_silk = strip_silk_near_pads(gerber_src, SILK_PAD_MIN_CLEARANCE_MM)
            st.info(f"stripped {n_silk} body-outline silk elements within "
                    f"{SILK_PAD_MIN_CLEARANCE_MM} mm of a pad (export copy)")
        if STRIP_FOOTPRINT_SILK:
            n_fps = strip_footprint_silk(gerber_src, STRIP_FOOTPRINT_SILK)
            st.info(f"stripped {n_fps} silk elements from "
                    f"{len(STRIP_FOOTPRINT_SILK)} named footprints (export copy)")
        if EXPAND_THT_MASK_MARGIN:
            n_mask = expand_thru_hole_mask_margin(gerber_src, THT_MASK_MARGIN_MM)
            st.info(f"set {THT_MASK_MARGIN_MM} mm solder-mask margin on "
                    f"{n_mask} through-hole pads (export copy)")

        try:
            st.info("kicad-cli pcb export gerbers (Protel, X2, soldermask subtract)")
            run([
                kcli, "pcb", "export", "gerbers",
                "--output", str(GERBERS_BUILD_DIR) + "/",
                "--layers", FAB_LAYERS,
                "--subtract-soldermask",
                "--check-zones",
                "--use-drill-file-origin",
                str(gerber_src),
            ], hide_output=True)
        finally:
            if tmpdir is not None:
                shutil.rmtree(tmpdir, ignore_errors=True)
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
            # aux origin — MUST match the gerber/CPL --use-drill-file-origin
            # frame, else holes are offset from pads (JLCPCB DFM "Missing
            # plated through-hole").
            "--drill-origin", "plot",
            str(PCB_PATH),
        ], hide_output=True)
        n_d = len(list(GERBERS_BUILD_DIR.glob("*.drl")))
        st.ok(f"wrote {n_d} drill files + drill_map PDFs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
