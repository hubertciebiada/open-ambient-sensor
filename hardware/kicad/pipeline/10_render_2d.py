"""Stage 10/11: 2D PCB SVG renders.

Renders three production-style SVG views: top, edge-cuts overlay, bottom
(mirrored). Edge.Cuts always included. `--check-zones` refills the GND
pour before plotting so the rendered SVG shows filled copper, not just
the zone outline (generate.py doesn't emit pre-computed `filled_polygon`
data because that's KiCad's job and its output carries non-deterministic
UUIDs we don't want to commit).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Stage, run, find_kicad_cli, RENDERS, PCB  # noqa: E402

STAGE_NAME = "render_2d"

SVG_TARGETS = [
    ("2d-top",     "Edge.Cuts,F.Cu,F.Mask,F.SilkS,F.CrtYd,F.Fab"),
    ("2d-cutouts", "Edge.Cuts,F.Cu,Dwgs.User"),
    ("2d-bottom",  "Edge.Cuts,B.Cu,B.Mask,B.SilkS,B.CrtYd,B.Fab"),
]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        RENDERS.mkdir(exist_ok=True)

        for name, layers in SVG_TARGETS:
            out = RENDERS / f"{name}.svg"
            cmd = [
                kcli, "pcb", "export", "svg",
                "--output", str(out),
                "--layers", layers,
                "--mode-single",
                "--page-size-mode", "2",
                "--fit-page-to-board",
                "--exclude-drawing-sheet",
                "--check-zones",
                str(PCB),
            ]
            if name == "2d-bottom":
                cmd.insert(-1, "--mirror")
            st.info(f"rendering {out.name}")
            run(cmd, hide_output=True)
            st.ok(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
