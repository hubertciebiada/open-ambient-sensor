"""Stage 12/11: PNG conversion via cairosvg.

Converts every `renders/*.svg` file produced by stages 10/11 to PNG at
1600 px output width. cairosvg is optional — if not installed, the stage
prints a WARN and exits 0 (PNG previews are nice-to-have, not required).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Stage, RENDERS  # noqa: E402

STAGE_NAME = "render_png"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        RENDERS.mkdir(exist_ok=True)
        try:
            import cairosvg  # type: ignore[import-not-found]
        except ImportError:
            st.warn("cairosvg not installed — pip install cairosvg to enable PNG conversion")
            return 0

        svgs = sorted(RENDERS.glob("*.svg"))
        for svg in svgs:
            png = svg.with_suffix(".png")
            cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=1600)
            st.ok(f"{svg.name} -> {png.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
