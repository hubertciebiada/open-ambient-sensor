"""boardgen/_footprints_stock.py — KiCad-stock footprint wrappers + infra.

Every `gen_*_pcb_footprint` here is a thin wrapper that delegates to
`_emit_stock_lib_footprint(src_path, lib_nickname, ...)`, which parses
a verbatim `.kicad_mod` file from the user's KiCad installation and
re-emits it at a given (x, y, rotation) on the OAS PCB. Audit-15/16
rule: NO hand-coded pad coordinates anywhere.

Also includes the two PCB-placement reference footprints
(`gen_sen66_reference_pcb_footprint`, `gen_ld2410_reference_pcb_footprint`)
which use the same parse-and-emit mechanism against project-local
`oas:*` library files.

Split from `_footprints.py` at v0.40-post-audit-16 to keep each module
within typical LLM context window.
"""
from __future__ import annotations

import math
import re
import textwrap
from pathlib import Path

from boardgen._common import (  # noqa: F401
    U, fmt, HERE,
    PCB_VERSION, GEN_VERSION,
)
from boardgen._project import (  # noqa: F401
    fx, fy,
    HOLE_DIAMETER, COURTYARD_RADIUS, CUTOUTS,
    SEN66_ANCHOR_X, SEN66_ANCHOR_Y, SEN66_ROTATION,
    SEN66_ZIPTIE_LOCAL, _sen66_local_to_pcb,
    J3_X, J3_Y, J3_ROTATION,
    LD2410_BODY_W, LD2410_BODY_H,
    LD2410_SILK_INSET, LD2410_SILK_INSET_CONN, LD2410_EMIT_SILK_OUTLINE,
    LD2410_ANTENNA_X_END, LD2410_CONNECTOR_X, LD2410_CONNECTOR_Y,
    LD2410_ANCHOR_X, LD2410_ANCHOR_Y, LD2410_ROTATION,
    _ld2410_local_to_pcb,
    J4_PCB_X, J4_PCB_Y, J4_PCB_ROTATION,
    ESP32_BODY_W, ESP32_BODY_L,
    ESP32_PIN_ROW_INSET, ESP32_PIN_PITCH, ESP32_PIN_COUNT_PER_ROW,
    ESP32_PIN_START_OFFSET,
    ESP32_ANCHOR_X, ESP32_ANCHOR_Y, ESP32_ROTATION,
    J1_PCB_X, J1_PCB_Y, J1_PCB_ROTATION,
    J9_PCB_X, J9_PCB_Y, J9_PCB_ROTATION,
    J10_PCB_X, J10_PCB_Y, J10_PCB_ROTATION,
    LED_RING_COUNT, LED_RING_THETA_START_DEG, LED_RING_THETA_STEP_DEG,
    LED_RING_SKIP_INDICES,
    SK6812SIDE_BODY_W, SK6812SIDE_BODY_H,
    SK6812SIDE_PAD_HEIGHT, SK6812SIDE_PAD_Y,
    SK6812SIDE_PAD_X_OFFSETS, SK6812SIDE_PADS,
    FUSE1812L_BODY_W, FUSE1812L_BODY_H,
    FUSE1812L_PAD_W, FUSE1812L_PAD_H, FUSE1812L_PAD_X,
    _led_ring_position, _led_cap_position,
)

# SEN66 body geometry constants are defined in _footprints_custom (where
# the mechanical-reference footprint owns them). `gen_sen66_reference_pcb_footprint`
# (stock) reads from the same library so it needs the same body extents.
from boardgen._footprints_custom import (  # noqa: F401
    SEN66_BODY_X, SEN66_BODY_Y, SEN66_BODY_Z,
    SEN66_INLET1_CX, SEN66_INLET1_CY, SEN66_INLET1_DX, SEN66_INLET1_DY,
    SEN66_INLET2_CX, SEN66_INLET2_CY, SEN66_INLET2_DX, SEN66_INLET2_DY,
    SEN66_OUTLET_CX, SEN66_OUTLET_CY, SEN66_OUTLET_DIA,
    SEN66_CONNECTOR_X, SEN66_CONNECTOR_Y, SEN66_DIVIDER_X,
)


def gen_sen66_reference_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed SEN66_Mechanical_Reference footprint instance.

    This is the embedded copy of `gen_sen66_mechanical_footprint()`'s
    library definition, positioned at PCB-local (x, y) with rotation
    `rotation` degrees. The PCB file format requires a full repetition
    of the footprint body — the library entry alone doesn't render.

    Mechanical-only: no pads, no plated holes. Graphics on F.Fab + F.CrtYd;
    nothing on F.Cu so this footprint contributes zero copper. v0.53
    (issue #2): the module recesses through a real board cutout, so the two
    F.SilkS elements (body outline + "JST GH cable ->" text) that fell inside
    the opening were removed — see gen_sen66_mechanical_footprint() for the
    full rationale. Kept in sync with that library definition.
    """
    x_min, y_min = 0.0, 0.0
    x_max, y_max = SEN66_BODY_X, SEN66_BODY_Y
    uuid_tag = "sen66-pcb"

    # Inlet #1 — obround.
    in1_r = SEN66_INLET1_DY / 2.0
    in1_x1 = SEN66_INLET1_CX - SEN66_INLET1_DX / 2.0 + in1_r
    in1_x2 = SEN66_INLET1_CX + SEN66_INLET1_DX / 2.0 - in1_r
    in1_y = SEN66_INLET1_CY

    # Inlet #2 — rectangle.
    in2_x1 = SEN66_INLET2_CX - SEN66_INLET2_DX / 2.0
    in2_x2 = SEN66_INLET2_CX + SEN66_INLET2_DX / 2.0
    in2_y1 = SEN66_INLET2_CY - SEN66_INLET2_DY / 2.0
    in2_y2 = SEN66_INLET2_CY + SEN66_INLET2_DY / 2.0

    out_r = SEN66_OUTLET_DIA / 2.0

    return textwrap.dedent(f"""\
        \t(footprint "oas:SEN66_Mechanical_Reference"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "Sensirion SEN66 mechanical-reference (no pads). SEN66-SIN-T, MPN 3.001.030. 55.2x25.6x21.3 mm. PCB-mounted face-up (v0.6); openings face UP through AK-N-94 perforated cover. JST GH 6-pin connector on body +X short edge wires to J3 (~60 mm cable).")
        \t\t(attr board_only exclude_from_pos_files exclude_from_bom)
        \t\t(property "Reference" "SENS1"
        \t\t\t(at {fmt(SEN66_BODY_X / 2.0)} -1.5 0)
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "SEN66_Mechanical_Reference"
        \t\t\t(at {fmt(SEN66_BODY_X / 2.0)} {fmt(SEN66_BODY_Y + 1.5)} 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "oas:SEN66_Mechanical_Reference"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "https://sensirion.com/resource/datasheet/SEN6x"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "Sensirion SEN66 mechanical-reference footprint (no pads). SEN66-SIN-T, material 3.001.030. Body 55.2x25.6x21.3 mm. PCB-mounted face-up (v0.6); openings face UP through AK-N-94 perforated cover."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-outline:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(in1_x1)} {fmt(in1_y - in1_r)})
        \t\t\t(end {fmt(in1_x2)} {fmt(in1_y - in1_r)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-inlet1-top:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(in1_x1)} {fmt(in1_y + in1_r)})
        \t\t\t(end {fmt(in1_x2)} {fmt(in1_y + in1_r)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-inlet1-bot:' + uuid_tag)}")
        \t\t)
        \t\t(fp_arc
        \t\t\t(start {fmt(in1_x1)} {fmt(in1_y - in1_r)})
        \t\t\t(mid {fmt(in1_x1 - in1_r)} {fmt(in1_y)})
        \t\t\t(end {fmt(in1_x1)} {fmt(in1_y + in1_r)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-inlet1-arcl:' + uuid_tag)}")
        \t\t)
        \t\t(fp_arc
        \t\t\t(start {fmt(in1_x2)} {fmt(in1_y + in1_r)})
        \t\t\t(mid {fmt(in1_x2 + in1_r)} {fmt(in1_y)})
        \t\t\t(end {fmt(in1_x2)} {fmt(in1_y - in1_r)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-inlet1-arcr:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(in2_x1)} {fmt(in2_y1)})
        \t\t\t(end {fmt(in2_x2)} {fmt(in2_y2)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-inlet2:' + uuid_tag)}")
        \t\t)
        \t\t(fp_circle
        \t\t\t(center {fmt(SEN66_OUTLET_CX)} {fmt(SEN66_OUTLET_CY)})
        \t\t\t(end {fmt(SEN66_OUTLET_CX + out_r)} {fmt(SEN66_OUTLET_CY)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-outlet:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(SEN66_DIVIDER_X)} {fmt(y_min + 1.0)})
        \t\t\t(end {fmt(SEN66_DIVIDER_X)} {fmt(y_max - 1.0)})
        \t\t\t(stroke (width 0.08) (type dash))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-divider:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(SEN66_CONNECTOR_X - 2.0)} {fmt(SEN66_CONNECTOR_Y - 2.4)})
        \t\t\t(end {fmt(SEN66_CONNECTOR_X + 1.0)} {fmt(SEN66_CONNECTOR_Y + 2.4)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-conn-marker:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(-0.25)} {fmt(-0.25)})
        \t\t\t(end {fmt(SEN66_BODY_X + 0.25)} {fmt(SEN66_BODY_Y + 0.25)})
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-courtyard:' + uuid_tag)}")
        \t\t)
        \t)""")
        # v0.22: F.CrtYd RESTORED as a programmatic guardrail. SEN66 lies
        # FLAT on PCB on its 25.6 x 55.2 mm back face — ZERO clearance
        # under it (the 21.5 mm is body height ABOVE PCB, not standoff).
        # NO SMD components may be placed inside; the courtyard
        # intentionally encloses the body shadow so DRC catches mistakes.


def _kicad_install_path() -> Path:
    """Locate the KiCad 10 installation root.

    Used to load stock footprint definitions (e.g. JST_GH_SM06B-GHS-TB)
    so the embedded PCB copy matches the library byte-for-byte and
    DRC's lib_footprint_mismatch check stays silent. Walks the common
    Windows install paths; falls back to scanning `kicad-cli` on PATH
    if neither default exists.
    """
    candidates = [
        Path(r"C:/Program Files/KiCad/10.0/share/kicad"),
        Path(r"C:/Program Files/KiCad/9.0/share/kicad"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "Could not find KiCad install directory. Tried: "
        + ", ".join(str(c) for c in candidates)
    )


_J3_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Connector_JST.pretty"
    / "JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal.kicad_mod"
)

_J4_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Connector_PinHeader_1.27mm.pretty"
    / "PinHeader_1x05_P1.27mm_Vertical.kicad_mod"
)

# v0.17: J1 — 24 V Phoenix MSTBA 5.08 mm pitch 3-pin pluggable terminal
# block (base PCB-side header). Matches the schematic part library symbol
# `Connector:Screw_Terminal_01x03` placed in `power.kicad_sch` with the
# value `Phoenix_MSTBA_2,5/3-G-5,08`.
_J1_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Connector_Phoenix_MSTB.pretty"
    / "PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal.kicad_mod"
)

# v0.19: J9 — Qwiic / Stemma QT JST SH 4-pin horizontal SMD socket.
# Standard part: JST SM04B-SRSS-TB (or compatible — every Qwiic /
# Stemma QT host uses this footprint).
_J9_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Connector_JST.pretty"
    / "JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal.kicad_mod"
)

# v0.19: J10 — native-USB recovery header. 6-pin 2.54 mm vertical
# through-hole pin header. DNP — pads only on production boards.
_J10_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Connector_PinHeader_2.54mm.pretty"
    / "PinHeader_1x06_P2.54mm_Vertical.kicad_mod"
)

# v0.40 post-order systemic fix: replace inline `_emit_two_pad_smd_footprint`
# hand-coded SMD geometry with verbatim KiCad stock library parsing for
# every two-pad SMD passive on the OAS PCB. Same parse-and-patch pattern
# as J3/J4/J1/J9/J10. Stock files all live under
# `${KICAD_INSTALL}/share/kicad/footprints/<lib>.pretty/<name>.kicad_mod`.
# All SMD passives have their pads centered at footprint-local origin so
# no XY translation is needed at the call site.
_C0402_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Capacitor_SMD.pretty"
    / "C_0402_1005Metric.kicad_mod"
)
_C0603_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Capacitor_SMD.pretty"
    / "C_0603_1608Metric.kicad_mod"
)
_C0805_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Capacitor_SMD.pretty"
    / "C_0805_2012Metric.kicad_mod"
)
_R0603_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Resistor_SMD.pretty"
    / "R_0603_1608Metric.kicad_mod"
)
_D_SMA_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Diode_SMD.pretty"
    / "D_SMA.kicad_mod"
)
_D_SMB_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Diode_SMD.pretty"
    / "D_SMB.kicad_mod"
)
_D_SOD323_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Diode_SMD.pretty"
    / "D_SOD-323.kicad_mod"
)
# v0.40 post-order: L1 + L2 use CENKER CKCS5040 series (LCSC C354612 /
# C354602 per lcsc-mapping.csv); pin out the matching stock library
# `L_Cenker_CKCS5040.kicad_mod` (pitch 3.30 mm, pads 2.2 × 4.2 mm),
# NOT the previously-mislabeled `L_APV_ANR5040` (pitch 3.7 mm).
_L_CENKER_CKCS5040_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Inductor_SMD.pretty"
    / "L_Cenker_CKCS5040.kicad_mod"
)
# v0.42 (2026-05-20): the KiCad stock `Fuse_*_*Metric` footprint paths
# were removed. F1 (the only fuse on the board) now uses the project-local
# `oas:Fuse_1812L_4532Metric` land — KiCad's generic IPC chip-fuse land
# mismatched the Littelfuse 1812L termination geometry. See
# `gen_fuse_1812l_pcb_footprint` and CLAUDE.md Deviation budget.
# v0.40 post-order: SOT-23 for Q1 P-MOSFET. Stock layout has pads in an
# "E" pattern (pads 1, 2 on -X column at Y=±0.95; pad 3 on +X at Y=0),
# size 1.475 × 0.6 mm. The previous custom geometry rotated the pattern
# 90° to "⊥" (pads 1, 2 on -Y row; pad 3 on +Y) with smaller 1.0 × 0.6 mm
# pads — that would have caused JLCPCB to place the AO3401A 90° rotated
# relative to the canonical SOT-23 orientation declared in the Footprint
# property, swapping G / S / D net connections.
_SOT23_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Package_TO_SOT_SMD.pretty"
    / "SOT-23.kicad_mod"
)
# U1 LM2596S-5.0 TO-263-5 package.
#  - `_TO263_5_LIB_FOOTPRINT_PATH`: KiCad stock TO-263-5_TabPin3 — used
#    ONLY as the silk / courtyard / F.Fab / 3D-model donor for the
#    project-local land below (see gen_to263_5_lm2596_footprint).
#  - `_TO263_5_LM2596_LIB_FOOTPRINT_PATH`: the project-local
#    oas:TO-263-5_LM2596 land emitted by boardgen stage 01. The stock
#    TO-263-5_TabPin3 land is GENERIC IPC and mismatched the exact
#    ordered part (LM2596S-5.0/NOPB, LCSC C116713): 9.15 mm lead-tab
#    pitch vs the part's 10.252 mm → U1's thermal tab only ~25 %
#    overlapped on JLCPCB DFM. v0.43 replaces it with the verbatim
#    C116713 land (CLAUDE.md Deviation budget; same precedent as F1).
_TO263_5_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Package_TO_SOT_SMD.pretty"
    / "TO-263-5_TabPin3.kicad_mod"
)
_TO263_5_LM2596_LIB_FOOTPRINT_PATH = (
    HERE / "libraries" / "oas.pretty" / "TO-263-5_LM2596.kicad_mod"
)
# v0.40 audit-16: U2 TPS62933 SOT-583-8 package. Previous generator
# emitted custom header "SOT-583_TPS62933" — non-canonical. Replace with
# verbatim stock parsing of Package_TO_SOT_SMD:SOT-583-8.
_SOT583_8_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Package_TO_SOT_SMD.pretty"
    / "SOT-583-8.kicad_mod"
)
# v0.40 audit-16: 1×6 P2.54 mm THT pin header (J2 — UART/Boot recovery).
# Same stock-library entry as J10 (_J10_LIB_FOOTPRINT_PATH) but emitted
# via a different generator. Consolidating to verbatim stock parsing.
_J2_LIB_FOOTPRINT_PATH = _J10_LIB_FOOTPRINT_PATH
# v0.40 post-order: radial THT bulk caps. Origin in stock = pin 1 (NOT
# body center). XY placement in boardgen call sites uses the body
# center convention, so callers must subtract pitch/2 from x when
# rotation=0 to keep the body center at the requested coordinate. See
# gen_capacitor_polarized_radial_pcb_footprint for the wrapper that does
# this translation.
_CP_RADIAL_D8_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Capacitor_THT.pretty"
    / "CP_Radial_D8.0mm_P3.50mm.kicad_mod"
)
_CP_RADIAL_D6_3_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Capacitor_THT.pretty"
    / "CP_Radial_D6.3mm_P2.50mm.kicad_mod"
)


def _pinsocket_lib_footprint_path(pin_count: int):
    return (
        _kicad_install_path() / "footprints" / "Connector_PinSocket_2.54mm.pretty"
        / f"PinSocket_1x{pin_count:02d}_P2.54mm_Vertical.kicad_mod"
    )


def _read_kicad_lib_symbol(lib_filename: str, sym_name: str, lib_nickname: str) -> str:
    """Extract a single `(symbol "X" ...)` block from a KiCad stock symbol
    library file, prefix the symbol name with `lib_nickname:` (so it matches
    KiCad's `LibName:SymName` lookup convention inside embedded schematic
    lib_symbols), and re-indent to 2 tabs deep so it slots straight into our
    sub-sheet `(lib_symbols ...)` block.

    The stock libraries indent symbol blocks 1 tab deep (one level inside
    `(kicad_symbol_lib ...)`); our embedded copies live inside
    `(kicad_sch ... (lib_symbols ...))` which puts them 2 tabs deep.
    """
    src = (_kicad_install_path() / "symbols" / lib_filename).read_text(encoding="utf-8")
    needle = f'(symbol "{sym_name}"'
    start = src.find(needle)
    if start < 0:
        raise RuntimeError(f"symbol {sym_name!r} not found in {lib_filename}")
    depth = 0
    end = start
    for i in range(start, len(src)):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    block = src[start:end]
    # Prefix the symbol name with the library nickname so KiCad resolves it
    # as e.g. `Connector_Generic:Conn_01x05`.
    block = block.replace(needle, f'(symbol "{lib_nickname}:{sym_name}"', 1)
    # Re-indent: stock-library symbols are indented 1 tab; we want 2 tabs.
    return "\n".join("\t" + line for line in block.split("\n"))


def _annotate_pad_rotations(body_text: str, rotation: float) -> str:
    """Inject the footprint rotation into every `(pad ...)` block's `(at)`.

    KiCad pcbnew, when saving a rotated footprint, writes each pad with
    an explicit rotation in its `(at lx ly <rotation>)` clause (e.g.
    `(at -1.5 1.325 90)`). When the rotation is OMITTED (just `(at lx ly)`),
    KiCad's DRC interprets the pad's geometry as PCB-axis-aligned rather
    than rotated with the footprint — producing spurious pad-clearance
    and solder-mask-bridge violations.

    Walk through the supplied body_text (the footprint's child blocks
    concatenated as a string), find every `(pad "..." ... (at lx ly))`,
    and rewrite the `(at lx ly)` to `(at lx ly <rotation>)`. Pads that
    already have an explicit rotation in their `(at ...)` are left
    untouched (defensive, although the KiCad library SM06B-GHS-TB has
    none).
    """
    import re

    # Match: `(at <num> <num>)` where the closing paren immediately follows
    # the second numeric token. Captures the two numbers as g1, g2.
    pat = re.compile(
        r"\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)",
    )

    # Split body into pad blocks vs other blocks; only annotate inside pads.
    out: list[str] = []
    depth = 0
    cur: list[str] = []
    blocks: list[tuple[bool, str]] = []   # (is_pad, text)
    is_pad = False
    for ch in body_text:
        cur.append(ch)
        if ch == "(":
            if depth == 0:
                # Beginning of a top-level S-expression. Inspect first
                # 8 chars to see if it's a (pad ...) clause.
                pass
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                block = "".join(cur)
                # Check if the block starts (modulo leading whitespace
                # and tabs from reindent) with "(pad ".
                stripped = block.lstrip()
                blocks.append((stripped.startswith("(pad "), block))
                cur = []

    # If there are trailing characters (whitespace) outside any block,
    # `cur` is non-empty; append it as a non-pad chunk.
    if cur:
        blocks.append((False, "".join(cur)))

    parts = []
    for is_pad_block, block in blocks:
        if is_pad_block:
            block = pat.sub(rf"(at \1 \2 {rotation})", block, count=1)
        parts.append(block)
    return "".join(parts)


def gen_j3_jst_gh_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed J3 — JST_GH_SM06B-GHS-TB horizontal SMD socket.

    Reads the KiCad 10 stock library footprint
    `Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal`
    from the system KiCad install, then patches:
      - Top-level `(footprint "...")` → prefix with library nickname
        `Connector_JST:` so DRC matches it against the stock library
      - `(version ...)` and `(generator ...)` → drop (KiCad pcbnew
        ignores them inside embedded footprints; their presence flags
        lib_footprint_mismatch)
      - Insert `(uuid ...)` and `(at <fx(x)> <fy(y)> <rotation>)` for
        positioning
      - Add OAS-side `(property "Reference" "J3" ...)` /
        `(property "Value" "..." ...)` etc. replacing the library's
        Reference="REF**" and Value="JST_GH_SM06B-GHS-TB_…" defaults
      - Replace inline `${REFERENCE}` reference token with literal "J3"
      - Replace inline KiCad layer prefixes (already 7-bit ASCII, just
        passed through)
      - Keep the 3D model block (audit-19, 2026-05-19): path uses
        ${KICAD10_3DMODEL_DIR} which KiCad 10 resolves at render time.
        The local 3D render in stage 13 picks up the JST_GH SMD socket
        body mesh from the stock library.
    """
    src = _J3_LIB_FOOTPRINT_PATH.read_text(encoding="utf-8")
    uuid_tag = "j3-jst-gh"

    # Drop the top-level header line + version/generator/etc — we re-emit
    # them with our own UUID and (at ...).
    lines = src.split("\n")
    # First line: (footprint "JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal"
    assert lines[0].startswith("(footprint "), f"unexpected first line: {lines[0]!r}"
    # Skip header + (version ...) + (generator ...) + (layer ...) + (descr ...) + (tags ...).
    # The library file has the structure: (footprint "..." (version ...) (generator ...) (layer "F.Cu") (descr "...") (tags "...") (property "Reference" "REF**" ...) (property "Value" "..." ...) (property "KiLib_Generator" ...) (attr smd) (duplicate_pad_numbers_are_jumpers no) ...).
    # We want to keep everything from `(attr smd)` onward, but DROP the
    # (property "Reference" ...), (property "Value" ...) and
    # (property "KiLib_Generator" ...) so we can re-emit them with OAS
    # values. Also drop the final `(embedded_fonts no)` block at the
    # bottom; we replace with our own. (model ...) is KEPT.

    # The easiest parse: split on top-level S-expression bounds. KiCad
    # footprint files are well-formatted; each (key ...) at the indent
    # level "\t(" is a top-level child. We walk the file and split.
    depth = 0
    current: list[str] = []
    items: list[str] = []
    for ch in src:
        if ch == "(":
            if depth == 0:
                current = []  # outermost paren — start fresh
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
            if depth == 0:
                items.append("".join(current))
                current = []
        else:
            if depth > 0:
                current.append(ch)
    # `items` now has exactly one element — the top-level (footprint ...).
    assert len(items) == 1, f"expected 1 top-level item, got {len(items)}"
    top = items[0]

    # Now extract the children of the (footprint ...) block. Strip the
    # outermost paren wrapper, then iterate through the inner content.
    inner = top.strip()
    assert inner.startswith("(footprint") and inner.endswith(")")
    # Remove "(footprint " prefix and trailing ")".
    inner = inner[len("(footprint"):].rstrip()
    inner = inner.rstrip(")").rstrip()
    # The next token is the footprint name (quoted string).
    inner = inner.lstrip()
    assert inner.startswith('"')
    name_end = inner.index('"', 1)
    fp_name = inner[1:name_end]
    inner_after_name = inner[name_end + 1:]

    # Walk children inside `inner_after_name`. Each child is either a
    # (key ...) S-expression or whitespace.
    children: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in inner_after_name:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                children.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)

    # Filter out the items we want to REPLACE (version, generator,
    # property Reference, property Value, property KiLib_Generator,
    # embedded_fonts). (model ...) is KEPT — audit-19 (2026-05-19) —
    # so the local 3D render shows the JST_GH SMD socket body. Paths
    # use ${KICAD10_3DMODEL_DIR} which KiCad 10 resolves at render time.
    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
    )
    body_children = []
    for child in children:
        if any(child.startswith(p) for p in SKIP_PREFIXES):
            continue
        body_children.append(child)

    # Re-indent each child to be nested inside our placed (footprint).
    # The library content uses single-tab indent for first-level
    # children; once embedded in the PCB it needs two-tab indent.
    def reindent_for_pcb(s: str) -> str:
        out_lines = []
        for ln in s.split("\n"):
            if ln == "":
                out_lines.append(ln)
            else:
                out_lines.append("\t" + ln)
        return "\n".join(out_lines)

    body_text = "\n".join(reindent_for_pcb(c) for c in body_children)

    # Replace the inline ${REFERENCE} token inside fp_text user blocks
    # with the literal "J3" so the F.Fab REFERENCE text renders cleanly.
    body_text = body_text.replace('"${REFERENCE}"', '"J3"')

    # KiCad quirk: when a footprint is placed with non-zero rotation,
    # each pad's `(at lx ly)` must carry the rotation explicitly
    # (`(at lx ly <rotation>)`), or DRC interprets the pad's shape as
    # ABSOLUTE (PCB-aligned) instead of rotating with the footprint —
    # leading to false-positive pad-pad clearance and solder-mask-bridge
    # errors. Demo PCBs in the KiCad install (e.g.
    # demos/cm5_minima/CM5_MINIMA_3.kicad_pcb) show pcbnew itself
    # writes pad rotation explicitly on save. Replicate that here:
    # walk through `body_text` and, for each `(pad ...) ... (at lx ly)`
    # without a third token, inject the footprint rotation.
    if rotation != 0:
        body_text = _annotate_pad_rotations(body_text, rotation)

    # New (property ...) entries for Reference, Value, Footprint, etc.,
    # to be placed immediately after the (tags ...) header.
    properties = textwrap.dedent(f"""\
        \t\t(property "Reference" "J3"
        \t\t\t(at 0 -3.9 {rotation})
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "JST SM06B-GHS-TB (SEN66 connector)"
        \t\t\t(at 0 3.9 {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "http://www.jst-mfg.com/product/pdf/eng/eGH.pdf"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "JST GH 6-pin SMD horizontal socket SM06B-GHS-TB. Mates with SEN66 JST GH cable. Sourceable: TME / Mouser / Botland."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)""")

    return textwrap.dedent(f"""\
        \t(footprint "Connector_JST:{fp_name}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        """) + properties + "\n" + body_text + "\n\t)"


def gen_ld2410_reference_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed LD2410_Mechanical_Reference footprint instance.

    Mirrors `gen_sen66_reference_pcb_footprint`: this is the embedded
    full-body copy that pcbnew needs alongside the library definition,
    positioned at PCB-local (x, y) with `rotation` degrees. No pads —
    purely F.Fab + F.SilkS + F.CrtYd graphics marking the LD2410
    daughterboard's projected shadow on the OAS PCB as a keep-out zone.

    Mechanical-only: no pads, no plated holes. The 5 electrical
    connections live in J4 (stock PinHeader_1x05_P1.27mm_Vertical
    footprint placed separately).
    """
    x_min, y_min = 0.0, 0.0
    x_max, y_max = LD2410_BODY_W, LD2410_BODY_H
    inset = LD2410_SILK_INSET
    uuid_tag = "ld2410-pcb"

    conn_x = LD2410_CONNECTOR_X
    conn_y_top = LD2410_CONNECTOR_Y - 2.54
    conn_y_bot = LD2410_CONNECTOR_Y + 2.54

    # v0.15.9: U-shaped silk silhouette (3 fp_line). See library footprint
    # function gen_ld2410_mechanical_footprint() for the geometry rationale
    # — connector-side short edge is omitted so the U opens onto J4's stock
    # silk frame; both long edges stop short of the J4 silk-frame Y zone
    # via LD2410_SILK_INSET_CONN = 1.8.
    x_silk_end = x_max - LD2410_SILK_INSET_CONN
    y_silk_top = y_min + inset
    y_silk_bot = y_max - inset
    silk_outline = "" if not LD2410_EMIT_SILK_OUTLINE else textwrap.dedent(f"""\
        \t\t(fp_line
        \t\t\t(start {fmt(x_min + inset)} {fmt(y_silk_top)})
        \t\t\t(end {fmt(x_min + inset)} {fmt(y_silk_bot)})
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk-antenna-edge:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(x_min + inset)} {fmt(y_silk_top)})
        \t\t\t(end {fmt(x_silk_end)} {fmt(y_silk_top)})
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk-long-edge-1:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(x_min + inset)} {fmt(y_silk_bot)})
        \t\t\t(end {fmt(x_silk_end)} {fmt(y_silk_bot)})
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk-long-edge-2:' + uuid_tag)}")
        \t\t)""")

    return textwrap.dedent(f"""\
        \t(footprint "oas:LD2410_Mechanical_Reference"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "HiLink HLK-LD2410B mechanical-reference (no pads). 24 GHz mmWave presence radar daughterboard. Body ~35x7x7 mm above OAS PCB on 1.27 mm pin header (J4). Antenna patches on the LD2410 top face point through the enclosure cover.")
        \t\t(attr board_only exclude_from_pos_files exclude_from_bom)
        \t\t(property "Reference" "LDR1"
        \t\t\t(at {fmt(LD2410_BODY_W / 2.0)} -1.5 0)
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "LD2410_Mechanical_Reference"
        \t\t\t(at {fmt(LD2410_BODY_W / 2.0)} {fmt(LD2410_BODY_H + 1.5)} 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "oas:LD2410_Mechanical_Reference"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "https://www.hlktech.net/index.php?id=988"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "HiLink HLK-LD2410B 24 GHz mmWave presence radar daughterboard mechanical-reference. Body ~35x7x7 mm. Mounts via 5-pin 1.27 mm pin header (J4) above the OAS PCB; antenna patches on the LD2410 top face point toward the AK-N-94 cover."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-outline:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(x_min + 1.0)} {fmt(y_min + 1.0)})
        \t\t\t(end {fmt(LD2410_ANTENNA_X_END)} {fmt(y_max - 1.0)})
        \t\t\t(stroke (width 0.1) (type dash))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-antenna:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(conn_x - 1.5)} {fmt(conn_y_top - 0.7)})
        \t\t\t(end {fmt(conn_x)} {fmt(conn_y_bot + 0.7)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-conn-marker:' + uuid_tag)}")
        \t\t)
        """) + silk_outline + "\n\t)"


def gen_j4_pinheader_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed J4 — stock 5-pin 1.27 mm vertical THROUGH-HOLE pin
    header where the HLK-LD2410B daughterboard's pins are soldered in.

    Loads the KiCad 10 stock footprint
    `Connector_PinHeader_1.27mm:PinHeader_1x05_P1.27mm_Vertical` and
    patches it the same way as `gen_j3_jst_gh_pcb_footprint` does for
    the SEN66 socket: drop version/generator/embedded_fonts/model;
    rewrite the OAS-side Reference / Value / Footprint / Datasheet /
    Description properties; inject (uuid) + (at x y rotation); and (if
    rotation != 0) annotate each pad's rotation in (at lx ly <rotation>)
    to silence the pcbnew lib_footprint_mismatch / pad-clearance edge
    cases.
    """
    src = _J4_LIB_FOOTPRINT_PATH.read_text(encoding="utf-8")
    uuid_tag = "j4-pinheader"

    lines = src.split("\n")
    assert lines[0].startswith("(footprint "), f"unexpected first line: {lines[0]!r}"

    # Same S-expression parse as the J3 helper.
    depth = 0
    cur: list[str] = []
    items: list[str] = []
    for ch in src:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                items.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)
    assert len(items) == 1
    top = items[0]
    inner = top.strip()
    assert inner.startswith("(footprint") and inner.endswith(")")
    inner = inner[len("(footprint"):].rstrip()
    inner = inner.rstrip(")").rstrip().lstrip()
    assert inner.startswith('"')
    name_end = inner.index('"', 1)
    fp_name = inner[1:name_end]
    inner_after_name = inner[name_end + 1:]

    children: list[str] = []
    depth = 0
    cur = []
    for ch in inner_after_name:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                children.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)

    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
        # (model ...) kept — audit-19 (2026-05-19): local 3D render
        # picks up stock library chip body meshes via KiCad's
        # ${KICAD10_3DMODEL_DIR} env var resolution at render time.
    )
    body_children = []
    for child in children:
        if any(child.startswith(p) for p in SKIP_PREFIXES):
            continue
        body_children.append(child)

    def reindent_for_pcb(s: str) -> str:
        out_lines = []
        for ln in s.split("\n"):
            if ln == "":
                out_lines.append(ln)
            else:
                out_lines.append("\t" + ln)
        return "\n".join(out_lines)

    body_text = "\n".join(reindent_for_pcb(c) for c in body_children)

    # Replace the inline ${REFERENCE} token inside fp_text user blocks
    # with the literal "J4".
    body_text = body_text.replace('"${REFERENCE}"', '"J4"')

    if rotation != 0:
        body_text = _annotate_pad_rotations(body_text, rotation)

    properties = textwrap.dedent(f"""\
        \t\t(property "Reference" "J4"
        \t\t\t(at 0 -1.9 {rotation})
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "1x5 P1.27mm header (HLK-LD2410B)"
        \t\t\t(at 0 6.98 {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "Connector_PinHeader_1.27mm:PinHeader_1x05_P1.27mm_Vertical"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "Generic 5-pin 1.27 mm pitch vertical through-hole pin header. Carries the HLK-LD2410B daughterboard's pin row: VCC/GND/TX/RX/OUT. The LD2410 body sits ~5-7 mm above the OAS PCB on these pins; the solder joints provide both electrical and mechanical retention."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)""")

    return textwrap.dedent(f"""\
        \t(footprint "Connector_PinHeader_1.27mm:{fp_name}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        """) + properties + "\n" + body_text + "\n\t)"


def gen_j1_terminal_block_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed J1 — 24 V Phoenix MSTBA 5.08 mm pitch 3-pin pluggable
    terminal block (PCB-side header / "base") at PCB (x, y) with `rotation`
    degrees.

    Reads the KiCad 10 stock library footprint
    `Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal`
    from the system KiCad install, then mirrors the same patching logic as
    `gen_j3_jst_gh_pcb_footprint` / `gen_j4_pinheader_pcb_footprint`:
      - prefix the footprint name with library nickname so DRC matches it
      - drop (version), (generator), library Reference/Value/KiLib_Generator
        properties, embedded_fonts, model
      - inject our own (uuid) + (at x y rotation) + OAS-side
        Reference="J1" / Value / Footprint / Datasheet / Description
      - replace inline ${REFERENCE} → "J1"
      - if rotation != 0, annotate each pad's (at lx ly) with the rotation
        so DRC rotates pad geometry with the footprint
    """
    src = _J1_LIB_FOOTPRINT_PATH.read_text(encoding="utf-8")
    uuid_tag = "j1-terminal-block"

    # Parse top-level (footprint ...) S-expression and split into children
    # (same parser as gen_j3 / gen_j4).
    lines = src.split("\n")
    assert lines[0].startswith("(footprint "), f"unexpected first line: {lines[0]!r}"

    depth = 0
    cur: list[str] = []
    items: list[str] = []
    for ch in src:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                items.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)
    assert len(items) == 1
    top = items[0]
    inner = top.strip()
    assert inner.startswith("(footprint") and inner.endswith(")")
    inner = inner[len("(footprint"):].rstrip()
    inner = inner.rstrip(")").rstrip().lstrip()
    assert inner.startswith('"')
    name_end = inner.index('"', 1)
    fp_name = inner[1:name_end]
    inner_after_name = inner[name_end + 1:]

    children: list[str] = []
    depth = 0
    cur = []
    for ch in inner_after_name:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                children.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)

    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
        # (model ...) kept — audit-19 (2026-05-19): local 3D render
        # picks up stock library chip body meshes via KiCad's
        # ${KICAD10_3DMODEL_DIR} env var resolution at render time.
    )
    body_children = []
    for child in children:
        if any(child.startswith(p) for p in SKIP_PREFIXES):
            continue
        body_children.append(child)

    def reindent_for_pcb(s: str) -> str:
        out_lines = []
        for ln in s.split("\n"):
            if ln == "":
                out_lines.append(ln)
            else:
                out_lines.append("\t" + ln)
        return "\n".join(out_lines)

    body_text = "\n".join(reindent_for_pcb(c) for c in body_children)

    # Replace the inline ${REFERENCE} token inside fp_text user blocks
    # with the literal "J1".
    body_text = body_text.replace('"${REFERENCE}"', '"J1"')

    if rotation != 0:
        body_text = _annotate_pad_rotations(body_text, rotation)

    properties = textwrap.dedent(f"""\
        \t\t(property "Reference" "J1"
        \t\t\t(at 5.08 -3.2 {rotation})
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "Phoenix_MSTBA_2,5/3-G-5,08 (24V input)"
        \t\t\t(at 5.08 11.2 {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "https://www.phoenixcontact.com/online/portal/us?uri=pxc-oc-itemdetail:pid=1757255"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "Phoenix Contact MSTBA 2,5/3-G-5,08 — 3-pin 5.08 mm pitch pluggable terminal block base (PCB-side header). 24 V supply input: pin 1 = +24V_unprotected, pin 2 = GND, pin 3 = PE. Mates with a Phoenix COMBICON 5.08 mm 3-pin plug; the user-removable plug accepts solid or stranded 0.2-2.5 mm² conductors. Order code 1757255 (12 A) or 1923872 (16 A HC)."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)""")

    return textwrap.dedent(f"""\
        \t(footprint "Connector_Phoenix_MSTB:{fp_name}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        """) + properties + "\n" + body_text + "\n\t)"


def _emit_stock_lib_footprint(
    *,
    src_path,
    lib_nickname: str,
    reference: str,
    value: str,
    datasheet: str,
    description: str,
    x: float, y: float, rotation: float,
    uuid_tag: str,
    ref_offset_x: float = 0.0,
    ref_offset_y: float = -2.0,
    val_offset_x: float = 0.0,
    val_offset_y: float = 3.0,
    hide_ref: bool = False,
    hide_value: bool = True,
    dnp: bool = False,
    pin_name_map: dict[str, str] | None = None,
    polarity_mark: str = "none",
    polarity_uuid_tag: str | None = None,
    model_override: str | None = None,
) -> str:
    """Generic helper to embed a KiCad stock-library footprint into the PCB.

    Mirrors the parse-and-patch logic from `gen_j3_jst_gh_pcb_footprint`
    / `gen_j4_pinheader_pcb_footprint` / `gen_j1_terminal_block_pcb_footprint`,
    factored into one place so adding new connectors only requires:
      1. an `_X_LIB_FOOTPRINT_PATH` Path constant pointing at the stock
         library file
      2. one call to this helper with the desired Reference / Value /
         Datasheet / Description and the placement (x, y, rotation)

    Logic:
      - Read the stock .kicad_mod
      - Parse the top-level `(footprint "<name>" ...)` S-expression
      - Drop `(version)`, `(generator)`, `(generator_version)`, library
        `(property "Reference" ...)`, `(property "Value" ...)`,
        `(property "KiLib_Generator" ...)`, and `(embedded_fonts ...)`
        children. `(model ...)` blocks are KEPT so the local 3D render
        (stage 13) shows actual component bodies (chip / IC / connector
        meshes) rather than just pads. KiCad 10 resolves the
        `${KICAD10_3DMODEL_DIR}` env-var paths at render time.
      - Re-indent all remaining children one level deeper for nesting
        in the PCB file
      - Substitute the inline `${REFERENCE}` token with the literal
        Reference designator
      - If `rotation != 0`, annotate every pad's `(at lx ly)` with the
        rotation (KiCad quirk — without this, DRC misreads pad shapes
        as PCB-axis-aligned, causing false-positive pad clearance / mask
        bridge errors)
      - Prepend our own (uuid), (at), and OAS-side Reference / Value /
        Footprint / Datasheet / Description properties

    `ref_offset_x / y` and `val_offset_x / y` position the new Reference
    (on F.SilkS) and Value (on F.Fab) text relative to the footprint
    anchor, in footprint-local mm.
    """
    src = src_path.read_text(encoding="utf-8")

    # Parse the top-level (footprint ...) wrapper.
    depth = 0
    cur: list[str] = []
    items: list[str] = []
    for ch in src:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                items.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)
    assert len(items) == 1
    inner = items[0].strip()
    assert inner.startswith("(footprint") and inner.endswith(")")
    inner = inner[len("(footprint"):].rstrip()
    inner = inner.rstrip(")").rstrip().lstrip()
    assert inner.startswith('"')
    name_end = inner.index('"', 1)
    fp_name = inner[1:name_end]
    inner_after_name = inner[name_end + 1:]

    children: list[str] = []
    depth = 0
    cur = []
    for ch in inner_after_name:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                children.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)

    # (model ...) blocks are INTENTIONALLY KEPT (audit-19, 2026-05-19)
    # so kicad-cli pcb render in stage 13 picks up the chip / IC /
    # connector 3D meshes from the stock library. Paths use
    # ${KICAD10_3DMODEL_DIR} which the KiCad installer sets at
    # runtime — fully deterministic + portable across machines with
    # KiCad 10 installed.
    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
    )
    body_children = [c for c in children if not any(c.startswith(p) for p in SKIP_PREFIXES)]

    def reindent_for_pcb(s: str) -> str:
        out_lines = []
        for ln in s.split("\n"):
            if ln == "":
                out_lines.append(ln)
            else:
                out_lines.append("\t" + ln)
        return "\n".join(out_lines)

    body_text = "\n".join(reindent_for_pcb(c) for c in body_children)
    body_text = body_text.replace('"${REFERENCE}"', f'"{reference}"')

    # v0.23 fix for review Mn4: when the matching schematic symbol carries
    # `(dnp yes)`, mirror it on the PCB-side `(attr ...)` clause so the
    # position file + BOM export honor DNP. Stock-library `_emit_stock_lib_*`
    # footprints inherit `(attr through_hole)` or `(attr smd)` from the
    # source .kicad_mod; append the JLCPCB-recognised flags here.
    if dnp:
        import re as _re
        body_text = _re.sub(
            r"\(attr\s+([^)]+?)\)",
            lambda m: f"(attr {m.group(1).strip()} exclude_from_pos_files exclude_from_bom dnp)",
            body_text,
            count=1,
        )

    # v0.40 post-order: when the matching schematic symbol uses letter pin
    # numbers (e.g. Device:Q_PMOS where pin numbers are "G", "S", "D"),
    # remap the stock numeric pad names ("1", "2", "3" in the SOT-23
    # stock footprint) to the corresponding letter names so
    # `sync_pcb_nets_from_schematic` can match the netlist nodes (Q1.G /
    # Q1.S / Q1.D) to the PCB pads. The geometry stays VERBATIM stock —
    # only the pad NAME (which is internal connectivity metadata, not
    # gerber-visible) changes.
    if pin_name_map:
        import re as _re

        def _remap_pad_name(m):
            stock_name = m.group(1)
            mapped = pin_name_map.get(stock_name, stock_name)
            return f'(pad "{mapped}"'

        body_text = _re.sub(r'\(pad\s+"([^"]+)"', _remap_pad_name, body_text)

    if rotation != 0:
        body_text = _annotate_pad_rotations(body_text, rotation)

    # Optional override of the stock `(model "...")` path. Use when the stock
    # `.kicad_mod` references a STEP file that does NOT exist in the KiCad
    # install (e.g. `Fuse:Fuse_2920_7451Metric.kicad_mod` points at
    # `Fuse.3dshapes/Fuse_2920_7451Metric.step` — file absent in KiCad 10).
    # The replacement keeps any (offset)/(scale)/(rotate) subclauses intact,
    # only swapping the path string.
    if model_override is not None:
        import re as _re
        body_text = _re.sub(
            r'\(model\s+"[^"]+"',
            f'(model "{model_override}"',
            body_text,
        )

    # v0.40 post-order: optional cathode-bar marker on F.SilkS for diodes
    # (D1 SMBJ24A / D2 SS14 / D3 Zener). KLC convention: pad 1 = cathode
    # (K), pad 2 = anode (A). Append a vertical line on F.SilkS at the
    # cathode pad's INNER edge + 0.25 mm clearance so the silk bar stays
    # clear of the pad mask opening. The polarity_uuid_tag suffix lets
    # multiple diodes coexist with deterministic-different UUIDs.
    if polarity_mark == "cathode_bar":
        # Derive cathode-bar X from the actual stock pad-1 geometry
        # (parsed out of body_text). Stock SMA / SMB / SOD-323 all have
        # pad 1 centered at (-pitch/2, 0) with size (pad_w × pad_h).
        import re as _re
        pad1_match = _re.search(
            r'\(pad\s+"1"\s+smd\s+\w+\s*\n?\s*\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+-?\d+(?:\.\d+)?)?\s*\)\s*\n?\s*\(size\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\)',
            body_text,
        )
        if pad1_match is not None:
            pad1_cx = float(pad1_match.group(1))
            pad1_w = float(pad1_match.group(3))
            pad1_h = float(pad1_match.group(4))
            pad1_inner_edge_x = pad1_cx + pad1_w / 2.0
            bar_x = pad1_inner_edge_x + 0.25
            bar_half_h = min(pad1_h / 2.0, pad1_h / 2.0)
            tag = polarity_uuid_tag or uuid_tag
            cathode_bar_clause = (
                f"\n\t\t(fp_line\n"
                f"\t\t\t(start {fmt(bar_x)} -{fmt(bar_half_h)})\n"
                f"\t\t\t(end {fmt(bar_x)} {fmt(bar_half_h)})\n"
                f"\t\t\t(stroke (width 0.12) (type solid))\n"
                f"\t\t\t(layer \"F.SilkS\")\n"
                f"\t\t\t(uuid \"{U('fp-silk-cathode:' + tag)}\")\n"
                f"\t\t)"
            )
            body_text = body_text + cathode_bar_clause

    ref_hide_line = "\t\t\t(hide yes)\n" if hide_ref else ""
    val_hide_line = "\t\t\t(hide yes)\n" if hide_value else ""
    properties = textwrap.dedent(f"""\
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(ref_offset_x)} {fmt(ref_offset_y)} {rotation})
        \t\t\t(layer "F.SilkS")
        """) + ref_hide_line + textwrap.dedent(f"""\
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(val_offset_x)} {fmt(val_offset_y)} {rotation})
        \t\t\t(layer "F.Fab")
        """) + val_hide_line + textwrap.dedent(f"""\
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "{lib_nickname}:{fp_name}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "{datasheet}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "{description}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)""")

    return textwrap.dedent(f"""\
        \t(footprint "{lib_nickname}:{fp_name}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        """) + properties + "\n" + body_text + "\n\t)"


def gen_j9_qwiic_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed J9 — JST SH 4-pin horizontal SMD Qwiic / Stemma QT
    socket at PCB (x, y) with `rotation` degrees. Reads the stock
    `Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal`
    footprint and re-emits it with OAS-side metadata.
    """
    return _emit_stock_lib_footprint(
        src_path=_J9_LIB_FOOTPRINT_PATH,
        lib_nickname="Connector_JST",
        reference="J9",
        value="JST SM04B-SRSS-TB (Qwiic / Stemma QT)",
        datasheet="https://www.jst-mfg.com/product/pdf/eng/eSH.pdf",
        description="JST SH 4-pin 1.0 mm pitch horizontal SMD socket. Standard Qwiic / Stemma QT host footprint — pinout (looking at connector mouth from cable side): pin 1 = GND (black), pin 2 = +3.3V (red), pin 3 = SDA (blue), pin 4 = SCL (yellow). Mates with any genuine Sparkfun Qwiic or Adafruit Stemma QT cable.",
        x=x, y=y, rotation=rotation,
        uuid_tag="j9-qwiic",
        ref_offset_x=0.0, ref_offset_y=-3.6,
        val_offset_x=0.0, val_offset_y=4.6,
        # Hide in-footprint ref + value text: the board-level
        # "J9 Qwiic" cutout silk label + per-pin F.Fab labels already
        # identify the connector. With rotation 180°, an in-footprint
        # ref would land off the PCB south of the chord.
        hide_ref=True, hide_value=True,
    )


def gen_j10_recovery_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed J10 — 6-pin 2.54 mm vertical THT pin header for
    native-USB recovery flashing of the ESP32-C6. Reads the stock
    `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical`
    footprint and re-emits it with OAS-side metadata.

    J10 is DNP (Do Not Populate) — the assembled PCB carries only the
    plated through-hole pads + silkscreen labelling. If a field debugger
    ever needs native-USB-Serial-JTAG access (e.g. after both DevKitM-1
    on-module USB-C ports get damaged), the user solders a standard
    2.54 mm 6-pin pin header onto the pads + wires through it to the
    serial-JTAG endpoint.
    """
    return _emit_stock_lib_footprint(
        src_path=_J10_LIB_FOOTPRINT_PATH,
        lib_nickname="Connector_PinHeader_2.54mm",
        reference="J10",
        value="Native-USB recovery (DNP)",
        datasheet="",
        description="6-pin 2.54 mm vertical through-hole pin header (DNP). Exposes the ESP32-C6 native USB-Serial-JTAG D-/D+ pair (GPIO 12/13) plus EN (chip enable / reset) and BOOT strap (GPIO 9) on solder pads at the C3 case-wall opening. Used only for emergency recovery flashing — the production OAS unit flashes via OTA after first commission. Pinout: 1=GND, 2=+3V3, 3=USB_DM, 4=USB_DP, 5=EN, 6=BOOT.",
        x=x, y=y, rotation=rotation,
        uuid_tag="j10-recovery",
        ref_offset_x=2.5, ref_offset_y=-1.5,
        val_offset_x=2.5, val_offset_y=15.0,
        # Hide in-footprint ref + value text: with rotation 180°,
        # an in-footprint ref would land south of the chord (off PCB).
        # The board-level "J10 flash" cutout silk label + per-pin
        # F.Fab labels identify the connector.
        hide_ref=True, hide_value=True,
        # v0.23 fix for review Mn4: schematic symbol carries `(dnp yes)`;
        # mirror it on the PCB so pos files + BOM exclude J10.
        dnp=True,
    )


def gen_pinsocket_pcb_footprint(
    *,
    pin_count: int,
    x: float, y: float, rotation: int,
    reference: str,
    value: str,
    descr: str,
    uuid_tag: str,
) -> str:
    """Emit a stock-library `PinSocket_1xN_P2.54mm_Vertical` footprint placed
    at PCB (x, y) with `rotation` degrees. Used for the ESP32-C6 DevKitM-1
    daughterboard mating sockets (the board plugs into
    these female 2.54 mm headers, sitting ~3-5 mm above the OAS PCB).
    Logic mirrors `gen_j4_pinheader_pcb_footprint`: skip stock metadata,
    rewrite the OAS-side properties, inject deterministic UUIDs, and
    rotate pads if needed.
    """
    src = _pinsocket_lib_footprint_path(pin_count).read_text(encoding="utf-8")
    fp_name_short = f"PinSocket_1x{pin_count:02d}_P2.54mm_Vertical"

    # Parse the top-level (footprint ...) wrapper exactly like gen_j4.
    depth = 0
    cur: list[str] = []
    items: list[str] = []
    for ch in src:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                items.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)
    assert len(items) == 1
    inner = items[0].strip()
    assert inner.startswith("(footprint") and inner.endswith(")")
    inner = inner[len("(footprint"):].rstrip()
    inner = inner.rstrip(")").rstrip().lstrip()
    assert inner.startswith('"')
    name_end = inner.index('"', 1)
    fp_name = inner[1:name_end]
    inner_after_name = inner[name_end + 1:]

    children: list[str] = []
    depth = 0
    cur = []
    for ch in inner_after_name:
        if ch == "(":
            if depth == 0:
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                children.append("".join(cur))
        else:
            if depth > 0:
                cur.append(ch)

    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
        # (model ...) kept — audit-19 (2026-05-19): local 3D render
        # picks up stock library chip body meshes via KiCad's
        # ${KICAD10_3DMODEL_DIR} env var resolution at render time.
    )
    body_children = []
    for child in children:
        if any(child.startswith(p) for p in SKIP_PREFIXES):
            continue
        body_children.append(child)

    def reindent_for_pcb(s: str) -> str:
        out_lines = []
        for ln in s.split("\n"):
            if ln == "":
                out_lines.append(ln)
            else:
                out_lines.append("\t" + ln)
        return "\n".join(out_lines)

    body_text = "\n".join(reindent_for_pcb(c) for c in body_children)
    body_text = body_text.replace('"${REFERENCE}"', f'"{reference}"')

    if rotation != 0:
        body_text = _annotate_pad_rotations(body_text, rotation)

    properties = textwrap.dedent(f"""\
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 -1.9 {rotation})
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at 0 {fmt((pin_count - 1) * 2.54 + 1.5)} {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "Connector_PinSocket_2.54mm:{fp_name_short}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "{descr}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)""")

    return textwrap.dedent(f"""\
        \t(footprint "Connector_PinSocket_2.54mm:{fp_name}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        """) + properties + "\n" + body_text + "\n\t)"


def gen_sk6812_side_pcb_footprint(
    *, x: float, y: float, rotation: float, reference: str, uuid_tag: str,
    hide_ref: bool = True,
    show_pin_labels: bool = False,
) -> str:
    """Emit a placed SK6812-SIDE footprint instance at PCB (x, y).

    Embeds the same body content as `gen_sk6812_side_footprint()` (the
    library file body) directly into the PCB file so opening pcbnew
    without the project-local library still renders the placement.

    `hide_ref` defaults to True for the LED ring use-case: the 11 LEDs
    sit on a Ø22 mm pitch circle with various rotations (270° → 300°
    around the ring), so per-LED designators are emitted as board-level
    `gr_text` outside the ring instead (see `gen_silk_labels`), keeping
    them horizontal and avoiding silk_overlap with the cap ring inside.

    `show_pin_labels` (default False) — when True, emit 4 small vertical
    `fp_text` labels on F.SilkS above the pad row identifying each pin
    function (Di / Vd / Do / Gd). v0.41 (2026-05-19): used for the
    reference LED D11 so the assembled board can be visually verified
    for correct LED orientation (DIN side faces inward on the ring).
    """
    body_hw = SK6812SIDE_BODY_W / 2.0
    body_hh = SK6812SIDE_BODY_H / 2.0
    pad_x_min = min(lx - pw / 2.0 for lx, pw in SK6812SIDE_PADS)
    pad_x_max = max(lx + pw / 2.0 for lx, pw in SK6812SIDE_PADS)
    crty_x_min = min(-body_hw, pad_x_min) - 0.20
    crty_x_max = max(+body_hw, pad_x_max) + 0.20
    crty_y_min = -body_hh - 0.20
    crty_y_max = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.20
    pin1_dot_x = SK6812SIDE_PADS[0][0] + SK6812SIDE_PADS[0][1] / 2.0   # pad 1 inner edge
    # v0.44: 0.50 mm above pad 1's top edge for JLCPCB "Silkscreen to
    # pad" clearance — MUST stay in sync with gen_sk6812_side_footprint()
    # in _footprints_custom.py (the library-file copy of this geometry),
    # else KiCad flags lib_footprint_mismatch.
    pin1_dot_y = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.50
    arrow_tip_y = -body_hh - 0.35
    arrow_base_y = -body_hh + 0.25
    pad_blocks = []
    for pin_num, (lx, pw) in enumerate(SK6812SIDE_PADS, start=1):
        # Pad rotation injected explicitly so DRC interprets the pad
        # geometry as rotated WITH the footprint (KiCad quirk — see
        # `_annotate_pad_rotations` rationale).
        rot_clause = f" {rotation}" if rotation != 0 else ""
        pad_blocks.append(textwrap.dedent(f"""\
            \t\t(pad "{pin_num}" smd rect
            \t\t\t(at {fmt(lx)} {fmt(SK6812SIDE_PAD_Y)}{rot_clause})
            \t\t\t(size {fmt(pw)} {fmt(SK6812SIDE_PAD_HEIGHT)})
            \t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
            \t\t\t(uuid "{U(f'fp-pad:{uuid_tag}:{pin_num}')}")
            \t\t)"""))
    pads = "\n".join(pad_blocks)
    ref_hide_line = "\n\t\t\t(hide yes)" if hide_ref else ""
    # Optional silk pin labels (v0.41 2026-05-19): 2 vertical 2-char labels
    # ("Di" at pad 1, "Gd" at pad 4) on F.SilkS — used on the reference LED
    # D11 so the assembled board can be visually verified for orientation.
    # Why only the two edge pins? At 0.95 mm pad pitch a 1.0×1.0 mm label
    # (= design rule min text size) per pad would overlap neighbors. Two
    # edge labels still uniquely identify orientation: knowing where DIN
    # (pad 1) and GND (pad 4) sit, VDD/DOUT are unambiguously the two
    # middle pads from datasheet. Vertical orientation (text rotation +90
    # relative to footprint) because horizontal 2-char @ 1.0 mm wouldn't
    # fit even between two pads at the edge spacing.
    if show_pin_labels:
        # v0.44: 1.45 mm above pad 1's top edge — follows the pin-1 dot
        # up (dot centre +1.25, outer edge +1.475 with the lifted 0.15 mm
        # silk stroke) keeping ~0.225 mm silk clearance to it.
        label_y = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT / 2 + 1.45
        label_text_rot = (rotation + 90) % 360
        edge_pins = ((1, "Di", SK6812SIDE_PAD_X_OFFSETS[0]),   # pad 1 = DIN
                     (4, "Gd", SK6812SIDE_PAD_X_OFFSETS[3]))   # pad 4 = GND
        pin_label_blocks = []
        for idx, label, lx in edge_pins:
            pin_label_blocks.append(textwrap.dedent(f"""\
                \t\t(fp_text user "{label}"
                \t\t\t(at {fmt(lx)} {fmt(label_y)} {label_text_rot})
                \t\t\t(layer "F.SilkS")
                \t\t\t(uuid "{U(f'fp-silk-pinlabel-{idx}:' + uuid_tag)}")
                \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
                \t\t)"""))
        pin_labels_block = "\n" + "\n".join(pin_label_blocks)
    else:
        pin_labels_block = ""
    return textwrap.dedent(f"""\
        \t(footprint "oas:SK6812-SIDE"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "SK6812 SIDE-A addressable RGB LED. 4020 side-emit, integrated WS281x controller. Pinout 1=DIN 2=VDD 3=DOUT 4=GND.")
        \t\t(attr smd)
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 -1.5 {rotation})
        \t\t\t(layer "F.SilkS"){ref_hide_line}
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "SK6812-SIDE"
        \t\t\t(at 0 2.5 {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "oas:SK6812-SIDE"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "http://www.normandled.com/upload/201810/SK6812%20SIDE-A%20LED%20Datasheet.pdf"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "SK6812 SIDE-A 4020 side-emit addressable RGB LED (Normand / OPSCO). Pinout 1=DIN, 2=VDD, 3=DOUT, 4=GND."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(-body_hw)} {fmt(-body_hh)})
        \t\t\t(end {fmt(body_hw)} {fmt(body_hh)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-body:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(crty_x_min)} {fmt(crty_y_min)})
        \t\t\t(end {fmt(crty_x_max)} {fmt(crty_y_max)})
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-crtyd:' + uuid_tag)}")
        \t\t)
        \t\t(fp_circle
        \t\t\t(center {fmt(pin1_dot_x)} {fmt(pin1_dot_y)})
        \t\t\t(end {fmt(pin1_dot_x + 0.15)} {fmt(pin1_dot_y)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(fill solid)
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-pin1-dot:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start 0 {fmt(arrow_base_y)})
        \t\t\t(end 0 {fmt(arrow_tip_y)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-arrow-stem:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(-0.3)} {fmt(arrow_tip_y + 0.3)})
        \t\t\t(end 0 {fmt(arrow_tip_y)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-arrow-wing-l:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(+0.3)} {fmt(arrow_tip_y + 0.3)})
        \t\t\t(end 0 {fmt(arrow_tip_y)})
        \t\t\t(stroke (width 0.08) (type solid))
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-arrow-wing-r:' + uuid_tag)}")
        \t\t)
        """) + pads + pin_labels_block + "\n" + textwrap.dedent("""\
        \t\t(model "${KIPRJMOD}/libraries/oas.3dshapes/SK6812-SIDE-A.step"
        \t\t\t(offset (xyz 0 0 0))
        \t\t\t(scale (xyz 1 1 1))
        \t\t\t(rotate (xyz 0 0 0))
        \t\t)""") + "\n\t)"


def gen_capacitor_0402_pcb_footprint(
    *, x: float, y: float, rotation: float, reference: str, value: str,
    uuid_tag: str, descr: str = "100 nF 0402 X7R decoupling capacitor",
    hide_ref: bool = True,
) -> str:
    """Emit a placed Capacitor_SMD:C_0402_1005Metric footprint instance.

    v0.40 post-order: pad geometry transcribed VERBATIM from KiCad stock
    `Capacitor_SMD:C_0402_1005Metric.kicad_mod` via `_emit_stock_lib_footprint`.
    Previous hand-coded inline geometry used pad_pitch 0.85 mm with
    rect pad 0.62 × 0.70 mm — deviated from stock (pitch 0.96 mm, roundrect
    pad 0.56 × 0.62 mm), which would have placed the AQI LED ring
    decoupling caps with non-stock pad geometry, failing the "ZERO
    hand-solder friendly deviations" mandate.

    `hide_ref` defaults to True; the OAS PCB emits per-instance designators
    as board-level `gr_text` from `gen_designator_labels()` instead.
    """
    return _emit_stock_lib_footprint(
        src_path=_C0402_LIB_FOOTPRINT_PATH,
        lib_nickname="Capacitor_SMD",
        reference=reference,
        value=value,
        datasheet="",
        description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-1.4,
        val_offset_x=0.0, val_offset_y=1.4,
        hide_ref=hide_ref, hide_value=True,
    )


# -----------------------------------------------------------------------------
# v0.20 C2 fix: stub generators for power-section / decoupling footprints
# -----------------------------------------------------------------------------
# These emit minimal self-contained footprints (pads + small F.Fab body
# outline + F.CrtYd rectangle) for the schematic-side components that
# previously had no PCB placement. They are intentionally minimalist:
# the goal is to land each part at a sensible location on the PCB with
# pads correctly numbered so the v0.20 net-sync pass attaches schematic
# nets to them — NOT to provide production-quality 3D models or
# silkscreen typography. Final placement / silk artwork should be
# refined during routing iterations.
#
# Footprint conventions:
#   - Reference text on F.SilkS, hidden (the board-level gr_text labels
#     in gen_silk_labels() can be added later if desired).
#   - Value text on F.Fab, hidden.
#   - Footprint property carries the canonical KiCad library:footprint
#     name so BOM / position-file exports work out of the box.
#   - One inline footprint per component instance (no library lookup);
#     the .kicad_pcb remains stand-alone.
#   - All footprints declare `(attr smd)` or `(attr through_hole)` so
#     KiCad's position-file exporter treats them correctly.


def _emit_two_pad_smd_footprint(
    *, x: float, y: float, rotation: int,
    reference: str, value: str, uuid_tag: str,
    descr: str, footprint_name: str,
    pad_pitch: float, pad_w: float, pad_h: float,
    body_w: float, body_h: float,
    attr: str = "smd",
    pad_type: str = "smd",
    pad_shape: str = "roundrect",
    pad_roundrect_rratio: float = 0.25,
    footprint_lib: str | None = None,
    hide_ref: bool = True,
    polarity_mark: str = "none",
) -> str:
    """Emit a generic two-pad SMD footprint (Cap/Res/Diode/Inductor SMD).

    Pads 1 and 2 are at footprint-local ±(pad_pitch/2) on the X axis,
    centered on Y = 0. Pin numbering is 1 (left/-X) → 2 (right/+X) which
    matches every two-terminal passive in the KiCad symbol library
    (Device:C, Device:R, Device:D, Device:L), so the net-sync pass
    binds them correctly without per-component override.

    `hide_ref` defaults to True. The OAS PCB instead emits a per-component
    board-level `gr_text` designator from `gen_designator_labels()` for
    every populated component — that gives us per-instance positioning
    control (avoiding silk_overlap with J5/J6 socket frames, the
    MOD1 daughterboard outline, and the LED-ring cap collisions
    that the in-footprint Reference text would otherwise trigger). Pass
    `hide_ref=False` only if you really want the in-footprint reference
    text on a future board where no curated gr_text label exists.
    """
    pad_x = pad_pitch / 2.0
    crty_x = pad_x + pad_w / 2.0 + 0.10
    crty_y = max(pad_h, body_h) / 2.0 + 0.10
    rot_clause = f" {rotation}" if rotation != 0 else ""
    extra = ""
    if pad_shape == "roundrect":
        extra = f"\n\t\t\t(roundrect_rratio {pad_roundrect_rratio})"
    # v0.24: lib-qualify the `(property "Footprint" ...)` value so the
    # schematic back-fill emits a valid `Lib:Name` reference (silences
    # ERC `footprint_link_issues` warnings introduced in v0.23 Mn3).
    fp_property_value = (
        f"{footprint_lib}:{footprint_name}" if footprint_lib else footprint_name
    )
    ref_hide_line = "\n\t\t\t(hide yes)" if hide_ref else ""
    # v0.36 I1 fix: polarity marker on F.SilkS. For diodes, pad 1 = cathode
    # (KiCad KLC convention) and the cathode-bar marker goes on the cathode
    # side of the body so the hand-assembler can see polarity at a glance.
    # Without this, the silkscreen has no polarity indicator — a backwards
    # diode is a silent failure (D1 TVS gives 0 protection, D2 freewheel
    # shorts the SW node, D3 Zener clamp dies).
    cathode_bar_clause = ""
    if polarity_mark == "cathode_bar":
        # Vertical line on F.SilkS at the cathode end. Pad 1 = cathode per
        # KiCad's KLC. For SMA/SMB/SOD-323 the body extends BETWEEN the pads
        # but pads also extend into the body extent on the X axis (e.g. SMA
        # pad 1 east edge at X=-1.05 vs body west edge at X=-2.15 — pad
        # overhangs body by 1.1 mm on the inner side). A naive "bar at body
        # west edge" places the bar OVER pad 1's exposed metal → silk_over_copper
        # DRC fail. Correct placement: bar between the pad's inner edge (east
        # edge of pad 1) and the body's east-of-pad region, with ≥0.15 mm
        # clearance to the pad mask opening. Pad 1 east edge =
        # -(pad_pitch/2) + pad_w/2; bar at that X + 0.25 mm gives 0.25 mm
        # clearance. The bar stays inside body_w/2 since for all our diode
        # packages (SMA/SMB/SOD-323) body extends past the pad inner edge.
        pad_inner_edge_x = -(pad_pitch / 2.0) + (pad_w / 2.0)
        bar_x = pad_inner_edge_x + 0.25
        # Bar height: keep it within body_h so it doesn't poke past the body
        # outline. Limit to pad_h to avoid the bar extending past pad metal on
        # the Y axis (which would only matter if bar X were over pad metal —
        # belt-and-suspenders).
        bar_half_h = min(body_h / 2.0 - 0.05, pad_h / 2.0)
        cathode_bar_clause = (
            f"\n\t\t(fp_line\n"
            f"\t\t\t(start {fmt(bar_x)} -{fmt(bar_half_h)})\n"
            f"\t\t\t(end {fmt(bar_x)} {fmt(bar_half_h)})\n"
            f"\t\t\t(stroke (width 0.12) (type solid))\n"
            f"\t\t\t(layer \"F.SilkS\")\n"
            f"\t\t\t(uuid \"{U('fp-silk-cathode:' + uuid_tag)}\")\n"
            f"\t\t)"
        )
    return textwrap.dedent(f"""\
        \t(footprint "{footprint_name}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "{descr}")
        \t\t(attr {attr})
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 -{fmt(crty_y + 0.8)} {rotation})
        \t\t\t(layer "F.SilkS"){ref_hide_line}
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at 0 {fmt(crty_y + 0.8)} {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "{fp_property_value}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "{descr}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(fp_rect
        \t\t\t(start -{fmt(body_w/2)} -{fmt(body_h/2)})
        \t\t\t(end {fmt(body_w/2)} {fmt(body_h/2)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-body:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start -{fmt(crty_x)} -{fmt(crty_y)})
        \t\t\t(end {fmt(crty_x)} {fmt(crty_y)})
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-crtyd:' + uuid_tag)}")
        \t\t){cathode_bar_clause}
        \t\t(pad "1" {pad_type} {pad_shape}
        \t\t\t(at -{fmt(pad_x)} 0{rot_clause})
        \t\t\t(size {fmt(pad_w)} {fmt(pad_h)})
        \t\t\t(layers "F.Cu" "F.Paste" "F.Mask"){extra}
        \t\t\t(uuid "{U('fp-pad-1:' + uuid_tag)}")
        \t\t)
        \t\t(pad "2" {pad_type} {pad_shape}
        \t\t\t(at {fmt(pad_x)} 0{rot_clause})
        \t\t\t(size {fmt(pad_w)} {fmt(pad_h)})
        \t\t\t(layers "F.Cu" "F.Paste" "F.Mask"){extra}
        \t\t\t(uuid "{U('fp-pad-2:' + uuid_tag)}")
        \t\t)
        \t)""")


def gen_resistor_0603_pcb_footprint(*, x: float, y: float, rotation: int,
                                     reference: str, value: str, uuid_tag: str,
                                     descr: str = "Resistor 0603",
                                     hide_ref: bool = True) -> str:
    """0603 SMD resistor placement.

    v0.40 post-order: pad geometry transcribed VERBATIM from KiCad stock
    `Resistor_SMD:R_0603_1608Metric.kicad_mod`. Previous inline geometry
    (pitch 1.70 mm, pad 0.95 × 0.95 mm) deviated from stock (pitch
    1.65 mm, pad 0.8 × 0.95 mm); fails the "ZERO hand-solder friendly
    deviations" mandate."""
    return _emit_stock_lib_footprint(
        src_path=_R0603_LIB_FOOTPRINT_PATH,
        lib_nickname="Resistor_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-1.45,
        val_offset_x=0.0, val_offset_y=1.45,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_capacitor_0603_pcb_footprint(*, x: float, y: float, rotation: int,
                                      reference: str, value: str, uuid_tag: str,
                                      descr: str = "Capacitor 0603",
                                      hide_ref: bool = True) -> str:
    """0603 SMD ceramic capacitor.

    v0.40 post-order: pad geometry transcribed VERBATIM from KiCad stock
    `Capacitor_SMD:C_0603_1608Metric.kicad_mod`."""
    return _emit_stock_lib_footprint(
        src_path=_C0603_LIB_FOOTPRINT_PATH,
        lib_nickname="Capacitor_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-1.45,
        val_offset_x=0.0, val_offset_y=1.45,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_capacitor_0805_pcb_footprint(*, x: float, y: float, rotation: int,
                                      reference: str, value: str, uuid_tag: str,
                                      descr: str = "Capacitor 0805",
                                      hide_ref: bool = True) -> str:
    """0805 SMD ceramic capacitor — for 10 µF / 22 µF input/output bulk
    on the 3.3 V buck stage.

    v0.40 post-order: pad geometry transcribed VERBATIM from KiCad stock
    `Capacitor_SMD:C_0805_2012Metric.kicad_mod` (pitch 1.90 mm, pad
    1.0 × 1.45 mm — slightly different from previous 1.80 mm / 1.15 ×
    1.40 mm)."""
    return _emit_stock_lib_footprint(
        src_path=_C0805_LIB_FOOTPRINT_PATH,
        lib_nickname="Capacitor_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-1.75,
        val_offset_x=0.0, val_offset_y=1.75,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_diode_sma_pcb_footprint(*, x: float, y: float, rotation: int,
                                 reference: str, value: str, uuid_tag: str,
                                 descr: str = "Diode SMA",
                                 hide_ref: bool = True) -> str:
    """SMA package — Schottky / TVS / Zener. Cathode is pin 1 (KiCad
    convention for Device:D / Device:D_Schottky), anode pin 2.

    v0.40 post-order: pad geometry + silk transcribed VERBATIM from
    KiCad stock `Diode_SMD:D_SMA.kicad_mod` (pitch 4.0 mm, pad 2.5 ×
    1.8 mm). The stock footprint already includes a cathode-end silk
    band at X=-3.51 (vertical line from Y=-1.65 to +1.65), so no
    custom polarity marker is needed."""
    return _emit_stock_lib_footprint(
        src_path=_D_SMA_LIB_FOOTPRINT_PATH,
        lib_nickname="Diode_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-2.6,
        val_offset_x=0.0, val_offset_y=2.6,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_diode_smb_pcb_footprint(*, x: float, y: float, rotation: int,
                                 reference: str, value: str, uuid_tag: str,
                                 descr: str = "Diode SMB",
                                 hide_ref: bool = True) -> str:
    """SMB package — larger TVS / Schottky.

    v0.40 post-order: pad geometry + silk transcribed VERBATIM from
    KiCad stock `Diode_SMD:D_SMB.kicad_mod` (pitch 4.3 mm, pad 2.5 ×
    2.3 mm). Stock silk already marks the cathode end."""
    return _emit_stock_lib_footprint(
        src_path=_D_SMB_LIB_FOOTPRINT_PATH,
        lib_nickname="Diode_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-3.1,
        val_offset_x=0.0, val_offset_y=3.1,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_diode_sod323_pcb_footprint(*, x: float, y: float, rotation: int,
                                    reference: str, value: str, uuid_tag: str,
                                    descr: str = "Diode SOD-323",
                                    hide_ref: bool = True) -> str:
    """SOD-323 small Zener / TVS package.

    v0.40 post-order: pad geometry + silk transcribed VERBATIM from
    KiCad stock `Diode_SMD:D_SOD-323.kicad_mod` (pitch 2.1 mm, pad 0.6
    × 0.45 mm). Stock silk already marks the cathode end."""
    return _emit_stock_lib_footprint(
        src_path=_D_SOD323_LIB_FOOTPRINT_PATH,
        lib_nickname="Diode_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-1.5,
        val_offset_x=0.0, val_offset_y=1.5,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_inductor_smd_5x5_pcb_footprint(*, x: float, y: float, rotation: int,
                                         reference: str, value: str, uuid_tag: str,
                                         descr: str = "Inductor SMD ~5×5 mm",
                                         hide_ref: bool = True) -> str:
    """Power inductor footprint for CENKER CKCS5040 series (33 µH for L1
    / 2.2 µH for L2). 5.0 × 5.0 × 4.0 mm body.

    v0.40 post-order: pad geometry transcribed VERBATIM from KiCad stock
    `Inductor_SMD:L_Cenker_CKCS5040.kicad_mod` (pitch 3.30 mm, pad
    2.2 × 4.2 mm). Previous footprint name `L_APV_ANR5040` was a
    mismatch — the selected LCSC parts (C354612 33µH, C354602 2.2µH)
    are CENKER CKCS5040 series, and KiCad ships a dedicated
    `L_Cenker_CKCS5040.kicad_mod` with a different (tighter) land
    pattern."""
    return _emit_stock_lib_footprint(
        src_path=_L_CENKER_CKCS5040_LIB_FOOTPRINT_PATH,
        lib_nickname="Inductor_SMD",
        reference=reference, value=value,
        datasheet="https://www.ckcoil.com/file/upload/spae532/2023-07/11/202307110955366446.pdf",
        description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-3.6,
        val_offset_x=0.0, val_offset_y=3.6,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_fuse_1812l_pcb_footprint(*, x: float, y: float, rotation: int,
                                  reference: str, value: str, uuid_tag: str,
                                  descr: str = "PTC polyfuse 1812 (Littelfuse 1812L series).",
                                  hide_ref: bool = True) -> str:
    """Emit a placed Littelfuse-1812L PTC fuse footprint instance at PCB (x, y).

    Embeds the same body content as `gen_fuse_1812l_footprint()` (the
    library file body) directly into the PCB file so opening pcbnew
    without the project-local library still renders the placement.

    v0.42 (2026-05-20): replaces the former `gen_polyfuse_smd_pcb_footprint`
    which delegated to KiCad stock `Fuse:Fuse_1812_4532Metric`. That stock
    land is a GENERIC IPC 1812 chip-fuse pattern (pad gap 3.15 mm) and
    does NOT match the Littelfuse 1812L termination geometry (gap
    2.30 mm) — JLCPCB DFM flagged the part's pin inner edge 0.43 mm past
    the copper ("pin inner edge"). This custom land is the verbatim
    EasyEDA F1812 footprint of LCSC C151170. See oas:Fuse_1812L_4532Metric
    / CLAUDE.md Deviation budget. 3D model: KiCad stock
    `Resistor_SMD.3dshapes/R_1812_4532Metric.step` — the 1812 PTC body is
    dimensionally a 1812 chip, so the resistor STEP is a 1:1 visual
    surrogate (CC-BY-SA 4.0 + Design Exception, bundled with KiCad).
    """
    body_hw = FUSE1812L_BODY_W / 2.0
    body_hh = FUSE1812L_BODY_H / 2.0
    pad_hw = FUSE1812L_PAD_W / 2.0
    pad_hh = FUSE1812L_PAD_H / 2.0
    pad_outer_x = FUSE1812L_PAD_X + pad_hw
    crty_x = max(body_hw, pad_outer_x) + 0.20
    crty_y = max(body_hh, pad_hh) + 0.20
    silk_x = 0.8
    silk_y = body_hh + 0.09
    ref_hide_line = "\n\t\t\t(hide yes)" if hide_ref else ""
    rot_clause = f" {rotation}" if rotation != 0 else ""
    pad_blocks = []
    for pin_num, sign in ((1, -1.0), (2, +1.0)):
        pad_blocks.append(textwrap.dedent(f"""\
            \t\t(pad "{pin_num}" smd rect
            \t\t\t(at {fmt(sign * FUSE1812L_PAD_X)} 0{rot_clause})
            \t\t\t(size {fmt(FUSE1812L_PAD_W)} {fmt(FUSE1812L_PAD_H)})
            \t\t\t(layers "F.Cu" "F.Mask" "F.Paste")
            \t\t\t(uuid "{U(f'fp-pad:{uuid_tag}:{pin_num}')}")
            \t\t)"""))
    pads = "\n".join(pad_blocks)
    return textwrap.dedent(f"""\
        \t(footprint "oas:Fuse_1812L_4532Metric"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "{descr}")
        \t\t(attr smd)
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 {fmt(-(body_hh + 1.0))} {rotation})
        \t\t\t(layer "F.SilkS"){ref_hide_line}
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at 0 {fmt(body_hh + 1.0)} {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "oas:Fuse_1812L_4532Metric"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Datasheet" "https://www.lcsc.com/datasheet/C151170.pdf"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ds:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "Littelfuse 1812L075/33DR PTC resettable fuse — 33 V, 750 mA hold / 1.5 A trip, 1812 SMD."
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(-body_hw)} {fmt(-body_hh)})
        \t\t\t(end {fmt(body_hw)} {fmt(body_hh)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-body:' + uuid_tag)}")
        \t\t)
        \t\t(fp_text user "{reference}"
        \t\t\t(at 0 0 {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(-crty_x)} {fmt(-crty_y)})
        \t\t\t(end {fmt(crty_x)} {fmt(crty_y)})
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-crtyd:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(-silk_x)} {fmt(-silk_y)})
        \t\t\t(end {fmt(silk_x)} {fmt(-silk_y)})
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk-top:' + uuid_tag)}")
        \t\t)
        \t\t(fp_line
        \t\t\t(start {fmt(-silk_x)} {fmt(silk_y)})
        \t\t\t(end {fmt(silk_x)} {fmt(silk_y)})
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk-bot:' + uuid_tag)}")
        \t\t)
        """) + pads + "\n" + textwrap.dedent("""\
        \t\t(model "${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_1812_4532Metric.step"
        \t\t\t(offset (xyz 0 0 0))
        \t\t\t(scale (xyz 1 1 1))
        \t\t\t(rotate (xyz 0 0 0))
        \t\t)""") + "\n\t)"


def gen_capacitor_polarized_radial_pcb_footprint(*, x: float, y: float, rotation: int,
                                                   reference: str, value: str, uuid_tag: str,
                                                   diameter_mm: float = 6.3,
                                                   pitch_mm: float = 2.5,
                                                   descr: str = "Electrolytic radial through-hole",
                                                   hide_ref: bool = True) -> str:
    """Polarized electrolytic capacitor — radial through-hole. Pad 1
    (anode, +) on -X side, pad 2 (cathode, -) on +X side.

    v0.40 post-order: geometry transcribed VERBATIM from KiCad stock
    `Capacitor_THT:CP_Radial_D<diameter>mm_P<pitch>mm.kicad_mod`. The
    stock footprint origin is at PIN 1 (not body center), so this
    wrapper translates the caller's "body center" XY by -pitch/2 along
    the local X axis (accounting for rotation) so the physical body
    still ends up centered at the requested (x, y) coordinate.
    Previous custom geometry used `rect` pads + body-center origin;
    stock uses `roundrect` pad-1 + pin-1 origin. Pad shape change is
    cosmetic at JLCPCB but matches the user-mandated "ZERO 'hand-solder
    friendly' deviations" rule."""
    import math
    if diameter_mm == 8.0 and pitch_mm == 3.5:
        src_path = _CP_RADIAL_D8_LIB_FOOTPRINT_PATH
        fp_basename = "CP_Radial_D8.0mm_P3.50mm"
    elif diameter_mm == 6.3 and pitch_mm == 2.5:
        src_path = _CP_RADIAL_D6_3_LIB_FOOTPRINT_PATH
        fp_basename = "CP_Radial_D6.3mm_P2.50mm"
    else:
        raise ValueError(
            f"No stock CP_Radial library entry for D{diameter_mm}mm_P{pitch_mm}mm; "
            f"add a path constant + the stock .kicad_mod entry"
        )

    # Translate (x, y) from body-center to pin-1-origin convention.
    # Stock has pin 1 at footprint local (0, 0), pin 2 at (pitch, 0),
    # body center at (pitch/2, 0). Caller passes the body center; the
    # footprint anchor needs to be at body_center - (pitch/2, 0) rotated
    # by `rotation` degrees CCW (KiCad screen rotation convention is
    # CCW positive in footprint-local frame for this transformation).
    theta = math.radians(rotation)
    half_pitch = pitch_mm / 2.0
    dx = -half_pitch * math.cos(theta)
    dy = -half_pitch * math.sin(theta)
    anchor_x = x + dx
    anchor_y = y + dy

    return _emit_stock_lib_footprint(
        src_path=src_path,
        lib_nickname="Capacitor_THT",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=anchor_x, y=anchor_y, rotation=rotation,
        uuid_tag=uuid_tag,
        # Reference / Value text offsets: place outside the body
        # diameter on the rotated footprint frame. Body radius +0.6
        # gives clearance for 1.0 mm text height.
        ref_offset_x=half_pitch, ref_offset_y=-(diameter_mm / 2.0 + 0.6),
        val_offset_x=half_pitch, val_offset_y=(diameter_mm / 2.0 + 0.6),
        hide_ref=hide_ref, hide_value=True,
    )


def gen_sot23_3pin_pcb_footprint(*, x: float, y: float, rotation: int,
                                  reference: str, value: str, uuid_tag: str,
                                  descr: str = "SOT-23 3-pin",
                                  pin_names: tuple[str, str, str] = ("1", "2", "3"),
                                  hide_ref: bool = True) -> str:
    """SOT-23 footprint — 3 pads. Pad geometry transcribed VERBATIM from
    KiCad stock `Package_TO_SOT_SMD:SOT-23.kicad_mod`:
      pad 1 at (-0.9375, -0.95), size 1.475 × 0.6 mm  (bottom-left in
                                                       stock "E" pattern)
      pad 2 at (-0.9375, +0.95), size 1.475 × 0.6 mm  (top-left)
      pad 3 at (+0.9375,  0),    size 1.475 × 0.6 mm  (right-center)

    v0.40 post-order CRITICAL fix: previous custom geometry rotated the
    pads 90° to a "⊥" pattern (pads 1/2 along -Y bottom row, pad 3 at
    top centre) with smaller 1.0 × 0.6 mm pads. JLCPCB places SMD parts
    using their tape-feeder orientation derived from the canonical
    footprint NAME (declared as `Package_TO_SOT_SMD:SOT-23`); the
    mismatch between declared-name "E" orientation and emitted "⊥"
    geometry would have rotated the AO3401A 90° relative to the
    intended G/S/D-on-pad mapping, swapping reverse-polarity
    protection's gate, source and drain connections.

    `pin_names` remaps the stock pad NAMES from the canonical "1"/"2"/"3"
    to whatever the schematic symbol uses. For Q1 (Device:Q_PMOS, pin
    names "G"/"S"/"D"), pass `pin_names=("G", "S", "D")` and the SOT-23
    stock pad "1" (gate position, bottom-left in stock layout) becomes
    pad "G", stock pad "2" (source, top-left) → "S", stock pad "3"
    (drain, right) → "D". Pad NAMES are internal connectivity metadata
    (not visible in gerbers); pad GEOMETRY stays verbatim stock so the
    JLCPCB place-and-route engine sees the same canonical pattern."""
    pin_name_map: dict[str, str] | None = None
    if tuple(pin_names) != ("1", "2", "3"):
        pin_name_map = {
            "1": pin_names[0],
            "2": pin_names[1],
            "3": pin_names[2],
        }
    return _emit_stock_lib_footprint(
        src_path=_SOT23_LIB_FOOTPRINT_PATH,
        lib_nickname="Package_TO_SOT_SMD",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-2.4,
        val_offset_x=0.0, val_offset_y=2.4,
        hide_ref=hide_ref, hide_value=True,
        pin_name_map=pin_name_map,
    )


def gen_to263_5_lm2596_footprint() -> str:
    """Project-local oas:TO-263-5_LM2596 footprint (library .kicad_mod).

    The KiCad stock Package_TO_SOT_SMD:TO-263-5_TabPin3 is a GENERIC IPC
    TO-263-5 land that does NOT match the exact ordered part — LM2596S-5.0/
    NOPB, LCSC C116713. The EasyEDA footprint of C116713 has the lead row
    at 3.50 x 1.02 mm and the tab at 8.705 x 10.587 mm with a 10.252 mm
    lead-to-tab pitch; the stock land uses 4.6 x 1.1 leads, a 9.4 x 10.8
    tab and a 9.15 mm pitch. That 1.1 mm pitch mismatch left U1's thermal
    tab only ~25 % overlapped on JLCPCB DFM ("Lead area overlapping pad"
    Danger, jlcdfm.com, v0.43 board, 2026-05-21).

    This footprint keeps the stock silkscreen, courtyard, F.Fab body
    outline and 3D model VERBATIM and swaps ONLY the 6 pads — 5 leads +
    1 tab, all with full F.Paste (single tab aperture, no windowpane) —
    for the verbatim C116713 land. JLCPCB DFM then compares the part to
    a copy of its own land.

    Anchor stays the stock body-centre origin, so U1's PCB placement and
    the GND-tab via-in-pad need no move. Leads land at X = -8.230, the
    tab centre at X = +2.022 (lead-tab pitch 10.252, body-centre origin).
    Same precedent as oas:Fuse_1812L_4532Metric (F1).
    """
    stock = _TO263_5_LIB_FOOTPRINT_PATH.read_text(encoding="utf-8")
    head = stock[:stock.index("\t(pad ")]
    tail = stock[stock.index("\t(embedded_fonts"):]

    subs = [
        ('(footprint "TO-263-5_TabPin3"', '(footprint "TO-263-5_LM2596"'),
        ('(property "Value" "TO-263-5_TabPin3"',
         '(property "Value" "TO-263-5_LM2596"'),
        ('\t(descr "TO-263/D2PAK/DDPAK SMD package, '
         'http://www.infineon.com/cms/en/product/packages/'
         'PG-TO263/PG-TO263-5-1/")',
         '\t(descr "TO-263-5 / D2PAK-5 land for LM2596S-5.0 (LCSC C116713) '
         '— verbatim EasyEDA C116713 pads, lead-tab pitch 10.252 mm; '
         'silk / courtyard / F.Fab / 3D from KiCad stock TO-263-5_TabPin3.")'),
        ('\t(tags "D2PAK DDPAK TO-263 D2PAK-5 TO-263-5 SOT-426")',
         '\t(tags "TO-263 TO-263-5 D2PAK-5 LM2596 oas")'),
    ]
    for old, new in subs:
        assert old in head, (
            "TO-263-5_TabPin3 stock donor changed — re-validate "
            f"gen_to263_5_lm2596_footprint; missing: {old[:48]!r}"
        )
        head = head.replace(old, new)

    # Verbatim LCSC C116713 land (body-centre origin, KiCad orientation:
    # leads on -X, tab on +X). Pin order per LM2596 datasheet TI SNVS124N
    # Table 1: 1=VIN, 2=OUT, 3=GND (tab + pin 3), 4=FB, 5=~ON/OFF.
    #
    # PASTE: all 6 pads carry full F.Paste — the EasyEDA C116713
    # footprint gives the thermal tab a SINGLE full-coverage paste
    # aperture, NOT a windowpane. JLCPCB DFM "Lead area overlapping pad"
    # pairs the tab lead with a paste aperture; an earlier 4-window
    # windowpane here left no single window covering >=75% of the slug
    # (jlcdfm.com 2026-05-21, value 0.23). A single full aperture that
    # equals the part's own land clears it.
    lead_y = (-3.4, -1.7, 0.0, 1.7, 3.4)
    pads: list[str] = []
    # 5 lead pads + the tab pad (both numbered "3" — same GND net).
    for n, ly in zip("12345", lead_y):
        pads.append(
            f'\t(pad "{n}" smd rect\n'
            f'\t\t(at -8.23 {fmt(ly)})\n'
            f'\t\t(size 3.5 1.02)\n'
            f'\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n'
            f'\t)'
        )
        if n == "3":
            pads.append(
                '\t(pad "3" smd rect\n'
                '\t\t(at 2.022 0)\n'
                '\t\t(size 8.705 10.587)\n'
                '\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n'
                '\t)'
            )
    return head + "\n".join(pads) + "\n" + tail


def gen_to263_5_pcb_footprint(*, x: float, y: float, rotation: int,
                               reference: str, value: str, uuid_tag: str,
                               descr: str = "TO-263-5 LM2596S",
                               hide_ref: bool = True) -> str:
    """TO-263-5 (D2PAK-5) placed footprint for U1 (LM2596S-5.0).

    v0.43: switched from KiCad stock Package_TO_SOT_SMD:TO-263-5_TabPin3
    to the project-local oas:TO-263-5_LM2596 land (verbatim LCSC C116713
    geometry) — the generic stock land mismatched the part's lead-tab
    pitch by 1.1 mm and tripped JLCPCB DFM "Lead area overlapping pad"
    on U1's thermal tab. See gen_to263_5_lm2596_footprint and CLAUDE.md
    Deviation budget. This stays Lesson-1 compliant: pad geometry is
    parsed verbatim from the oas library file (written by boardgen
    stage 01) via _emit_stock_lib_footprint — no hand-coded pads here.

    Pin order per LM2596 datasheet TI lit no SNVS124N Table 1:
      1=VIN, 2=OUT (switch node), 3=GND (tab+pin3), 4=FB, 5=~ON/OFF
    """
    return _emit_stock_lib_footprint(
        src_path=_TO263_5_LM2596_LIB_FOOTPRINT_PATH,
        lib_nickname="oas",
        reference=reference, value=value,
        datasheet="http://www.ti.com/lit/ds/symlink/lm2596.pdf",
        description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-6.65,
        val_offset_x=0.0, val_offset_y=6.65,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_sot583_pcb_footprint(*, x: float, y: float, rotation: int,
                              reference: str, value: str, uuid_tag: str,
                              descr: str = "SOT-583 8-pin TPS62933",
                              hide_ref: bool = True) -> str:
    """SOT-583-8 / VSON-8 footprint for TPS62933.

    v0.40 audit-16: refactored to verbatim KiCad stock parsing of
    Package_TO_SOT_SMD:SOT-583-8. Previous version inline-emitted the
    pad coordinates BUT used a non-canonical footprint header name
    "SOT-583_TPS62933" — same class of defect as the v0.40-rejected
    TO-263-5_LM2596 generator. Now the entire footprint comes from the
    stock library verbatim, with the canonical "SOT-583-8" header.

    Pin layout per TI TPS62933 datasheet SLUSEA4D Rev D Table 7-1:
      Pin 1=RT, 2=EN, 3=VIN, 4=GND, 5=SW, 6=BST, 7=SS, 8=FB
    Body 1.6 × 2.1 mm, 0.5 mm pitch within a row.
    """
    return _emit_stock_lib_footprint(
        src_path=_SOT583_8_LIB_FOOTPRINT_PATH,
        lib_nickname="Package_TO_SOT_SMD",
        reference=reference, value=value,
        datasheet="https://www.ti.com/lit/ds/symlink/tps62933.pdf",
        description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-1.8,
        val_offset_x=0.0, val_offset_y=1.8,
        hide_ref=hide_ref, hide_value=True,
    )


def gen_pinheader_6_recovery_pcb_footprint(*, x: float, y: float, rotation: int,
                                            reference: str, value: str, uuid_tag: str,
                                            descr: str = "PinHeader 1x06 P2.54 mm THT (DNP recovery)",
                                            hide_ref: bool = True) -> str:
    """1×6 2.54 mm pitch through-hole pin header (J2 — schematic-side
    DNP recovery header).

    v0.40 audit-16: refactored to verbatim KiCad stock parsing of
    Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical (same
    stock entry used by J10). Previous version inline-emitted a custom
    footprint header "PinHeader_1x06_P2.54mm_Vertical" (no lib prefix),
    duplicating the layout but losing the canonical name. DNP attribute
    layered on top via _emit_stock_lib_footprint's `dnp=True`."""
    return _emit_stock_lib_footprint(
        src_path=_J2_LIB_FOOTPRINT_PATH,
        lib_nickname="Connector_PinHeader_2.54mm",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=2.5, ref_offset_y=-1.5,
        val_offset_x=2.5, val_offset_y=15.0,
        hide_ref=hide_ref, hide_value=True,
        dnp=True,
    )
