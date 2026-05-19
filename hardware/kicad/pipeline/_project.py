"""OAS project-specific config for the generic pipeline stages.

Generic stages under `pipeline/generic/` import constants from this
module. To port the pipeline to a different KiCad project:

  1. Copy `pipeline/_common.py` and `pipeline/generic/` into the new repo.
  2. Create the new repo's own `_project.py` based on this template,
     editing every constant to match the new project's filenames /
     schematic structure / render-layer preferences.
  3. Optionally create `pipeline/<project>/` for project-specific
     verification stages (analog to OAS's `pipeline/oas/`).
  4. The orchestrator (`regenerate.py`) auto-discovers stages from
     every immediate subdirectory of `pipeline/`, sorted by basename.

NOTE: `pipeline/oas/05_check_dc.py`, `06_check_boot.py`, and
`07_check_ampacity.py` are deeply hardcoded to OAS's specific circuit
(resistor values, ESP32-C6 GPIO map, +24V/+5V/+3V3 rail budgets). They
are NOT parameterized through this file — a new project either reuses
them verbatim (if it shares the same power chain + ESP32-C6 module) or
writes its own `pipeline/<project>/` verification stages.
"""
from __future__ import annotations

from pathlib import Path

KICAD_ROOT = Path(__file__).parent.parent  # hardware/kicad

# Top-level files ----------------------------------------------------------
PCB_PATH = KICAD_ROOT / "oas.kicad_pcb"
SCH_PATH = KICAD_ROOT / "oas.kicad_sch"

# Stage 01: generate.py command -------------------------------------------
GENERATE_SCRIPT = KICAD_ROOT / "generate.py"

# Stage 02: determinism source-files list ---------------------------------
# Mix of fixed filenames (joined with KICAD_ROOT at use site) and rglob
# patterns (also relative to KICAD_ROOT).
SOURCE_FILES_FIXED = [
    "oas.kicad_pro",
    "oas.kicad_sch",
    "oas.kicad_pcb",
    "power.kicad_sch",
    "mcu.kicad_sch",
    "sensors.kicad_sch",
    "io.kicad_sch",
    "fp-lib-table",
    "sym-lib-table",
]
SOURCE_FILES_GLOBS = [
    "libraries/**/*.kicad_mod",
    "libraries/**/*.kicad_sym",
]

# Stage 10: PCB 2D render targets -----------------------------------------
# Each tuple: (renders/ subdir, output prefix, comma-separated KiCad layers, mirror?)
PCB_2D_TARGETS = [
    ("pcb", "2d-top",     "Edge.Cuts,F.Cu,F.Mask,F.SilkS,F.CrtYd,F.Fab", False),
    ("pcb", "2d-cutouts", "Edge.Cuts,F.Cu,Dwgs.User",                    False),
    ("pcb", "2d-bottom",  "Edge.Cuts,B.Cu,B.Mask,B.SilkS,B.CrtYd,B.Fab", True),
]

# Stage 11: schematic SVG renders -----------------------------------------
# Each tuple: (renders/ subdir, output prefix, schematic filename relative to KICAD_ROOT)
SCH_SUB_SHEETS = [
    ("sch", "sch-root",    "oas.kicad_sch"),
    ("sch", "sch-power",   "power.kicad_sch"),
    ("sch", "sch-mcu",     "mcu.kicad_sch"),
    ("sch", "sch-sensors", "sensors.kicad_sch"),
    ("sch", "sch-io",      "io.kicad_sch"),
]

# Stage 13: 3D render targets ---------------------------------------------
# Each tuple: (renders/ subdir, output filename, extra kicad-cli render flags)
PCB_3D_TARGETS = [
    ("pcb", "3d-top.png", []),
    ("pcb", "3d-iso.png", ["--rotate", "-45,0,45", "--perspective", "--floor"]),
]

# Stage 24: pygerber preflight composite render destination subdir.
PREFLIGHT_SUBDIR = "pcb"

# ===========================================================================
# Production export — vendor-isolated layout
# ===========================================================================
#
# Architecture (audit-19, 2026-05-19): the project itself is vendor-neutral.
# Stage 20 emits raw gerbers + drill to hardware/build/gerbers/ (intermediate,
# gitignored). Each manufacturing vendor gets its own pipeline subdirectory
# (`pipeline/<vendor>/`) writing exactly 4 deliverables — ZIP + BOM + CPL top
# + CPL bottom — into hardware/output/<vendor>/. Adding a new fabricator
# means creating a new sibling to `pipeline/jlcpcb/` and a new vendor folder
# under hardware/output/. Zero edits to `generic/` or `oas/` stages.

# Intermediate vendor-neutral raw fab data (gerbers + drill + drill_map PDFs).
# Gitignored via the generic `**/build/` rule in .gitignore.
GERBERS_BUILD_DIR = KICAD_ROOT.parent / "build" / "gerbers"

# Vendor-specific deliverables parent. Each vendor lives under its own
# subdirectory carrying EXACTLY 4 files.
OUTPUT_ROOT = KICAD_ROOT.parent / "output"

# Stage 20: gerber + drill ------------------------------------------------
# Fab deliverable layers. NOT F.Fab / B.Fab / F.CrtYd / B.CrtYd / Dwgs.User
# — those are internal documentation, not for production.
FAB_LAYERS = (
    "F.Cu,B.Cu,"
    "F.Mask,B.Mask,"
    "F.Silkscreen,B.Silkscreen,"
    "F.Paste,B.Paste,"
    "Edge.Cuts"
)

# Stage 24: preflight -----------------------------------------------------
# Expected drill statistics from generate.py geometry. Update when board
# mechanicals change (mounting hole count / zip-tie hole count).
NPTH_EXPECTED_TOOLS = {3.00, 3.80}     # 3.00 = zip-tie pairs, 3.80 = M3 mount
NPTH_EXPECTED_HOLES = 4 + 3            # 4 zip-tie + 3 M3 mounting
PTH_MIN_DRILL_MM = 0.30                # JLCPCB std 2-layer minimum

# ===========================================================================
# Vendor: JLCPCB (pipeline/jlcpcb/ stages 29-32)
# ===========================================================================

JLCPCB_OUTPUT_DIR = OUTPUT_ROOT / "jlcpcb"

# Stage 30: position file outputs.
# Each tuple: (kicad-cli --side argument, output filename relative to
# JLCPCB_OUTPUT_DIR). JLCPCB CPL upload requires header
# `Designator, Mid X, Mid Y, Layer, Rotation` — the stage post-processes
# kicad-cli's default `Ref, Val, Package, PosX, PosY, Rot, Side` to that.
POS_OUTPUT_FILES = [
    ("front", "oas-top-CPL.csv"),
    ("back",  "oas-bottom-CPL.csv"),
]

# Stage 31: BOM with LCSC mapping.
# LCSC mapping lives as a Python dict in `hardware/kicad/lcsc_mapping.py`
# (single source of truth, imported by stage 31 + boardgen/_postprocess.py
# for informational schematic-field injection).
BOM_OUTPUT_FILE = "oas-bom.csv"

# Reference designators that go through THT hand-solder line (not SMT).
# A BOM row whose ALL designators belong here gets emitted with blank
# LCSC + JLCPCB_Library = "THT (hand-solder)". J1 Phoenix terminal,
# J4 LD2410 1.27 mm header, J5/J6 ESP32 sockets, J7/J8 MIKROE-2462
# sockets, C1/C3 D8 radial bulk, C4 D6.3 radial bulk.
THT_REFERENCES = {"J1", "J4", "J5", "J6", "J7", "J8", "C1", "C3", "C4"}

# Stage 32: ZIP bundle.
BUNDLE_NAME = "oas-jlcpcb.zip"
# Globs relative to GERBERS_BUILD_DIR. Set as globs so a layer-list change
# in FAB_LAYERS automatically widens the bundle.
BUNDLE_GLOBS = ["*.gtl", "*.gbl", "*.gts", "*.gbs",
                "*.gto", "*.gbo", "*.gtp", "*.gbp",
                "*.gm1", "*.drl"]
