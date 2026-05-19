"""boardgen — shared utilities for the OAS KiCad source-file generator.

This module holds project-AGNOSTIC framework helpers: paths, KiCad format
versions, the deterministic UUID system (`U`, `sheet_context`, `_OAS_NS`),
the `Context` dataclass that boardgen stages share state through, and
basic number formatting.

Project-specific constants (geometry, EXTERNAL_MODULES, GPIO map,
daughterboard placement) live in `boardgen/_project.py`.

Stage files under `boardgen/NN_<name>.py` import from this module via:

    from boardgen._common import U, sheet_context, Context, HERE, ...

`generate.py` (the thin orchestrator) walks `boardgen/[0-9][0-9]_*.py`
via importlib, instantiates a single `Context`, and threads it through
each stage's `run(ctx)` entry point.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Paths -------------------------------------------------------------------
# `HERE` points at hardware/kicad/ (the directory that holds generate.py,
# regenerate.py, the .kicad_* output files, libraries/, pipeline/, etc.).
# Stages write produced files relative to this path.
HERE = Path(__file__).parent.parent

# KiCad file format versions ---------------------------------------------
PCB_VERSION = 20260206
SCH_VERSION = 20260306   # canonical KiCad 10.0.2 schematic version
GEN_VERSION = "10.0"

# OAS project board-level identification — printed on F.SilkS so a physical
# PCB can be identified by version + URL without booting the device.
# v0.38: added per audit-26 good-practice recommendation. Update OAS_VERSION
# on each release tag.
OAS_NAME_SHORT = "Open Ambient Sensor"
OAS_VERSION_LINE = "OAS  v0.40"
OAS_REPO_URL = "github.com/HubertCiebiada/open-ambient-sensor"


# Number formatting -------------------------------------------------------
def fmt(x: float) -> str:
    """KiCad-style coordinate: up to 6 decimals, no trailing zeros required."""
    return f"{x:.6f}".rstrip("0").rstrip(".")


# Deterministic UUID system ----------------------------------------------
_OAS_NS = uuid.uuid5(uuid.NAMESPACE_OID, "oas.open-ambient-sensor")
_seen_uuid_tags: set[str] = set()
_current_sheet: str = ""


class sheet_context:
    """Scope-guard that namespaces every U() call made inside the `with` block
    under the given sub-sheet name.

    Two sub-sheets often need UUIDs for objects with the same logical name
    (a wire tagged "3v3-bus" exists in both power.kicad_sch and mcu.kicad_sch).
    Wrapping each `gen_*_sch()` body in `with sheet_context("power"):` makes
    U("wire:3v3-bus") produce different UUIDs in different sheets without
    every helper having to know which sheet it's emitting into.
    """
    def __init__(self, name: str):
        self.name = name
    def __enter__(self):
        global _current_sheet
        self._prev = _current_sheet
        _current_sheet = self.name
        return self
    def __exit__(self, *a):
        global _current_sheet
        _current_sheet = self._prev


def U(tag: str) -> str:
    """Deterministic UUID v5 derived solely from `tag` under the OAS namespace.

    If called inside a `with sheet_context(name):` block, `tag` is silently
    prefixed with `name:` so the same tag in two different sub-sheets
    produces two distinct UUIDs.

    Stability rule: a given (sheet, tag) pair always returns the same UUID,
    regardless of call order. Adding or removing unrelated `U(...)` calls
    does NOT shift other UUIDs. The whole project is bit-identical across
    regenerations.

    Uniqueness is the caller's responsibility — every distinct location that
    needs a UUID must pass a distinct (sheet, tag) pair. This function
    asserts tags are not reused within a single run to catch accidental
    collisions early.
    """
    if not tag:
        raise ValueError("U(): tag must be a non-empty string")
    full_tag = f"{_current_sheet}:{tag}" if _current_sheet else tag
    if full_tag in _seen_uuid_tags:
        raise ValueError(f"U(): duplicate tag {full_tag!r} — UUIDs must be unique by tag")
    _seen_uuid_tags.add(full_tag)
    return str(uuid.uuid5(_OAS_NS, full_tag))


# Root project + sheet UUIDs (must match between .kicad_pro and .kicad_sch)
# Use a tagged seed so this UUID is stable independent of call order elsewhere.
ROOT_SHEET_UUID = str(uuid.uuid5(_OAS_NS, "sheet:root"))

# Hierarchical sub-sheets — functional grouping (see CLAUDE.md):
#   power   — input protection + bucks 24V → 5V → 3.3V
#   mcu     — ESP32-C6-DevKitM-1-N4 + decoupling
#   sensors — SEN66, LD2410, NT3H1101 NFC (status LED is the onboard
#             NeoPixel on DevKitM-1, so it lives logically in the mcu sheet)
#   io      — connector cluster along the chord (24V terminal, Qwiic, SWD)
#
# Two distinct UUIDs per sub-sheet:
#   SHEET_BLOCK_UUIDS[name] — UUID of the (sheet ...) block in the root file.
#     This is the identifier KiCad uses in hierarchical paths and the value
#     that goes into oas.kicad_pro's "sheets" array.
#   SHEET_FILE_UUIDS[name] — top-level (uuid) of the sub-sheet file itself.
#     Unrelated to the sheets array.
SUBSHEETS = ("power", "mcu", "sensors", "io")
SHEET_BLOCK_UUIDS = {
    name: str(uuid.uuid5(_OAS_NS, f"sheet-block:{name}")) for name in SUBSHEETS
}
SHEET_FILE_UUIDS = {
    name: str(uuid.uuid5(_OAS_NS, f"sheet-file:{name}")) for name in SUBSHEETS
}
SUBSHEET_DISPLAY_NAMES = {
    "power":   "Power",
    "mcu":     "MCU",
    "sensors": "Sensors",
    "io":      "IO",
}
# 2×2 grid placement of (sheet ...) blocks on the root sheet drawing,
# matching the verified template: Power top-left, MCU top-right,
# Sensors bottom-left, IO bottom-right.
SUBSHEET_POSITIONS = {
    "power":   (50.8,  50.8),
    "mcu":     (101.6, 50.8),
    "sensors": (50.8,  88.9),
    "io":      (101.6, 88.9),
}
SUBSHEET_SIZE = (38.1, 17.78)  # v0.19: bumped 12.7 -> 17.78 mm tall so MCU
                                 # right edge can fit UART_TX/RX + USB_DM/DP/EN/
                                 # BOOT (6 pins on 2.54 mm grid → 15.24 mm) and
                                 # IO left edge can fit I2C_SDA/SCL + USB_DM/DP/
                                 # EN/BOOT.


# Stage-shared mutable state ---------------------------------------------
@dataclass
class Context:
    """In-memory state threaded through boardgen/NN_*.py stages by the
    generate.py orchestrator. Each stage's `run(ctx)` may read and mutate
    these fields; downstream stages see the updated values.

    Fields:
      pcb_text          last-written oas.kicad_pcb body (filled by stage 02,
                        re-read and re-written by stages 12/13)
      pcb_ref_to_fp     map of {schematic Reference -> Footprint property
                        string} built from the freshly-written PCB; used by
                        each per-sheet stage to back-fill Footprint property
                        on its symbols
      lcsc_metadata_map (Value, Footprint) -> {Manufacturer, MPN, LCSC, ...}
                        lookup built from lcsc_mapping.py; injected on every
                        matching schematic symbol
    """
    pcb_text: str = ""
    pcb_ref_to_fp: dict = field(default_factory=dict)
    lcsc_metadata_map: dict = field(default_factory=dict)
