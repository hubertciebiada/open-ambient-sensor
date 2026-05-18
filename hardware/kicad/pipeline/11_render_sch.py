"""Stage 11/11: schematic SVG renders.

kicad-cli sch export svg writes one SVG per schematic file into the
output directory, naming it after the input file's stem (e.g. power.svg).
We render each hierarchical sub-sheet directly (passing its file) so we
get one clean SVG per sub-sheet, then rename to sch-<name>.svg for a
consistent and gitignore-friendly output set.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Stage, run, find_kicad_cli, RENDERS, KICAD_ROOT  # noqa: E402

STAGE_NAME = "render_sch"

SCH_TARGETS = [
    ("sch-root",    KICAD_ROOT / "oas.kicad_sch"),
    ("sch-power",   KICAD_ROOT / "power.kicad_sch"),
    ("sch-mcu",     KICAD_ROOT / "mcu.kicad_sch"),
    ("sch-sensors", KICAD_ROOT / "sensors.kicad_sch"),
    ("sch-io",      KICAD_ROOT / "io.kicad_sch"),
]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        RENDERS.mkdir(exist_ok=True)

        for out_name, src in SCH_TARGETS:
            # Render into a temp subdir (prefixed `_` so it stays gitignored
            # along with the DRC/ERC reports), then atomically move the
            # produced file into renders/ under the desired sch-<name>.svg
            # filename. .replace() overwrites on Windows even when a viewer
            # has the destination open.
            tmp_dir = RENDERS / f"_{out_name}-tmp"
            tmp_dir.mkdir(exist_ok=True)
            run([
                kcli, "sch", "export", "svg",
                "--output", str(tmp_dir),
                "--exclude-drawing-sheet",
                "--no-background-color",
                str(src),
            ], hide_output=True)
            produced = tmp_dir / f"{src.stem}.svg"
            final = RENDERS / f"{out_name}.svg"
            produced.replace(final)
            try:
                tmp_dir.rmdir()
            except OSError:
                pass
            st.ok(f"wrote {final.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
