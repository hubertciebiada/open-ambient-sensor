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

ROTATION CORRECTIONS — KiCad footprint "0° rotation" reference differs
from JLCPCB tape-feeder "0° rotation" reference for many packages. The
v0.40 JLCPCB DFM render showed U1 LM2596S, Q1 AO3401A, and SK6812-SIDE
LEDs all visually misplaced (leads off-pad / die emitting inward). Fix:
load the community rotation correction table from the JLCKicadTools
submodule (https://github.com/matthewlai/JLCKicadTools, MIT) and apply
per-footprint regex-matched offsets to the rotation column before
writing the CPL.

Excludes DNP footprints (J2 recovery header, J10 native-USB recovery) and
uses the drill-file origin so CPL coords match the gerbers.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli, KICAD_ROOT  # noqa: E402
from _project import PCB_PATH, GERBER_OUTPUT_DIR, POS_OUTPUT_FILES  # noqa: E402

STAGE_NAME = "export_pos"

ROTATIONS_CSV = (
    KICAD_ROOT / "third_party" / "JLCKicadTools" / "jlc_kicad_tools" / "cpl_rotations_db.csv"
)


def load_rotation_corrections() -> list[tuple[re.Pattern, float]]:
    """Load (compiled_regex, offset_deg) tuples from the JLCKicadTools CSV.

    Schema per row: `<regex>,<rotation_offset>[,<dx>,<dy>]`. Rotation only;
    offset_x/y currently ignored (kicad-cli's `--use-drill-file-origin`
    already handles positional alignment with gerbers).

    Hard FAIL if CSV missing (submodule not initialized) — clear error
    message tells the developer the single fix command.
    """
    if not ROTATIONS_CSV.exists():
        sys.exit(
            "[FAIL] rotation correction CSV missing at "
            f"{ROTATIONS_CSV.relative_to(KICAD_ROOT.parent)} — "
            "run: git submodule update --init --recursive"
        )
    out: list[tuple[re.Pattern, float]] = []
    with ROTATIONS_CSV.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2:
                continue
            pattern = row[0].strip().strip('"')
            try:
                offset = float(row[1])
            except ValueError:
                continue
            out.append((re.compile(pattern), offset))
    return out


def apply_rotation_corrections(rows: list[list[str]], st: Stage) -> tuple[int, int]:
    """Modify the rotation column in-place based on footprint-regex matches.

    Each kicad-cli CSV row: [Ref, Val, Package, PosX, PosY, Rot, Side].
    `Package` includes the "Lib:Name" prefix; we match the bare name.
    Returns (n_applied, n_unmatched).
    """
    corrections = load_rotation_corrections()
    st.info(f"loaded {len(corrections)} rotation patterns from JLCKicadTools")

    n_applied = 0
    n_unmatched = 0
    for row in rows:
        if len(row) < 7:
            continue
        ref, _val, pkg, _x, _y, rot, _side = row
        pkg_bare = pkg.split(":", 1)[-1]

        matched = False
        for rx, offset in corrections:
            if rx.match(pkg_bare):
                new_rot = (float(rot) + offset) % 360
                if offset != 0:
                    st.info(
                        f"  {ref} ({pkg_bare}) {rot}deg + {offset:+g}deg = {new_rot:g}deg"
                    )
                row[5] = (
                    str(int(new_rot)) if new_rot == int(new_rot) else f"{new_rot:g}"
                )
                n_applied += 1
                matched = True
                break
        if not matched:
            n_unmatched += 1

    return n_applied, n_unmatched


def postprocess_cpl_for_jlcpcb(path: Path, st: Stage) -> tuple[int, int, int]:
    """Rewrite a kicad-cli CPL output in place to JLCPCB upload format.

    Input header (kicad-cli):   Ref,Val,Package,PosX,PosY,Rot,Side
    Output header (JLCPCB):     Designator,Mid X,Mid Y,Layer,Rotation

    Applies rotation corrections before column reformatting.
    Returns (footprint_count, n_corrections_applied, n_unmatched).
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return 0, 0, 0

    data_rows = [r for r in rows[1:] if r]
    n_applied, n_unmatched = apply_rotation_corrections(data_rows, st)

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
    return len(out) - 1, n_applied, n_unmatched


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
            n, applied, unmatched = postprocess_cpl_for_jlcpcb(out, st)
            st.ok(
                f"wrote {fname} ({n} footprints, JLCPCB-format; "
                f"rotations: {applied} corrected, {unmatched} unchanged)"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
