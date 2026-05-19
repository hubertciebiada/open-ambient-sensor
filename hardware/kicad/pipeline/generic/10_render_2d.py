"""Stage 10/11: 2D PCB SVG renders.

Renders three production-style SVG views: top, edge-cuts overlay, bottom
(mirrored). Edge.Cuts always included. `--check-zones` refills the GND
pour before plotting so the rendered SVG shows filled copper, not just
the zone outline (boardgen doesn't emit pre-computed `filled_polygon`
data because that's KiCad's job and its output carries non-deterministic
UUIDs we don't want to commit).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli, RENDERS  # noqa: E402
from _project import PCB_PATH, PCB_2D_TARGETS  # noqa: E402

STAGE_NAME = "render_2d"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        RENDERS.mkdir(exist_ok=True)

        for subdir, name, layers, mirror in PCB_2D_TARGETS:
            out_dir = RENDERS / subdir
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"{name}.svg"
            cmd = [
                kcli, "pcb", "export", "svg",
                "--output", str(out),
                "--layers", layers,
                "--mode-single",
                "--page-size-mode", "2",
                "--fit-page-to-board",
                "--exclude-drawing-sheet",
                "--check-zones",
                str(PCB_PATH),
            ]
            if mirror:
                cmd.insert(-1, "--mirror")
            st.info(f"rendering {out.name}")
            run(cmd, hide_output=True)
            st.ok(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
