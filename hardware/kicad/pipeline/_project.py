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
# Each tuple: (output prefix, comma-separated KiCad layers, mirror?)
PCB_2D_TARGETS = [
    ("2d-top",     "Edge.Cuts,F.Cu,F.Mask,F.SilkS,F.CrtYd,F.Fab", False),
    ("2d-cutouts", "Edge.Cuts,F.Cu,Dwgs.User",                    False),
    ("2d-bottom",  "Edge.Cuts,B.Cu,B.Mask,B.SilkS,B.CrtYd,B.Fab", True),
]

# Stage 11: schematic SVG renders -----------------------------------------
# Each tuple: (output prefix, schematic filename relative to KICAD_ROOT)
SCH_SUB_SHEETS = [
    ("sch-root",    "oas.kicad_sch"),
    ("sch-power",   "power.kicad_sch"),
    ("sch-mcu",     "mcu.kicad_sch"),
    ("sch-sensors", "sensors.kicad_sch"),
    ("sch-io",      "io.kicad_sch"),
]

# Stage 13: 3D render targets ---------------------------------------------
# Each tuple: (output filename, extra kicad-cli render flags)
PCB_3D_TARGETS = [
    ("3d-top.png", []),
    ("3d-iso.png", ["--rotate", "-45,0,45", "--perspective", "--floor"]),
]
