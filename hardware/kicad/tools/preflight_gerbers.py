"""
OAS — pre-flight gerber check.

Programmatic verification that the gerbers in ../../gerbers/ are sane
before uploading to JLCPCB:

  1. **Integrity** — every expected file is present, non-zero size, the
     ZIP bundle is readable, member count matches.
  2. **Drill statistics** — parse the Excellon files (PTH + NPTH), count
     tool sizes + hole positions, sanity-check against expected values
     from generate.py:
       - PTH: vias (0.30) + assorted component holes
       - NPTH: 3.00 mm zip-tie + 3.80 mm M3 mounting holes (exactly 4 + 3)
  3. **Visual render** — composite renders of (Edge.Cuts + F.Cu + F.Mask
     + F.SilkS) for the top, mirrored for the bottom, saved to
     ../renders/preflight-top.png / preflight-bottom.png. Side-by-side
     these match the regenerate.py renders' geometry; mismatches mean
     something went wrong in the gerber export.

Run AFTER `export_production.py`.

Output: prints a pass/fail table; non-zero exit on any failure.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

try:
    from pygerber.gerberx3.api.v2 import (
        GerberFile,
        FileTypeEnum,
        Project,
        OnParserErrorEnum,
    )
except ImportError:
    sys.exit("ERROR: pygerber not installed. Run: pip install pygerber")

HERE = Path(__file__).parent
GERBERS = HERE.parent.parent / "gerbers"
RENDERS = HERE.parent / "renders"

# Expected file set from export_production.py (matches what JLCPCB needs)
EXPECTED_FILES = {
    "oas-F_Cu.gtl":          (FileTypeEnum.COPPER, "Top copper"),
    "oas-B_Cu.gbl":          (FileTypeEnum.COPPER, "Bottom copper"),
    "oas-F_Mask.gts":        (FileTypeEnum.MASK,   "Top solder mask"),
    "oas-B_Mask.gbs":        (FileTypeEnum.MASK,   "Bottom solder mask"),
    "oas-F_Silkscreen.gto":  (FileTypeEnum.SILK,   "Top silkscreen"),
    "oas-B_Silkscreen.gbo":  (FileTypeEnum.SILK,   "Bottom silkscreen"),
    "oas-F_Paste.gtp":       (FileTypeEnum.PASTE,  "Top solder paste"),
    "oas-B_Paste.gbp":       (FileTypeEnum.PASTE,  "Bottom solder paste"),
    "oas-Edge_Cuts.gm1":     (FileTypeEnum.EDGE,   "Board outline"),
}
DRILL_FILES = {
    "oas-PTH.drl": "Plated through-holes",
    "oas-NPTH.drl": "Non-plated holes",
}
ZIP_EXPECTED = 11  # 9 gerbers + 2 drills

# Expected from generate.py — see HOLE_POSITIONS + ZIP_TIE_HOLES constants
EXPECTED_NPTH_TOOLS = {3.00, 3.80}    # zip-tie pairs + 3× M3 mounting holes
EXPECTED_NPTH_COUNT = 4 + 3           # 4 zip-tie + 3 mounting = 7 holes
EXPECTED_MIN_PTH_DRILL = 0.30         # JLCPCB std-2-layer cutoff


def check(name: str, cond: bool, detail: str = "") -> bool:
    """One-line pass/fail row. Returns cond for chaining into a fail flag."""
    mark = "PASS" if cond else "FAIL"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return cond


def parse_drill_tools(drl_path: Path) -> tuple[dict[int, float], int]:
    """Parse an Excellon drill file. Returns ({tool_number: diameter_mm},
    total_hole_count). Excellon header lines `TnnCdd.dd` declare tool n at
    diameter dd.dd; body has `Tnn\\n` lines selecting that tool followed
    by `XnnnYnnn` hole positions."""
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


def render_composite_top() -> None:
    """Render top-side composite (Edge.Cuts + F.Cu + F.Mask + F.SilkS).
    Order matters — files render bottom-up, so Edge.Cuts last gives the
    outline on top of everything; copper first puts it at the bottom of
    the visual stack."""
    files = [
        GerberFile.from_file(GERBERS / "oas-F_Cu.gtl",         file_type=FileTypeEnum.COPPER),
        GerberFile.from_file(GERBERS / "oas-F_Mask.gts",       file_type=FileTypeEnum.MASK),
        GerberFile.from_file(GERBERS / "oas-F_Silkscreen.gto", file_type=FileTypeEnum.SILK),
        GerberFile.from_file(GERBERS / "oas-Edge_Cuts.gm1",    file_type=FileTypeEnum.EDGE),
    ]
    proj = Project(files).parse(on_parser_error=OnParserErrorEnum.Ignore)
    out = RENDERS / "preflight-top.png"
    proj.render_raster(out, dpmm=20)
    print(f"  wrote {out.name} ({out.stat().st_size / 1024:.1f} kB)")


def render_composite_bottom() -> None:
    files = [
        GerberFile.from_file(GERBERS / "oas-B_Cu.gbl",         file_type=FileTypeEnum.COPPER),
        GerberFile.from_file(GERBERS / "oas-B_Mask.gbs",       file_type=FileTypeEnum.MASK),
        GerberFile.from_file(GERBERS / "oas-B_Silkscreen.gbo", file_type=FileTypeEnum.SILK),
        GerberFile.from_file(GERBERS / "oas-Edge_Cuts.gm1",    file_type=FileTypeEnum.EDGE),
    ]
    proj = Project(files).parse(on_parser_error=OnParserErrorEnum.Ignore)
    out = RENDERS / "preflight-bottom.png"
    proj.render_raster(out, dpmm=20)
    print(f"  wrote {out.name} ({out.stat().st_size / 1024:.1f} kB)")


def main() -> None:
    failed = False

    print("\n=== 1/4  File integrity ===")
    for fname, (_ftype, desc) in EXPECTED_FILES.items():
        p = GERBERS / fname
        ok = p.exists() and p.stat().st_size > 0
        failed |= not check(f"{fname:30s} {desc}", ok,
                            f"{p.stat().st_size if p.exists() else 0} B")
    for fname, desc in DRILL_FILES.items():
        p = GERBERS / fname
        ok = p.exists() and p.stat().st_size > 0
        failed |= not check(f"{fname:30s} {desc}", ok,
                            f"{p.stat().st_size if p.exists() else 0} B")
    zip_path = GERBERS / "oas-jlcpcb.zip"
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path) as zf:
                bad = zf.testzip()
                count = len(zf.namelist())
            ok = bad is None and count == ZIP_EXPECTED
            failed |= not check(
                f"{'oas-jlcpcb.zip':30s} Bundle for JLCPCB", ok,
                f"{count} entries, integrity={'OK' if bad is None else 'BROKEN'}",
            )
        except zipfile.BadZipFile:
            failed |= not check("oas-jlcpcb.zip readable", False, "BadZipFile")
    else:
        failed |= not check("oas-jlcpcb.zip exists", False)

    print("\n=== 2/4  Drill statistics ===")
    pth_tools, pth_holes = parse_drill_tools(GERBERS / "oas-PTH.drl")
    print(f"  PTH:  {len(pth_tools)} tool sizes, {pth_holes} holes total")
    for tn, dia in sorted(pth_tools.items(), key=lambda kv: kv[1]):
        print(f"        T{tn} = {dia:.3f} mm")
    min_pth = min(pth_tools.values()) if pth_tools else 0
    failed |= not check(
        f"PTH min drill >= {EXPECTED_MIN_PTH_DRILL} mm (JLCPCB std-2-layer)",
        min_pth >= EXPECTED_MIN_PTH_DRILL,
        f"actual: {min_pth:.3f} mm",
    )
    failed |= not check("PTH has at least 1 hole", pth_holes > 0, f"{pth_holes} holes")

    npth_tools, npth_holes = parse_drill_tools(GERBERS / "oas-NPTH.drl")
    print(f"  NPTH: {len(npth_tools)} tool sizes, {npth_holes} holes total")
    for tn, dia in sorted(npth_tools.items(), key=lambda kv: kv[1]):
        print(f"        T{tn} = {dia:.3f} mm")
    npth_dia_set = {round(d, 2) for d in npth_tools.values()}
    failed |= not check(
        f"NPTH tool sizes == {EXPECTED_NPTH_TOOLS}",
        npth_dia_set == EXPECTED_NPTH_TOOLS,
        f"actual: {npth_dia_set}",
    )
    failed |= not check(
        f"NPTH hole count == {EXPECTED_NPTH_COUNT} (4 zip-tie + 3 mounting)",
        npth_holes == EXPECTED_NPTH_COUNT,
        f"actual: {npth_holes}",
    )

    print("\n=== 3/4  Render composite top ===")
    try:
        render_composite_top()
    except Exception as e:
        failed = True
        check("Top composite render", False, f"{type(e).__name__}: {e}")

    print("\n=== 4/4  Render composite bottom ===")
    try:
        render_composite_bottom()
    except Exception as e:
        failed = True
        check("Bottom composite render", False, f"{type(e).__name__}: {e}")

    print()
    if failed:
        sys.exit("ERROR: pre-flight checks FAILED — see above")
    print("All pre-flight checks PASSED.")
    print(f"Compare against KiCad-side renders:")
    print(f"  {RENDERS.relative_to(HERE.parent.parent)}/preflight-top.png    vs  2d-top.png")
    print(f"  {RENDERS.relative_to(HERE.parent.parent)}/preflight-bottom.png vs  2d-bottom.png")


if __name__ == "__main__":
    main()
