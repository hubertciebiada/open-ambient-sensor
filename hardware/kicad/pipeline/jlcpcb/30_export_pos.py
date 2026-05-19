"""Stage 30: SMT pick-and-place position files in JLCPCB CPL format.

JLCPCB CPL upload REQUIRES exact column header (per the 2026-05-15 first-
order learning the hard way — "Failed processing the CPL file" error
otherwise):

    Designator, Mid X, Mid Y, Layer, Rotation

KiCad-cli's default header is `Ref, Val, Package, PosX, PosY, Rot, Side`
and JLCPCB does NOT auto-detect. We post-process the CSV after kicad-cli
emits it: rename columns, capitalize 'Top'/'Bottom', keep 4-decimal
precision (more is rejected, less is fine), drop Val/Package columns
(JLCPCB ignores them).

ROTATION CORRECTIONS — KiCad footprint "0 deg rotation" reference differs
from JLCPCB tape-feeder reference for many packages. We load a combined
list of corrections from `_rotations.load_combined()` (upstream
JLCKicadTools CSV + OAS-specific gap-fillers) and apply per-row.

Excludes DNP footprints (J2 recovery header, J10 native-USB recovery) and
uses the drill-file origin so CPL coords match the gerbers.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))   # pipeline/
sys.path.insert(0, str(Path(__file__).parent))          # pipeline/jlcpcb/
from _common import Stage, run, find_kicad_cli  # noqa: E402
from _project import PCB_PATH, JLCPCB_OUTPUT_DIR, POS_OUTPUT_FILES  # noqa: E402
from _rotations import load_combined, stats  # noqa: E402, F401

STAGE_NAME = "export_pos"


def apply_rotation_corrections(rows: list[list[str]], st: Stage) -> tuple[int, int, int]:
    """Modify the rotation column in-place based on footprint-regex matches.

    Each kicad-cli CSV row: [Ref, Val, Package, PosX, PosY, Rot, Side].
    `Package` includes the "Lib:Name" prefix; we match the bare name.
    Lookup precedence enforced by `load_combined()` order: upstream
    first, OAS-specific second (gap-fillers).
    Returns (n_upstream_applied, n_oas_applied, n_unmatched).
    """
    corrections = load_combined()
    n_upstream = sum(1 for *_, src in corrections if src == "upstream")
    n_oas = len(corrections) - n_upstream
    st.info(f"loaded {n_upstream} upstream + {n_oas} OAS-specific rotation patterns")

    n_up_hit = 0
    n_oas_hit = 0
    n_unmatched = 0
    for row in rows:
        if len(row) < 7:
            continue
        ref, _val, pkg, _x, _y, rot, _side = row
        pkg_bare = pkg.split(":", 1)[-1]

        matched_src = None
        for rx, offset, source in corrections:
            if rx.match(pkg_bare):
                new_rot = (float(rot) + offset) % 360
                if offset != 0:
                    src_tag = "upstream" if source == "upstream" else "OAS"
                    st.info(
                        f"  [{src_tag}] {ref} ({pkg_bare}) {rot}deg + {offset:+g}deg = {new_rot:g}deg"
                    )
                row[5] = (
                    str(int(new_rot)) if new_rot == int(new_rot) else f"{new_rot:g}"
                )
                matched_src = source
                break

        if matched_src == "upstream":
            n_up_hit += 1
        elif matched_src is not None:
            n_oas_hit += 1
        else:
            n_unmatched += 1

    return n_up_hit, n_oas_hit, n_unmatched


def postprocess_cpl_for_jlcpcb(path: Path, st: Stage) -> tuple[int, int, int, int]:
    """Rewrite a kicad-cli CPL output in place to JLCPCB upload format.

    Input header (kicad-cli):   Ref,Val,Package,PosX,PosY,Rot,Side
    Output header (JLCPCB):     Designator,Mid X,Mid Y,Layer,Rotation

    Applies rotation corrections before column reformatting.
    Returns (footprint_count, n_upstream, n_oas, n_unmatched).
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return 0, 0, 0, 0

    data_rows = [r for r in rows[1:] if r]
    n_up, n_oas, n_unmatched = apply_rotation_corrections(data_rows, st)

    out = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]]
    for row in data_rows:
        ref, _val, _pkg, x, y, rot, side = row
        x_fmt = f"{float(x):.4f}"
        y_fmt = f"{float(y):.4f}"
        rot_f = float(rot)
        rot_fmt = str(int(rot_f)) if rot_f == int(rot_f) else f"{rot_f:g}"
        layer = "Top" if side.lower().startswith("top") else "Bottom"
        out.append([ref, x_fmt, y_fmt, layer, rot_fmt])
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(out)
    return len(out) - 1, n_up, n_oas, n_unmatched


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        JLCPCB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for side, fname in POS_OUTPUT_FILES:
            out = JLCPCB_OUTPUT_DIR / fname
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
            n, n_up, n_oas, n_unmatched = postprocess_cpl_for_jlcpcb(out, st)
            st.ok(
                f"wrote {fname} ({n} footprints; "
                f"rotations: {n_up} upstream + {n_oas} OAS + {n_unmatched} unchanged)"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
