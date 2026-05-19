"""Stage 24: pre-flight gerber sanity check.

Programmatic verification that the raw gerbers in hardware/build/gerbers/
are sane before any vendor packages them:

  1. **Integrity** — every expected file present, non-zero size.
  2. **Drill statistics** — parse Excellon files (PTH + NPTH), count
     tool sizes + hole positions, sanity-check against expected values
     from boardgen geometry (NPTH_EXPECTED_TOOLS / NPTH_EXPECTED_HOLES
     / PTH_MIN_DRILL_MM in _project).
  3. **Composite renders** — render (Edge.Cuts + Cu + Mask + Silk) via
     pygerber for both sides, save to renders/preflight-top.png and
     renders/preflight-bottom.png. Side-by-side they should match the
     stage 10 KiCad-side renders' geometry; mismatch = gerber export bug.

This stage is vendor-neutral — it reads the raw gerbers in
GERBERS_BUILD_DIR, not any vendor ZIP. Per-vendor ZIP integrity is each
vendor stage's own responsibility (stage 32 testzip in pipeline/jlcpcb/).

pygerber is an optional dependency (analogous to stage 12 cairosvg) — if
not installed, the stage emits a WARN and exits 0 so the pipeline runs
out-of-box.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, RENDERS  # noqa: E402
from _project import (  # noqa: E402
    GERBERS_BUILD_DIR,
    NPTH_EXPECTED_TOOLS,
    NPTH_EXPECTED_HOLES,
    PTH_MIN_DRILL_MM,
    PREFLIGHT_SUBDIR,
)

STAGE_NAME = "preflight_gerbers"

EXPECTED_GERBERS = [
    ("oas-F_Cu.gtl",         "Top copper"),
    ("oas-B_Cu.gbl",         "Bottom copper"),
    ("oas-F_Mask.gts",       "Top solder mask"),
    ("oas-B_Mask.gbs",       "Bottom solder mask"),
    ("oas-F_Silkscreen.gto", "Top silkscreen"),
    ("oas-B_Silkscreen.gbo", "Bottom silkscreen"),
    ("oas-F_Paste.gtp",      "Top solder paste"),
    ("oas-B_Paste.gbp",      "Bottom solder paste"),
    ("oas-Edge_Cuts.gm1",    "Board outline"),
]
EXPECTED_DRILLS = [
    ("oas-PTH.drl",  "Plated through-holes"),
    ("oas-NPTH.drl", "Non-plated holes"),
]


def parse_drill_tools(drl_path: Path) -> tuple[dict[int, float], int]:
    """Parse Excellon drill file. Returns ({tool_number: diameter_mm},
    total_hole_count). Header line `TnnCdd.dd` declares tool n at
    diameter dd.dd; body has `Tnn` lines selecting that tool followed by
    `XnnnYnnn` hole positions."""
    tools: dict[int, float] = {}
    holes = 0
    current_tool: int | None = None
    in_header = True
    for line in drl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line == "%":
            in_header = False
            continue
        if in_header:
            m = re.match(r"^T(\d+)C([\d.]+)", line)
            if m:
                tools[int(m.group(1))] = float(m.group(2))
        else:
            m_sel = re.match(r"^T(\d+)$", line)
            if m_sel:
                current_tool = int(m_sel.group(1))
                continue
            if line.startswith("X") and current_tool is not None:
                holes += 1
    return tools, holes


def main() -> int:
    with Stage(STAGE_NAME) as st:
        try:
            from pygerber.gerberx3.api.v2 import (  # type: ignore[import-not-found]
                GerberFile,
                FileTypeEnum,
                Project,
                OnParserErrorEnum,
            )
        except ImportError:
            st.warn("pygerber not installed — pip install pygerber to enable preflight")
            return 0

        RENDERS.mkdir(exist_ok=True)
        preflight_dir = RENDERS / PREFLIGHT_SUBDIR
        preflight_dir.mkdir(parents=True, exist_ok=True)

        # 1) File integrity (raw fab data only; vendor ZIPs are each
        # vendor stage's own concern — stage 32 in pipeline/jlcpcb/ runs
        # zipfile.testzip() on its own output).
        st.info(f"checking integrity of {len(EXPECTED_GERBERS) + len(EXPECTED_DRILLS)} files")
        for fname, desc in EXPECTED_GERBERS + EXPECTED_DRILLS:
            p = GERBERS_BUILD_DIR / fname
            if not p.exists() or p.stat().st_size == 0:
                st.fail(f"{fname} missing or empty ({desc})")
            st.ok(f"{fname:30s} {desc} ({p.stat().st_size} B)")

        # 2) Drill statistics
        st.info("drill statistics")
        pth_tools, pth_holes = parse_drill_tools(GERBERS_BUILD_DIR / "oas-PTH.drl")
        st.ok(f"PTH: {len(pth_tools)} tool sizes, {pth_holes} holes total")
        for tn, dia in sorted(pth_tools.items(), key=lambda kv: kv[1]):
            st.info(f"  T{tn} = {dia:.3f} mm")
        min_pth = min(pth_tools.values()) if pth_tools else 0
        if min_pth < PTH_MIN_DRILL_MM:
            st.fail(f"PTH min drill {min_pth:.3f} mm < {PTH_MIN_DRILL_MM} mm")
        st.ok(f"PTH min drill {min_pth:.3f} mm >= {PTH_MIN_DRILL_MM} mm (JLCPCB std-2-layer)")

        npth_tools, npth_holes = parse_drill_tools(GERBERS_BUILD_DIR / "oas-NPTH.drl")
        st.ok(f"NPTH: {len(npth_tools)} tool sizes, {npth_holes} holes total")
        for tn, dia in sorted(npth_tools.items(), key=lambda kv: kv[1]):
            st.info(f"  T{tn} = {dia:.3f} mm")
        npth_dia_set = {round(d, 2) for d in npth_tools.values()}
        if npth_dia_set != NPTH_EXPECTED_TOOLS:
            st.fail(f"NPTH tool sizes {npth_dia_set} != expected {NPTH_EXPECTED_TOOLS}")
        if npth_holes != NPTH_EXPECTED_HOLES:
            st.fail(f"NPTH hole count {npth_holes} != expected {NPTH_EXPECTED_HOLES}")
        st.ok(f"NPTH matches expected ({NPTH_EXPECTED_HOLES} holes, tools {NPTH_EXPECTED_TOOLS})")

        # 3) Composite renders
        st.info("rendering composite top + bottom (pygerber)")
        for side, files, out_name in [
            ("top", [
                (GERBERS_BUILD_DIR / "oas-F_Cu.gtl",         FileTypeEnum.COPPER),
                (GERBERS_BUILD_DIR / "oas-F_Mask.gts",       FileTypeEnum.MASK),
                (GERBERS_BUILD_DIR / "oas-F_Silkscreen.gto", FileTypeEnum.SILK),
                (GERBERS_BUILD_DIR / "oas-Edge_Cuts.gm1",    FileTypeEnum.EDGE),
            ], "preflight-top.png"),
            ("bottom", [
                (GERBERS_BUILD_DIR / "oas-B_Cu.gbl",         FileTypeEnum.COPPER),
                (GERBERS_BUILD_DIR / "oas-B_Mask.gbs",       FileTypeEnum.MASK),
                (GERBERS_BUILD_DIR / "oas-B_Silkscreen.gbo", FileTypeEnum.SILK),
                (GERBERS_BUILD_DIR / "oas-Edge_Cuts.gm1",    FileTypeEnum.EDGE),
            ], "preflight-bottom.png"),
        ]:
            try:
                gerber_files = [GerberFile.from_file(p, file_type=ft) for p, ft in files]
                proj = Project(gerber_files).parse(on_parser_error=OnParserErrorEnum.Ignore)
                out_path = preflight_dir / out_name
                proj.render_raster(out_path, dpmm=20)
                st.ok(f"wrote {PREFLIGHT_SUBDIR}/{out_name} ({out_path.stat().st_size / 1024:.1f} kB)")
            except Exception as e:
                st.fail(f"{side} composite render: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
