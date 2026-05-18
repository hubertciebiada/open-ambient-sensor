"""Stage 13/11: 3D PCB renders (expensive — ~15 s each).

Renders two views via `kicad-cli pcb render`:
  - 3d-top.png   straight-down top view
  - 3d-iso.png   isometric (--rotate '-45,0,45' --perspective --floor)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Stage, run, find_kicad_cli, RENDERS, PCB  # noqa: E402

STAGE_NAME = "render_3d"

RENDER_TARGETS = [
    ("3d-top.png", []),
    ("3d-iso.png", ["--rotate", "-45,0,45", "--perspective", "--floor"]),
]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        RENDERS.mkdir(exist_ok=True)

        for out_name, extra in RENDER_TARGETS:
            st.info(f"rendering {out_name} (~15s)")
            run([
                kcli, "pcb", "render",
                "--output", str(RENDERS / out_name),
                "--side", "top",
                "--width", "1600", "--height", "1600",
                "--background", "opaque",
                "--quality", "high",
                *extra,
                str(PCB),
            ], hide_output=True)
            st.ok(f"wrote {out_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
