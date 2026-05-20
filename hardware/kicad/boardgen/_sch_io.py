"""boardgen/_sch_io.py - io.kicad_sch generator."""
from __future__ import annotations

import math
import textwrap

from boardgen._common import U, fmt, sheet_context, SCH_VERSION, GEN_VERSION, SHEET_FILE_UUIDS, ROOT_SHEET_UUID, SUBSHEET_DISPLAY_NAMES
from boardgen._project import fx, fy, PROJECT_SHORTNAME
from boardgen._lib_symbols import IO_LIB_SYMBOLS
from boardgen._sch_helpers import (
    _sch_wire, _sch_junction, _sch_power_flag,
    _sch_hierarchical_label, _sch_no_connect, _sch_local_label,
    _sch_conn_01x04, _sch_conn_01x06, _sch_conn_01x05, _sch_conn_01xn,
    _sch_sw_push,
    _conn_01xn_pin_xy, _CONN_01XN_PIN1_LIB_Y,
)


# -----------------------------------------------------------------------------
# gen_io_sch
# -----------------------------------------------------------------------------
def gen_io_sch() -> str:
    """IO sub-sheet — chord-east case-wall connectors (v0.19).

    The IO sub-sheet hosts the two connectors that live on the OAS PCB's
    chord-edge case-wall openings:

      J9 — Qwiic / Stemma QT expansion port (always populated)
        4-pin JST SH 1.0 mm pitch horizontal SMD socket. Standard Qwiic
        pinout (GND, +3.3V, SDA, SCL). Mates with any Sparkfun Qwiic
        or Adafruit Stemma QT cable. Connector mouth faces the chord
        edge so the cable plugs in from outside the case through the C2
        RJ45 / Ethernet opening.

      J10 — Native-USB recovery header (DNP by default)
        6-pin 2.54 mm vertical pin header. Solder pads exposed on the
        OAS PCB at the C3 case-wall opening; accessible via pogopin
        jig for emergency reflashing if both DevKitM-1 on-module USB-C
        ports are damaged. ESP32-C6 has no traditional JTAG/SWD; this
        header exposes the native USB-Serial-JTAG D-/D+ pair on
        GPIO 12 / 13, plus EN (chip reset) and GPIO 9 (BOOT strap).
        Pinout (pin 1 = north / cutout-interior, pin 6 = south / chord):
          J10.1 (top)    GND
          J10.2          +3V3   (sense / level reference)
          J10.3          USB_DM (GPIO 12, native USB D-)
          J10.4          USB_DP (GPIO 13, native USB D+)
          J10.5          EN     (chip enable / reset)
          J10.6 (bottom) BOOT   (GPIO 9, pull low to enter ROM bootloader)

      SW1 — Side-actuated tactile push-button (always populated)
        C&K PTS645VK392LFS right-angle THT SPST momentary. Lives at the
        chord edge in the AK-N-94 USB-C case-wall opening (left of C2).
        Pin 1 -> BTN net (ESP32-C6 GPIO 1), pin 2 -> GND. Firmware: short
        press cycles the LED ring brightness, long press restarts the MCU.

    Inter-sheet nets imported via hierarchical_label (matching sheet pins
    are declared on the root sheet's IO block, exported by the MCU sub-
    sheet which sources the underlying ESP32-C6 GPIOs):
      I2C_SDA      (bidirectional, J9 pin 3) — shared bus, MCU GPIO 6
      I2C_SCL      (input,         J9 pin 4) — shared bus, MCU GPIO 7
      USB_DM       (bidirectional, J10 pin 3) — MCU GPIO 12 (USB D-)
      USB_DP       (bidirectional, J10 pin 4) — MCU GPIO 13 (USB D+)
      EN           (input,         J10 pin 5) — MCU RST pin
      BOOT         (input,         J10 pin 6) — MCU GPIO 9 BOOT strap
      BTN          (output,        SW1 pin 1) — MCU GPIO 1 push-button

    +3V3 and GND join via global power symbols (same KiCad convention
    used in the power / mcu / sensors sub-sheets).

    Sourcing:
      - J9 PCB-side socket: JST SH SM04B-SRSS-TB (1.0 mm pitch, 4-pin,
        horizontal SMD with PCB-mount mech pads). Sparkfun PRT-14417,
        Adafruit 4209 — both ship the same JST genuine part. Compatible
        with any Sparkfun Qwiic or Adafruit Stemma QT cable assembly.
      - J10 PCB-side pads: stock 2.54 mm 6-pin THT pin header
        (Sullins PRPC006SAAN-RC or any compatible). DNP — only the pads
        are present on production boards; user solders a header before
        the first emergency flash if ever needed.
    """
    file_uuid = SHEET_FILE_UUIDS["io"]

    # =====================================================================
    # J9 — Qwiic JST SH 4-pin (always populated)
    # =====================================================================
    # Standard Qwiic pinout (Sparkfun convention, identical to Adafruit
    # Stemma QT): pin 1 = GND (BLACK wire), pin 2 = +3.3V (RED), pin 3
    # = SDA (BLUE), pin 4 = SCL (YELLOW).
    #
    # With angle=0 and Conn_01x04, lib pin Y maps to schem as:
    #   Pin 1 (top):    (J9_X - 5.08, J9_Y - 2.54) → GND
    #   Pin 2:          (J9_X - 5.08, J9_Y)        → +3V3
    #   Pin 3:          (J9_X - 5.08, J9_Y + 2.54) → SDA
    #   Pin 4 (bottom): (J9_X - 5.08, J9_Y + 5.08) → SCL
    J9_X = 95.25
    J9_Y = 82.55
    J9_PIN_X = J9_X - 5.08          # 90.17 — pin tip column
    J9_PIN_Y = {
        1: J9_Y - 2.54,             # 80.01 — GND
        2: J9_Y,                    # 82.55 — +3V3
        3: J9_Y + 2.54,             # 85.09 — SDA
        4: J9_Y + 5.08,             # 87.63 — SCL
    }

    # Hier label column for I²C signals exiting J9 to MCU sub-sheet.
    HLABEL_LEFT_X = 67.31           # west of J9 pin tips, with breathing room

    parts: list[str] = []

    # ----- J9 pin 1 (GND, top): hop WEST to GND power flag -----
    PWR_J9_GND_X = J9_PIN_X - 5.08  # 85.09
    parts.append(_sch_wire(J9_PIN_X, J9_PIN_Y[1], PWR_J9_GND_X, J9_PIN_Y[1], "j9-p1-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J9_GND_X, y=J9_PIN_Y[1], angle=270,
        reference="#PWR60",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr60-gnd-j9-p1",
        sheet_key="io",
    ))

    # ----- J9 pin 2 (+3V3): wire UP to +3V3 power flag -----
    PWR_J9_3V3_Y = J9_PIN_Y[2] - 3.81  # 78.74 — flag anchor above pin
    parts.append(_sch_wire(J9_PIN_X, PWR_J9_3V3_Y, J9_PIN_X, J9_PIN_Y[2], "j9-p2-3v3-up"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=J9_PIN_X, y=PWR_J9_3V3_Y, angle=0,
        reference="#PWR61",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr61-3v3-j9-p2",
        sheet_key="io",
    ))

    # ----- J9 pin 3 (SDA): wire WEST to I2C_SDA hier label -----
    parts.append(_sch_wire(J9_PIN_X, J9_PIN_Y[3], HLABEL_LEFT_X, J9_PIN_Y[3], "j9-p3-sda"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SDA", shape="bidirectional",
        x=HLABEL_LEFT_X, y=J9_PIN_Y[3], angle=180, justify="right",
        uuid_tag="sda-j9",
    ))

    # ----- J9 pin 4 (SCL): wire WEST to I2C_SCL hier label -----
    parts.append(_sch_wire(J9_PIN_X, J9_PIN_Y[4], HLABEL_LEFT_X, J9_PIN_Y[4], "j9-p4-scl"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SCL", shape="input",
        x=HLABEL_LEFT_X, y=J9_PIN_Y[4], angle=180, justify="right",
        uuid_tag="scl-j9",
    ))

    # =====================================================================
    # J10 — Native-USB recovery header (DNP)
    # =====================================================================
    # 6-pin 2.54 mm vertical pin header. Placed in the lower half of the
    # IO sheet. Uses _sch_conn_01x06 which lays out pin 1 at top (Y-5.08)
    # and pin 6 at bottom (Y+7.62). dnp=True so JLCPCB assembly skips the
    # part, but the pads + silk are still produced on the PCB.
    #
    # Pin assignment:
    #   J10.1 (top)    GND
    #   J10.2          +3V3
    #   J10.3          USB_DM
    #   J10.4          USB_DP
    #   J10.5          EN
    #   J10.6 (bottom) BOOT
    J10_X = 95.25
    J10_Y = 132.08             # south of J9 (J9_Y=82.55), gap ≈ 49 mm — room
                                # for J9's value-text label below + J10's
                                # ref label above
    J10_PIN_X = J10_X - 5.08    # 90.17 — pin tip column
    J10_PIN_Y = {
        1: J10_Y - 5.08,        # 127.00 — GND  (top)
        2: J10_Y - 2.54,        # 129.54 — +3V3
        3: J10_Y,               # 132.08 — USB_DM
        4: J10_Y + 2.54,        # 134.62 — USB_DP
        5: J10_Y + 5.08,        # 137.16 — EN
        6: J10_Y + 7.62,        # 139.70 — BOOT (bottom)
    }

    # ----- J10 pin 1 (GND, top): drop UP to GND flag -----
    # Flag at angle=180 (triangle points down). Anchor sits ABOVE pin 1.
    PWR_J10_GND_Y = J10_PIN_Y[1] - 3.81   # 123.19 — flag anchor above pin 1
    parts.append(_sch_wire(J10_PIN_X, PWR_J10_GND_Y, J10_PIN_X, J10_PIN_Y[1], "j10-p1-gnd-up"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=J10_PIN_X, y=PWR_J10_GND_Y, angle=180,
        reference="#PWR62",
        value_offset_x=0.0, value_offset_y=-3.81,
        uuid_tag="pwr62-gnd-j10-p1",
        sheet_key="io",
    ))

    # ----- J10 pin 2 (+3V3): wire WEST to +3V3 flag -----
    # GND on pin 1 takes the UP-direction flag; +3V3 on pin 2 hops west
    # to its own flag — the two flag labels stay 5+ mm apart so their
    # value-text doesn't collide on the rendered schematic.
    PWR_J10_3V3_X = J10_PIN_X - 5.08  # 85.09
    parts.append(_sch_wire(J10_PIN_X, J10_PIN_Y[2], PWR_J10_3V3_X, J10_PIN_Y[2], "j10-p2-3v3-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=PWR_J10_3V3_X, y=J10_PIN_Y[2], angle=270,
        reference="#PWR63",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr63-3v3-j10-p2",
        sheet_key="io",
    ))

    # ----- J10 pins 3..6 (signal lines): wire WEST to hier labels -----
    for pin_num, label_name, shape in [
        (3, "USB_DM", "bidirectional"),
        (4, "USB_DP", "bidirectional"),
        (5, "EN",     "input"),
        (6, "BOOT",   "input"),
    ]:
        py = J10_PIN_Y[pin_num]
        parts.append(_sch_wire(J10_PIN_X, py, HLABEL_LEFT_X, py, f"j10-p{pin_num}-{label_name.lower()}"))
        parts.append(_sch_hierarchical_label(
            name=label_name, shape=shape,
            x=HLABEL_LEFT_X, y=py, angle=180, justify="right",
            uuid_tag=f"{label_name.lower()}-j10",
        ))

    # =====================================================================
    # SW1 — side-actuated tactile push-button (v0.42)
    # =====================================================================
    # SW1 lives at the chord edge in the AK-N-94 USB-C case-wall opening
    # (PCB CUTOUTS "USBC", immediately left of C2). Stock Switch:SW_Push
    # is a horizontal 2-pin SPST momentary part. With angle=0:
    #   Pin 1 (left)  at (SW1_X - 5.08, SW1_Y) -> BTN net (ESP32-C6 GPIO 1)
    #   Pin 2 (right) at (SW1_X + 5.08, SW1_Y) -> GND
    # Firmware: short press cycles the LED ring brightness, long press
    # restarts the ESP32-C6.
    SW1_X = 95.25
    SW1_Y = 105.41              # open band between J9 (Y≈82) and J10 (Y≈132);
                                # 105.41 = 83 × 1.27 mm connection grid
    SW1_PIN1_X = SW1_X - 5.08   # 90.17 — left pin (BTN)
    SW1_PIN2_X = SW1_X + 5.08   # 100.33 — right pin (GND)

    # ----- SW1 pin 1 (BTN): wire WEST to the BTN hier label -----
    # shape="output": the button signal originates on this (IO) sheet and
    # exits to the MCU sub-sheet, which receives it as an input.
    parts.append(_sch_wire(SW1_PIN1_X, SW1_Y, HLABEL_LEFT_X, SW1_Y, "sw1-p1-btn"))
    parts.append(_sch_hierarchical_label(
        name="BTN", shape="output",
        x=HLABEL_LEFT_X, y=SW1_Y, angle=180, justify="right",
        uuid_tag="btn-sw1",
    ))

    # ----- SW1 pin 2 (GND): hop EAST to a GND power flag -----
    PWR_SW1_GND_X = SW1_PIN2_X + 5.08   # 105.41
    parts.append(_sch_wire(SW1_PIN2_X, SW1_Y, PWR_SW1_GND_X, SW1_Y, "sw1-p2-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_SW1_GND_X, y=SW1_Y, angle=90,
        reference="#PWR64",
        value_offset_x=3.81, value_offset_y=0.0,
        uuid_tag="pwr64-gnd-sw1-p2",
        sheet_key="io",
    ))

    # =====================================================================
    # Symbol instances
    # =====================================================================
    parts.append(_sch_conn_01x04(
        x=J9_X, y=J9_Y, angle=0,
        reference="J9",
        value="JST SH SM04B-SRSS-TB (Qwiic / Stemma QT)",
        uuid_tag="j9-qwiic",
        sheet_key="io",
    ))
    parts.append(_sch_conn_01x06(
        x=J10_X, y=J10_Y, angle=0,
        reference="J10",
        value="1x6 P2.54mm pin header — native USB recovery (DNP)",
        uuid_tag="j10-recovery",
        dnp=True,
        sheet_key="io",
    ))
    parts.append(_sch_sw_push(
        x=SW1_X, y=SW1_Y, angle=0,
        reference="SW1",
        value="C&K PTS645VK392LFS",
        uuid_tag="sw1-button",
        sheet_key="io",
    ))

    body = "\n".join(parts)
    return textwrap.dedent(f"""\
        (kicad_sch
        \t(version {SCH_VERSION})
        \t(generator "eeschema")
        \t(generator_version "{GEN_VERSION}")
        \t(uuid "{file_uuid}")
        \t(paper "A4")
        \t(lib_symbols
        {IO_LIB_SYMBOLS()}
        \t)
        {body}
        \t(embedded_fonts no)
        )
        """)


from boardgen._project_files import (
    gen_pro,
    gen_fp_lib_table,
    gen_sym_lib_table,
    gen_oas_symbol_library,
)

# -----------------------------------------------------------------------------
# Netlist post-processor (Option A from pre-routing-review v0.19 / C1)
# -----------------------------------------------------------------------------
#
# After boardgen emits oas.kicad_pcb (with every pad on net 0), we re-run
# `kicad-cli sch export netlist` to produce a KiCad-flavoured S-expression
# netlist describing every electrical net in the just-written schematic.
# We then parse that netlist and rewrite oas.kicad_pcb in-place so that
# every pad whose (footprint_reference, pad_number) appears in the netlist
# gets the matching (net <code> "<name>") clause. The net dictionary is
# also added to the PCB header so KiCad can reference net codes by ID.
#
# This is the script-driven equivalent of the user opening pcbnew and
# pressing F8 (Tools → Update PCB from Schematic). After this pass the
# PCB has full electrical linkage for every PCB-side footprint that has a
# matching schematic symbol — making the next-step copper routing
# meaningful.
#
# Footprints WITHOUT a matching schematic reference (mechanical-only
# refs like SENS1 / LDR1 / MOD1 / MOD2 / H1..H3 / ZT1..ZT4, plus any
# orphan socket footprints) keep their pads on net 0. Those refs are
# expected to remain mechanical and are excluded from the BOM (attr
# board_only / exclude_from_bom).


from boardgen._postprocess import (
    sync_pcb_nets_from_schematic,
    _parse_footprint_placements,
    check_z_clearance_violations,
    _build_pcb_ref_to_footprint,
    _build_lcsc_metadata_map,
    _apply_schematic_footprints,
    _apply_schematic_lcsc_metadata,
)


from boardgen._routing import (
    ROUTING_CHUNKS,
    apply_routing_to_pcb,
)


# -----------------------------------------------------------------------------
# Write everything
# -----------------------------------------------------------------------------
