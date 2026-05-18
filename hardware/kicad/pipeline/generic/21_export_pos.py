"""Stage 21: SMT pick-and-place position files in JLCPCB CPL format.

JLCPCB CPL upload REQUIRES exact column header (per the 2026-05-15 first-
order learning the hard way — "Failed processing the CPL file" error
otherwise):

    Designator, Mid X, Mid Y, Layer, Rotation

KiCad-cli's default header is `Ref, Val, Package, PosX, PosY, Rot, Side`
and JLCPCB does NOT auto-detect. We post-process the CSV after kicad-cli
emits it: rename columns, capitalize 'Top'/'Bottom', keep 4-decimal
precision (more is rejected, less is fine), drop Val/Package columns
(JLCPCB ignores them).

Excludes DNP footprints (J2 recovery header, J10 native-USB recovery) and
uses the drill-file origin so CPL coords match the gerbers.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli  # noqa: E402
from _project import PCB_PATH, GERBER_OUTPUT_DIR, POS_OUTPUT_FILES  # noqa: E402

STAGE_NAME = "export_pos"


def postprocess_cpl_for_jlcpcb(path: Path) -> int:
    """Rewrite a kicad-cli CPL output in place to JLCPCB upload format.

    Input header (kicad-cli):   Ref,Val,Package,PosX,PosY,Rot,Side
    Output header (JLCPCB):     Designator,Mid X,Mid Y,Layer,Rotation

    Returns the data-row count (excluding header).
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return 0
    out = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]]
    for row in rows[1:]:
        if not row:
            continue
        ref, _val, _pkg, x, y, rot, side = row
        x_fmt = f"{float(x):.4f}"
        y_fmt = f"{float(y):.4f}"
        rot_f = float(rot)
        rot_fmt = str(int(rot_f)) if rot_f == int(rot_f) else f"{rot_f:g}"
        layer = "Top" if side.lower().startswith("top") else "Bottom"
        out.append([ref, x_fmt, y_fmt, layer, rot_fmt])
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(out)
    return len(out) - 1


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        GERBER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for side, fname in POS_OUTPUT_FILES:
            out = GERBER_OUTPUT_DIR / fname
            run([
                kcli, "pcb", "export", "pos",
                "--output", str(out),
                "--side", side,
                "--format", "csv",
                "--units", "mm",
                "--use-drill-file-origin",
                "--smd-only",
                "--exclude-dnp",
                str(PCB_PATH),
            ], hide_output=True)
            n = postprocess_cpl_for_jlcpcb(out)
            st.ok(f"wrote {fname} ({n} footprints, JLCPCB-format)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
