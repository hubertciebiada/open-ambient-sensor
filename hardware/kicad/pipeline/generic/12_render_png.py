"""Stage 12/11: PNG conversion via cairosvg.

Converts every `renders/*.svg` file produced by stages 10/11 to PNG at
1600 px output width. `renders/` is committed as a visual changelog, so
a silently-skipped conversion would let the committed PNGs drift out of
sync with their SVGs without anyone noticing. cairosvg is therefore
REQUIRED, not optional — the stage hard-fails if it is not importable.
One-time setup: `pip install cairosvg`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, RENDERS  # noqa: E402

STAGE_NAME = "render_png"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        RENDERS.mkdir(exist_ok=True)
        try:
            import cairosvg
        except ImportError:
            print("[FAIL] cairosvg not importable — required for stage 12 PNG conversion")
            print("[FAIL] one-time setup: pip install cairosvg")
            st.fail("cairosvg missing")

        # rglob picks up SVGs from every subdir under renders/ (pcb/, sch/,
        # plus any future grouping). PNG lands in the same dir as its SVG.
        svgs = sorted(RENDERS.rglob("*.svg"))
        for svg in svgs:
            png = svg.with_suffix(".png")
            cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=1600)
            rel = svg.relative_to(RENDERS)
            st.ok(f"{rel} -> {rel.with_suffix('.png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
