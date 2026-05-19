"""
Generate the KiCad 10 base project for OAS (Open Ambient Sensor).

Produces:
  - oas.kicad_pro       (project; design rules tuned for JLCPCB)
  - oas.kicad_sch       (root schematic, references 4 sub-sheets)
  - power.kicad_sch     (power sub-sheet — input terminal J1 + power flags)
  - mcu.kicad_sch       (MCU sub-sheet)
  - sensors.kicad_sch   (sensors sub-sheet)
  - io.kicad_sch        (empty sub-sheet — chord connector cluster)
  - oas.kicad_pcb       (board outline on Edge.Cuts + 3 mounting holes)
  - libraries/oas.pretty/MountingHole_3.8mm_M3.kicad_mod  (custom footprint)

Geometry is derived from the SZOMK AK-N-94 manufacturer DXF:
  - PCB: Ø120 mm D-shape (arc R=60 + flat chord 82.6 mm at the bottom)
  - 3× M3 mounting holes (Ø3.8 mm) on pitch circle Ø110 mm
  - Origin = centre of the PCB outline circle = centroid of the pitch circle

In KiCad, +Y grows downward on screen, so the flat chord at +Y is visually
the *bottom edge* — matching CLAUDE.md ("flat chord on the bottom edge for
natural convection upward").
"""
import json
import math
import sys
import textwrap
import uuid
from pathlib import Path

from boardgen._common import (
    HERE,
    PCB_VERSION, SCH_VERSION, GEN_VERSION,
    OAS_NAME_SHORT, OAS_VERSION_LINE, OAS_REPO_URL,
    fmt,
    _OAS_NS, _seen_uuid_tags,
    sheet_context, U,
    ROOT_SHEET_UUID,
    SUBSHEETS, SHEET_BLOCK_UUIDS, SHEET_FILE_UUIDS,
    SUBSHEET_DISPLAY_NAMES, SUBSHEET_POSITIONS, SUBSHEET_SIZE,
    Context,
)
from boardgen._project import (
    PROJECT_NAME, PROJECT_SHORTNAME, PROJECT_DESCRIPTION, PROJECT_REPO,
    PROJECT_LICENSE_HW, PROJECT_LICENSE_FW,
    BOARD_REVISION, BOARD_RELEASE_DATE,
    EXTERNAL_MODULES,
    GPIO_ASSIGNMENTS, GPIO_RESERVED, GPIO_SPARE,
    ASSEMBLY_INSTRUCTIONS, CASE_VERIFICATION_CHECKLIST, LOCALLY_SOURCED_PARTS,
    PAGE_CENTRE_X, PAGE_CENTRE_Y,
    R_OUTLINE, CHORD, HALF_CHORD, Y_CHORD,
    R_PITCH, HOLE_OFFSET_X, HOLE_OFFSET_Y, HOLE_POSITIONS,
    EDGE_CUTS_WIDTH, HOLE_DIAMETER, COURTYARD_RADIUS,
    CABLE_HOLE_DIAMETER, CUTOUTS,
    fx, fy,
    SEN66_ANCHOR_X, SEN66_ANCHOR_Y, SEN66_ROTATION,
    SEN66_ZIPTIE_LOCAL, _sen66_local_to_pcb,
    J3_X, J3_Y, J3_ROTATION,
    LD2410_BODY_W, LD2410_BODY_H, LD2410_BODY_Z,
    LD2410_SILK_INSET, LD2410_SILK_INSET_CONN, LD2410_EMIT_SILK_OUTLINE,
    LD2410_ANTENNA_X_END, LD2410_CONNECTOR_X, LD2410_CONNECTOR_Y,
    LD2410_ANCHOR_X, LD2410_ANCHOR_Y, LD2410_ROTATION,
    _ld2410_local_to_pcb,
    J4_PCB_X, J4_PCB_Y, J4_PCB_ROTATION,
    ESP32_BODY_W, ESP32_BODY_L, ESP32_BODY_Z,
    ESP32_PIN_ROW_INSET, ESP32_PIN_PITCH, ESP32_PIN_COUNT_PER_ROW,
    ESP32_PIN_START_OFFSET,
    ESP32_ANCHOR_X, ESP32_ANCHOR_Y, ESP32_ROTATION,
    MIKROE2462_BODY_W, MIKROE2462_BODY_L, MIKROE2462_BODY_Z,
    MIKROE2462_PIN_ROW_INSET, MIKROE2462_PIN_PITCH,
    MIKROE2462_PIN_COUNT_PER_ROW, MIKROE2462_PIN_START_OFFSET,
    MIKROE2462_ANCHOR_X, MIKROE2462_ANCHOR_Y, MIKROE2462_ROTATION,
    J1_PCB_X, J1_PCB_Y, J1_PCB_ROTATION,
    J9_PCB_X, J9_PCB_Y, J9_PCB_ROTATION,
    J10_PCB_X, J10_PCB_Y, J10_PCB_ROTATION,
    LED_RING_RADIUS, LED_RING_COUNT, LED_RING_THETA_START_DEG,
    LED_RING_THETA_STEP_DEG, LED_RING_SKIP_INDICES, LED_RING_CAP_RADIAL_OFFSET,
    SK6812SIDE_BODY_W, SK6812SIDE_BODY_H, SK6812SIDE_BODY_Z,
    SK6812SIDE_PAD_PITCH, SK6812SIDE_PAD_WIDTH, SK6812SIDE_PAD_HEIGHT,
    SK6812SIDE_PAD_Y, SK6812SIDE_PAD_X_OFFSETS,
    _led_ring_position, _led_cap_position, _led_local_to_pcb,
)


from boardgen._footprints import (
    gen_mounting_hole_footprint,
    gen_sen66_mechanical_footprint,
    gen_ld2410_mechanical_footprint,
    gen_ziptie_hole_footprint,
    gen_sk6812_side_footprint,
    gen_cutouts,
    gen_daughterboard_mech_lib_file,
    gen_power_pcb_footprints,
    gen_sensors_pcb_footprints,
    gen_silk_labels,
    _read_kicad_lib_symbol,
)


from boardgen._pcb import gen_pcb

# -----------------------------------------------------------------------------
# 3) Hierarchical schematic — root + 4 per-function sub-sheets
# -----------------------------------------------------------------------------
# Per-sheet hierarchical sheet pins for the root sheet block. The matching
# hierarchical_label inside the sub-sheet binds the inter-sheet net by name.
# Format: list of (name, shape, x_offset, y_offset, angle) tuples where
# (x_offset, y_offset) is relative to the (sheet ...) block's anchor and
# angle is 180 for left-edge pins (pointing out left) or 0 for right-edge
# pins (pointing out right).
#
# Each block spans (x..x+sx, y..y+sy) in page-absolute mm:
#   power:   (50.8..88.9,   50.8..63.5)
#   mcu:     (101.6..139.7, 50.8..63.5)
#   sensors: (50.8..88.9,   88.9..101.6)
#   io:      (101.6..139.7, 88.9..101.6)
#
# Pins are added preemptively for chunk #4. The sensors / io sheets will
# emit matching hierarchical_label entities in chunks #5 and #6.
SUBSHEET_PINS: dict[str, list[tuple[str, str, float, float, int]]] = {
    "power": [],
    "mcu": [
        # name,        shape,           dx,   dy,    angle (180=left-edge, 0=right-edge)
        ("I2C_SDA",     "bidirectional", 0.0,  1.27, 180),
        ("I2C_SCL",     "output",        0.0,  3.81, 180),
        ("LD2410_OUT",  "input",         0.0,  6.35, 180),
        ("NFC_FD",      "input",         0.0,  8.89, 180),
        # v0.16: WS2812_DIN — MCU drives the SK6812-SIDE AQI status-LED
        # ring (chain of 12 LEDs in sensors sub-sheet). GPIO 8 → first
        # LED DIN. Exported as `output` from the MCU side. Placed on LEFT
        # edge alongside the other sensor-bound nets; matched against the
        # sensors sub-sheet's WS2812_DIN pin on the same edge for a
        # symmetric inter-sheet wire route (mirrors the NFC_FD pattern).
        ("WS2812_DIN",  "output",        0.0, 11.43, 180),
        ("UART_TX",     "output",        38.1, 1.27, 0),
        ("UART_RX",     "input",         38.1, 3.81, 0),
        # v0.19: IO-bound nets — exposed on J10 recovery header in the
        # IO sub-sheet so a field debugger can re-flash the ESP32-C6 via
        # native USB-Serial-JTAG (GPIO 12 = USB D-, GPIO 13 = USB D+) +
        # EN (chip reset) + BOOT (GPIO 9, drop low to enter ROM bootloader)
        # when both DevKitM-1 onboard USB-C ports are unavailable. Routed
        # out of MCU on the RIGHT edge alongside UART_TX/RX so the wires
        # take a short east-going run from U3 to the right page boundary.
        ("USB_DM",      "bidirectional", 38.1,  6.35, 0),
        ("USB_DP",      "bidirectional", 38.1,  8.89, 0),
        ("EN",          "output",        38.1, 11.43, 0),
        ("BOOT",        "output",        38.1, 13.97, 0),
    ],
    "sensors": [
        # name,        shape,           dx,   dy,    angle (180=left-edge, 0=right-edge)
        # I2C_SDA / I2C_SCL come in from the MCU sub-sheet. The hierarchical
        # merge by name is independent of geometry, so the side these sit on
        # is purely visual. We put them on the RIGHT edge to keep them clear
        # of the left-edge cluster on the MCU sheet block above.
        ("I2C_SDA",     "bidirectional", 38.1,  1.27, 0),
        ("I2C_SCL",     "input",         38.1,  3.81, 0),
        # chunk #5b: LD2410 mmWave radar — UART (256 kbd) + presence GPIO.
        # Directions are from the sensors-sub-sheet perspective and are
        # opposite-polarity to the matching mcu sub-sheet pins (see above).
        ("LD2410_OUT",  "output",        38.1,  6.35, 0),
        ("UART_TX",     "input",         38.1,  8.89, 0),
        ("UART_RX",     "output",        38.1, 11.43, 0),
        # chunk #5c: MIKROE-2462 NFC Tag 2 Click — field-detect interrupt.
        ("NFC_FD",      "output",         0.0,  6.35, 180),
        # v0.16: AQI status-LED ring input.
        ("WS2812_DIN",  "input",          0.0,  8.89, 180),
    ],
    # v0.19: IO sub-sheet — chord-east connectors (J9 Qwiic + J10 recovery).
    # I2C_SDA / I2C_SCL match the MCU exports (shared bus); USB_DM / USB_DP /
    # EN / BOOT come from MCU for the native-USB recovery header.
    "io": [
        ("I2C_SDA",     "bidirectional", 0.0,  1.27, 180),
        ("I2C_SCL",     "input",         0.0,  3.81, 180),
        ("USB_DM",      "bidirectional", 0.0,  6.35, 180),
        ("USB_DP",      "bidirectional", 0.0,  8.89, 180),
        ("EN",          "input",         0.0, 11.43, 180),
        ("BOOT",        "input",         0.0, 13.97, 180),
    ],
}


def _gen_sheet_pin(name: str, shape: str, x: float, y: float, angle: int, uuid_tag: str) -> str:
    """Emit a (pin ...) entry inside a root sheet block.

    `(at X Y angle)`: angle 180 = pin tip points LEFT (placed on the LEFT
    edge of the block); angle 0 = pin tip points RIGHT (RIGHT edge).
    `justify` follows the angle convention so the text never overlaps
    the block body.

    Indented to nest inside a (sheet ...) block (2 tabs base = inside the
    block's body, matching the other (property ...) entries).
    """
    justify = "right" if angle == 180 else "left"
    return (
        f"\t\t(pin \"{name}\" {shape}\n"
        f"\t\t\t(at {fmt(x)} {fmt(y)} {angle})\n"
        f"\t\t\t(uuid \"{U('sheetpin:'+uuid_tag)}\")\n"
        f"\t\t\t(effects\n"
        f"\t\t\t\t(font\n"
        f"\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t\t(justify {justify})\n"
        f"\t\t\t)\n"
        f"\t\t)"
    )


def _gen_sheet_block(name: str, page: int) -> str:
    """One (sheet ...) block placed on the root drawing.

    `name` is the lowercase key (power/mcu/sensors/io); the display name
    and file name are derived from it. `page` is the page number assigned
    in the root's project instance path (root itself is page 1, so the
    first sub-sheet starts at 2).
    """
    x, y = SUBSHEET_POSITIONS[name]
    sx, sy = SUBSHEET_SIZE
    display = SUBSHEET_DISPLAY_NAMES[name]
    block_uuid = SHEET_BLOCK_UUIDS[name]
    # Property anchor positions copied from the verified template
    # (Sheetname above the box, Sheetfile below it).
    name_y = y - 0.7116    # 50.8 -> 50.0884 in template
    file_y = y + sy + 0.4446  # 50.8 + 12.7 + 0.4446 = 63.9446
    # Sheet pins (per-net hierarchical ports). For chunk #4 only the MCU
    # block has pins; the other blocks remain empty until their sub-sheet
    # content is added.
    pin_entries = "\n".join(
        _gen_sheet_pin(
            pname, shape, x + dx, y + dy, angle,
            uuid_tag=f"{name}-{pname}",
        )
        for pname, shape, dx, dy, angle in SUBSHEET_PINS[name]
    )
    # Pin entries are already correctly indented at 2 tabs (nested inside
    # the (sheet ...) block). Prepend a newline so they appear on their own
    # lines, after the last (property ...) block and before (instances ...).
    pin_block = ("\n" + pin_entries) if pin_entries else ""
    # Build the (sheet ...) block with literal tabs (no textwrap.dedent so
    # the interpolated pin_block, whose lines do not share the template's
    # leading whitespace, remains correctly indented).
    return (
        f"\t(sheet\n"
        f"\t\t(at {fmt(x)} {fmt(y)})\n"
        f"\t\t(size {fmt(sx)} {fmt(sy)})\n"
        f"\t\t(exclude_from_sim no)\n"
        f"\t\t(in_bom yes)\n"
        f"\t\t(on_board yes)\n"
        f"\t\t(dnp no)\n"
        f"\t\t(fields_autoplaced yes)\n"
        f"\t\t(stroke\n"
        f"\t\t\t(width 0.1524)\n"
        f"\t\t\t(type solid)\n"
        f"\t\t)\n"
        f"\t\t(fill\n"
        f"\t\t\t(color 0 0 0 0.0000)\n"
        f"\t\t)\n"
        f"\t\t(uuid \"{block_uuid}\")\n"
        f"\t\t(property \"Sheetname\" \"{display}\"\n"
        f"\t\t\t(at {fmt(x)} {fmt(name_y)} 0)\n"
        f"\t\t\t(effects\n"
        f"\t\t\t\t(font\n"
        f"\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t\t(justify left bottom)\n"
        f"\t\t\t)\n"
        f"\t\t)\n"
        f"\t\t(property \"Sheetfile\" \"{name}.kicad_sch\"\n"
        f"\t\t\t(at {fmt(x)} {fmt(file_y)} 0)\n"
        f"\t\t\t(effects\n"
        f"\t\t\t\t(font\n"
        f"\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t\t(justify left top)\n"
        f"\t\t\t)\n"
        f"\t\t){pin_block}\n"
        f"\t\t(instances\n"
        f"\t\t\t(project \"oas\"\n"
        f"\t\t\t\t(path \"/{ROOT_SHEET_UUID}\"\n"
        f"\t\t\t\t\t(page \"{page}\")\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t)\n"
        f"\t)"
    )


def _root_wire(x1: float, y1: float, x2: float, y2: float, tag: str) -> str:
    """Emit a (wire ...) entity on the root schematic.

    Same shape as `_sch_wire`, but takes page-absolute mm coordinates
    (no fx/fy offset) since the root schematic uses A4 page space, and
    a separate uuid namespace tag prefix `root-wire:` so the UUIDs
    don't collide with sub-sheet wire UUIDs.
    """
    return textwrap.dedent(f"""\
        \t(wire
        \t\t(pts
        \t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})
        \t\t)
        \t\t(stroke
        \t\t\t(width 0)
        \t\t\t(type default)
        \t\t)
        \t\t(uuid "{U('root-wire:'+tag)}")
        \t)""")


def gen_root_sch() -> str:
    """Root schematic referencing the 4 per-function sub-sheets.

    Contains:
      - One (sheet ...) block per sub-sheet (power / mcu / sensors / io).
      - Inter-sheet wires connecting matching hierarchical sheet pins
        across sub-sheets, so KiCad's ERC sees each net as electrically
        connected at the parent level (not just at the per-sub-sheet
        label-matching level). Without these wires, ERC reports each
        sheet pin as "pin_not_connected" even though the underlying
        nets are joined by name.

    Inter-sheet wires added so far:
      - I2C_SDA  : MCU block left-edge pin (101.60, 52.07) ↔
                   Sensors block right-edge pin (88.9, 90.17)
      - I2C_SCL  : MCU block left-edge pin (101.60, 54.61) ↔
                   Sensors block right-edge pin (88.9, 92.71)

    Later chunks will add LD2410_OUT, NFC_FD (sensors→MCU), and
    UART_TX/UART_RX (MCU→sensors via LD2410 connector) as their sub-
    sheet content lands.
    """
    sheet_blocks = "\n".join(
        _gen_sheet_block(name, page)
        for page, name in enumerate(SUBSHEETS, start=2)
    )

    # Inter-sheet wires for nets present in BOTH MCU and Sensors blocks.
    # Each route: short east stub from sensors pin → vertical to MCU pin
    # row → short east stub into MCU pin.
    inter_wires: list[str] = []
    # I2C_SDA — sensors (88.9, 90.17) ↔ MCU (101.60, 52.07).
    # Vertical leg at X = 95.25 — clean midpoint between the right edge
    # of sensors block (X=88.9) and the left edge of MCU block (X=101.6).
    inter_wires.append(_root_wire(88.9, 90.17, 95.25, 90.17, "sda-east-from-sensors"))
    inter_wires.append(_root_wire(95.25, 90.17, 95.25, 52.07, "sda-vertical"))
    inter_wires.append(_root_wire(95.25, 52.07, 101.60, 52.07, "sda-east-into-mcu"))
    # I2C_SCL — sensors (88.9, 92.71) ↔ MCU (101.60, 54.61).
    # Vertical leg at X = 97.79 (offset from the SDA leg so the two
    # nets don't share a wire endpoint mid-route).
    inter_wires.append(_root_wire(88.9, 92.71, 97.79, 92.71, "scl-east-from-sensors"))
    inter_wires.append(_root_wire(97.79, 92.71, 97.79, 54.61, "scl-vertical"))
    inter_wires.append(_root_wire(97.79, 54.61, 101.60, 54.61, "scl-east-into-mcu"))
    # chunk #5b inter-sheet wires for the LD2410 nets.
    # LD2410_OUT — sensors right-edge (88.9, 95.25) ↔ MCU left-edge
    # (101.60, 57.15). Same simple east-stub / vertical / east-stub
    # routing as the I²C nets. Vertical leg at X=100.33 (next 2.54 mm
    # slot after the SCL vertical at 97.79; still 1.27 mm west of the
    # MCU block's left edge at 101.60).
    inter_wires.append(_root_wire(88.9, 95.25, 100.33, 95.25, "ldr-east-from-sensors"))
    inter_wires.append(_root_wire(100.33, 95.25, 100.33, 57.15, "ldr-vertical"))
    inter_wires.append(_root_wire(100.33, 57.15, 101.60, 57.15, "ldr-east-into-mcu"))
    # UART_TX / UART_RX — sensors right-edge ↔ MCU right-edge (139.7).
    # The MCU's UART pins sit on the right edge of its block because the
    # internal U3 symbol exposes GPIO16/17 on its right side. To reach
    # them, the wire goes east past the io block's right edge (139.7),
    # vertical up the east side of the page, then west into the MCU pin.
    #
    # v0.21 CROSSOVER FIX — the previous routing ran the east-going
    # horizontal segments at Y=97.79 (UART_TX) and Y=100.33 (UART_RX),
    # the SAME Y as the IO sub-sheet's USB_DP (Y=97.79) and EN (Y=100.33)
    # LEFT-edge sheet pins. The east-going UART wires X-range
    # [88.9..143.51 / 146.05] OVERLAPPED with the IO block's
    # west-into-io wires at the same Y, in X-range [101.6..156.21 /
    # 158.75]. The overlap zone X ∈ [101.6, 143.51 / 146.05] was where
    # KiCad merged UART_TX with USB_DP and UART_RX with EN, producing
    # bogus nets `/IO/USB_DP` (binding J4 pin 3 LD2410_RX with U3 pin 28
    # USB_DP) and `/IO/EN` (binding J4 pin 2 LD2410_TX with U3 pin 2
    # RST). Fix: route the UART east stub OUT of the IO-block-row Y
    # range first by stepping SOUTH off the sensors block bottom
    # (Y=106.68) to Y=110.49 (UART_TX) / Y=113.03 (UART_RX), then east
    # past the page-right column, then north to the MCU UART pins, then
    # west into the MCU block. The intermediate east stub at X=95.25
    # (UART_TX) / X=97.79 (UART_RX) sits between the sensors block right
    # edge (X=88.9) and the IO block left edge (X=101.6), avoiding any
    # overlap with the IO USB_DP / EN routes.
    # UART_TX route:
    inter_wires.append(_root_wire(88.9, 97.79, 95.25, 97.79, "uart-tx-east-stub"))
    inter_wires.append(_root_wire(95.25, 97.79, 95.25, 110.49, "uart-tx-south"))
    inter_wires.append(_root_wire(95.25, 110.49, 143.51, 110.49, "uart-tx-east-under-io"))
    inter_wires.append(_root_wire(143.51, 110.49, 143.51, 52.07, "uart-tx-vertical"))
    inter_wires.append(_root_wire(143.51, 52.07, 139.7, 52.07, "uart-tx-west-into-mcu"))
    # UART_RX route (parallel, one grid step south of UART_TX):
    inter_wires.append(_root_wire(88.9, 100.33, 97.79, 100.33, "uart-rx-east-stub"))
    inter_wires.append(_root_wire(97.79, 100.33, 97.79, 113.03, "uart-rx-south"))
    inter_wires.append(_root_wire(97.79, 113.03, 146.05, 113.03, "uart-rx-east-under-io"))
    inter_wires.append(_root_wire(146.05, 113.03, 146.05, 54.61, "uart-rx-vertical"))
    inter_wires.append(_root_wire(146.05, 54.61, 139.7, 54.61, "uart-rx-west-into-mcu"))
    # chunk #5c inter-sheet wire for NFC_FD.
    # NFC_FD — sensors left-edge (50.8, 95.25) ↔ MCU left-edge (101.60, 59.69).
    # Both pins on left side of their blocks (sensors at angle 180 dx=0,
    # MCU at angle 180 dx=0). Route: sensors LEFT stub goes WEST out of
    # the sensors block to a vertical leg at X=44.45, up past the
    # sensors block top edge (Y=88.9), then NORTHEAST across the empty
    # space below the power block to the MCU block's LEFT edge.
    inter_wires.append(_root_wire(50.8, 95.25, 44.45, 95.25, "nfc-fd-west-from-sensors"))
    inter_wires.append(_root_wire(44.45, 95.25, 44.45, 59.69, "nfc-fd-vertical"))
    inter_wires.append(_root_wire(44.45, 59.69, 101.60, 59.69, "nfc-fd-east-into-mcu"))
    # v0.16 inter-sheet wire for WS2812_DIN.
    # WS2812_DIN — sensors left-edge (50.8, 97.79) ↔ MCU left-edge
    # (101.60, 62.23). Same routing topology as NFC_FD but using a
    # parallel vertical leg at X=41.91 (one grid step west of the
    # NFC_FD leg at X=44.45) and matching horizontal Y rows so the two
    # nets stay visually separated.
    inter_wires.append(_root_wire(50.8, 97.79, 41.91, 97.79, "ws2812-din-west-from-sensors"))
    inter_wires.append(_root_wire(41.91, 97.79, 41.91, 62.23, "ws2812-din-vertical"))
    inter_wires.append(_root_wire(41.91, 62.23, 101.60, 62.23, "ws2812-din-east-into-mcu"))

    # v0.19 inter-sheet wires for the IO sub-sheet.
    # The IO block sits at (101.6, 88.9) size 38.1×17.78 — directly
    # BELOW the MCU block (101.6, 50.8). Sheet pins:
    #   IO left edge:  I2C_SDA (101.6, 90.17), I2C_SCL (101.6, 92.71),
    #                  USB_DM (101.6, 95.25), USB_DP (101.6, 97.79),
    #                  EN (101.6, 100.33), BOOT (101.6, 102.87)
    #   MCU right edge for new exports: USB_DM (139.7, 57.15),
    #                  USB_DP (139.7, 59.69), EN (139.7, 62.23),
    #                  BOOT (139.7, 64.77)
    #
    # ---- I2C bus extension to IO sub-sheet ----
    # Sensors→MCU I²C routing already exists at Y=90.17 / 92.71 with
    # the vertical legs at X=95.25 / 97.79. Extend each horizontal wire
    # east from those vertical legs into the IO block left edge at
    # X=101.60, sharing the same Y row. KiCad merges by wire-endpoint
    # contact, so a junction forms at (95.25, 90.17) / (97.79, 92.71).
    inter_wires.append(_root_wire(95.25, 90.17, 101.60, 90.17, "sda-east-into-io"))
    inter_wires.append(_root_wire(97.79, 92.71, 101.60, 92.71, "scl-east-into-io"))
    # ---- USB_DM / USB_DP / EN / BOOT — MCU right ↔ IO left ----
    # MCU pins on right edge (X=139.7), IO pins on left edge (X=101.6).
    # Route topology: east stub from MCU pin → vertical down EAST of
    # MCU/IO blocks → west stub into IO pin. Vertical legs at X=143.51,
    # 146.05, 148.59, 151.13 (one column per net, 2.54 mm apart).
    # Routing wraps around the east side of both blocks; the io block
    # right edge is at X=139.7 so the verticals at X=143.51+ stay clear.
    USB_DM_VERT_X = 153.67
    USB_DP_VERT_X = 156.21
    EN_VERT_X     = 158.75
    BOOT_VERT_X   = 161.29
    # USB_DM: MCU (139.7, 57.15) ↔ IO (101.6, 95.25)
    inter_wires.append(_root_wire(139.7, 57.15, USB_DM_VERT_X, 57.15, "usb-dm-east-from-mcu"))
    inter_wires.append(_root_wire(USB_DM_VERT_X, 57.15, USB_DM_VERT_X, 95.25, "usb-dm-vertical"))
    inter_wires.append(_root_wire(USB_DM_VERT_X, 95.25, 101.6, 95.25, "usb-dm-west-into-io"))
    # USB_DP: MCU (139.7, 59.69) ↔ IO (101.6, 97.79)
    inter_wires.append(_root_wire(139.7, 59.69, USB_DP_VERT_X, 59.69, "usb-dp-east-from-mcu"))
    inter_wires.append(_root_wire(USB_DP_VERT_X, 59.69, USB_DP_VERT_X, 97.79, "usb-dp-vertical"))
    inter_wires.append(_root_wire(USB_DP_VERT_X, 97.79, 101.6, 97.79, "usb-dp-west-into-io"))
    # EN: MCU (139.7, 62.23) ↔ IO (101.6, 100.33)
    inter_wires.append(_root_wire(139.7, 62.23, EN_VERT_X, 62.23, "en-east-from-mcu"))
    inter_wires.append(_root_wire(EN_VERT_X, 62.23, EN_VERT_X, 100.33, "en-vertical"))
    inter_wires.append(_root_wire(EN_VERT_X, 100.33, 101.6, 100.33, "en-west-into-io"))
    # BOOT: MCU (139.7, 64.77) ↔ IO (101.6, 102.87)
    inter_wires.append(_root_wire(139.7, 64.77, BOOT_VERT_X, 64.77, "boot-east-from-mcu"))
    inter_wires.append(_root_wire(BOOT_VERT_X, 64.77, BOOT_VERT_X, 102.87, "boot-vertical"))
    inter_wires.append(_root_wire(BOOT_VERT_X, 102.87, 101.6, 102.87, "boot-west-into-io"))
    wires_text = "\n".join(inter_wires)

    return textwrap.dedent(f"""\
        (kicad_sch
        \t(version {SCH_VERSION})
        \t(generator "eeschema")
        \t(generator_version "{GEN_VERSION}")
        \t(uuid "{ROOT_SHEET_UUID}")
        \t(paper "A4")
        \t(lib_symbols
        \t)
        """) + sheet_blocks + "\n" + wires_text + textwrap.dedent("""
        \t(sheet_instances
        \t\t(path "/"
        \t\t\t(page "1")
        \t\t)
        \t)
        \t(embedded_fonts no)
        )
        """)


def gen_subsheet_sch(name: str) -> str:
    """Empty per-function sub-sheet (just the file header + empty lib_symbols).

    Placeholder for upcoming per-function content (chunks #1b onward).
    """
    file_uuid = SHEET_FILE_UUIDS[name]
    return textwrap.dedent(f"""\
        (kicad_sch
        \t(version {SCH_VERSION})
        \t(generator "eeschema")
        \t(generator_version "{GEN_VERSION}")
        \t(uuid "{file_uuid}")
        \t(paper "A4")
        \t(lib_symbols
        \t)
        \t(embedded_fonts no)
        )
        """)


# -----------------------------------------------------------------------------
# 3b) Power sub-sheet — input terminal J1
# -----------------------------------------------------------------------------
# The five library symbols below are copied verbatim from KiCad 10's stock
# symbol libraries (GPL, freely redistributable, and embedded into every saved
# schematic by KiCad itself). They are taken from:
#   - C:\Program Files\KiCad\10.0\share\kicad\symbols\Connector.kicad_sym
#   - C:\Program Files\KiCad\10.0\share\kicad\symbols\power.kicad_sym
# Embedding them in our power.kicad_sch keeps the project self-contained: the
# .kicad_sch file can be opened on any machine without requiring the user's
# KiCad library path to be set correctly.
POWER_LIB_SYMBOLS = """\
\t\t(symbol "Connector:Screw_Terminal_01x03"
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "J"
\t\t\t\t(at 0 5.08 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "Screw_Terminal_01x03"
\t\t\t\t(at 0 -5.08 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Generic screw terminal, single row, 01x03, script generated (kicad-library-utils/schlib/autogen/connector/)"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "screw terminal"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "TerminalBlock*:*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Screw_Terminal_01x03_1_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 3.81)
\t\t\t\t\t(end 1.27 -3.81)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type background)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.5334 2.8702) (xy 0.3302 2.032)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.5334 0.3302) (xy 0.3302 -0.508)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.5334 -2.2098) (xy 0.3302 -3.048)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.3556 3.048) (xy 0.508 2.2098)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.3556 0.508) (xy 0.508 -0.3302)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.3556 -2.032) (xy 0.508 -2.8702)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 0 2.54)
\t\t\t\t\t(radius 0.635)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 0 0)
\t\t\t\t\t(radius 0.635)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 0 -2.54)
\t\t\t\t\t(radius 0.635)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 2.54 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 0 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 -2.54 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:+24V"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "+24V"
\t\t\t\t(at 0 3.556 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"+24V\\""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+24V_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.762 1.27) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 2.54) (xy 0.762 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+24V_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:GND"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "GND"
\t\t\t\t(at 0 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"GND\\" , ground"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "GND_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "GND_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 270)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:Earth_Protective"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -10.16 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "Earth_Protective"
\t\t\t\t(at 0 -7.62 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"Earth_Protective\\""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global ground gnd clean"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Earth_Protective_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.635 -4.445) (xy 0.635 -4.445)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.127 -5.08) (xy 0.127 -5.08)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 -3.81) (xy 0 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 0 -3.81)
\t\t\t\t\t(radius 2.54)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 1.27 -3.81) (xy -1.27 -3.81)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Earth_Protective_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 270)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:PWR_FLAG"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#FLG"
\t\t\t\t(at 0 1.905 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "PWR_FLAG"
\t\t\t\t(at 0 3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Special symbol for telling ERC where power comes from"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "flag power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "PWR_FLAG_0_0"
\t\t\t\t(pin power_out line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "PWR_FLAG_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "OAS:Q_PMOS_GDS"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "Q"
\t\t\t\t(at 5.08 1.27 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "Q_PMOS"
\t\t\t\t(at 5.08 -1.27 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 5.08 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "P-MOSFET transistor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "PMOS P-MOS"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Q_PMOS_GDS_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.254 1.905) (xy 0.254 -1.905)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.254 0) (xy -2.54 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.762 2.286) (xy 0.762 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.762 1.778) (xy 3.302 1.778) (xy 3.302 -1.778) (xy 0.762 -1.778)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.762 0.508) (xy 0.762 -0.508)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.762 -1.27) (xy 0.762 -2.286)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 1.651 0)
\t\t\t\t\t(radius 2.794)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 2.286 0) (xy 1.27 0.381) (xy 1.27 -0.381) (xy 2.286 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type outline)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 2.54 2.54) (xy 2.54 1.778)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 2.54 1.778)
\t\t\t\t\t(radius 0.254)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type outline)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(circle
\t\t\t\t\t(center 2.54 -1.778)
\t\t\t\t\t(radius 0.254)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type outline)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 2.54 -2.54) (xy 2.54 0) (xy 0.762 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 2.921 -0.381) (xy 3.683 -0.381)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 3.302 -0.381) (xy 2.921 0.254) (xy 3.683 0.254) (xy 3.302 -0.381)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Q_PMOS_GDS_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 2.54 5.08 270)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "D"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin input line
\t\t\t\t\t(at -5.08 0 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "G"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 2.54 -5.08 90)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "S"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:R"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "R"
\t\t\t\t(at 2.032 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "R"
\t\t\t\t(at 0 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at -1.778 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Resistor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "R res resistor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "R_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "R_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.016 -2.54)
\t\t\t\t\t(end 1.016 2.54)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "R_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:Polyfuse"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "F"
\t\t\t\t(at -2.54 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "Polyfuse"
\t\t\t\t(at 2.54 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 1.27 -5.08 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Resettable fuse, polymeric positive temperature coefficient"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "resettable fuse PTC PPTC polyfuse polyswitch"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "*polyfuse* *PTC*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Polyfuse_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.524 2.54) (xy -1.524 1.524) (xy 1.524 -1.524) (xy 1.524 -2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -0.762 2.54)
\t\t\t\t\t(end 0.762 -2.54)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 2.54) (xy 0 -2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Polyfuse_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:D_TVS"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "D"
\t\t\t\t(at 0 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "D_TVS"
\t\t\t\t(at 0 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Bidirectional transient-voltage-suppression diode"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "diode TVS thyrector"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "TO-???* *_Diode_* *SingleDiode* D_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "D_TVS_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -2.54 1.27) (xy -2.54 -1.27) (xy 2.54 1.27) (xy 2.54 -1.27) (xy -2.54 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0.508 1.27) (xy 0 1.27) (xy 0 -1.27) (xy -0.508 -1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 1.27 0) (xy -1.27 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "D_TVS_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at -3.81 0 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "A1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 3.81 0 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "A2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:D_Zener"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "D"
\t\t\t\t(at 0 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "D_Zener"
\t\t\t\t(at 0 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Zener diode"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "diode"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "TO-???* *_Diode_* *SingleDiode* D_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "D_Zener_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.27 -1.27) (xy -1.27 1.27) (xy -0.762 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 1.27 0) (xy -1.27 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 1.27 -1.27) (xy 1.27 1.27) (xy -1.27 0) (xy 1.27 -1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "D_Zener_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at -3.81 0 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "K"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 3.81 0 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "A"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:C"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0.254)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "C"
\t\t\t\t(at 0.635 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "C"
\t\t\t\t(at 0.635 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0.9652 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Unpolarized capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "cap capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "C_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -2.032 0.762) (xy 2.032 0.762)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.508)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -2.032 -0.762) (xy 2.032 -0.762)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.508)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:C_Polarized"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0.254)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "C"
\t\t\t\t(at 0.635 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "C_Polarized"
\t\t\t\t(at 0.635 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0.9652 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Polarized capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "cap capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "CP_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_Polarized_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -2.286 0.508)
\t\t\t\t\t(end 2.286 1.016)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.778 2.286) (xy -0.762 2.286)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.27 2.794) (xy -1.27 1.778)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start 2.286 -0.508)
\t\t\t\t\t(end -2.286 -1.016)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type outline)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_Polarized_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:+5V"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "+5V"
\t\t\t\t(at 0 3.556 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"+5V\\""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+5V_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.762 1.27) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 2.54) (xy 0.762 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+5V_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:+3V3"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "+3V3"
\t\t\t\t(at 0 3.556 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"+3V3\\""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+3V3_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.762 1.27) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 2.54) (xy 0.762 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+3V3_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:L"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "L"
\t\t\t\t(at -1.27 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "L"
\t\t\t\t(at 1.905 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Inductor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "inductor choke coil reactor magnetic"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "Choke_* *Coil* Inductor_* L_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "L_0_1"
\t\t\t\t(arc
\t\t\t\t\t(start 0 2.54)
\t\t\t\t\t(mid 0.6323 1.905)
\t\t\t\t\t(end 0 1.27)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(arc
\t\t\t\t\t(start 0 1.27)
\t\t\t\t\t(mid 0.6323 0.635)
\t\t\t\t\t(end 0 0)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(arc
\t\t\t\t\t(start 0 0)
\t\t\t\t\t(mid 0.6323 -0.635)
\t\t\t\t\t(end 0 -1.27)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(arc
\t\t\t\t\t(start 0 -1.27)
\t\t\t\t\t(mid 0.6323 -1.905)
\t\t\t\t\t(end 0 -2.54)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "L_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:D_Schottky"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "D"
\t\t\t\t(at 0 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "D_Schottky"
\t\t\t\t(at 0 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Schottky diode"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "diode Schottky"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "TO-???* *_Diode_* *SingleDiode* D_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "D_Schottky_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.905 0.635) (xy -1.905 1.27) (xy -1.27 1.27) (xy -1.27 -1.27) (xy -0.635 -1.27) (xy -0.635 -0.635)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 1.27 1.27) (xy 1.27 -1.27) (xy -1.27 0) (xy 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 1.27 0) (xy -1.27 0)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "D_Schottky_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at -3.81 0 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "K"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 3.81 0 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "A"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Regulator_Switching:LM2596S-5"
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "U"
\t\t\t\t(at -10.16 6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "LM2596S-5"
\t\t\t\t(at 0 6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" "Package_TO_SOT_SMD:TO-263-5_TabPin3"
\t\t\t\t(at 1.27 -6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t(italic yes)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" "http://www.ti.com/lit/ds/symlink/lm2596.pdf"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "5V 3A Step-Down Voltage Regulator, TO-263"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "Step-Down Voltage Regulator 5V 3A"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "TO?263*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "LM2596S-5_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -10.16 5.08)
\t\t\t\t\t(end 10.16 -5.08)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type background)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "LM2596S-5_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at -12.7 2.54 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "VIN"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin output line
\t\t\t\t\t(at 12.7 -2.54 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "OUT"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 -7.62 90)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GND"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin input line
\t\t\t\t\t(at 12.7 2.54 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "FB"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "4"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin input line
\t\t\t\t\t(at -12.7 -2.54 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "~{ON}/OFF"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "5"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Regulator_Switching:TPS62933"
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 13.97 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "TPS62933"
\t\t\t\t(at 0 11.43 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" "Package_TO_SOT_SMD:SOT-583-8"
\t\t\t\t(at 0 -25.4 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps62933.pdf"
\t\t\t\t(at 0 -22.86 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "3.8-30V, 3A Synchronous Buck Converters with pulse frequency modulation (PFM), SOT583-8"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "synchronous buck converter pulse frequency modulation"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "SOT?583*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "TPS62933_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -5.08 10.16)
\t\t\t\t\t(end 5.08 -10.16)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type background)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "TPS62933_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at -7.62 -5.08 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "RT"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin input line
\t\t\t\t\t(at -7.62 5.08 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "EN"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin power_in line
\t\t\t\t\t(at -7.62 7.62 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "VIN"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 -12.7 90)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GND"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "4"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin output line
\t\t\t\t\t(at 7.62 0 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "SW"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "5"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 7.62 7.62 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "BST"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "6"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -7.62 -2.54 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "SS"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "7"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin input line
\t\t\t\t\t(at 7.62 -7.62 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "FB"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "8"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)"""


# -----------------------------------------------------------------------------
# Helpers for symbol/wire/junction emission in power.kicad_sch
# -----------------------------------------------------------------------------
def _sch_wire(x1: float, y1: float, x2: float, y2: float, tag: str) -> str:
    return textwrap.dedent(f"""\
        \t(wire
        \t\t(pts
        \t\t\t(xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})
        \t\t)
        \t\t(stroke
        \t\t\t(width 0)
        \t\t\t(type default)
        \t\t)
        \t\t(uuid "{U('wire:'+tag)}")
        \t)""")


def _sch_junction(x: float, y: float, tag: str) -> str:
    return textwrap.dedent(f"""\
        \t(junction
        \t\t(at {fmt(x)} {fmt(y)})
        \t\t(diameter 0)
        \t\t(color 0 0 0 0)
        \t\t(uuid "{U('junction:'+tag)}")
        \t)""")


def _sch_power_flag(
    lib_id: str, value: str, x: float, y: float, angle: int,
    reference: str, value_offset_x: float, value_offset_y: float, uuid_tag: str,
    sheet_key: str = "power",
) -> str:
    """Emit a power-symbol instance (+24V / GND / Earth_Protective / PWR_FLAG).

    `value_offset_x/y` give the Value-label position relative to (x, y) in
    schematic mm — chosen empirically per symbol so the visible label
    matches the symbol's default placement convention.

    `sheet_key` selects which sub-sheet's hierarchical path is recorded in
    the symbol's instance block. Defaults to "power" for compatibility with
    the existing power-section calls; the MCU sub-sheet passes "mcu".
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuid = U("sym-pin:" + uuid_tag)
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "{lib_id}")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x)} {fmt(y - 3.81)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + value_offset_x)} {fmt(y + value_offset_y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_q_pmos(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a P-MOSFET (Device:Q_PMOS) symbol instance.

    Pin numbers in the stock Device:Q_PMOS are letters: "D", "G", "S".
    With angle=0, lib pin positions map to schematic as:
      D pin: (x + 2.54, y - 5.08)   [upper-right of body]
      G pin: (x - 5.08, y)          [left of body]
      S pin: (x + 2.54, y + 5.08)   [lower-right of body]
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_d_uuid = U("sym-pin:" + uuid_tag + "-d")
    pin_g_uuid = U("sym-pin:" + uuid_tag + "-g")
    pin_s_uuid = U("sym-pin:" + uuid_tag + "-s")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "OAS:Q_PMOS_GDS")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 5.08)} {fmt(y - 2.54)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 5.08)} {fmt(y + 0.0)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "3"
        \t\t\t(uuid "{pin_d_uuid}")
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin_g_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin_s_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_resistor(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
    sheet_key: str = "power",
) -> str:
    """Emit a resistor (Device:R) symbol instance.

    With angle=0, lib pin positions map to schematic as:
      Pin 1 (top):    (x, y - 3.81)
      Pin 2 (bottom): (x, y + 3.81)

    `sheet_key` selects which sub-sheet's hierarchical path is recorded in
    the symbol's instance block. Defaults to "power"; the MCU sub-sheet
    passes "mcu" for its I2C pull-ups.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Device:R")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y + 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 90)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_polyfuse(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a polyfuse (Device:Polyfuse) symbol instance.

    With angle=0, lib pin positions map to schematic as:
      Pin 1 (top):    (x, y - 3.81)
      Pin 2 (bottom): (x, y + 3.81)

    Reference text is placed to the left of the symbol, value text to the
    right, matching the stock symbol convention (which has Reference at
    lib (-2.54, 0, 90) and Value at lib (2.54, 0, 90)).
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Device:Polyfuse")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y - 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y + 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_diode_tvs(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a TVS diode (Device:D_TVS) symbol instance.

    The stock Device:D_TVS symbol is the two-headed bidirectional TVS body
    shape with horizontal pins A1 (pin 1) and A2 (pin 2) at lib (-3.81, 0)
    and (3.81, 0). For our unidirectional SMBJ24A part the symbol's drawn
    "back-to-back" geometry is just KiCad's convention for the TVS class —
    the actual part's polarity is encoded in the footprint and BOM value.

    With angle=90 (CCW 90° rotation in lib coords -> CW 90° on screen),
    lib pin positions map to schematic as:
      Pin 2 (top):    (x, y - 3.81)
      Pin 1 (bottom): (x, y + 3.81)

    Reference text is placed to the right of the body, value text below it
    on the same side. The property at-angle is set to compensate for the
    symbol rotation so the labels render horizontal on screen even when
    the symbol body is rotated: KiCad's renderer applies the symbol's
    rotation on top of the property's local-frame angle, so we subtract
    the symbol angle here (mod 360) to keep the effective text rotation
    at 0° on the page.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    # Compensation so labels render horizontal regardless of symbol rotation.
    text_angle = (-angle) % 360
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Device:D_TVS")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced no)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y - 1.27)} {text_angle})
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y + 1.27)} {text_angle})
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_capacitor(
    lib_id: str, x: float, y: float, angle: int,
    reference: str, value: str, uuid_tag: str,
    sheet_key: str = "power",
) -> str:
    """Emit a capacitor (Device:C or Device:C_Polarized) symbol instance.

    Both stock symbols share the same property/pin layout — pin 1 at lib
    (0, +3.81) and pin 2 at lib (0, -3.81), with Reference text at lib
    (0.635, +2.54) and Value text at lib (0.635, -2.54), both left-justified.

    With angle=0, lib pin positions map to schematic as:
      Pin 1 (top):    (x, y - 3.81)
      Pin 2 (bottom): (x, y + 3.81)

    For Device:C_Polarized the pin 1 is the ANODE (+, top in default
    orientation) and pin 2 is the CATHODE (-, bottom). The filled
    rectangle on the bottom plate marks the cathode side.

    `sheet_key` selects which sub-sheet's hierarchical path is recorded in
    the symbol's instance block. Defaults to "power".
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "{lib_id}")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y + 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_inductor(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit an inductor (Device:L) symbol instance.

    With angle=0, lib pin positions map to schematic as:
      Pin 1 (top):    (x, y - 3.81)
      Pin 2 (bottom): (x, y + 3.81)

    Reference text is placed to the LEFT of the body, value text to the RIGHT,
    matching the stock symbol convention (Reference at lib (-1.27, 0, 90) and
    Value at lib (1.905, 0, 90)). The property text-angle is set to 0 so the
    labels render horizontal regardless of the symbol's rotation angle.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Device:L")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x - 2.54)} {fmt(y - 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify right)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 1.27)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_diode_schottky(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a Schottky diode (Device:D_Schottky) symbol instance.

    Pin 1 in the stock symbol is the cathode K (lib (-3.81, 0)), pin 2 is the
    anode A (lib (3.81, 0)). With angle=270 (CW 90° rotation in schematic
    Y-flipped coords), lib pin positions map to schematic as:
      Pin 1 K (top, cathode): (x, y - 3.81)
      Pin 2 A (bottom, anode): (x, y + 3.81)

    This is the standard catch-diode orientation for a buck converter — the
    cathode faces UP toward the switch node, the anode faces DOWN to GND.

    Reference text is placed to the right of the body, value text below it
    on the same side. The property at-angle is set to 0 so labels render
    horizontal regardless of symbol rotation.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    text_angle = (-angle) % 360
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Device:D_Schottky")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced no)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y - 1.27)} {text_angle})
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y + 1.27)} {text_angle})
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_diode_zener(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a Zener diode (Device:D_Zener) symbol instance.

    Pin 1 in the stock symbol is the cathode K (lib (-3.81, 0)), pin 2 is the
    anode A (lib (3.81, 0)). With angle=270 (CW 90° rotation in schematic
    Y-flipped coords), lib pin positions map to schematic as:
      Pin 1 K (top, cathode): (x, y - 3.81)
      Pin 2 A (bottom, anode): (x, y + 3.81)

    For the Q1 gate-source clamp, the cathode faces UP (toward Q1.S / VIN
    net) and the anode faces DOWN (toward the R4/R1 junction on the gate
    side). When the gate-source voltage tries to exceed -10 V (gate well
    below source), the Zener breaks down in reverse and clamps the gate-
    side junction to V_S - 10 V, keeping |Vgs| within the AO3401A's
    +/-12 V absolute maximum (v0.37 — was 18 V Zener pre-fix; v0.36
    swap PMV65XP → AO3401A exposed the Vgs_max regression).

    Reference text is placed to the right of the body, value text below it
    on the same side. The property at-angle is set so labels render
    horizontal regardless of symbol rotation (text_angle = -angle mod 360).
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    text_angle = (-angle) % 360
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Device:D_Zener")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced no)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y - 1.27)} {text_angle})
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 3.81)} {fmt(y + 1.27)} {text_angle})
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_buck_lm2596_5(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a LM2596S-5 buck regulator symbol instance.

    With angle=0 (no rotation), lib pin positions map to schematic as:
      Pin 1 VIN     (left, top):    (x - 12.7, y - 2.54)
      Pin 2 OUT     (right, bot):   (x + 12.7, y + 2.54)
      Pin 3 GND     (centre, bot):  (x,        y + 7.62)
      Pin 4 FB      (right, top):   (x + 12.7, y - 2.54)
      Pin 5 ON/OFF  (left, bot):    (x - 12.7, y + 2.54)

    The symbol body is a rectangle (lib -10.16, -5.08) to (10.16, 5.08) — i.e.
    20.32 mm wide × 10.16 mm tall on the schematic.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    pin3_uuid = U("sym-pin:" + uuid_tag + "-3")
    pin4_uuid = U("sym-pin:" + uuid_tag + "-4")
    pin5_uuid = U("sym-pin:" + uuid_tag + "-5")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Regulator_Switching:LM2596S-5")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x - 10.16)} {fmt(y - 6.35)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x)} {fmt(y - 6.35)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" "Package_TO_SOT_SMD:TO-263-5_TabPin3"
        \t\t\t(at {fmt(x + 1.27)} {fmt(y + 6.35)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t(italic yes)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "http://www.ti.com/lit/ds/symlink/lm2596.pdf"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(pin "3"
        \t\t\t(uuid "{pin3_uuid}")
        \t\t)
        \t\t(pin "4"
        \t\t\t(uuid "{pin4_uuid}")
        \t\t)
        \t\t(pin "5"
        \t\t\t(uuid "{pin5_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_buck_tps62933(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit a TPS62933 (synchronous buck regulator) symbol instance.

    8-pin device. With angle=0, lib pin positions map to schematic as:
      Pin 1 RT  (left, bottom):       (x - 7.62, y + 5.08)
      Pin 2 EN  (left, top):          (x - 7.62, y - 5.08)
      Pin 3 VIN (left, top-most):     (x - 7.62, y - 7.62)
      Pin 4 GND (centre, bottom):     (x,        y + 12.7)
      Pin 5 SW  (right, centre):      (x + 7.62, y)
      Pin 6 BST (right, top):         (x + 7.62, y - 7.62)
      Pin 7 SS  (left, mid-bottom):   (x - 7.62, y + 2.54)
      Pin 8 FB  (right, bottom):      (x + 7.62, y + 7.62)

    The symbol body is a rectangle (lib -5.08, -10.16) to (5.08, 10.16) — i.e.
    10.16 mm wide × 20.32 mm tall on the schematic.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    pin3_uuid = U("sym-pin:" + uuid_tag + "-3")
    pin4_uuid = U("sym-pin:" + uuid_tag + "-4")
    pin5_uuid = U("sym-pin:" + uuid_tag + "-5")
    pin6_uuid = U("sym-pin:" + uuid_tag + "-6")
    pin7_uuid = U("sym-pin:" + uuid_tag + "-7")
    pin8_uuid = U("sym-pin:" + uuid_tag + "-8")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Regulator_Switching:TPS62933")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x - 5.08)} {fmt(y - 11.43)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 1.27)} {fmt(y - 11.43)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" "Package_TO_SOT_SMD:SOT-583-8"
        \t\t\t(at {fmt(x)} {fmt(y + 12.7)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t(italic yes)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps62933.pdf"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{pin2_uuid}")
        \t\t)
        \t\t(pin "3"
        \t\t\t(uuid "{pin3_uuid}")
        \t\t)
        \t\t(pin "4"
        \t\t\t(uuid "{pin4_uuid}")
        \t\t)
        \t\t(pin "5"
        \t\t\t(uuid "{pin5_uuid}")
        \t\t)
        \t\t(pin "6"
        \t\t\t(uuid "{pin6_uuid}")
        \t\t)
        \t\t(pin "7"
        \t\t\t(uuid "{pin7_uuid}")
        \t\t)
        \t\t(pin "8"
        \t\t\t(uuid "{pin8_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def gen_power_sch() -> str:
    """Power sub-sheet — J1 input + D1 surge clamp + Q1 reverse-polarity + R4/D3 Vgs clamp + R1 pulldown + F1 polyfuse + C1/C2 caps + U1 24V->5V buck.

    Power flow runs LEFT-TO-RIGHT and UPWARD on screen:

        J1 (input) ──┬── Q1.S → Q1.D → F1 → +24V (protected rail, exits up-right)
                     │     │            ↑
                     │     │            D3 (10V Zener, cathode → S net,
                     │     │                 anode → R4/R1 junction)
                     │     │
                     │     Q1.G → R4 (1k series) → (junction) → R1 (100k) → GND
                     │                              │
                     │                              D3.anode lands here
                     │
                     D1 (TVS surge clamp, shunts excess voltage to GND below)
                     │
                     └── J1.2 (GND), J1.3 (PE) — drop down to their own flags

    The TVS D1 sits BEFORE Q1 in the chain (tap point on the J1.1 → Q1.S
    wire). A surge that exceeds Q1's Vds_max would destroy Q1 before its
    reverse-polarity function could engage, so D1 must clamp upstream of
    Q1. SMBJ24A clamps at ~38.9V at 1A peak, leaving comfortable margin
    below Q1's absolute maximum (AO3401A Vds_max = -30V; comfortable
    margin even at the worst-case 38.9V clamp event).

    The Q1 gate-source clamp (R4 + D3) is mandatory because AO3401A
    (v0.36 swap from PMV65XP) has Vgs_max = +/-12V, while the natural
    pull-down through R1 alone would set Vgs = -24V at the 24V supply,
    exceeding the absolute max. With D3 (10V Zener, v0.37 — was 18V
    pre-fix) shunting the gate-side junction to source whenever the
    gate tries to drop more than 10V below source, |Vgs| is clamped
    to <=10V (2V margin under AO3401A's ±12V limit; AND optimal
    Rds_on operating point at Vgs=-10V). R4 (1k) provides series
    isolation in the gate path.

    Layout (page-absolute mm, KiCad +Y is down on screen):

        - J1 placed on the LEFT (mirror_y so pins face RIGHT into the circuit)
        - D1 mid-VIN (angle=90, body vertical), top pin on VIN wire, bottom
          pin drops to a local GND symbol. No new PWR_FLAG sentinel — the
          existing GND sentinel on J1.2 covers the global GND net.
        - Q1 placed to the right of D1, angle=0:
            Q1.D on top  → wire goes UP through F1 to the +24V power flag
            Q1.S on bottom-right (Y aligns with J1.1)
            Q1.G on left side → wire drops DOWN through R4 (series) →
                                R4/R1 junction → R1 (pulldown) → GND.
                                (Crosses J1.1 row at X=Q1_G_X without a
                                 junction — KiCad convention for the
                                 non-connected crossing.)
        - R4 (1k, series gate resistor) directly below Q1.G in the same
          column as R1. Body fits in clear Y band between VIN row (93.98)
          and the R4/R1 junction.
        - R1 (100k, gate pulldown) below R4; R1.bot → dedicated GND flag.
        - D3 (10V Zener, angle=270) placed LEFT of the R4/R1 column with
          its CATHODE wired UP to the VIN net (Q1.S side, via a T-tap on
          the existing vin-horiz wire) and its ANODE wired DOWN-and-RIGHT
          via an L-route to the R4/R1 junction. Clamp current at steady
          state flows S -> D3 (reverse breakdown at Vz=10V) -> junction
          -> R1 -> GND, drawing only (24V - 10V) / 100k = 0.14 mA
          (P_D3 = 1.4 mW, 143x under BZT52C10S 200 mW rating). R4
          (1 kohm gate series) carries NO steady-state current because
          gate is DC high-impedance (Igss <= 100 nA). v0.40 post-order
          math fix: pre-fix said "14 mA × 10 V = 140 mW" — used R4 (1k)
          instead of R1 (100k) for the current loop, off by 100x.
        - F1 above Q1.D, vertical Polyfuse
        - +24V flag, GND flag, Earth_Protective flag — each in its own column
          with ≥15 mm horizontal spacing between independent columns so the
          value-text labels of adjacent symbols cannot overlap.
        - PWR_FLAG sentinels are placed on each power net AT a junction
          on the main wire, with their Value-text offset SIDEWAYS (to the
          right of the symbol) so they never stack vertically with the
          power-flag's Value-text. This was the bug causing label overlap
          in the previous layout.
        - C1 (bulk electrolytic, 100uF 50V) sits in its OWN column to the
          right of F1, tapping the protected +24V rail at the F1.top pin
          and dropping to a local GND symbol. The horizontal +24V tap wire
          terminates at the F1.top pin, where the f1-to-junc24v wire
          continues upward to the +24V flag — a junction dot marks the
          three-way connection.
        - C2 (Y2 ceramic, 10nF Y2) closes the EMI loop between circuit
          GND and the PE conductor. Placed in clear space LEFT of the
          GND flag column with C2.top wired horizontally east to the
          Earth_Protective flag pin and C2.bot wired south-then-east to
          the existing GND horizontal at COL_GND. A junction dot at
          (COL_GND, GND_HORIZ_Y) marks the three-way GND tap.
    """
    file_uuid = SHEET_FILE_UUIDS["power"]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"

    # ----- Page-frame fit shift -----
    # Uniform offset applied to every BASE position anchor in this function
    # so the whole power section fits inside the A4 drawing-sheet frame
    # (297 x 210 mm, usable inner area roughly X=10..280, Y=10..195 with a
    # title block reserved at the bottom-right corner X=200..297, Y=170..210).
    #
    # The schematic grew organically through chunks #1a..#1h, accumulating
    # rightward (24V protection -> 5V buck -> 3.3V buck) and downward
    # (the 3.3V cascade sits below the protection block). The latest
    # additions pushed COL_3V3 to X=279.40 (PWR_FLAG value-text would
    # render at X=279.40 + 5.08 ~= 284.5, near the page right edge) and
    # R3_GND text to Y~167.6, close to the title-block top at Y=170.
    #
    # The shift below is a PURE LAYOUT operation: every (x, y) anchor moves
    # by the same amount. Wires, junctions, hierarchical labels, and
    # electrical connections remain logically identical. ERC and net topology
    # are unaffected.
    #
    # NOTE on the inline `# 93.98 — ...` style comments scattered through
    # this function: those numbers were the PRE-SHIFT values of the
    # corresponding derived quantities, kept as readability hints. They
    # are now off by (PWR_X_SHIFT, PWR_Y_SHIFT) but the mathematical
    # derivations (e.g. `J1_Y - 2.54`) remain correct.
    # Shifts must be integer multiples of the 1.27 mm schematic connection
    # grid so wire endpoints and symbol pins stay on-grid after the shift.
    PWR_X_SHIFT = -30.48     # mm — shift entire power section LEFT (24 x 1.27 mm)
    PWR_Y_SHIFT = -10.16     # mm — shift entire power section UP (8 x 1.27 mm)

    # ----- J1: Phoenix MSTBA 2,5/3-G-5,08 (5.08 mm pitch) -----
    # mirror_y so the pin tips exit to the RIGHT of the body, putting J1
    # visually on the LEFT side of the schematic with the circuit growing
    # to its right.
    J1_X = 87.63 + PWR_X_SHIFT
    J1_Y = 96.52 + PWR_Y_SHIFT
    # With mirror_y applied to a symbol at angle=0, the lib pin at
    # (-5.08, +2.54) maps to schematic position (J1_X + 5.08, J1_Y - 2.54).
    # i.e. pin 1 tip is to the right of and above the body anchor.
    PIN1_Y = J1_Y - 2.54     # 93.98 — +24V_unprotected
    PIN2_Y = J1_Y            # 96.52 — GND
    PIN3_Y = J1_Y + 2.54     # 99.06 — PE
    PIN_X  = J1_X + 5.08     # 92.71 — pin tips on right side of mirrored body

    # ----- Q1: P-MOSFET reverse-polarity (PMV65XP), angle=0, no mirror -----
    # With angle=0, pin schematic positions are:
    #   D = (Q1_X + 2.54, Q1_Y - 5.08)   TOP-right    → goes UP to F1 → +24V
    #   G = (Q1_X - 5.08, Q1_Y)          LEFT side   → drops DOWN through
    #                                                  R4 (series) → junction
    #                                                  with D3.anode → R1 → GND
    #   S = (Q1_X + 2.54, Q1_Y + 5.08)   BOTTOM-right → wires to J1.1
    # Y is set so Q1.S aligns with J1.1's row (PIN1_Y = 93.98).
    Q1_X = 113.03 + PWR_X_SHIFT
    Q1_Y = 88.9 + PWR_Y_SHIFT
    Q1_D_X = Q1_X + 2.54     # 115.57
    Q1_D_Y = Q1_Y - 5.08     # 83.82
    Q1_G_X = Q1_X - 5.08     # 107.95
    Q1_G_Y = Q1_Y            # 88.9
    Q1_S_X = Q1_X + 2.54     # 115.57
    Q1_S_Y = Q1_Y + 5.08     # 93.98 — matches PIN1_Y; same horizontal row as J1.1

    # ----- F1: PTC polyfuse (Bourns MF-RHT075/60-2 candidate), angle=0 -----
    # In series between Q1.D and the +24V power flag.
    # With angle=0:
    #   F1.1 (top)    = (F1_X, F1_Y - 3.81)
    #   F1.2 (bottom) = (F1_X, F1_Y + 3.81)
    # Provides resettable overcurrent protection on the protected +24V rail.
    # 750 mA hold current gives ~2x margin over the ~350 mA combined load
    # while still well below the 1.5 A trip threshold. 60V rating provides
    # comfortable margin over the SMBJ24A surge-clamp ceiling (38.9V).
    F1_X = Q1_D_X            # 115.57 — same vertical column as Q1.D
    F1_Y = 76.2 + PWR_Y_SHIFT
    F1_TOP_Y = F1_Y - 3.81   # 72.39
    F1_BOT_Y = F1_Y + 3.81   # 80.01

    # ----- R4: 1k series gate resistor, angle=0 -----
    # In series with Q1.G, between Q1.G and the R4/R1 junction where D3
    # (Zener clamp) ties in. R4 provides series isolation in the gate path
    # so transient currents from the Zener clamp activation don't disturb
    # Q1's gate drive directly. R4's body sits in the clear Y band between
    # the VIN row (93.98) and the R4/R1 junction (104.14) — body Y range
    # ~96.52 to ~101.60, well clear of the VIN crossing at 93.98.
    R4_X = Q1_G_X            # 107.95 — same column as Q1.G, R1
    R4_Y = 99.06 + PWR_Y_SHIFT
    R4_TOP_Y = R4_Y - 3.81   # 95.25
    R4_BOT_Y = R4_Y + 3.81   # 102.87

    # ----- R4/R1 junction (Y row where D3.anode also lands) -----
    # The junction sits between R4.bot (102.87) and R1.top (105.41) at a
    # clean 1.27 mm grid increment. D3's anode wire enters from the LEFT,
    # making this point a 3-way T.
    R4_R1_JUNC_Y = 104.14 + PWR_Y_SHIFT    # 1.27 mm above R1.top

    # ----- R1: 100k gate-GND pulldown, angle=0 -----
    # Sits directly below R4 in the same column. The wire chain
    # Q1.G -> R4 -> junction -> R1 -> GND replaces the previous direct
    # Q1.G -> R1 pulldown. This vertical chain CROSSES J1.1's horizontal
    # wire at (Q1_G_X, PIN1_Y) without a junction — standard schematic
    # convention for non-connected crossings.
    R1_X = Q1_G_X            # 107.95
    R1_Y = 109.22 + PWR_Y_SHIFT
    R1_TOP_Y = R1_Y - 3.81   # 105.41
    R1_BOT_Y = R1_Y + 3.81   # 113.03

    # ----- D3: 10 V Zener gate-source clamp, angle=270 (body vertical) -----
    # AO3401A (v0.36 swap from PMV65XP) has Vgs_max = +/-12V absolute
    # maximum. With R1 alone pulling the gate toward GND, Vgs at the 24V
    # supply settles at -24V — exceeding the gate-oxide limit by 2x and
    # destroying Q1. D3 (10V Zener, v0.37 — was 18V pre-fix; 18V would
    # have clamped Vgs at -18V, still 6V over AO3401A's ±12V limit)
    # clamps |Vgs| to <=10V by shunting current from Q1.S to the R4/R1
    # junction whenever the junction voltage drops more than 10V below
    # source. With the clamp active, the junction sits at V_S - 10V =
    # 14V; the gate sees the same 14V through R4 (no DC gate current),
    # so Vgs = 14 - 24 = -10V (2V margin under ±12V; ALSO the optimal
    # Rds_on operating point for AO3401A at 45 mΩ).
    #
    # Pin 1 in Device:D_Zener is the CATHODE (K, lib (-3.81, 0)), pin 2 is
    # the ANODE (A, lib (3.81, 0)). With angle=270, the cathode (pin 1)
    # lands at the TOP (Y - 3.81) and the anode (pin 2) at the BOTTOM
    # (Y + 3.81) of the rotated body. The top pin connects to the VIN
    # net (Q1.S side, via a T-tap on the existing vin-horiz wire); the
    # bottom pin routes via an L-wire (down-then-right) to the R4/R1
    # junction.
    #
    # X is set so D3 sits in clear space between D1 (now at X=96.52, one
    # grid step left of its original 100.33 to give breathing room for
    # text labels) and the R1 column (X=107.95). With D3_X=102.87 and
    # body half-width ~1.27 mm, D3 body X range is ~101.60 to 104.14 —
    # well clear of D1 (body ends at X=97.79) and the R1 column (X=107.95).
    D3_X = 102.87 + PWR_X_SHIFT
    D3_Y = 99.06 + PWR_Y_SHIFT  # centred between VIN row and R4/R1 junction row
    D3_K_Y = D3_Y - 3.81     # 95.25 — short stub up to VIN row (93.98)
    D3_A_Y = D3_Y + 3.81     # 102.87 — short stub down-then-right to junction

    # ----- D1: TVS surge-clamp diode (SMBJ24A), angle=90 (body vertical) -----
    # Tap point on the J1.1 -> Q1.S wire (the UNPROTECTED VIN net). With
    # angle=90, lib pin (-3.81, 0) -> schem (D1_X, D1_Y + 3.81) is the
    # BOTTOM pin and lib (3.81, 0) -> schem (D1_X, D1_Y - 3.81) is the TOP
    # pin. The top pin lands on the VIN row (Y = PIN1_Y = 93.98) so D1_Y
    # = 93.98 + 3.81 = 97.79. X chosen between J1.1 (X = 92.71) and
    # Q1.S (X = 115.57), leaving the existing R1 column (X = 107.95) and
    # its value-text untouched. X = 96.52 (= 76 × 1.27) was moved one
    # grid step LEFT of the previous 100.33 to give breathing room
    # between D1's "SMBJ24A" value text (at X=100.33+, ~5 mm wide) and
    # D3's vertical body at X=102.87.
    D1_X = 96.52 + PWR_X_SHIFT
    D1_Y = 97.79 + PWR_Y_SHIFT
    D1_TOP_Y = D1_Y - 3.81   # 93.98 — matches PIN1_Y / VIN wire row
    D1_BOT_Y = D1_Y + 3.81   # 101.60 — wire continues DOWN to local GND symbol
    # GND symbol for D1's bottom pin. Local-only — no extra PWR_FLAG
    # sentinel: the J1.2 GND drop already supplies the ERC power-source
    # marker on the global GND net, and a second PWR_FLAG would cause
    # "Power output to Power output" conflicts.
    D1_GND_Y = 105.41 + PWR_Y_SHIFT  # GND symbol anchor, same Y row as R1.top

    # ----- Per-net flag columns -----
    # +24V flag column: Q1.D / F1 column at X=115.57.
    # R1-GND flag column: directly below Q1.G / R1 at X=107.95.
    # PE flag column: shifted slightly LEFT of J1.3's pin tip (X=82.55)
    #   so the PE drop wire and PE PWR_FLAG sentinel sit clear of J1's
    #   body and don't share a column with any other flag.
    # GND flag column: far to the LEFT of J1 (X=67.31). The GND wire hops
    #   one grid step right of the J1 pin tips, drops to a Y BELOW the PE
    #   flag, then runs LEFT to its own column.
    # Column spacing rationale:
    #   - GND flag X=67.31, PE flag X=82.55: 15.24 mm gap (≥15 mm rule)
    #   - PE flag X=82.55, R1_GND flag X=107.95: 25.40 mm gap
    #   - R1_GND X=107.95, +24V flag X=115.57: 7.62 mm gap. This narrow gap
    #     is acceptable because the R1_GND flag (Y ≈ 117) and the +24V flag
    #     (Y ≈ 62) are separated by >50 mm vertically — their value-text
    #     labels are nowhere near each other on screen.
    COL_24V    = Q1_D_X      # 115.57
    COL_R1_GND = R1_X        # 107.95
    COL_PE     = 82.55 + PWR_X_SHIFT   # 5.08 mm left of J1.3 pin tip (PIN_X=92.71)
    COL_GND    = 67.31 + PWR_X_SHIFT   # far left of J1

    # Flag stack Y coordinates. Spacing FLAG-to-PWR_FLAG (sentinel) = 5.08 mm.
    JUNC_24V_Y = 67.31 + PWR_Y_SHIFT       # PWR_FLAG sentinel sits at this junction
    FLAG_24V_Y = 62.23 + PWR_Y_SHIFT       # +24V triangle, 5.08 mm above the sentinel
    # PE wire: drops from J1.3 down to PE_TURN_Y, runs LEFT to COL_PE, then
    # DOWN through the PE PWR_FLAG sentinel to the Earth_Protective symbol.
    PE_TURN_Y  = 105.41 + PWR_Y_SHIFT      # Y at which PE wire turns from down to left
    JUNC_PE_Y  = 110.49 + PWR_Y_SHIFT      # PE PWR_FLAG sentinel — on the PE vertical drop
    FLAG_PE_Y  = 115.57 + PWR_Y_SHIFT      # Earth_Protective symbol, 5.08 mm below sentinel
    # GND wire: hops right of J1 pins, drops past PE flag's body AND its
    # value-text label ("Earth_Protective" at Y≈123), runs LEFT in clear
    # space, then DOWN through its own PWR_FLAG sentinel to the GND symbol.
    GND_HORIZ_Y = 127.00 + PWR_Y_SHIFT     # horizontal leg of GND wire, clear of PE flag area
    JUNC_GND_Y = GND_HORIZ_Y # GND PWR_FLAG sentinel sits here, on the leg
    FLAG_GND_Y = 132.08 + PWR_Y_SHIFT      # GND symbol, 5.08 mm below the sentinel
    FLAG_R1_GND_Y = 116.84 + PWR_Y_SHIFT   # second GND symbol below R1.bot

    # ----- C1: bulk electrolytic capacitor (100uF 50V), angle=0 -----
    # C_Polarized: pin 1 (top, ANODE +) on the protected +24V rail,
    # pin 2 (bottom, CATHODE -) to GND. 50 V rating gives margin over
    # both the 24 V nominal and the SMBJ24A's 38.9 V surge-clamp voltage.
    # 100 uF is sized for ~500 mA peak load — enough hold-up for sub-ms
    # transients (WS2812 white-bright, radar refresh, MCU TX bursts).
    #
    # Placed in its OWN column at X=142.24, 26.67 mm (= 10.5 grid steps)
    # to the right of F1's column (X=115.57). The wide horizontal gap
    # is needed because F1's Value text "PTC 750mA / 60V" is left-
    # justified at X=119.38 and renders ~17 mm wide, reaching to ~X=137
    # at the displayed character spacing — placing C1's Value text any
    # closer (e.g. at X=137.16) caused the F1 voltage suffix and the
    # "100uF" of C1 to visibly touch in the rendered PNG. The extra
    # 7.62 mm of column spacing gives a clear visual gap.
    #
    # C1.top is at the SAME Y as F1.top (72.39), so the +24V tap wire
    # is a single horizontal segment from F1.top to C1.top. The F1.top
    # pin then has three connections (F1 body, f1-to-junc24v upward,
    # f1-to-c1 rightward) — a junction dot at (F1_X, F1_TOP_Y) marks it.
    C1_X = 142.24 + PWR_X_SHIFT
    C1_Y = 76.2 + PWR_Y_SHIFT
    C1_TOP_Y = C1_Y - 3.81   # 72.39 — matches F1_TOP_Y
    C1_BOT_Y = C1_Y + 3.81   # 80.01
    # GND symbol for C1.bottom — independent column, separated >5 cm
    # vertically from any other GND label so its "GND" text cannot
    # collide with neighbouring symbols.
    C1_GND_Y = 83.82 + PWR_Y_SHIFT         # 1.5 grid steps below C1.bot

    # ----- C2: Y2 ceramic capacitor (10nF Y2), angle=0 -----
    # Closes the EMI loop between circuit GND and the PE conductor.
    # Y2 safety class is mandatory for any GND-to-PE cap — rated for
    # ~1.5 kV impulse withstand, fails open-circuit (not short, which
    # would defeat the protective-earth function).
    #
    # Placed in clear space LEFT of the GND flag column. C2_X is set
    # so the value-text labels of C2 stay clear of the Earth_Protective
    # symbol's value-text ("Earth_Protective" at (82.55, 123.19),
    # spanning ~X=75.4 to ~X=89.7). C2 sits at X=60.96 — left of that
    # band by ~14 mm.
    #
    # Pin 1 (top) connects to the Earth_Protective net via a horizontal
    # wire at Y=FLAG_PE_Y (115.57), terminating at the PE flag's symbol
    # pin. Pin 2 (bottom) connects to the global GND net via a short
    # vertical drop to the existing GND horizontal at Y=GND_HORIZ_Y
    # (127.0). A new horizontal wire extends from (C2_X, GND_HORIZ_Y)
    # east to (COL_GND, GND_HORIZ_Y) where it meets the existing
    # gnd-vert-low/gnd-horiz-left L-corner, producing a 3-way GND tap
    # that requires its own junction dot.
    C2_X = 60.96 + PWR_X_SHIFT
    C2_Y = 119.38 + PWR_Y_SHIFT
    C2_TOP_Y = C2_Y - 3.81   # 115.57 — matches FLAG_PE_Y (PE flag pin row)
    C2_BOT_Y = C2_Y + 3.81   # 123.19

    # ----- Wires -----
    parts: list[str] = []

    # J1.1 (unprotected +24V) → Q1.S: horizontal wire across the schematic.
    # D1's top pin taps off this wire at (D1_X, PIN1_Y) — a junction dot is
    # added below to make the T-connection electrically valid.
    parts.append(_sch_wire(PIN_X, PIN1_Y, Q1_S_X, Q1_S_Y, "vin-horiz"))

    # D1.top (on VIN) → D1.bottom is internal to the symbol; we only need
    # the wire from D1.bottom down to its local GND symbol.
    parts.append(_sch_wire(D1_X, D1_BOT_Y, D1_X, D1_GND_Y, "d1bot-to-gnd"))

    # Q1.D → F1.bot: short vertical hop.
    parts.append(_sch_wire(Q1_D_X, Q1_D_Y, F1_X, F1_BOT_Y, "q1d-to-f1"))
    # F1.top → +24V junction (where PWR_FLAG sentinel taps off).
    parts.append(_sch_wire(F1_X, F1_TOP_Y, COL_24V, JUNC_24V_Y, "f1-to-junc24v"))
    # +24V junction → +24V flag.
    parts.append(_sch_wire(COL_24V, JUNC_24V_Y, COL_24V, FLAG_24V_Y, "junc24v-to-flag"))

    # Q1.G -> R4 -> (junction with D3.anode) -> R1 -> GND chain.
    # The chain crosses J1.1's horizontal VIN wire at (Q1_G_X, PIN1_Y) at
    # the Q1.G -> R4.top segment, without a junction dot — standard
    # schematic convention for non-connected crossings.
    parts.append(_sch_wire(Q1_G_X, Q1_G_Y, R4_X, R4_TOP_Y, "q1g-to-r4"))
    parts.append(_sch_wire(R4_X, R4_BOT_Y, R4_X, R4_R1_JUNC_Y, "r4-to-junction"))
    parts.append(_sch_wire(R4_X, R4_R1_JUNC_Y, R1_X, R1_TOP_Y, "junction-to-r1"))

    # D3 (Zener) clamp wires.
    # D3.K (top) -> VIN net (T-tap on the existing vin-horiz wire at
    # (D3_X, PIN1_Y) — a junction dot is added below to mark the tap).
    parts.append(_sch_wire(D3_X, D3_K_Y, D3_X, PIN1_Y, "d3k-to-vin"))
    # D3.A (bottom) -> R4/R1 junction via an L-route: drop down to the
    # junction Y row, then run east to the junction X column.
    parts.append(_sch_wire(D3_X, D3_A_Y, D3_X, R4_R1_JUNC_Y, "d3a-vert"))
    parts.append(_sch_wire(D3_X, R4_R1_JUNC_Y, R4_X, R4_R1_JUNC_Y, "d3a-horiz"))

    # R1.bot → R1-GND flag (no junction, no PWR_FLAG sentinel — GND is global
    # and the J1.2 stack already supplies the sentinel for ERC).
    parts.append(_sch_wire(R1_X, R1_BOT_Y, COL_R1_GND, FLAG_R1_GND_Y, "r1bot-to-r1gnd"))

    # J1.2 GND wire: hop one grid step RIGHT of J1's pin tips (clearing the
    # J1.3 pin-tip column so the wire doesn't short into PE), drop DOWN past
    # J1's body and PE flag's body, run LEFT to COL_GND, then DOWN through
    # the GND PWR_FLAG sentinel to the GND symbol.
    GND_HOP_X = PIN_X + 2.54   # 95.25 — temporary drop column for J1.2
    parts.append(_sch_wire(PIN_X, PIN2_Y, GND_HOP_X, PIN2_Y, "gnd-pin-hop"))
    parts.append(_sch_wire(GND_HOP_X, PIN2_Y, GND_HOP_X, GND_HORIZ_Y, "gnd-vert-drop"))
    parts.append(_sch_wire(GND_HOP_X, GND_HORIZ_Y, COL_GND, GND_HORIZ_Y, "gnd-horiz-left"))
    parts.append(_sch_wire(COL_GND, GND_HORIZ_Y, COL_GND, FLAG_GND_Y, "gnd-vert-low"))

    # J1.3 PE wire: drop DOWN below J1 body, turn LEFT to COL_PE, drop DOWN
    # through the PE PWR_FLAG sentinel to Earth_Protective. PE drops at
    # X=PIN_X (just to the right of J1's body) so it doesn't cross J1's
    # rectangle; the LEFT turn happens at PE_TURN_Y which is well below
    # J1's body bottom (Y=100.33).
    parts.append(_sch_wire(PIN_X, PIN3_Y, PIN_X, PE_TURN_Y, "pe-vert-drop"))
    parts.append(_sch_wire(PIN_X, PE_TURN_Y, COL_PE, PE_TURN_Y, "pe-horiz-left"))
    parts.append(_sch_wire(COL_PE, PE_TURN_Y, COL_PE, JUNC_PE_Y, "pe-vert-mid"))
    parts.append(_sch_wire(COL_PE, JUNC_PE_Y, COL_PE, FLAG_PE_Y, "pe-vert-low"))

    # C1: +24V rail tap from F1.top → C1.top, then C1.bot → C1-local GND.
    # The F1.top pin becomes a 3-way (F1 body, vertical wire upward to the
    # +24V flag, horizontal wire rightward to C1) — a junction dot below
    # marks the T-connection.
    parts.append(_sch_wire(F1_X, F1_TOP_Y, C1_X, C1_TOP_Y, "f1top-to-c1"))
    parts.append(_sch_wire(C1_X, C1_BOT_Y, C1_X, C1_GND_Y, "c1bot-to-gnd"))

    # C2: PE flag pin → C2.top via a horizontal wire at Y=FLAG_PE_Y.
    # C2.bot → existing GND horizontal at Y=GND_HORIZ_Y via a short
    # vertical drop, then a horizontal segment east to (COL_GND, GND_HORIZ_Y)
    # which is the existing gnd-horiz-left/gnd-vert-low corner — adding a
    # third wire here turns it into a T-junction (needs junction dot).
    parts.append(_sch_wire(C2_X, C2_TOP_Y, COL_PE, FLAG_PE_Y, "c2top-to-pe"))
    parts.append(_sch_wire(C2_X, C2_BOT_Y, C2_X, GND_HORIZ_Y, "c2bot-to-gnd-vert"))
    parts.append(_sch_wire(C2_X, GND_HORIZ_Y, COL_GND, GND_HORIZ_Y, "c2-to-gnd-horiz"))

    # ----- Junctions (T-branch points where PWR_FLAG sentinels join wires) -----
    parts.append(_sch_junction(COL_24V, JUNC_24V_Y, "24v"))
    parts.append(_sch_junction(COL_GND, JUNC_GND_Y, "gnd"))
    parts.append(_sch_junction(COL_PE,  JUNC_PE_Y,  "pe"))
    # T-branch where D1's top pin taps the J1 → Q1 VIN wire.
    parts.append(_sch_junction(D1_X, PIN1_Y, "vin-d1"))
    # T-branch where D3's cathode taps the same J1 → Q1 VIN wire.
    parts.append(_sch_junction(D3_X, PIN1_Y, "vin-d3"))
    # 3-way junction where R4.bot wire, R1.top wire, and D3.anode L-wire
    # meet on the gate-pulldown column.
    parts.append(_sch_junction(R4_X, R4_R1_JUNC_Y, "r4-r1-d3"))
    # T-branch where C1's +24V tap meets the F1.top → +24V flag wire at
    # the F1 pin location.
    parts.append(_sch_junction(F1_X, F1_TOP_Y, "vin-c1"))
    # T-branch where C2's GND tap meets the existing GND horizontal at
    # the COL_GND corner (where gnd-horiz-left ends and gnd-vert-low
    # starts; the third wire is C2's new c2-to-gnd-horiz).
    parts.append(_sch_junction(COL_GND, GND_HORIZ_Y, "gnd-c2"))

    # ----- J1 symbol (Phoenix MSTBA 2,5/3-G-5,08, mirror_y so pins face right) -----
    j1_uuid = U("sym:j1")
    j1_pin1_uuid = U("sym-pin:j1-1")
    j1_pin2_uuid = U("sym-pin:j1-2")
    j1_pin3_uuid = U("sym-pin:j1-3")
    parts.append(textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector:Screw_Terminal_01x03")
        \t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t(mirror y)
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{j1_uuid}")
        \t\t(property "Reference" "J1"
        \t\t\t(at {fmt(J1_X - 2.54)} {fmt(J1_Y - 7.62)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify right)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "Phoenix_MSTBA_2,5/3-G-5,08"
        \t\t\t(at {fmt(J1_X - 2.54)} {fmt(J1_Y - 5.08)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify right)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal"
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "https://www.phoenixcontact.com/online/portal/us?uri=pxc-oc-itemdetail:pid=1757255"
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" "Phoenix Contact MSTBA 2,5/3-G-5,08 — 3-pin 5.08 mm pitch pluggable terminal block base. 24 V supply input: pin 1 = +24V_unprotected, pin 2 = GND, pin 3 = PE. Mates with a Phoenix COMBICON 5.08 mm 3-pin plug. Order code 1757255 (12 A) or 1923872 (16 A HC)."
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{j1_pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{j1_pin2_uuid}")
        \t\t)
        \t\t(pin "3"
        \t\t\t(uuid "{j1_pin3_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "J1")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)"""))

    # ----- D1: TVS surge-clamp diode (SMBJ24A), unidirectional, SMB package -----
    # Tap point is BEFORE Q1 on the unprotected VIN net — Q1's Vds_max is
    # -50V on PMV65XP, and a transient above that would destroy Q1
    # before its reverse-polarity function could engage. SMBJ24A clamps
    # at Vc=38.9V at 1A peak (10/1000 us), holding VIN below Q1's
    # absolute maximum with comfortable margin. Vrwm=24V matches the
    # nominal supply; Vbr_min=26.7V so the diode is off at the working
    # point and consumes ~uA leakage. Peak pulse power 600W. F1 (PTC)
    # downstream catches the sustained over-current that follows a
    # clamped event.
    # angle=270 (NOT 90) — see CRITICAL-1 fix in v0.36 swarm audit. KiCad's
    # Device:D_TVS lib_id has both pins named A1/A2 (bidirectional convention),
    # but the SMBJ24A is UNIDIRECTIONAL with a cathode bar marker. KiCad's
    # Diode_SMD:D_SMB stock footprint follows the KLC: pad 1 = cathode.
    # `sync_pcb_nets_from_schematic` maps schematic-pin-N → PCB-pad-N, so
    # whichever schematic pin sits on the VIN wire becomes PCB pad 1 = cathode
    # only if that schematic pin number is 1. At angle=90, schematic pin 2
    # lands on TOP (VIN) and pin 1 lands on BOTTOM (GND) → PCB pad 1 = GND
    # = REVERSED TVS. At angle=270, pin 1 lands on TOP (VIN) and pin 2 on
    # BOTTOM (GND) → PCB pad 1 = cathode = VIN ✓.
    parts.append(_sch_diode_tvs(
        x=D1_X, y=D1_Y, angle=270,
        reference="D1", value="SMBJ24A", uuid_tag="d1",
    ))

    # ----- D3: 10 V Zener gate-source clamp (AO3401A Vgs protection) -----
    # v0.37: changed from 18 V to 10 V Zener after AO3401A swap (v0.36) and
    # re-audit found AO3401A Vgs_max = ±12 V (NOT ±20 V as the original
    # PMV65XP design assumed). 18 V Zener would have clamped Vgs at -18 V,
    # exceeding AO3401A's ±12 V rating by 6 V. 10 V Zener clamps Vgs at
    # -10 V — 2 V margin under ±12 V AND optimal Rds_on operating point
    # for AO3401A (45 mΩ at Vgs=-10 V per Alpha-Omega datasheet curve).
    # D3 cathode taps the J1.1 -> Q1.S VIN wire; anode lands on the R4/R1
    # junction so a clamp event sinks current from Q1.S through D3
    # (reverse breakdown at Vz=10V) into the junction and out through
    # R1 to GND. Candidate part: BZT52C10S (10 V Zener, SOD-323, 200 mW,
    # JLCPCB Basic Parts Library). v0.40 post-order MATH FIX: steady-state
    # Pz = (24-10)/R1(100k) × 10V = 0.14 mA × 10V = 1.4 mW (143× under
    # 200 mW rating, NOT 1.43×). Pre-fix said "140 mW within 200 mW"
    # which used R4 (1k) as the limiting resistor — wrong by 100×. R4
    # carries no steady-state current because Q1's gate is DC
    # high-impedance (Igss ≤ 100 nA per AO3401A datasheet).
    parts.append(_sch_diode_zener(
        x=D3_X, y=D3_Y, angle=270,
        reference="D3", value="10V Zener 200mW", uuid_tag="d3",
    ))

    # ----- Q1: P-MOSFET reverse-polarity protection (AO3401A) -----
    # v0.36 substitution from PMV65XP (Vds=-20V was insufficient).
    # Source = J1.1 (unprotected input), Drain = +24V protected rail.
    # When input polarity is correct, the body diode conducts initially,
    # then the gate is pulled negative through R4 + R1 to GND. The D3
    # 10 V Zener clamp (v0.37) limits |Vgs| to <=10V, so the channel turns
    # fully on at Vgs = -10V — shorting out the body diode for low Rds_on
    # conduction loss (45 mΩ at Vgs=-10V per AO3401A datasheet).
    # v0.36 CRITICAL-4: AO3401A (Alpha & Omega Semiconductor), drop-in for the
    # pre-v0.36 PMV65XP. PMV65XP claimed Vds_max=-50V in the source comment
    # but the actual datasheet value is Vds_max=-20V — would have been
    # exceeded by 19V during a 38.9V SMBJ24A clamp event.
    # AO3401A: Vds_max=-30V (8.9V margin over the 38.9V clamp — tight but
    # safe for transient events under nanoseconds), Vgs_max=±12V (D3 Zener
    # clamp at -18V is still REQUIRED to keep |Vgs| within ±12V at startup),
    # Id continuous=-4A, RDS(on) typ=60 mΩ at Vgs=-10V (better than PMV65XP's
    # 90 mΩ). Same SOT-23 footprint, same G/S/D pin order.
    # JLCPCB Extended Library, mass stock.
    parts.append(_sch_q_pmos(
        x=Q1_X, y=Q1_Y, angle=0,
        reference="Q1", value="AO3401A", uuid_tag="q1",
    ))

    # ----- F1: PTC polyfuse, 750 mA hold / 60 V -----
    # Candidate part: Bourns MF-RHT075/60-2 (750 mA hold, 1.5 A trip,
    # 60 V max, 1812 SMD). The 60V rating provides comfortable margin
    # over the SMBJ24A surge-clamp ceiling (38.9V) — critical if Q1
    # fails short and the clamp voltage appears across F1. The 750 mA
    # hold current widens the safety margin against C1 (100 uF)
    # cold-start inrush while staying within the ~350 mA combined
    # load budget. Final footprint (1812 SMD) TBD in PCB-layout chunk;
    # verify JLCPCB stock on order day.
    parts.append(_sch_polyfuse(
        x=F1_X, y=F1_Y, angle=0,
        reference="F1", value="PTC 750mA / 60V", uuid_tag="f1",
    ))

    # ----- R1: 100 kΩ gate-GND pulldown -----
    parts.append(_sch_resistor(
        x=R1_X, y=R1_Y, angle=0,
        reference="R1", value="100k 1%", uuid_tag="r1",
    ))

    # ----- R4: 1 kΩ series gate resistor (Zener clamp current limiter) -----
    # Sits in series with Q1.G between the Q1.G pin and the R4/R1 junction
    # where D3 (Zener) ties in. R4 provides series isolation in the gate
    # path so transient currents during a Zener clamp event are limited
    # and do not disturb Q1's gate drive directly.
    parts.append(_sch_resistor(
        x=R4_X, y=R4_Y, angle=0,
        reference="R4", value="1k", uuid_tag="r4",
    ))

    # ----- C1: bulk electrolytic, 100 uF / 50 V -----
    # Polarized — pin 1 (top) is the ANODE (+), wired to the protected +24V
    # rail at F1.top. Pin 2 (bottom) is the CATHODE (-), wired to GND.
    # Buffers transient load steps (WS2812 white-bright, radar refreshes,
    # MCU TX bursts) and absorbs ripple from the upstream supply. 50 V
    # rating gives margin over both the 24 V nominal and the SMBJ24A's
    # 38.9 V surge-clamp voltage.
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C1_X, y=C1_Y, angle=0,
        reference="C1", value="100uF 50V", uuid_tag="c1",
    ))

    # ----- C2: Y2 safety-class ceramic, 10 nF -----
    # Non-polarized. Pin 1 (top) on the Earth_Protective net, pin 2 (bottom)
    # on global GND. Closes the conducted-EMI loop between circuit GND and
    # the chassis PE conductor so high-frequency switching noise from the
    # downstream bucks returns to chassis ground through this cap rather
    # than escaping along the supply leads. Y2 class is mandatory for any
    # cap connecting circuit GND to PE — rated for ~1.5 kV impulse withstand,
    # fails open-circuit (not short, which would defeat the protective
    # earth function).
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C2_X, y=C2_Y, angle=0,
        reference="C2", value="10nF Y2", uuid_tag="c2",
    ))

    # ----- Power flag symbols (+24V, GND, Earth_Protective, R1-GND, D1-GND, C1-GND) -----
    # +24V flag with text "+24V" placed ABOVE the triangle (standard).
    # value_offset_y matches the +24V lib's default Value position
    # (lib (0, +3.556) → schem (0, -3.556)) so the text sits just above
    # the triangle's vertex without overlapping it.
    parts.append(_sch_power_flag(
        lib_id="power:+24V", value="+24V",
        x=COL_24V, y=FLAG_24V_Y, angle=0,
        reference="#PWR01",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr01-24v",
    ))
    # GND flag (J1.2). Value-text BELOW.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_GND, y=FLAG_GND_Y, angle=0,
        reference="#PWR02",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr02-gnd",
    ))
    # Earth_Protective flag (J1.3). Value-text BELOW (offset y=7.62 to
    # clear the symbol's Ø2.54 mm circle below the bar).
    parts.append(_sch_power_flag(
        lib_id="power:Earth_Protective", value="Earth_Protective",
        x=COL_PE, y=FLAG_PE_Y, angle=0,
        reference="#PWR03",
        value_offset_x=0.0, value_offset_y=7.62,
        uuid_tag="pwr03-pe",
    ))
    # GND for R1.bottom — same net as #PWR02 via the global power label.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_R1_GND, y=FLAG_R1_GND_Y, angle=0,
        reference="#PWR04",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr04-gnd-r1",
    ))
    # GND for D1.bottom (TVS anode) — same net as #PWR02 via the global
    # power label. No matching PWR_FLAG sentinel: see note below in the
    # PWR_FLAG section.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=D1_X, y=D1_GND_Y, angle=0,
        reference="#PWR05",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr05-gnd-d1",
    ))
    # GND for C1.bottom (bulk-cap cathode) — same net as #PWR02 via the
    # global power label. No PWR_FLAG sentinel (same reason as above).
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C1_X, y=C1_GND_Y, angle=0,
        reference="#PWR06",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr06-gnd-c1",
    ))

    # ----- PWR_FLAG sentinels -----
    # Each sentinel's "PWR_FLAG" value-text is offset SIDEWAYS (positive X)
    # so it sits next to the symbol rather than above it — this is the fix
    # for the label overlap that was visible in the previous render where
    # PWR_FLAG text was directly under the power-symbol's Value-text.
    PF_TEXT_OFFSET = 5.08    # mm horizontal offset of "PWR_FLAG" text from symbol
    # +24V net sentinel: graphic UP (angle=0) toward the +24V triangle above.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_24V, y=JUNC_24V_Y, angle=0,
        reference="#FLG01",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=-2.54,
        uuid_tag="flg01-24v",
    ))
    # GND net sentinel: graphic DOWN (angle=180) toward the GND symbol below.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_GND, y=JUNC_GND_Y, angle=180,
        reference="#FLG02",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=2.54,
        uuid_tag="flg02-gnd",
    ))
    # PE net sentinel: graphic DOWN.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_PE, y=JUNC_PE_Y, angle=180,
        reference="#FLG03",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=2.54,
        uuid_tag="flg03-pe",
    ))
    # NOTE: no PWR_FLAG sentinel on the R1-GND or D1-GND drops — GND is a
    # global net and FLG02 (on J1.2's drop) already supplies the "power
    # source" marker for ERC. Adding a second PWR_FLAG on the same GND net
    # would create a "Power output to Power output" connection error.

    # =========================================================================
    # 24V -> 5V buck converter block (U1 LM2596S-5.0 + L1 + D2 + C3/C13/C4/C14)
    # =========================================================================
    # First active block in the power section. Takes the protected +24V rail
    # (downstream of F1 / C1) and produces a regulated 5V output that powers
    # the LD2410 mmWave radar (~80 mA) and the WS2812 status LED (~60 mA
    # white-bright) — total ~140 mA, well below the LM2596's 3 A rating.
    #
    # Component selection rationale (see commit message and CLAUDE.md):
    #   * LM2596S-5.0  : 40 V Vin_max, fixed 5 V output, 3 A, 150 kHz, TO-263.
    #                    The 40 V rating is the binding constraint — it
    #                    matches D1 (SMBJ24A) which clamps surges at 38.9 V.
    #                    Lower-rated bucks (TPS62933 17V, MP2451 26V,
    #                    TPS54302 28V) would not survive a clamped surge.
    #                    Fixed-output variant eliminates the FB resistor
    #                    divider (one fewer place for a layout error).
    #   * L1 33 uH    : Standard inductor value from the LM2596 datasheet
    #                    typical-application table for 5 V output at 150 kHz.
    #                    Shielded ferrite-core part with >=2 A saturation and
    #                    low DCR (<100 mOhm) keeps EMI and conduction loss low.
    #                    The 2 A saturation rating is the binding requirement:
    #                    LM2596 has no internal soft-start, so cold-start of
    #                    C4 (220 uF output bulk) can push the peak inductor
    #                    current above 1 A in the first few switching cycles.
    #                    A 1 A-rated inductor would saturate and trigger an
    #                    LM2596 over-current latch, producing an ugly power-on
    #                    glitch. Candidate parts (verify JLCPCB stock at order
    #                    day): Bourns SRR1208-330Y (33 uH, 1.95 A), Wurth
    #                    74404084330 (33 uH, 2.4 A — likely Extended Library).
    #   * D2 SS14     : 40 V / 1 A Schottky catch diode. LM2596 is an
    #                    ASYNCHRONOUS switcher — there is no internal
    #                    high-side flyback diode, so an external Schottky is
    #                    MANDATORY. SOD-123 or DO-214AC package, JLCPCB Basic.
    #   * C3 100uF/50V + C13 100 nF : input bulk + HF bypass at U1.VIN.
    #                    50 V rating gives margin over the 24 V nominal AND
    #                    the 38.9 V SMBJ24A clamp voltage.
    #   * C4 220uF/10V + C14 100 nF : output bulk + HF bypass at the +5V rail.
    #                    10 V rating gives 2x margin over 5 V; 220 uF is the
    #                    LM2596 datasheet recommendation for low output ripple.
    #
    # ON/OFF pin (pin 5, active-LOW) is tied to GND for always-on operation —
    # the buck has no shutdown / sleep mode in OAS. The U1 thermal pad will
    # need a copper pour to GND on the PCB (handled in the PCB-layout chunk).
    #
    # Layout (page-absolute mm, KiCad +Y is down on screen):
    #
    #                                              +5V flag (top-right corner)
    #                                              |
    #                                              ◊ PWR_FLAG_5V
    #                                              |
    #            FB ↑   +5V bus ─────── L1 ─── C4 ─── C14 ─┴── (to flag)
    #            |                |             |     |
    #     +24V bus extension      |             GND   GND
    #     ────────── C3 ── C13 ── U1.VIN     U1.OUT ── switch node
    #                  |     |    (LM2596S-5)   |
    #                  GND  GND                 |
    #                       U1.ON/OFF=GND       D2 (catch)
    #                       U1.GND=GND          |
    #                                           D2.A=GND
    #
    # The buck block sits far to the right of the existing power section.
    # U1 anchor at X=177.8 — 35.56 mm (= 4 grid steps of 8.89 mm = 7×1.27 mm)
    # to the right of C1's column (X=142.24). The wide horizontal gap leaves
    # room for C1's "100uF 50V" value text, then a clean run of +24V bus
    # heading east to the buck input.

    # ----- U1: LM2596S-5.0 buck regulator -----
    # Anchor Y chosen so that U1.VIN (lib (-12.7, +2.54)) lands exactly on the
    # +24V bus Y row (72.39). With Y_U1=74.93: VIN at 74.93-2.54 = 72.39 ✓.
    # Body rectangle spans schematic Y=[69.85, 80.01], X=[190.50, 210.82].
    # X chosen far enough right of C1, C3, C13 for cap value labels
    # ("100uF 50V" ~ 11.4 mm wide on screen) to never overlap U1 body.
    U1_X = 200.66 + PWR_X_SHIFT
    U1_Y = 74.93 + PWR_Y_SHIFT
    U1_VIN_X    = U1_X - 12.7     # 187.96
    U1_VIN_Y    = U1_Y - 2.54     # 72.39 — matches +24V bus row
    U1_OUT_X    = U1_X + 12.7     # 213.36
    U1_OUT_Y    = U1_Y + 2.54     # 77.47 — switch node row
    U1_GND_X    = U1_X            # 200.66
    U1_GND_Y    = U1_Y + 7.62     # 82.55
    U1_FB_X     = U1_X + 12.7     # 213.36
    U1_FB_Y     = U1_Y - 2.54     # 72.39
    U1_ONOFF_X  = U1_X - 12.7     # 187.96
    U1_ONOFF_Y  = U1_Y + 2.54     # 77.47 — same row as OUT

    # ----- C3: input bulk electrolytic, 100uF 50V, angle=0 -----
    # Pin 1 (top, anode +) on +24V bus, pin 2 (bottom) to GND. Placed between
    # C1 (X=142.24) and U1.VIN (X=187.96). Spacing of 17.78 mm to C1 and
    # 15.24 mm to C13 leaves clear gaps between adjacent caps' value-text
    # labels ("100uF 50V" renders ~11.4 mm wide at size 1.27).
    C3_X = 160.02 + PWR_X_SHIFT
    C3_Y = 76.20 + PWR_Y_SHIFT
    C3_TOP_Y = C3_Y - 3.81        # 72.39 — on +24V bus
    C3_BOT_Y = C3_Y + 3.81        # 80.01
    C3_GND_Y = 82.55 + PWR_Y_SHIFT  # GND symbol anchor, 2.54 below cap.bot

    # ----- C13: input HF ceramic bypass, 100nF, angle=0 -----
    C13_X = 175.26 + PWR_X_SHIFT
    C13_Y = 76.20 + PWR_Y_SHIFT
    C13_TOP_Y = C13_Y - 3.81      # 72.39 — on +24V bus
    C13_BOT_Y = C13_Y + 3.81      # 80.01
    C13_GND_Y = 82.55 + PWR_Y_SHIFT

    # ----- Switch node and L1 (33 uH shielded, vertical, angle=0) -----
    # Switch node row = U1.OUT row = Y=77.47. L1 vertical with bot pin on the
    # switch node, top pin on the +5V output bus. L1.bot at Y=74.93 sits
    # 2.54 mm ABOVE the switch node row, so a short vertical wire connects
    # them. L1.top at Y=67.31 = +5V bus row, 2.54 mm ABOVE U1's body top edge
    # (Y=69.85) for clear visual separation from the LM2596 rectangle.
    L1_X = 223.52 + PWR_X_SHIFT
    L1_Y = 71.12 + PWR_Y_SHIFT
    L1_TOP_Y = L1_Y - 3.81        # 67.31 — on +5V bus
    L1_BOT_Y = L1_Y + 3.81        # 74.93 — 2.54 above switch node row

    # ----- D2: SS14 Schottky catch diode, angle=270 (K top, A bottom) -----
    # Sits between U1.OUT and L1.bot on the switch node horizontal. With
    # angle=270 the cathode (pin 1) is at the TOP (Y - 3.81) facing the
    # switch node, and the anode (pin 2) is at the BOTTOM (Y + 3.81) heading
    # to GND. This is the standard buck catch-diode orientation: when the
    # high-side switch in U1 turns off, L1's flyback current circulates from
    # GND through D2 forward-biased into the switch node, holding it ~0.4 V
    # below GND rather than rising arbitrarily.
    D2_X = 218.44 + PWR_X_SHIFT
    D2_Y = 81.28 + PWR_Y_SHIFT
    D2_K_Y = D2_Y - 3.81          # 77.47 — on switch node row
    D2_A_Y = D2_Y + 3.81          # 85.09
    D2_GND_Y = 88.90 + PWR_Y_SHIFT  # GND symbol anchor, 3.81 below D2.A

    # ----- +5V output caps -----
    # C4 (polarized, 220uF/10V) and C14 (ceramic, 100nF) tap the +5V bus to
    # GND on the OUTPUT side of L1. Pin 1 (top, anode +) on +5V bus, pin 2
    # (bottom) to GND. Column spacing of 15.24 mm (C4↔L1, C14↔C4) keeps the
    # "220uF 10V" / "100nF" value-text labels clear of neighbouring caps'
    # references.
    C4_X = 238.76 + PWR_X_SHIFT
    C4_Y = 71.12 + PWR_Y_SHIFT
    C4_TOP_Y = C4_Y - 3.81        # 67.31 — on +5V bus
    C4_BOT_Y = C4_Y + 3.81        # 74.93
    C4_GND_Y = 77.47 + PWR_Y_SHIFT

    C14_X = 254.00 + PWR_X_SHIFT
    C14_Y = 71.12 + PWR_Y_SHIFT
    C14_TOP_Y = C14_Y - 3.81      # 67.31 — on +5V bus
    C14_BOT_Y = C14_Y + 3.81      # 74.93
    C14_GND_Y = 77.47 + PWR_Y_SHIFT

    # ----- +5V flag and PWR_FLAG sentinel -----
    # Column = C14 column (254.00). The flag stack lifts above the +5V bus
    # at Y=67.31: PWR_FLAG sentinel midway, +5V triangle at top-right Y=62.23
    # for visual alignment with the existing +24V flag (also at Y=62.23, far
    # to the left).
    COL_5V       = C14_X          # 254.00
    Y_5V_BUS     = 67.31 + PWR_Y_SHIFT  # +5V bus row (above U1 body top edge Y=69.85)
    JUNC_5V_Y    = 64.77 + PWR_Y_SHIFT  # PWR_FLAG sentinel on the vertical to flag
    FLAG_5V_Y    = 62.23 + PWR_Y_SHIFT  # +5V triangle, same Y as +24V flag

    # ----- Buck-block wires -----
    # +24V bus extension from C1.top (142.24, 72.39) RIGHT to U1.VIN
    # (165.10, 72.39). Single wire segment; junctions added at C3.top and
    # C13.top tap points, and at the (now 3-way) C1.top corner.
    parts.append(_sch_wire(C1_X, F1_TOP_Y, U1_VIN_X, U1_VIN_Y, "vin-c1-to-u1"))

    # C3.bot → C3-GND
    parts.append(_sch_wire(C3_X, C3_BOT_Y, C3_X, C3_GND_Y, "c13ot-to-gnd"))
    # C13.bot → C13-GND
    parts.append(_sch_wire(C13_X, C13_BOT_Y, C13_X, C13_GND_Y, "c13bot-to-gnd"))

    # U1.ON/OFF pin (pin 5, active-LOW) → local GND symbol. Always-on operation.
    U1_ONOFF_GND_Y = 82.55 + PWR_Y_SHIFT  # GND symbol below ON/OFF pin
    parts.append(_sch_wire(U1_ONOFF_X, U1_ONOFF_Y, U1_ONOFF_X, U1_ONOFF_GND_Y, "u1onoff-to-gnd"))
    # U1.GND (pin 3, centre-bottom) → local GND symbol below
    U1_GND_SYM_Y = 86.36 + PWR_Y_SHIFT    # GND symbol 3.81 below U1.GND pin
    parts.append(_sch_wire(U1_GND_X, U1_GND_Y, U1_GND_X, U1_GND_SYM_Y, "u1gnd-to-gndsym"))

    # Switch node horizontal: U1.OUT (X=U1_OUT_X) → L1.bot column (X=L1_X).
    # D2.K's pin tip lands on this wire at (D2_X, U1_OUT_Y) — a junction dot
    # marks the T-connection.
    parts.append(_sch_wire(U1_OUT_X, U1_OUT_Y, L1_X, U1_OUT_Y, "u1out-switch-horiz"))
    # Short vertical from switch node row up to L1.bot pin.
    parts.append(_sch_wire(L1_X, U1_OUT_Y, L1_X, L1_BOT_Y, "switch-to-l1bot"))

    # D2.A (anode, bottom) → D2-GND symbol
    parts.append(_sch_wire(D2_X, D2_A_Y, D2_X, D2_GND_Y, "d2a-to-gnd"))

    # FB (pin 4) → +5V bus: short vertical hop UP from FB pin to the +5V row.
    parts.append(_sch_wire(U1_FB_X, U1_FB_Y, U1_FB_X, Y_5V_BUS, "fb-to-5v-bus"))

    # +5V bus horizontal from FB column (190.50) RIGHT through L1.top, C4.top,
    # C14.top — a single wire segment with junctions at the tap points.
    parts.append(_sch_wire(U1_FB_X, Y_5V_BUS, COL_5V, Y_5V_BUS, "5v-bus"))

    # C4.bot → C4-GND
    parts.append(_sch_wire(C4_X, C4_BOT_Y, C4_X, C4_GND_Y, "c14ot-to-gnd"))
    # C14.bot → C14-GND
    parts.append(_sch_wire(C14_X, C14_BOT_Y, C14_X, C14_GND_Y, "c14bot-to-gnd"))

    # +5V bus terminus → PWR_FLAG sentinel column upward, then to +5V flag.
    parts.append(_sch_wire(COL_5V, Y_5V_BUS, COL_5V, JUNC_5V_Y, "5v-bus-to-junc"))
    parts.append(_sch_wire(COL_5V, JUNC_5V_Y, COL_5V, FLAG_5V_Y, "5v-junc-to-flag"))

    # ----- Buck-block junctions -----
    # C1.top is now a 3-way: existing f1-to-c1 enters from left, NEW
    # vin-c1-to-u1 exits right, C1's body pin drops down.
    parts.append(_sch_junction(C1_X, F1_TOP_Y, "vin-c1-extended"))
    # C3.top tap on +24V bus.
    parts.append(_sch_junction(C3_X, C3_TOP_Y, "24v-c3"))
    # C13.top tap on +24V bus.
    parts.append(_sch_junction(C13_X, C13_TOP_Y, "24v-c13"))
    # D2.K tap on switch node.
    parts.append(_sch_junction(D2_X, U1_OUT_Y, "switch-d2"))
    # L1.top tap on +5V bus.
    parts.append(_sch_junction(L1_X, Y_5V_BUS, "5v-l1"))
    # C4.top tap on +5V bus.
    parts.append(_sch_junction(C4_X, Y_5V_BUS, "5v-c4"))
    # C14.top + bus terminus + vertical to PWR_FLAG: 3-way.
    parts.append(_sch_junction(COL_5V, Y_5V_BUS, "5v-c14"))
    # PWR_FLAG sentinel position on the vertical to the +5V flag.
    parts.append(_sch_junction(COL_5V, JUNC_5V_Y, "5v"))

    # ----- U1: LM2596S-5.0 -----
    parts.append(_sch_buck_lm2596_5(
        x=U1_X, y=U1_Y, angle=0,
        reference="U1", value="LM2596S-5.0", uuid_tag="u1",
    ))

    # ----- L1: 33 uH shielded inductor, >=2 A sat, low DCR -----
    # See the buck-block component-selection comment above for why the
    # saturation rating was uprated from 1 A to 2 A (LM2596 cold-start
    # inrush via C4 = 220 uF can exceed 1 A in the first switching cycles).
    parts.append(_sch_inductor(
        x=L1_X, y=L1_Y, angle=0,
        reference="L1", value="33uH 2A", uuid_tag="l1",
    ))

    # ----- D2: SS14 Schottky catch diode -----
    parts.append(_sch_diode_schottky(
        x=D2_X, y=D2_Y, angle=270,
        reference="D2", value="SS14", uuid_tag="d2",
    ))

    # ----- C3: input bulk electrolytic, 100 uF / 50 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C3_X, y=C3_Y, angle=0,
        reference="C3", value="100uF 50V", uuid_tag="c3",
    ))

    # ----- C13: input HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C13_X, y=C13_Y, angle=0,
        reference="C13", value="100nF", uuid_tag="c13",
    ))

    # ----- C4: output bulk electrolytic, 220 uF / 10 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C4_X, y=C4_Y, angle=0,
        reference="C4", value="220uF 10V", uuid_tag="c4",
    ))

    # ----- C14: output HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C14_X, y=C14_Y, angle=0,
        reference="C14", value="100nF", uuid_tag="c14",
    ))

    # ----- Local GND symbols around U1 / inductor / caps -----
    # Each GND symbol creates a global-label drop to the GND net. No PWR_FLAG
    # sentinel on any of these — FLG02 (on J1.2's drop) already supplies the
    # ERC power-source marker for the GND net.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C3_X, y=C3_GND_Y, angle=0,
        reference="#PWR07",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr07-gnd-c3",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C13_X, y=C13_GND_Y, angle=0,
        reference="#PWR08",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr08-gnd-c13",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U1_ONOFF_X, y=U1_ONOFF_GND_Y, angle=0,
        reference="#PWR09",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr09-gnd-u1onoff",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U1_GND_X, y=U1_GND_SYM_Y, angle=0,
        reference="#PWR10",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr10-gnd-u1",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=D2_X, y=D2_GND_Y, angle=0,
        reference="#PWR11",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr11-gnd-d2",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C4_X, y=C4_GND_Y, angle=0,
        reference="#PWR12",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr12-gnd-c4",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C14_X, y=C14_GND_Y, angle=0,
        reference="#PWR13",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr13-gnd-c14",
    ))

    # ----- +5V flag at top-right of the buck block -----
    parts.append(_sch_power_flag(
        lib_id="power:+5V", value="+5V",
        x=COL_5V, y=FLAG_5V_Y, angle=0,
        reference="#PWR14",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr14-5v",
    ))

    # ----- PWR_FLAG sentinel on the new +5V net -----
    # Without this, ERC would error "Input Power pin not driven by any Output
    # Power pins" on the +5V net — the LM2596's OUT pin is an `output` (not
    # `power_out`) so it doesn't count as a power source for the ERC check.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_5V, y=JUNC_5V_Y, angle=0,
        reference="#FLG04",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=-2.54,
        uuid_tag="flg04-5v",
    ))

    # =========================================================================
    # 5V -> 3.3V buck converter block (U2 TPS62933 + L2 + R2/R3 FB div + C5/C15/C6/C16/C7)
    # =========================================================================
    # Cascaded second buck stage. Takes the +5V rail produced by U1 (above)
    # and steps it down to a regulated 3.3V rail that powers the ESP32-C6
    # DevKitM-1-N4 (via its 3V3 pin, bypassing the module's onboard LDO so
    # we don't dissipate ~250 mW close to the SEN66 air-quality sensor),
    # plus the SEN66 itself and the NT3H1101 NFC tag.
    #
    # Component selection rationale (see commit message and CLAUDE.md):
    #   * TPS62933   : 3.8-30 V Vin range (17 V abs-max for the typical-use
    #                  recommendation, well above our 5 V), 3 A, 1.2 MHz
    #                  default (v0.40 post-order doc fix: pre-fix said
    #                  "500 kHz" but per TI SLUSEA4D §"Switching Frequency
    #                  Selection" the default for RT pin tied directly to
    #                  GND is 1.2 MHz internal oscillator; 500 kHz requires
    #                  RTSeT resistor sizing). SYNCHRONOUS topology (no
    #                  external Schottky catch diode needed — high-side
    #                  and low-side both internal). SOT-583-8 package,
    #                  JLCPCB Basic library. ~95% efficiency at ~300 mA
    #                  load — much better than LM2596's ~80% (LM2596 has
    #                  external Schottky losses and runs at 150 kHz so
    #                  the inductor ripple is much larger). The 17 V
    #                  Vin_max ceiling that ruled it out upstream of D1
    #                  is irrelevant here because we cascade from the
    #                  regulated +5V rail.
    #   * L2 2.2uH  : Per TPS62933 datasheet typical-application table for
    #                  3.3 V output at 1.2 MHz. Shielded SMD ferrite-core
    #                  inductor with ≥2 A saturation and ~50 mOhm DCR.
    #                  4×4 mm or 3×3 mm package — much smaller than LM2596's
    #                  33 uH because the higher fsw drops the inductor
    #                  requirement by ~15×.
    #   * R2 100k 1% / R3 30.9k 1% (FB divider): TPS62933 FB pin reference
    #                  voltage = 0.8 V per TI datasheet §"Electrical
    #                  Characteristics" (the pre-v0.36 0.6 V assumption was
    #                  WRONG — TPS62930 family is 0.6 V, TPS62933 is 0.8 V).
    #                  Vout = Vref × (1 + R2/R3) = 0.8 × (1 + 100/30.9) =
    #                  3.39 V — within ±3 % of 3.3 V target and well below
    #                  ESP32-C6 / SEN66 / NT3H1101 absolute-max VDD of 3.6 V.
    #                  R3 = 30.9 kΩ gives a low-current divider
    #                  (~26 µA), and R2 = 100 kΩ is a standard E96 value.
    #                  1% tolerance keeps the output voltage variation due
    #                  to divider tolerance below ±35 mV (≈1 %).
    #   * C5 10uF + C15 100nF : input bulk + HF ceramic bypass at U2.VIN.
    #                  Per datasheet: ceramic X5R/X7R; 16 V rating gives
    #                  3× margin over the 5 V input.
    #   * C6 22uF + C16 100nF : output bulk + HF ceramic bypass at the
    #                  +3.3V rail. Per datasheet; 10 V rating gives 3× margin
    #                  over 3.3 V.
    #   * C7 100nF (BST): bootstrap capacitor from BST pin to SW pin.
    #                  REQUIRED by TPS62933 for the high-side gate driver
    #                  bootstrap supply. Datasheet value.
    #   * C8 47nF (SS) : soft-start capacitor from SS pin to GND. SS tied
    #                  directly to GND DISABLES soft-start in TPS62933
    #                  (an earlier comment claiming a ~0.6 ms default was
    #                  incorrect — that figure came from a different TI
    #                  device family). With C8=47nF the soft-start time is
    #                  t_ss = C_ss * V_ref / I_ss = 47nF * 0.6V / 5uA ~=
    #                  5.6 ms, which falls within the 2-10 ms power-ramp
    #                  window specified by SEN66's application note for
    #                  reliable sensor initialization on cold boot.
    #
    # The RT pin (programmable switching frequency) is tied to GND — that
    # selects the default ~1.2 MHz internal oscillator (v0.40 post-order
    # doc fix; per TI SLUSEA4D § "Switching Frequency Selection"). SS pin
    # (soft-start)
    # uses C8 (47 nF) to ground to set t_ss ~= 5.6 ms (in the SEN66 power-
    # ramp window of 2-10 ms). EN pin is tied to VIN via a direct wire
    # (always-on operation — the TPS62933 enables when EN > 1.18 V, and
    # +5V provides plenty of headroom). The BST pin gets its bootstrap
    # cap C7 to the SW node.
    #
    # Layout (page-absolute mm, KiCad +Y is down on screen):
    #
    # The buck block sits BELOW the +24V protected-rail section so the
    # cascade flow reads top-to-bottom (24 V → 5 V → 3.3 V). U2 is placed
    # in the same X column as U1 (X=200.66) — vertically aligned, ~70 mm
    # below — emphasising the cascade visually. The +5V net enters U2.VIN
    # from above via a "+5V" global symbol placed at the top of the block;
    # the +3.3V net exits to the right through C6/C16 decoupling and a
    # PWR_FLAG sentinel into the +3.3V power flag at the far-right.

    # ----- U2: TPS62933 buck regulator -----
    # Anchor at X=200.66 (same X column as U1). Y=144.78 puts the body in
    # the clear area below the existing power-protection block (whose
    # lowest element is the GND flag at Y=132.08). With U2_Y=144.78 the
    # body spans Y=[134.62, 154.94] and pin rows are:
    #   VIN row Y=137.16 (lib (-7.62, +7.62) -> schem y-7.62 = 137.16)
    #   BST row Y=137.16 (same as VIN — used for the +3.3V bus on the right)
    #   EN  row Y=139.70
    #   SW  row Y=144.78 (centre — switch-node horizontal)
    #   SS  row Y=147.32
    #   RT  row Y=149.86
    #   FB  row Y=152.40
    #   GND row Y=157.48 (centre-bottom)
    U2_X = 200.66 + PWR_X_SHIFT
    U2_Y = 144.78 + PWR_Y_SHIFT
    U2_VIN_X    = U2_X - 7.62     # 193.04
    U2_VIN_Y    = U2_Y - 7.62     # 137.16 — +5V input bus row
    U2_EN_X     = U2_X - 7.62     # 193.04
    U2_EN_Y     = U2_Y - 5.08     # 139.70
    U2_RT_X     = U2_X - 7.62     # 193.04
    U2_RT_Y     = U2_Y + 5.08     # 149.86 — tied to GND (default 1.2 MHz)
    U2_SS_X     = U2_X - 7.62     # 193.04
    U2_SS_Y     = U2_Y + 2.54     # 147.32 — tied to GND via C8 (47 nF
                                  # soft-start cap; t_ss ~= 5.6 ms)
    U2_GND_X    = U2_X            # 200.66
    U2_GND_Y    = U2_Y + 12.7     # 157.48
    U2_SW_X     = U2_X + 7.62     # 208.28 — switch node
    U2_SW_Y     = U2_Y            # 144.78
    U2_BST_X    = U2_X + 7.62     # 208.28
    U2_BST_Y    = U2_Y - 7.62     # 137.16 — bootstrap cap node
    U2_FB_X     = U2_X + 7.62     # 208.28
    U2_FB_Y     = U2_Y + 7.62     # 152.40 — feedback tap

    # ----- C5: input bulk ceramic, 10uF 16V, angle=0 -----
    # Non-polarized ceramic X5R/X7R. Pin 1 (top) on +5V bus, pin 2 (bottom)
    # to GND. C5 sits 15.24 mm left of C15 — wide enough that the
    # value-text label "10uF 16V" (rendered ~10 mm at size 1.27) clears
    # C15's value-text "100nF" without visual overlap.
    C5_X = 170.18 + PWR_X_SHIFT   # 134 × 1.27
    C5_Y = 140.97 + PWR_Y_SHIFT   # 111 × 1.27
    C5_TOP_Y = C5_Y - 3.81        # 137.16 — on +5V bus row
    C5_BOT_Y = C5_Y + 3.81        # 144.78
    C5_GND_Y = 147.32 + PWR_Y_SHIFT  # GND symbol, 2.54 below cap.bot

    # ----- C15: input HF ceramic bypass, 100nF, angle=0 -----
    C15_X = 185.42 + PWR_X_SHIFT  # 146 × 1.27 — 15.24 mm right of C5, 7.62 left of VIN
    C15_Y = 140.97 + PWR_Y_SHIFT
    C15_TOP_Y = C15_Y - 3.81      # 137.16
    C15_BOT_Y = C15_Y + 3.81      # 144.78
    C15_GND_Y = 147.32 + PWR_Y_SHIFT

    # ----- +5V drop symbol -----
    # Global "+5V" power label placed ABOVE U2's VIN row, with angle=180
    # so the triangle points DOWN toward the buck block. Pin sits at the
    # symbol anchor (193.04, 130.81); a short vertical wire drops it onto
    # the VIN bus at Y=137.16. The same vertical wire continues DOWN past
    # the VIN bus row through U2.VIN pin to U2.EN pin — this is the
    # always-on EN tie (EN → VIN).
    Y_5V_DROP_TOP = 130.81 + PWR_Y_SHIFT  # 103 × 1.27 — on connection grid

    # ----- C7: BST (bootstrap) ceramic capacitor, 100nF, angle=0 -----
    # Vertical between U2.BST (top pin, Y=137.16) and U2.SW (bot pin,
    # Y=144.78). Placed at X=213.36, 5.08 mm right of the BST/SW pin
    # column (208.28). C7.top → BST extension wire row, C7.bot → SW
    # extension wire row. Required by TPS62933 for the high-side gate
    # driver bootstrap supply.
    C7_X = 213.36 + PWR_X_SHIFT   # 168 × 1.27
    C7_Y = 140.97 + PWR_Y_SHIFT
    C7_TOP_Y = C7_Y - 3.81        # 137.16 — on BST row
    C7_BOT_Y = C7_Y + 3.81        # 144.78 — on SW row

    # ----- C8: SS (soft-start) ceramic capacitor, 47nF, angle=0 -----
    # Vertical between U2.SS (top pin, Y=147.32) and a local GND symbol
    # below. Placed at X=191.77 (= 151 × 1.27), 1.27 mm LEFT of the U2.SS
    # pin tip column (193.04). C8.top sits exactly on the SS pin row so
    # the SS -> C8.top connection is a single short horizontal wire of
    # 1.27 mm. C8.bot connects to a new local GND symbol below.
    #
    # Without C8, with SS tied directly to GND, the TPS62933 disables
    # soft-start completely — Vout ramps in <<1 ms which can leave the
    # downstream SEN66 sensor in an undefined state on cold boot
    # (SEN66 datasheet requires a 2-10 ms power ramp for reliable init).
    # With C8 = 47 nF: t_ss = C_ss * V_ref / I_ss = 47 nF * 0.6 V / 5 uA
    # = 5.64 ms, comfortably within the 2-10 ms window.
    C8_X = 191.77 + PWR_X_SHIFT   # 151 × 1.27 — 1.27 mm left of SS pin tip
    C8_Y = 151.13 + PWR_Y_SHIFT   # 119 × 1.27
    C8_TOP_Y = C8_Y - 3.81        # 147.32 — matches U2.SS pin Y row
    C8_BOT_Y = C8_Y + 3.81        # 154.94 — body bottom row
    C8_GND_Y = 157.48 + PWR_Y_SHIFT  # GND symbol anchor below C8.bot

    # ----- L2: 2.2 uH shielded inductor, angle=0 -----
    # Vertical, between U2.SW (right of the body) and the +3.3V output bus.
    # L2.bot pin on the SW horizontal extension row (Y=144.78), L2.top
    # pin on the +3.3V bus row (Y=137.16). 7.62 mm pin-to-pin spacing
    # fits naturally between the two rows. Placed at X=226.06, 12.7 mm
    # right of C7's column — wide enough that C7's "100nF" value-text
    # (left-justified at X=C7+2.54) doesn't run into L2's reference text
    # (right-justified at X=L2-2.54).
    L2_X = 226.06 + PWR_X_SHIFT   # 178 × 1.27
    L2_Y = 140.97 + PWR_Y_SHIFT
    L2_TOP_Y = L2_Y - 3.81        # 137.16 — on +3.3V bus row
    L2_BOT_Y = L2_Y + 3.81        # 144.78 — on SW extension row

    # ----- R2 / R3: feedback divider for 3.3V output -----
    # TPS62933 FB pin reference voltage Vref = 0.8 V (TI datasheet, NOT 0.6 V
    # as the pre-v0.36 comments wrongly stated — that was the TPS62930-family
    # value, confused into this commentary).
    #   Vout = Vref × (1 + R2/R3)  =>  R2/R3 = (Vout/Vref - 1) = 3.125 for Vout=3.3V
    # With R3 = 30.9 kΩ:
    #   R2 = 96.6 kΩ ideal → nearest E96 = 100 kΩ
    #   → Vout = 0.8 × (1 + 100/30.9) = 3.39 V  (within ±3 % of 3.3 V target)
    #
    # Layout: R2 (top, 100 kΩ) and R3 (bottom, 30.9 kΩ) vertically stacked,
    # forming a divider between +3.3V (R2.top) and GND (R3.bot). FB tap
    # point is the R2.bot/R3.top junction. The U2.FB pin (at X=208.28,
    # Y=152.40) routes to the FB tap via a short L-wire: drop DOWN from
    # FB pin to Y=156.21 (clear of U2 body bottom at Y=154.94), then
    # RIGHT to the FB tap column at X=226.06.
    #
    # R2 and R3 are placed with a 2.54 mm gap between R2.bot (Y=144.78)
    # and R3.top (Y=147.32) so the two resistor body rectangles don't
    # touch on screen — easier to read. The connecting wire between
    # R2.bot and R3.top serves as the FB tap point.
    #
    # Wait — re-examining: if R2.top is to land on the +3.3V bus row
    # (Y=137.16) directly, then R2_Y=140.97 (R2.top = 140.97 - 3.81 =
    # 137.16, R2.bot = 144.78). But that puts R2.bot at Y=144.78 = the
    # SW row! At X=226.06 the SW extension wire does NOT reach (SW wire
    # X∈[208.28, 218.44]), so no electrical conflict, but visually the
    # FB-tap row at Y=144.78 sits on the same horizontal as the SW node.
    #
    # Cleaner: keep R2.top one row above the bus and add a short vertical
    # wire from R2.top up to the +3.3V bus. R2_Y=148.59 → R2.top=144.78
    # (a few mm below bus), then r2top-to-bus wire from (226.06, 144.78)
    # → (226.06, 137.16). R2.bot = 152.40. R3_Y=156.21 → R3.top=152.40,
    # R3.bot=160.02. FB tap = R2.bot = R3.top = (226.06, 152.40), same
    # Y as the U2.FB pin row — so the FB pin wire from (208.28, 152.40)
    # to (226.06, 152.40) is a single horizontal segment, no L-routing.
    # Much cleaner.
    COL_FB_DIV = 240.03 + PWR_X_SHIFT  # 189 × 1.27 — FB divider column (13.97 mm right of L2)
    R2_X = COL_FB_DIV
    R2_Y = 148.59 + PWR_Y_SHIFT   # 117 × 1.27
    R2_TOP_Y = R2_Y - 3.81        # 144.78
    R2_BOT_Y = R2_Y + 3.81        # 152.40 — FB tap row, matches U2.FB pin Y
    R3_X = COL_FB_DIV
    R3_Y = 156.21 + PWR_Y_SHIFT   # 123 × 1.27
    R3_TOP_Y = R3_Y - 3.81        # 152.40 — FB tap row, shared with R2.bot
    R3_BOT_Y = R3_Y + 3.81        # 160.02
    R3_GND_Y = 163.83 + PWR_Y_SHIFT  # GND symbol below R3.bot

    # ----- +3.3V output decoupling -----
    # C6 (22uF) and C16 (100nF) tap the +3.3V bus to GND. Placed to the
    # right of the FB divider with 15-16 mm column spacing so the
    # value-text labels ("44.2k 1%" / "22uF 10V" / "100nF") never overlap.
    C6_X = 256.54 + PWR_X_SHIFT   # 202 × 1.27 (16.51 right of R2)
    C6_Y = 140.97 + PWR_Y_SHIFT
    C6_TOP_Y = C6_Y - 3.81        # 137.16 — on +3.3V bus
    C6_BOT_Y = C6_Y + 3.81        # 144.78
    C6_GND_Y = 147.32 + PWR_Y_SHIFT

    C16_X = 271.78 + PWR_X_SHIFT  # 214 × 1.27 (15.24 right of C6)
    C16_Y = 140.97 + PWR_Y_SHIFT
    C16_TOP_Y = C16_Y - 3.81      # 137.16
    C16_BOT_Y = C16_Y + 3.81      # 144.78
    C16_GND_Y = 147.32 + PWR_Y_SHIFT

    # ----- +3.3V flag, PWR_FLAG sentinel -----
    # Column = C16 + 7.62 = 279.40. This sits ~25 mm right of the +5V flag
    # column (X=254 upstream), keeping the buck-3.3V section's PWR_FLAG
    # and flag visually distinct from the upstream +5V flag (which lives
    # in the same column but at a much lower Y, in the U1 block).
    COL_3V3      = 279.40 + PWR_X_SHIFT  # 220 × 1.27
    Y_3V3_BUS    = 137.16 + PWR_Y_SHIFT  # +3.3V bus row (same Y as VIN bus, but different X range)
    JUNC_3V3_Y   = 134.62 + PWR_Y_SHIFT  # PWR_FLAG sentinel sits here
    FLAG_3V3_Y   = 132.08 + PWR_Y_SHIFT  # +3V3 triangle, 2.54 above sentinel

    # ----- Buck-3.3V wires -----
    # Input side: +5V symbol → VIN bus, with EN tied to VIN as always-on.
    # The +5V "drop" symbol sits in the VIN/EN pin column (X=193.04)
    # above the body; its anchor is also the wire endpoint (length 0 pin
    # so the pin is at the symbol's (x, y)).
    Y_5V_DROP_TOP_X = U2_VIN_X    # 193.04 — VIN/EN/+5V drop column
    parts.append(_sch_wire(Y_5V_DROP_TOP_X, Y_5V_DROP_TOP, U2_VIN_X, U2_VIN_Y, "5v-to-vin"))
    parts.append(_sch_wire(U2_VIN_X, U2_VIN_Y, U2_EN_X, U2_EN_Y, "vin-to-en"))
    # VIN bus horizontal: C5.top → C15.top → U2.VIN pin
    parts.append(_sch_wire(C5_X, U2_VIN_Y, U2_VIN_X, U2_VIN_Y, "vin-bus-c5-c15-u2"))
    # C5 and C15 drops to local GND symbols
    parts.append(_sch_wire(C5_X, C5_BOT_Y, C5_X, C5_GND_Y, "c15ot-to-gnd"))
    parts.append(_sch_wire(C15_X, C15_BOT_Y, C15_X, C15_GND_Y, "c15bot-to-gnd"))

    # RT → GND: RT pin (programmable f_sw) tied to GND for default ~1.2 MHz.
    # The previous SS+RT shared-drop wiring was changed when SS was given
    # its own soft-start cap (C8): SS no longer shares a wire with RT.
    RT_GND_Y = 152.40 + PWR_Y_SHIFT  # GND symbol Y, below RT pin (149.86)
    parts.append(_sch_wire(U2_RT_X, U2_RT_Y, U2_RT_X, RT_GND_Y, "rt-to-gnd"))

    # SS → C8.top → C8.bot → GND: soft-start cap path. C8 sits 1.27 mm
    # west of the SS pin tip column so the SS → C8.top connection is a
    # single short horizontal wire; the C8.bot → GND drop continues
    # vertically to a new local GND symbol.
    parts.append(_sch_wire(U2_SS_X, U2_SS_Y, C8_X, C8_TOP_Y, "ss-to-c8"))
    parts.append(_sch_wire(C8_X, C8_BOT_Y, C8_X, C8_GND_Y, "c8bot-to-gnd"))

    # U2.GND (centre-bottom pin, pin 4) → local GND symbol below
    U2_GND_SYM_Y = 161.29 + PWR_Y_SHIFT  # 3.81 below U2.GND pin
    parts.append(_sch_wire(U2_GND_X, U2_GND_Y, U2_GND_X, U2_GND_SYM_Y, "u2gnd-to-gndsym"))

    # BST extension: U2.BST → C7.top, single horizontal stub.
    parts.append(_sch_wire(U2_BST_X, U2_BST_Y, C7_X, C7_TOP_Y, "u2bst-to-c7top"))
    # SW extension: U2.SW → L2.bot horizontal. Passes through C7.bot tap
    # column (X=213.36) — C7.bot pin endpoint lands on this wire, needing
    # a junction at the tap point.
    parts.append(_sch_wire(U2_SW_X, U2_SW_Y, L2_X, L2_BOT_Y, "u2sw-to-l2bot"))

    # FB pin → FB tap (R2.bot/R3.top junction at COL_FB_DIV). Single
    # horizontal wire at Y=152.40 (FB pin row = FB tap row, same Y), no
    # L-routing needed because the divider sits directly to the right of
    # the body in the same Y row.
    parts.append(_sch_wire(U2_FB_X, U2_FB_Y, COL_FB_DIV, R2_BOT_Y, "u2fb-to-fbtap"))

    # R2.top → +3.3V bus: short vertical hop up. R2.top at (226.06, 144.78);
    # +3.3V bus at Y=137.16.
    parts.append(_sch_wire(COL_FB_DIV, R2_TOP_Y, COL_FB_DIV, Y_3V3_BUS, "r2top-to-3v3bus"))

    # R3.bot → local GND symbol below
    parts.append(_sch_wire(COL_FB_DIV, R3_BOT_Y, COL_FB_DIV, R3_GND_Y, "r3bot-to-gnd"))

    # +3.3V bus horizontal: from L2.top RIGHT through R2-tap column,
    # C6 column, C16 column, to the flag column COL_3V3. Single wire
    # with junctions at the four tap points (R2 vertical end, C6 pin,
    # C16 pin, mid-bus T's).
    parts.append(_sch_wire(L2_X, Y_3V3_BUS, COL_3V3, Y_3V3_BUS, "3v3-bus"))

    # C6 and C16 drops to local GND symbols
    parts.append(_sch_wire(C6_X, C6_BOT_Y, C6_X, C6_GND_Y, "c16ot-to-gnd"))
    parts.append(_sch_wire(C16_X, C16_BOT_Y, C16_X, C16_GND_Y, "c16bot-to-gnd"))

    # +3.3V bus terminus → PWR_FLAG sentinel column upward, then to +3V3 flag.
    parts.append(_sch_wire(COL_3V3, Y_3V3_BUS, COL_3V3, JUNC_3V3_Y, "3v3-bus-to-junc"))
    parts.append(_sch_wire(COL_3V3, JUNC_3V3_Y, COL_3V3, FLAG_3V3_Y, "3v3-junc-to-flag"))

    # ----- Buck-3.3V junctions -----
    # VIN 4-way tap: VIN bus horizontal ends, +5V drop wire passes through,
    # VIN-to-EN wire starts. Plus U2.VIN pin endpoint.
    parts.append(_sch_junction(U2_VIN_X, U2_VIN_Y, "vin-u2"))
    # C15.top tap on VIN bus (mid-bus T with pin endpoint)
    parts.append(_sch_junction(C15_X, U2_VIN_Y, "vin-c15"))
    # SW wire passes through C7.bot tap column
    parts.append(_sch_junction(C7_X, U2_SW_Y, "sw-c7"))
    # FB tap: R2.bot pin + R3.top pin + FB wire end = 3 endpoints
    parts.append(_sch_junction(COL_FB_DIV, R2_BOT_Y, "fb-tap"))
    # +3.3V bus mid-bus T's: R2-vertical end, C6 pin, C16 pin
    parts.append(_sch_junction(COL_FB_DIV, Y_3V3_BUS, "3v3-r2"))
    parts.append(_sch_junction(C6_X, Y_3V3_BUS, "3v3-c6"))
    parts.append(_sch_junction(C16_X, Y_3V3_BUS, "3v3-c16"))
    # PWR_FLAG sentinel position on the vertical to the +3V3 flag
    parts.append(_sch_junction(COL_3V3, JUNC_3V3_Y, "3v3"))

    # ----- U2: TPS62933 -----
    parts.append(_sch_buck_tps62933(
        x=U2_X, y=U2_Y, angle=0,
        reference="U2", value="TPS62933", uuid_tag="u2",
    ))

    # ----- L2: 2.2 uH shielded inductor (2 A sat, ~50 mOhm DCR) -----
    parts.append(_sch_inductor(
        x=L2_X, y=L2_Y, angle=0,
        reference="L2", value="2.2uH 2A", uuid_tag="l2",
    ))

    # ----- C5: input bulk ceramic, 10 uF / 16 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C5_X, y=C5_Y, angle=0,
        reference="C5", value="10uF 16V", uuid_tag="c5",
    ))

    # ----- C15: input HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C15_X, y=C15_Y, angle=0,
        reference="C15", value="100nF", uuid_tag="c15",
    ))

    # ----- C6: output bulk ceramic, 22 uF / 10 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C6_X, y=C6_Y, angle=0,
        reference="C6", value="22uF 10V", uuid_tag="c6",
    ))

    # ----- C16: output HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C16_X, y=C16_Y, angle=0,
        reference="C16", value="100nF", uuid_tag="c16",
    ))

    # ----- C7: BST bootstrap ceramic, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C7_X, y=C7_Y, angle=0,
        reference="C7", value="100nF", uuid_tag="c7",
    ))

    # ----- C8: SS soft-start ceramic, 47 nF -----
    # See the C8 constants comment block above for the rationale (TPS62933
    # SS=GND disables soft-start; C8=47nF sets t_ss ~= 5.6 ms within the
    # SEN66 datasheet's 2-10 ms power-ramp window).
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C8_X, y=C8_Y, angle=0,
        reference="C8", value="47nF", uuid_tag="c8",
    ))

    # ----- R2: feedback divider top, 100 kΩ 1% (v0.36 — was 44.2k pre-fix) -----
    # See CRITICAL-2 fix in v0.36 swarm audit. TPS62933 Vref = 0.8 V per the
    # TI datasheet §"Electrical Characteristics" (NOT 0.6 V as the pre-v0.36
    # comments wrongly assumed). For Vout = 3.3 V: R2/R3 = (3.3/0.8 - 1) =
    # 3.125, so R2 = 100 k + R3 = 30.9 k yields Vout = 0.8 × (1 + 100/30.9)
    # = 3.39 V — within ±5 % of 3.3 V target. The pre-v0.36 schematic values
    # (R2=44.2k / R3=10k) were designed for Vref=0.6 V and would have produced
    # 4.34 V at the actual Vref=0.8 V — destroying ESP32-C6 + SEN66 (both
    # Vdd_max = 3.6 V).
    parts.append(_sch_resistor(
        x=R2_X, y=R2_Y, angle=0,
        reference="R2", value="100k 1%", uuid_tag="r2",
    ))

    # ----- R3: feedback divider bottom, 30.9 kΩ 1% (v0.36 — was 10k pre-fix) -----
    parts.append(_sch_resistor(
        x=R3_X, y=R3_Y, angle=0,
        reference="R3", value="30.9k 1%", uuid_tag="r3",
    ))

    # ----- +5V drop symbol (taps the global +5V net into U2.VIN) -----
    # angle=180 so the triangle points DOWN. The value-text "+5V" sits
    # above the symbol anchor (value_offset_y=-3.556, same as the upstream
    # +5V flag).
    parts.append(_sch_power_flag(
        lib_id="power:+5V", value="+5V",
        x=Y_5V_DROP_TOP_X, y=Y_5V_DROP_TOP, angle=180,
        reference="#PWR15",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr15-5v-drop",
    ))

    # ----- +3.3V flag at top-right of the buck-3.3V block -----
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=COL_3V3, y=FLAG_3V3_Y, angle=0,
        reference="#PWR16",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr16-3v3",
    ))

    # ----- Local GND symbols around U2 / L2 / R3 / caps -----
    # All share the global GND net. No PWR_FLAG sentinel on any of these
    # — FLG02 (on J1.2's drop) already supplies the ERC power-source
    # marker for the GND net.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C5_X, y=C5_GND_Y, angle=0,
        reference="#PWR17",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr17-gnd-c5",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C15_X, y=C15_GND_Y, angle=0,
        reference="#PWR18",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr18-gnd-c15",
    ))
    # RT pin GND drop (SS now has its own C8 soft-start cap to GND, so it
    # no longer shares this GND symbol with RT — see #PWR24 below for C8).
    # uuid_tag retained as "pwr19-gnd-ssrt" to preserve UUID stability
    # across the cap-fix rework.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U2_RT_X, y=RT_GND_Y, angle=0,
        reference="#PWR19",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr19-gnd-ssrt",
    ))
    # U2.GND (pin 4)
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U2_GND_X, y=U2_GND_SYM_Y, angle=0,
        reference="#PWR20",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr20-gnd-u2",
    ))
    # R3.bot (divider bottom to GND)
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_FB_DIV, y=R3_GND_Y, angle=0,
        reference="#PWR21",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr21-gnd-r3",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C6_X, y=C6_GND_Y, angle=0,
        reference="#PWR22",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr22-gnd-c6",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C16_X, y=C16_GND_Y, angle=0,
        reference="#PWR23",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr23-gnd-c16",
    ))
    # C8.bot (soft-start cap to GND)
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C8_X, y=C8_GND_Y, angle=0,
        reference="#PWR24",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr24-gnd-c8",
    ))

    # ----- PWR_FLAG sentinel on the new +3.3V net -----
    # Without this, ERC would error "Input Power pin not driven by any
    # Output Power pins" on the +3.3V net — TPS62933's SW pin is an
    # `output` (not `power_out`), so it doesn't count as a power source
    # for the ERC check.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_3V3, y=JUNC_3V3_Y, angle=0,
        reference="#FLG05",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=-2.54,
        uuid_tag="flg05-3v3",
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
        {POWER_LIB_SYMBOLS}
        \t)
        {body}
        \t(embedded_fonts no)
        )
        """)

# -----------------------------------------------------------------------------
# 3c) MCU sub-sheet — ESP32-C6-DevKitM-1-N4 (U3) + local decoupling + recovery header
# -----------------------------------------------------------------------------
# Embedded lib_symbols for the MCU sub-sheet. Self-contained: each sub-sheet
# carries its own copy of the symbols it uses (the +3V3 / GND and Device:C /
# Device:C_Polarized blocks are intentionally duplicated with POWER_LIB_SYMBOLS
# so the .kicad_sch file opens identically on any machine).
#
# Symbol sources:
#   - "OAS:ESP32-C6_DevKitM-1" : own work, defined inline below. Models the
#     Espressif official ESP32-C6-DevKitM-1-N4 development kit.
#
#     # Module Identification
#     MPN  : ESP32-C6-DevKitM-1-N4
#     EAN  : 5904422385651 (Botland)
#     User guide:
#       https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html
#     Chip : ESP32-C6FH4 (ESP32-C6-MINI-1 SoM with 4 MB internal SiP flash).
#            GPIO 10 and GPIO 11 are NOT bonded out — they serve internal
#            flash communication. Available GPIOs: 0, 1, 2, 3, 4, 5, 6, 7,
#            8, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23 (22 total).
#     Form factor : 48.26 × 25.4 mm. Two USB-C connectors (one through an
#                   onboard USB-to-UART bridge IC, one direct to native
#                   USB-Serial-JTAG on GPIO 12/13). Onboard power LED and
#                   addressable RGB NeoPixel (GPIO 8). Reset + Boot
#                   pushbuttons.
#     Headers : Two 15-pin headers, J1 (left) and J3 (right), 2.54 mm
#               pitch, mirroring Espressif's numbering. The symbol below
#               exposes all 30 header positions in faithful order so the
#               schematic matches the physical module.
#
#     Pin layout (J1 left, J3 right) reproduced from the official user
#     guide. Pin 1 of each header is the TOPMOST pin in this symbol so
#     the body matches the silk on the dev-kit (USB-C ports at the top).
#
#       J1 (left side, top→bottom)            J3 (right side, top→bottom)
#         1  3V3      power_in                  1  GND      power_in
#         2  RST      input                     2  GPIO16   bidirectional
#         3  GPIO2    bidirectional             3  GPIO17   bidirectional
#         4  GPIO3    bidirectional             4  GPIO23   bidirectional
#         5  GPIO4    bidirectional (MTMS)      5  GPIO22   bidirectional
#         6  GPIO5    bidirectional (MTDI)      6  GPIO21   bidirectional
#         7  GPIO0    bidirectional             7  GPIO20   bidirectional
#         8  GPIO1    bidirectional             8  GPIO19   bidirectional
#         9  GPIO8    bidirectional (RGB LED)   9  GPIO18   bidirectional
#        10  GPIO6    bidirectional (MTCK)     10  GPIO15   bidirectional
#        11  GPIO7    bidirectional (MTDO)     11  GPIO9    bidirectional (BOOT strap)
#        12  GPIO14   bidirectional            12  GND      power_in
#        13  GND      power_in                 13  GPIO13   bidirectional (USB D+)
#        14  5V       power_in                 14  GPIO12   bidirectional (USB D-)
#        15  GND      power_in                 15  GND      power_in
#
#   - "Connector_Generic:Conn_01x06" : copied verbatim from KiCad 10's stock
#     Connector_Generic.kicad_sym (GPL).
#   - "Device:R" : copied verbatim from KiCad 10's stock Device.kicad_sym
#     (GPL). Needed in the MCU sheet for R5/R6 I²C pull-ups.
#   - "Device:C", "Device:C_Polarized", "power:+3V3", "power:GND" : copied
#     verbatim from KiCad 10's stock libraries (GPL).


# DevKitM-1-N4 pin definitions — single source of truth for the lib symbol
# and (downstream) the gen_mcu_sch wiring helper. Each entry is
# (pin_number, gpio_name, type, header, header_pos). `gpio_name` is the
# string KiCad shows next to the pin in eeschema; `type` selects the
# KiCad pin electrical class.
#
# Pin number numbering convention (this symbol):
#   pins 1..15  = J1 (left header), top→bottom
#   pins 16..30 = J3 (right header), top→bottom
# Pin 1 = J1 top; pin 16 = J3 top. This way the geometric pin order
# mirrors the physical module silk and gen_mcu_sch can compute
# row Y by index directly.
ESP32C6_DEVKITM1_PINS: list[tuple[int, str, str, str, int]] = [
    # J1 (left side)
    ( 1, "3V3",      "power_in",      "J1",  1),
    ( 2, "RST",      "input",         "J1",  2),
    ( 3, "GPIO2",    "bidirectional", "J1",  3),
    ( 4, "GPIO3",    "bidirectional", "J1",  4),
    ( 5, "GPIO4",    "bidirectional", "J1",  5),
    ( 6, "GPIO5",    "bidirectional", "J1",  6),
    ( 7, "GPIO0",    "bidirectional", "J1",  7),
    ( 8, "GPIO1",    "bidirectional", "J1",  8),
    ( 9, "GPIO8",    "bidirectional", "J1",  9),
    (10, "GPIO6",    "bidirectional", "J1", 10),
    (11, "GPIO7",    "bidirectional", "J1", 11),
    (12, "GPIO14",   "bidirectional", "J1", 12),
    (13, "GND",      "power_in",      "J1", 13),
    (14, "5V",       "power_in",      "J1", 14),
    (15, "GND",      "power_in",      "J1", 15),
    # J3 (right side)
    (16, "GND",      "power_in",      "J3",  1),
    (17, "GPIO16",   "bidirectional", "J3",  2),
    (18, "GPIO17",   "bidirectional", "J3",  3),
    (19, "GPIO23",   "bidirectional", "J3",  4),
    (20, "GPIO22",   "bidirectional", "J3",  5),
    (21, "GPIO21",   "bidirectional", "J3",  6),
    (22, "GPIO20",   "bidirectional", "J3",  7),
    (23, "GPIO19",   "bidirectional", "J3",  8),
    (24, "GPIO18",   "bidirectional", "J3",  9),
    (25, "GPIO15",   "bidirectional", "J3", 10),
    (26, "GPIO9",    "bidirectional", "J3", 11),
    (27, "GND",      "power_in",      "J3", 12),
    (28, "GPIO13",   "bidirectional", "J3", 13),
    (29, "GPIO12",   "bidirectional", "J3", 14),
    (30, "GND",      "power_in",      "J3", 15),
]

# Quick lookup: signal-name → symbol pin number. The names in this map
# are the OAS-internal signal names (NOT the GPIO labels) — these are
# what gen_mcu_sch uses when it needs to find e.g. "the symbol pin
# tip for I2C_SDA". Pure GPIO labels (e.g. GPIO0/1/4/...) that we do
# NOT route are absent on purpose; they get no_connect markers driven
# by ESP32C6_DEVKITM1_PINS instead.
ESP32C6_DEVKITM1_SIGNAL_PIN: dict[str, int] = {
    # Power
    "3V3"        : 1,   # J1.1
    # Reset / boot — connected externally to recovery header J2
    "RST"        : 2,   # J1.2 (RST pin, drives chip EN)
    # OAS-routed GPIOs
    "LD2410_OUT" : 3,   # J1.3 = GPIO2 — safe non-strap input
    "NFC_FD"     : 4,   # J1.4 = GPIO3 — safe non-strap input
    "WS2812_DIN" : 9,   # J1.9 = GPIO8 — drives SK6812-SIDE AQI ring DIN
                        # (v0.16). Same GPIO as the DevKitM-1's onboard
                        # NeoPixel; the onboard NeoPixel is unreachable in
                        # deployed OAS units (it's wired to VCC_5V which
                        # floats without USB), so this GPIO drives only
                        # the external ring. See CLAUDE.md "OPEN ISSUE #2"
                        # resolution in the v0.16 changelog.
    "I2C_SDA"    : 10,  # J1.10 = GPIO6
    "I2C_SCL"    : 11,  # J1.11 = GPIO7
    "UART_TX"    : 17,  # J3.2  = GPIO16 → LD2410 RX, 256000 baud
    "UART_RX"    : 18,  # J3.3  = GPIO17 ← LD2410 TX, 256000 baud
    "BOOT"       : 26,  # J3.11 = GPIO9 (boot-mode strap)
    # v0.19: GPIO 12 / 13 routed to IO sub-sheet's J10 recovery header
    # (native USB-Serial-JTAG D-/D+). On a populated DevKitM-1 these
    # GPIOs are also wired internally to one of the on-module USB-C
    # ports; J10 exposes solder pads on the OAS PCB so a debugger can
    # drive native USB through a pogopin jig if both DevKitM-1 USB-C
    # ports get damaged. Sourced from MCU on the RIGHT edge alongside
    # UART_TX/RX. Signal names follow USB convention (DM = D-, DP = D+).
    "USB_DP"     : 28,  # J3.13 = GPIO13 (native USB D+)
    "USB_DM"     : 29,  # J3.14 = GPIO12 (native USB D-)
}

# Pin numbers that must receive (no_connect) markers (everything not
# used by OAS — every GPIO/Power pin that is neither in SIGNAL_PIN nor
# wired to a global power net such as GND).
#
# GND is handled separately: five GND pins (J1.13/15, J3.1/12/15)
# all tie to the GND power-symbol net; they are NOT no-connect.
# 5V (J1.14) is no-connect (we power the module from 3V3 only).
# GPIO8 (J1.9) is now ROUTED to the WS2812_DIN net driving the external
# SK6812-SIDE AQI status-LED ring (v0.16). The onboard DevKitM-1 NeoPixel
# on the same GPIO is unreachable in deployed units (its VDD is tied to
# VCC_5V which floats without USB), but the external ring on the OAS PCB
# is driven from the LM2596S-derived +5V rail so it lights up regardless.
# See CLAUDE.md "OPEN ISSUE #2" resolution in the v0.16 changelog.
# All remaining unused GPIOs are no-connect.
ESP32C6_DEVKITM1_NC_PINS: list[int] = [
    14,   # J1.14 = 5V       (powering via 3V3 pin; 5V unused)
    5,    # J1.5  = GPIO4    (MTMS, unused)
    6,    # J1.6  = GPIO5    (MTDI, unused)
    7,    # J1.7  = GPIO0    (unused)
    8,    # J1.8  = GPIO1    (unused)
    12,   # J1.12 = GPIO14   (unused)
    19,   # J3.4  = GPIO23   (unused)
    20,   # J3.5  = GPIO22   (unused)
    21,   # J3.6  = GPIO21   (unused)
    22,   # J3.7  = GPIO20   (unused)
    23,   # J3.8  = GPIO19   (unused)
    24,   # J3.9  = GPIO18   (unused)
    25,   # J3.10 = GPIO15   (unused)
    # v0.19: J3.13 (GPIO13 / USB D+) and J3.14 (GPIO12 / USB D-) moved
    # from NC to ESP32C6_DEVKITM1_SIGNAL_PIN as USB_DP / USB_DM; they
    # now reach the IO sub-sheet's J10 recovery header for native-USB
    # emergency flashing.
]
# Pin numbers that connect to the global GND net via a GND power symbol.
ESP32C6_DEVKITM1_GND_PINS: list[int] = [13, 15, 16, 27, 30]
# Sanity: every pin must be classified exactly once.
_all_pin_nums = {n for n, *_ in ESP32C6_DEVKITM1_PINS}
_used_signal_pins = set(ESP32C6_DEVKITM1_SIGNAL_PIN.values())
_used_gnd_pins = set(ESP32C6_DEVKITM1_GND_PINS)
_used_nc_pins = set(ESP32C6_DEVKITM1_NC_PINS)
assert _all_pin_nums == _used_signal_pins | _used_gnd_pins | _used_nc_pins, \
    f"ESP32C6_DEVKITM1 pin partition incomplete: " \
    f"missing={_all_pin_nums - (_used_signal_pins | _used_gnd_pins | _used_nc_pins)} "
assert not (_used_signal_pins & _used_gnd_pins), "signal vs GND overlap"
assert not (_used_signal_pins & _used_nc_pins), "signal vs NC overlap"
assert not (_used_gnd_pins & _used_nc_pins), "GND vs NC overlap"


# Geometric layout of the lib symbol (used by both the lib_symbol
# generator below and the gen_mcu_sch placement routine).
#
# 15 pin rows on each side, 2.54 mm pitch → 35.56 mm column height.
# Body rectangle a bit larger so pin labels have room. All coordinates
# are in the symbol-local frame (origin = symbol anchor).
ESP32C6_DEVKITM1_PIN_PITCH    = 2.54    # mm
ESP32C6_DEVKITM1_PIN_ROW_HALF = 14 * ESP32C6_DEVKITM1_PIN_PITCH / 2  # = 17.78 mm
ESP32C6_DEVKITM1_LIB_X_LEFT   = -12.7   # left-pin tip column (lib coords)
ESP32C6_DEVKITM1_LIB_X_RIGHT  = +12.7   # right-pin tip column
ESP32C6_DEVKITM1_LIB_PIN_LEN  = 2.54
# Body rectangle in lib coords (extends 1.27 mm above the top pin and
# below the bottom pin so the rectangle doesn't clip the pin labels).
ESP32C6_DEVKITM1_LIB_BODY_X   = 10.16
ESP32C6_DEVKITM1_LIB_BODY_Y   = ESP32C6_DEVKITM1_PIN_ROW_HALF + 1.27   # = 19.05


def _esp32c6_devkitm1_lib_symbol() -> str:
    """Return the (symbol "OAS:ESP32-C6_DevKitM-1" ...) lib-symbol block.

    Generated from ESP32C6_DEVKITM1_PINS so the pin list and the gen_mcu_sch
    wiring helper share a single source of truth. Indentation/formatting
    matches the surrounding MCU_LIB_SYMBOLS literal (tab-prefixed s-expr,
    leading two tabs = lib_symbols child block).

    KiCad's lib-symbol → schematic mapping at angle=0 is
        schem_y = anchor_y - lib_y
    so a top-of-screen pin needs a POSITIVE lib_y. Row 0 (pin 1, topmost
    on screen) therefore sits at lib_y = +ESP32C6_DEVKITM1_PIN_ROW_HALF.
    The pin-orientation field on the LEFT side is 0° (pin extends in the
    -X direction in lib coords, i.e. to the LEFT on screen). On the RIGHT
    side it is 180° (pin extends in +X, i.e. to the right on screen).
    Compare to KiCad's own Device:R: pin 1 (top) is at (0 3.81 270) —
    lib_y > 0 ⇒ top-of-screen, confirming the sign convention.
    """
    # Top row sits at lib_y = +PIN_ROW_HALF; each subsequent row is one
    # pitch MORE NEGATIVE, so row index goes top→bottom on screen.
    pin_y_top = +ESP32C6_DEVKITM1_PIN_ROW_HALF   # = +17.78
    body_x = ESP32C6_DEVKITM1_LIB_BODY_X
    body_y = ESP32C6_DEVKITM1_LIB_BODY_Y
    # Pin line definitions
    pin_lines: list[str] = []
    for idx, (n, name, ptype, header, hpos) in enumerate(ESP32C6_DEVKITM1_PINS):
        # The first 15 pins are J1 (left); rest are J3 (right).
        if header == "J1":
            x_lib = ESP32C6_DEVKITM1_LIB_X_LEFT
            row = hpos - 1                      # 0..14
            orient = 0                          # pin sticks out to the LEFT
        else:
            x_lib = ESP32C6_DEVKITM1_LIB_X_RIGHT
            row = hpos - 1
            orient = 180                        # pin sticks out to the RIGHT
        y_lib = pin_y_top - row * ESP32C6_DEVKITM1_PIN_PITCH
        pin_lines.append(
            f"\t\t\t\t(pin {ptype} line\n"
            f"\t\t\t\t\t(at {fmt(x_lib)} {fmt(y_lib)} {orient})\n"
            f"\t\t\t\t\t(length {fmt(ESP32C6_DEVKITM1_LIB_PIN_LEN)})\n"
            f"\t\t\t\t\t(name \"{name}\"\n"
            f"\t\t\t\t\t\t(effects\n"
            f"\t\t\t\t\t\t\t(font\n"
            f"\t\t\t\t\t\t\t\t(size 1.27 1.27)\n"
            f"\t\t\t\t\t\t\t)\n"
            f"\t\t\t\t\t\t)\n"
            f"\t\t\t\t\t)\n"
            f"\t\t\t\t\t(number \"{n}\"\n"
            f"\t\t\t\t\t\t(effects\n"
            f"\t\t\t\t\t\t\t(font\n"
            f"\t\t\t\t\t\t\t\t(size 1.27 1.27)\n"
            f"\t\t\t\t\t\t\t)\n"
            f"\t\t\t\t\t\t)\n"
            f"\t\t\t\t\t)\n"
            f"\t\t\t\t)"
        )
    pins_block = "\n".join(pin_lines)

    return (
        f"\t\t(symbol \"OAS:ESP32-C6_DevKitM-1\"\n"
        f"\t\t\t(pin_names\n"
        f"\t\t\t\t(offset 1.016)\n"
        f"\t\t\t)\n"
        f"\t\t\t(exclude_from_sim no)\n"
        f"\t\t\t(in_bom yes)\n"
        f"\t\t\t(on_board yes)\n"
        f"\t\t\t(in_pos_files yes)\n"
        f"\t\t\t(duplicate_pin_numbers_are_jumpers no)\n"
        f"\t\t\t(property \"Reference\" \"U\"\n"
        f"\t\t\t\t(at 0 {fmt(-(body_y + 1.27))} 0)\n"
        f"\t\t\t\t(show_name no)\n"
        f"\t\t\t\t(do_not_autoplace no)\n"
        f"\t\t\t\t(effects\n"
        f"\t\t\t\t\t(font\n"
        f"\t\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(property \"Value\" \"ESP32-C6_DevKitM-1-N4\"\n"
        f"\t\t\t\t(at 0 {fmt(body_y + 1.27)} 0)\n"
        f"\t\t\t\t(show_name no)\n"
        f"\t\t\t\t(do_not_autoplace no)\n"
        f"\t\t\t\t(effects\n"
        f"\t\t\t\t\t(font\n"
        f"\t\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(property \"Footprint\" \"\"\n"
        f"\t\t\t\t(at 0 0 0)\n"
        f"\t\t\t\t(show_name no)\n"
        f"\t\t\t\t(do_not_autoplace no)\n"
        f"\t\t\t\t(hide yes)\n"
        f"\t\t\t\t(effects\n"
        f"\t\t\t\t\t(font\n"
        f"\t\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(property \"Datasheet\" \"https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html\"\n"
        f"\t\t\t\t(at 0 0 0)\n"
        f"\t\t\t\t(show_name no)\n"
        f"\t\t\t\t(do_not_autoplace no)\n"
        f"\t\t\t\t(hide yes)\n"
        f"\t\t\t\t(effects\n"
        f"\t\t\t\t\t(font\n"
        f"\t\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(property \"Description\" \"Espressif ESP32-C6-DevKitM-1-N4 (EAN 5904422385651). ESP32-C6-MINI-1 SoM (ESP32-C6FH4, 4MB SiP flash). WiFi 6, BLE 5.3, Zigbee/Thread. 2x USB-C (USB-UART bridge + native USB-Serial-JTAG). Onboard power LED + addressable RGB NeoPixel on GPIO 8. 2x15 header pins (J1 left, J3 right).\"\n"
        f"\t\t\t\t(at 0 0 0)\n"
        f"\t\t\t\t(show_name no)\n"
        f"\t\t\t\t(do_not_autoplace no)\n"
        f"\t\t\t\t(hide yes)\n"
        f"\t\t\t\t(effects\n"
        f"\t\t\t\t\t(font\n"
        f"\t\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(property \"ki_keywords\" \"esp32-c6 devkit devkitm-1 espressif wifi ble\"\n"
        f"\t\t\t\t(at 0 0 0)\n"
        f"\t\t\t\t(show_name no)\n"
        f"\t\t\t\t(do_not_autoplace no)\n"
        f"\t\t\t\t(hide yes)\n"
        f"\t\t\t\t(effects\n"
        f"\t\t\t\t\t(font\n"
        f"\t\t\t\t\t\t(size 1.27 1.27)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(symbol \"ESP32-C6_DevKitM-1_0_1\"\n"
        f"\t\t\t\t(rectangle\n"
        f"\t\t\t\t\t(start {fmt(-body_x)} {fmt(-body_y)})\n"
        f"\t\t\t\t\t(end {fmt(body_x)} {fmt(body_y)})\n"
        f"\t\t\t\t\t(stroke\n"
        f"\t\t\t\t\t\t(width 0.254)\n"
        f"\t\t\t\t\t\t(type default)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t\t(fill\n"
        f"\t\t\t\t\t\t(type background)\n"
        f"\t\t\t\t\t)\n"
        f"\t\t\t\t)\n"
        f"\t\t\t)\n"
        f"\t\t\t(symbol \"ESP32-C6_DevKitM-1_1_1\"\n"
        f"{pins_block}\n"
        f"\t\t\t)\n"
        f"\t\t\t(embedded_fonts no)\n"
        f"\t\t)"
    )


# Stock KiCad Device:R lib symbol (verbatim copy from
# Device.kicad_sym, GPL). Needed in MCU_LIB_SYMBOLS because R5/R6 (I2C
# pull-ups) live on the MCU sub-sheet.
_DEVICE_R_LIB_SYMBOL = """\
\t\t(symbol "Device:R"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "R"
\t\t\t\t(at 2.032 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "R"
\t\t\t\t(at 0 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at -1.778 0 90)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Resistor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "R res resistor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "R_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "R_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.016 -2.54)
\t\t\t\t\t(end 1.016 2.54)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "R_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 1.27)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)"""


# The lib-symbol block continued below is a multi-symbol literal that
# wraps the Conn_01x06 / Device:C / Device:C_Polarized / power symbols
# inherited from KiCad's stock library. Combined at usage time with
# the dynamic ESP32-C6 symbol via MCU_LIB_SYMBOLS().
_MCU_LIB_SYMBOLS_TAIL = """\
\t\t(symbol "Connector_Generic:Conn_01x06"
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "J"
\t\t\t\t(at 0 7.62 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "Conn_01x06"
\t\t\t\t(at 0 -10.16 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Generic connector, single row, 01x06, script generated (kicad-library-utils/schlib/autogen/connector/)"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "connector"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "Connector*:*_1x??_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "Conn_01x06_1_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 6.35)
\t\t\t\t\t(end 1.27 -8.89)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type background)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 5.207)
\t\t\t\t\t(end 0 4.953)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 2.667)
\t\t\t\t\t(end 0 2.413)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 0.127)
\t\t\t\t\t(end 0 -0.127)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 -2.413)
\t\t\t\t\t(end 0 -2.667)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 -4.953)
\t\t\t\t\t(end 0 -5.207)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start -1.27 -7.493)
\t\t\t\t\t(end 0 -7.747)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.1524)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 5.08 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 2.54 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 0 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 -2.54 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_4"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "4"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 -5.08 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_5"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "5"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at -5.08 -7.62 0)
\t\t\t\t\t(length 3.81)
\t\t\t\t\t(name "Pin_6"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "6"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:C"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0.254)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "C"
\t\t\t\t(at 0.635 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "C"
\t\t\t\t(at 0.635 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0.9652 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Unpolarized capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "cap capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "C_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -2.032 0.762) (xy 2.032 0.762)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.508)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -2.032 -0.762) (xy 2.032 -0.762)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.508)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "Device:C_Polarized"
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0.254)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "C"
\t\t\t\t(at 0.635 2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "C_Polarized"
\t\t\t\t(at 0.635 -2.54 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(justify left)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0.9652 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Polarized capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "cap capacitor"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_fp_filters" "CP_*"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_Polarized_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -2.286 0.508)
\t\t\t\t\t(end 2.286 1.016)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.778 2.286) (xy -0.762 2.286)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -1.27 2.794) (xy -1.27 1.778)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(rectangle
\t\t\t\t\t(start 2.286 -0.508)
\t\t\t\t\t(end -2.286 -1.016)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type outline)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "C_Polarized_1_1"
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 3.81 270)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin passive line
\t\t\t\t\t(at 0 -3.81 90)
\t\t\t\t\t(length 2.794)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:+3V3"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "+3V3"
\t\t\t\t(at 0 3.556 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"+3V3\\""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+3V3_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy -0.762 1.27) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 2.54) (xy 0.762 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 2.54)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "+3V3_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)
\t\t(symbol "power:GND"
\t\t\t(power global)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 -6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "GND"
\t\t\t\t(at 0 -3.81 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Power symbol creates a global label with name \\"GND\\" , ground"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "global power"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "GND_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "GND_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 270)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name ""
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)"""


def MCU_LIB_SYMBOLS() -> str:
    """Concatenated lib_symbols block for the MCU sub-sheet.

    v0.21 (M3): the old per-project `OAS:ESP32-C6_DevKitM-1` 30-pin
    placeholder symbol (U3) is gone. The ESP32-C6 DevKitM-1-N4 plugs
    into the PCB via 2× 1×15 female pin sockets J5 (antenna-side row,
    DevKitM-1 J1 pins 1..15) and J6 (USB-side row, DevKitM-1 J3 pins
    1..15). Each socket is represented in the schematic by a
    `Connector_Generic:Conn_01x15` symbol whose pin numbering matches
    the PCB pad numbering 1:1 — so `sync_pcb_nets_from_schematic`
    propagates schematic nets onto J5/J6 pads without an intermediate
    placeholder.

    Combines:
      - `Connector_Generic:Conn_01x15` (J5, J6 schematic symbols)
      - Device:R lib symbol (R5/R6 I²C pull-ups)
      - Static tail (Conn_01x06, Device:C, Device:C_Polarized,
        power:+3V3, power:GND)
    """
    return "\n".join((
        _read_kicad_lib_symbol("Connector_Generic.kicad_sym", "Conn_01x15",
                               lib_nickname="Connector_Generic"),
        _DEVICE_R_LIB_SYMBOL,
        _MCU_LIB_SYMBOLS_TAIL,
    ))


# -----------------------------------------------------------------------------
# Helpers specific to the MCU sub-sheet (sheet_key="mcu" pinned)
# -----------------------------------------------------------------------------
def _sch_hierarchical_label(
    name: str, shape: str, x: float, y: float, angle: int,
    justify: str, uuid_tag: str,
) -> str:
    """Emit a (hierarchical_label ...) entity.

    Hierarchical labels mark inter-sheet net endpoints. The label name
    must match the corresponding sheet pin on the parent sheet's
    (sheet ...) block. `shape` is one of "input", "output",
    "bidirectional", "tri_state", "passive" — controls the visible
    arrowhead style. `angle` is the label rotation in degrees:
      0   = arrow points right (text reads L→R)
      90  = arrow points up    (text reads bottom→top)
      180 = arrow points left  (text reads R→L)
      270 = arrow points down  (text reads top→bottom)
    `justify` is "left" or "right" — controls which side of the anchor
    the text extends to.
    """
    return textwrap.dedent(f"""\
        \t(hierarchical_label "{name}"
        \t\t(shape {shape})
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(effects
        \t\t\t(font
        \t\t\t\t(size 1.27 1.27)
        \t\t\t)
        \t\t\t(justify {justify})
        \t\t)
        \t\t(uuid "{U('hlabel:'+uuid_tag)}")
        \t)""")


def _sch_no_connect(x: float, y: float, uuid_tag: str) -> str:
    """Emit a (no_connect ...) marker at the given pin tip.

    Tells ERC that the unconnected pin is intentional, suppressing
    the "unconnected pin" warning.
    """
    return textwrap.dedent(f"""\
        \t(no_connect
        \t\t(at {fmt(x)} {fmt(y)})
        \t\t(uuid "{U('nc:'+uuid_tag)}")
        \t)""")


def _sch_local_label(
    name: str, x: float, y: float, angle: int, justify: str, uuid_tag: str,
) -> str:
    """Emit a local (label ...) entity.

    Unlike hierarchical labels, local labels stay within their own
    schematic sheet but still join wires by name (any two wire endpoints
    that have a local label of the same name are connected). Useful for
    routing signals across the page without dragging a long wire — e.g.
    RST from J1.2 to a recovery header on the opposite side of U3.

    `angle` is the label rotation in degrees (0/90/180/270). `justify`
    is "left" or "right" — controls which side of the anchor the text
    extends to.
    """
    return textwrap.dedent(f"""\
        \t(label "{name}"
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(effects
        \t\t\t(font
        \t\t\t\t(size 1.27 1.27)
        \t\t\t)
        \t\t\t(justify {justify})
        \t\t)
        \t\t(uuid "{U('label:'+uuid_tag)}")
        \t)""")


def _sch_esp32c6_devkitm1(
    x: float, y: float, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit an ESP32-C6-DevKitM-1-N4 (OAS:ESP32-C6_DevKitM-1) symbol instance.

    30 pins total in a 2×15 layout (15 pins per header, matching the
    Espressif official user guide:
    https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html).

    Pin numbering convention (this symbol — see ESP32C6_DEVKITM1_PINS):
      Left side  (J1, pins 1..15, X = anchor_x - 12.7)
      Right side (J3, pins 16..30, X = anchor_x + 12.7)
    Pins are laid out top→bottom on each side. Top pin row (J1.1 / J3.1)
    sits at Y = anchor_y - ESP32C6_DEVKITM1_PIN_ROW_HALF (= 17.78 mm
    above anchor); bottom row (J1.15 / J3.15) at Y = anchor_y + 17.78.

    Use mcu_pin_xy(reference, pin_num, anchor_x, anchor_y) elsewhere to
    derive a single pin's tip coordinate without duplicating the layout
    math.
    """
    sym_uuid = U("sym:" + uuid_tag)
    n_pins = len(ESP32C6_DEVKITM1_PINS)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, n_pins + 1)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['mcu']}"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, n_pins + 1)
    )
    # Place Reference / Value labels just below the body so they don't
    # collide with the pin labels on either side.
    label_y_below = y + ESP32C6_DEVKITM1_LIB_BODY_Y + 2.54
    label_y_below2 = label_y_below + 2.54
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "OAS:ESP32-C6_DevKitM-1")
        \t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 13.97)} {fmt(label_y_below)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 13.97)} {fmt(label_y_below2)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" "Espressif ESP32-C6-DevKitM-1-N4 dev board (EAN 5904422385651; manual-mount daughter board)"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _mcu_pin_xy(pin_num: int, anchor_x: float, anchor_y: float) -> tuple[float, float]:
    """Schematic-frame (x, y) of the pin tip for ESP32-C6_DevKitM-1 pin `pin_num`.

    Mirrors the geometry built in _esp32c6_devkitm1_lib_symbol():
      - pins 1..15 are on the LEFT  side (X = anchor_x - 12.7)
      - pins 16..30 are on the RIGHT side (X = anchor_x + 12.7)
      - top pin (pin 1 / pin 16) sits at anchor_y - 17.78, next row +2.54, etc.
    """
    pin_record = ESP32C6_DEVKITM1_PINS[pin_num - 1]
    _, _, _, header, hpos = pin_record
    row = hpos - 1
    y_offset = -ESP32C6_DEVKITM1_PIN_ROW_HALF + row * ESP32C6_DEVKITM1_PIN_PITCH
    if header == "J1":
        return (anchor_x - 12.7, anchor_y + y_offset)
    return (anchor_x + 12.7, anchor_y + y_offset)


def _sch_conn_01x06(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
    dnp: bool = False, sheet_key: str = "mcu",
) -> str:
    """Emit a Connector_Generic:Conn_01x06 symbol instance.

    With angle=0 (no rotation), lib pin positions map to schematic as:
      Pin 1 (top):    (X-5.08, Y-5.08)
      Pin 2:          (X-5.08, Y-2.54)
      Pin 3:          (X-5.08, Y)
      Pin 4:          (X-5.08, Y+2.54)
      Pin 5:          (X-5.08, Y+5.08)
      Pin 6 (bottom): (X-5.08, Y+7.62)
    All pin tips on the LEFT side, body to the right (X = -1.27..+1.27 in
    lib → schem (X-1.27, ..., X+1.27)).

    `dnp` flags the part Do-Not-Populate. The part still appears on the
    PCB and in ERC, but a hatched overlay is drawn in eeschema and the
    BOM exporter marks it accordingly.

    `sheet_key` selects which sub-sheet's hierarchical path is recorded in
    the symbol's instance block (defaults to "mcu" for backwards compat
    with J2; the sensors sub-sheet passes "sensors" for the SEN66 J3
    connector).
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 7)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    dnp_flag = "yes" if dnp else "no"
    # v0.36 I3 fix: when dnp=True, also set in_bom=no so the schematic-level
    # BOM exporter (kicad-cli sch export bom) excludes the part. Without this,
    # the schematic-level BOM ships J2/J10 in the parts list even though the
    # PCB exclude_from_bom attribute correctly hides them in the production
    # position files. The two flags must stay consistent.
    in_bom_flag = "no" if dnp else "yes"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, 7)
    )
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector_Generic:Conn_01x06")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom {in_bom_flag})
        \t\t(on_board yes)
        \t\t(dnp {dnp_flag})
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 10.16)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y + 12.7)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_conn_02x08_top_bottom(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
    dnp: bool = False, sheet_key: str = "sensors",
) -> str:
    """Emit a Connector_Generic:Conn_02x08_Top_Bottom symbol instance.

    Used as the mikroBUS placeholder for the MIKROE-2462 NFC Tag 2 Click
    daughterboard (chunk #5c). 16 pins in two columns:
      LEFT  column (pins 1..8, top to bottom): X = -5.08
      RIGHT column (pins 9..16, top to bottom): X = +7.62
    Y axis steps in 2.54 mm increments. With angle=0, lib pin (lx, ly)
    maps to schem (x + lx, y - ly) — i.e. LIB +Y is UP, SCHEM +Y is DOWN.

    Pin schem positions (anchor = (x, y), angle 0):
      Pin n on LEFT  column (n in 1..8):  (x - 5.08,  y - (7.62 - 2.54*(n-1)))
      Pin n on RIGHT column (n in 9..16): (x + 7.62,  y - (7.62 - 2.54*(n-9)))

    Pin-function mapping (mikroBUS spec): pins 1..8 are LEFT side
    (AN, RST, CS, SCK, MISO, MOSI, +3.3V, GND); pins 9..16 are RIGHT
    side (PWM, INT, RX, TX, SCL, SDA, +5V, GND).
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 17)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    dnp_flag = "yes" if dnp else "no"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, 17)
    )
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector_Generic:Conn_02x08_Top_Bottom")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp {dnp_flag})
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 12.7)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y + 12.7)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "https://www.mikroe.com/nfc-tag-2-click"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" "mikroBUS 2x8 socket — MIKROE-2462 NFC Tag 2 Click daughterboard (NT3H1101 NTAG I²C plus + onboard PCB antenna)"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_conn_01x04(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
    dnp: bool = False, sheet_key: str = "io",
) -> str:
    """Emit a Connector_Generic:Conn_01x04 symbol instance.

    Mirrors `_sch_conn_01x05` for the 4-pin Qwiic / Stemma QT JST SH
    cable. Verified against the KiCad stock `Connector_Generic.kicad_sym`
    library: Conn_01x04 has lib pin Y positions at +2.54, 0, -2.54, -5.08
    (top to bottom in lib +Y up). With angle=0 in the schematic, lib +Y
    maps to schem -Y, so pin schem positions are:
      Pin 1 (top):    (X-5.08, Y-2.54)
      Pin 2:          (X-5.08, Y)
      Pin 3:          (X-5.08, Y+2.54)
      Pin 4 (bottom): (X-5.08, Y+5.08)
    All pin tips on the LEFT side. Body rect lib (-1.27, +3.81) to
    (+1.27, -6.35) → schem body Y = -3.81..+6.35; value-label anchored
    one grid step below the body bottom at schem Y+7.62.

    Used by the IO sub-sheet (chunk #6 / v0.19) for J9 — the JST SH 4-pin
    horizontal SMD Qwiic / Stemma QT expansion socket (standard pinout
    GND, +3.3V, SDA, SCL).
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 5)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    dnp_flag = "yes" if dnp else "no"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, 5)
    )
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector_Generic:Conn_01x04")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp {dnp_flag})
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 6.35)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y + 7.62)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _sch_conn_01x05(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
    dnp: bool = False, sheet_key: str = "sensors",
) -> str:
    """Emit a Connector_Generic:Conn_01x05 symbol instance.

    Mirrors `_sch_conn_01x06` for the 5-pin LD2410 cable. With angle=0,
    lib pin positions map to schematic as:
      Pin 1 (top):    (X-5.08, Y-5.08)
      Pin 2:          (X-5.08, Y-2.54)
      Pin 3:          (X-5.08, Y)
      Pin 4:          (X-5.08, Y+2.54)
      Pin 5 (bottom): (X-5.08, Y+5.08)
    All pin tips on the LEFT side, body to the right (X = -1.27..+1.27 in
    lib → schem (X-1.27, ..., X+1.27)).

    Property anchors differ from the 6-pin variant only at the Value
    field, which sits one row higher because the bottom pin is at Y+5.08
    (vs Y+7.62 for 6 pins): Value is anchored at Y+10.16 instead of Y+12.7.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 6)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    dnp_flag = "yes" if dnp else "no"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, 6)
    )
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector_Generic:Conn_01x05")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp {dnp_flag})
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y - 10.16)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(y + 10.16)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


# Pin-1 lib_y for each Connector_Generic:Conn_01xN stock symbol, read out
# of `C:\Program Files\KiCad\10.0\share\kicad\symbols\Connector_Generic.kicad_sym`.
# Each symbol's pins go top → bottom at 2.54 mm pitch starting from
# lib_y = Pin-1 lib_y. lib_y +ve is UP; schematic +Y is DOWN, so at
# angle=0 the pin Y in the schematic frame = anchor_y - lib_y.
_CONN_01XN_PIN1_LIB_Y: dict[int, float] = {
    4:  2.54,
    5:  5.08,
    6:  5.08,
    8:  7.62,
    15: 17.78,
}


def _sch_conn_01xn(
    *,
    pin_count: int,
    x: float, y: float, angle: int,
    reference: str, value: str, uuid_tag: str,
    dnp: bool = False, sheet_key: str,
) -> str:
    """Emit a Connector_Generic:Conn_01xN symbol instance (generic).

    Used in v0.21 (M3) for the J5 / J6 ESP32-DevKitM-1 socket pair
    (Conn_01x15) and the J7 / J8 MIKROE-2462 socket pair (Conn_01x08),
    which replaced U3 (ESP32 placeholder) and U4 (mikroBUS placeholder)
    respectively. Generalises `_sch_conn_01x05` / `_sch_conn_01x06`.

    With angle=0, lib pin tip positions map to schematic as:
      Pin n: (X - 5.08,  Y - (PIN1_LIB_Y - 2.54*(n-1)))
    All pin tips on the LEFT side, body to the right of the anchor.

    `pin_count` must be one of the keys of _CONN_01XN_PIN1_LIB_Y; add
    new entries there as needed.
    """
    if pin_count not in _CONN_01XN_PIN1_LIB_Y:
        raise ValueError(
            f"_sch_conn_01xn: unsupported pin_count={pin_count}; "
            f"extend _CONN_01XN_PIN1_LIB_Y with the pin-1 lib_y for "
            f"Conn_01x{pin_count:02d}."
        )
    pin1_lib_y = _CONN_01XN_PIN1_LIB_Y[pin_count]
    pin_n_lib_y_bottom = pin1_lib_y - (pin_count - 1) * 2.54
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, pin_count + 1)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    dnp_flag = "yes" if dnp else "no"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, pin_count + 1)
    )
    # Reference anchor sits above pin 1 (with a small margin); Value
    # anchor below the bottom pin. Use lib coords scaled to schem:
    #   ref_y_schem  = y - (pin1_lib_y + 2.54)
    #   val_y_schem  = y - (pin_n_lib_y_bottom - 2.54)
    ref_y = y - (pin1_lib_y + 2.54)
    val_y = y - (pin_n_lib_y_bottom - 2.54)
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector_Generic:Conn_01x{pin_count:02d}")
        \t\t(at {fmt(x)} {fmt(y)} {angle})
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp {dnp_flag})
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(ref_y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 2.54)} {fmt(val_y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def _conn_01xn_pin_xy(
    pin_num: int, anchor_x: float, anchor_y: float, pin_count: int,
) -> tuple[float, float]:
    """Schematic-frame (x, y) of pin tip `pin_num` for a Conn_01x{pin_count}
    instance at (anchor_x, anchor_y) and rotation 0.

    Mirrors `_sch_conn_01xn`: pins are on the LEFT edge at lib_x=-5.08;
    pin 1 sits at the top (lib_y = +PIN1_LIB_Y) and subsequent pins step
    down at 2.54 mm pitch.
    """
    pin1_lib_y = _CONN_01XN_PIN1_LIB_Y[pin_count]
    lib_y = pin1_lib_y - (pin_num - 1) * 2.54
    return (anchor_x - 5.08, anchor_y - lib_y)


def gen_mcu_sch() -> str:
    """MCU sub-sheet — ESP32-C6-DevKitM-1-N4 sockets J5/J6 + C9/C17
    decoupling + R5/R6 I²C pull-ups + J2 recovery header.

    v0.21 (M3): the previous 30-pin `OAS:ESP32-C6_DevKitM-1` placeholder
    symbol (U3) was a schematic-only abstraction with no PCB twin —
    `sync_pcb_nets_from_schematic` could not propagate any net to the
    PCB-side J5 / J6 female pin sockets, because the U3 symbol's pin
    references did not match the J5/J6 PCB pad references. v0.21
    replaces U3 with TWO `Connector_Generic:Conn_01x15` instances —
    J5 (ESP32 J1 row, pin tips on the LEFT, antenna-side socket on
    PCB) and J6 (ESP32 J3 row, pin tips on the RIGHT, USB-side socket
    on PCB) — whose schematic pin numbers 1..15 match the PCB pad
    numbers of the corresponding female pin socket 1:1. Now every
    used signal on the DevKitM-1 has a direct (J5 ref, pin) or
    (J6 ref, pin) → net mapping that `sync_pcb_nets_from_schematic`
    can apply to the PCB pads.

    Layout (schematic page-absolute mm, KiCad +Y is down on screen):

      +3V3 rail (Y=76.20) ===================================
        |       |        |       |        |       |
        C9      R5       R6      C17      +3V3    |
       (10uF)  (10k)    (10k)   (100nF)   PWR     | (drop right and down)
        |       v         v       |               |
        GND   SDA tap   SCL tap   GND             |
                                                  |
                                                  v
                                          J5.1 (3V3 pin) at top of J5

      J5 (Conn_01x15, angle=0)  at (144.78, 110.49). Pin tips on LEFT
      at X=139.70, pin 1 at TOP Y=92.71, pin 15 at BOTTOM Y=128.27.
      Represents the antenna-side header row (ESP32 module's J1).

      J6 (Conn_01x15, angle=180) at (160.02, 110.49). Pin tips on
      RIGHT at X=165.10, pin 1 at BOTTOM Y=128.27, pin 15 at TOP
      Y=92.71 (numbering visually reversed by the 180° rotation —
      KiCad still maps net assignments by pin number 1..15).
      Represents the USB-side header row (ESP32 module's J3).

      The J5 / J6 pin tips line up with the SAME X coordinates as
      the old U3 pin tips (139.70 left, 165.10 right), so the
      existing left- and right-edge hierarchical labels and all
      the +3V3 bus / R5 / R6 / C9 / C17 wiring drop in unchanged.

      J2 (SWD/UART recovery, DNP) — rotated to angle=180 in v0.21
      so its UART TX/RX pin row aligns with J6's UART_TX (pin 2 at
      Y=125.73) / UART_RX (pin 3 at Y=123.19). At angle=180 the J2
      pin order in screen Y is REVERSED vs angle=0: pin 1 (+3V3) at
      the BOTTOM, pin 6 (BOOT) at the TOP.

    DevKitM-1 pinout (CLAUDE.md v0.4 + v0.15.8 fixes). Pin numbers
    below are the J5 / J6 socket-side pin numbers 1..15, equal to
    the DevKitM-1's J1 / J3 header pin positions per the Espressif
    user guide.

      J5 (DevKitM-1 J1, antenna-side header)
        J5.1   3V3                              → +3V3 bus
        J5.2   RST                              → hier label "EN"
        J5.3   GPIO2                            → hier label "LD2410_OUT"
        J5.4   GPIO3                            → hier label "NFC_FD"
        J5.5   GPIO4   (strap MTMS)             → no_connect
        J5.6   GPIO5   (strap MTDI)             → no_connect
        J5.7   GPIO0                            → no_connect (spare)
        J5.8   GPIO1                            → no_connect (spare)
        J5.9   GPIO8   (strap boot, onboard LED)→ hier label "WS2812_DIN"
        J5.10  GPIO6                            → hier label "I2C_SDA"
        J5.11  GPIO7                            → hier label "I2C_SCL"
        J5.12  GPIO14                           → no_connect (spare)
        J5.13  GND                              → GND
        J5.14  5V                               → no_connect (powering 3V3 only)
        J5.15  GND                              → GND

      J6 (DevKitM-1 J3, USB-side header)
        J6.1   GND                              → GND
        J6.2   GPIO16  (UART0 TX)               → hier label "UART_TX"
        J6.3   GPIO17  (UART0 RX)               → hier label "UART_RX"
        J6.4   GPIO23                           → no_connect (spare)
        J6.5   GPIO22                           → no_connect (spare)
        J6.6   GPIO21                           → no_connect (spare)
        J6.7   GPIO20                           → no_connect (spare)
        J6.8   GPIO19                           → no_connect (spare)
        J6.9   GPIO18                           → no_connect (spare)
        J6.10  GPIO15  (strap)                  → no_connect
        J6.11  GPIO9   (strap, BOOT button)     → hier label "BOOT"
        J6.12  GND                              → GND
        J6.13  GPIO13  (USB D+)                 → hier label "USB_DP"
        J6.14  GPIO12  (USB D-)                 → hier label "USB_DM"
        J6.15  GND                              → GND

    Inter-sheet nets exported via hierarchical_label (matching sheet
    ports are declared on the root sheet's MCU sheet block):
      I2C_SDA, I2C_SCL    → sensors sub-sheet + io sub-sheet (Qwiic)
      UART_TX, UART_RX    → sensors sub-sheet (LD2410)
      LD2410_OUT          → sensors sub-sheet
      NFC_FD              → sensors sub-sheet
      USB_DM, USB_DP      → io sub-sheet (J10 native-USB recovery header)
      EN                  → io sub-sheet (J10 chip-enable / reset pin)
      BOOT                → io sub-sheet (J10 GPIO9 boot-mode strap)

    +3V3 and GND are NOT exported as hierarchical labels: the power
    section already declared them via global power symbols, which is
    KiCad's canonical mechanism for spanning power nets across hierarchy.
    Adding hier labels for them would produce "multiple net names on the
    same net" ERC noise without any electrical benefit.

    J2 (SWD/UART Recovery, DNP) pinout — same as v0.19 (only J2.5
    was renamed from "RST" → "EN" in v0.19 to share the hier-labelled
    EN net with the IO sub-sheet's J10 recovery EN pin):
      J2.1  +3V3
      J2.2  GND
      J2.3  UART_TX        — taps J6 pin 2 UART_TX
      J2.4  UART_RX        — taps J6 pin 3 UART_RX
      J2.5  EN             — hier label, joins J5 pin 2 RST
      J2.6  BOOT           — hier label, joins J6 pin 11 BOOT
    """
    file_uuid = SHEET_FILE_UUIDS["mcu"]

    # ===== J5 + J6: ESP32-C6-DevKitM-1-N4 socket pair =====
    # All coordinates on the 1.27 mm (50 mil) KiCad connection grid.
    # J5 (DevKitM-1 J1 row) at angle=0, anchor (144.78, 110.49). Pin
    # tips on LEFT at X=139.70 (= U3_X_LEFT pre-v0.21). Pin 1 at top
    # (Y=92.71), pin 15 at bottom (Y=128.27).
    # J6 (DevKitM-1 J3 row) at angle=180, anchor (160.02, 110.49). Pin
    # tips on RIGHT at X=165.10 (= U3_X_RIGHT pre-v0.21). Pin 1 at
    # BOTTOM (Y=128.27), pin 15 at TOP (Y=92.71) — order reversed by
    # the 180° rotation.
    J5_ANCHOR_X = 144.78          # pin tips at 144.78 - 5.08 = 139.70 LEFT
    J5_ANCHOR_Y = 110.49
    J5_PIN_X    = 139.70           # convenience: pin tip column
    J6_ANCHOR_X = 160.02          # pin tips at 160.02 + 5.08 = 165.10 RIGHT
    J6_ANCHOR_Y = 110.49
    J6_PIN_X    = 165.10           # convenience: pin tip column

    def j5_pin_y(pin_num: int) -> float:
        """Schematic Y of J5 pin tip n (n in 1..15). J5 is angle=0,
        so pin 1 at top, pin 15 at bottom."""
        x, y = _conn_01xn_pin_xy(pin_num, J5_ANCHOR_X, J5_ANCHOR_Y, 15)
        return y

    def j6_pin_y(pin_num: int) -> float:
        """Schematic Y of J6 pin tip n (n in 1..15). J6 is angle=180,
        so pin 1 at BOTTOM, pin 15 at TOP. With the angle-180 transform
        applied: pin n schem Y = anchor_y + lib_y, where lib_y = +17.78
        - 2.54*(n-1)."""
        pin1_lib_y = _CONN_01XN_PIN1_LIB_Y[15]
        lib_y = pin1_lib_y - (pin_num - 1) * 2.54
        return J6_ANCHOR_Y + lib_y

    # J5 / J6 pin-to-signal mapping (per CLAUDE.md v0.4 + v0.15.8 fixes).
    # The pin numbers below match the PCB pad numbers on the female pin
    # socket footprints J5 / J6 placed by `gen_pcb()`, and they also
    # match the DevKitM-1's J1 / J3 header pin positions 1..15 per the
    # Espressif user guide.
    J5_SIGNAL_PIN: dict[str, int] = {
        "3V3"        : 1,
        "RST"        : 2,
        "LD2410_OUT" : 3,
        "NFC_FD"     : 4,
        "WS2812_DIN" : 9,
        "I2C_SDA"    : 10,
        "I2C_SCL"    : 11,
    }
    J5_GND_PINS: list[int] = [13, 15]                     # J1.13, J1.15
    J5_NC_PINS:  list[int] = [5, 6, 7, 8, 12, 14]
    #                          GPIO4/5/0/1/14   5V (J1.14)
    J6_SIGNAL_PIN: dict[str, int] = {
        "UART_TX"    : 2,
        "UART_RX"    : 3,
        "BOOT"       : 11,
        "USB_DP"     : 13,
        "USB_DM"     : 14,
    }
    J6_GND_PINS: list[int] = [1, 12, 15]                  # J3.1, J3.12, J3.15
    J6_NC_PINS:  list[int] = [4, 5, 6, 7, 8, 9, 10]
    #                          GPIO23/22/21/20/19/18/15
    # Sanity: every pin must be classified exactly once on each row.
    assert set(J5_SIGNAL_PIN.values()) | set(J5_GND_PINS) | set(J5_NC_PINS) == set(range(1, 16))
    assert set(J6_SIGNAL_PIN.values()) | set(J6_GND_PINS) | set(J6_NC_PINS) == set(range(1, 16))
    assert not (set(J5_SIGNAL_PIN.values()) & set(J5_GND_PINS))
    assert not (set(J5_SIGNAL_PIN.values()) & set(J5_NC_PINS))
    assert not (set(J5_GND_PINS) & set(J5_NC_PINS))
    assert not (set(J6_SIGNAL_PIN.values()) & set(J6_GND_PINS))
    assert not (set(J6_SIGNAL_PIN.values()) & set(J6_NC_PINS))
    assert not (set(J6_GND_PINS) & set(J6_NC_PINS))

    # Per-signal pin-tip resolution (single source of truth).
    J5_3V3_Y    = j5_pin_y(J5_SIGNAL_PIN["3V3"])         # 92.71
    J5_RST_Y    = j5_pin_y(J5_SIGNAL_PIN["RST"])         # 95.25
    J5_LDR_Y    = j5_pin_y(J5_SIGNAL_PIN["LD2410_OUT"])  # 97.79
    J5_NFC_Y    = j5_pin_y(J5_SIGNAL_PIN["NFC_FD"])      # 100.33
    J5_WS_Y     = j5_pin_y(J5_SIGNAL_PIN["WS2812_DIN"])  # 113.03
    J5_SDA_Y    = j5_pin_y(J5_SIGNAL_PIN["I2C_SDA"])     # 115.57
    J5_SCL_Y    = j5_pin_y(J5_SIGNAL_PIN["I2C_SCL"])     # 118.11
    J6_TX_Y     = j6_pin_y(J6_SIGNAL_PIN["UART_TX"])     # 125.73
    J6_RX_Y     = j6_pin_y(J6_SIGNAL_PIN["UART_RX"])     # 123.19
    J6_BOOT_Y   = j6_pin_y(J6_SIGNAL_PIN["BOOT"])        # 102.87
    J6_USB_DP_Y = j6_pin_y(J6_SIGNAL_PIN["USB_DP"])      # 97.79
    J6_USB_DM_Y = j6_pin_y(J6_SIGNAL_PIN["USB_DM"])      # 95.25

    # ===== C9: bulk decoupling, 10uF polarized =====
    # Reviewer raised C9's voltage rating from 10 V to 16 V (v0.5):
    # the +3V3 rail's transient operating margin and reliability over
    # the device's expected lifetime is better served by a 0402 ceramic
    # with the standard ~5× derating headroom at 3.3 V.
    C9_X = 129.54
    C9_Y = 80.01
    C9_TOP_Y = C9_Y - 3.81   # 76.20 — pin 1 (anode +) on the +3V3 bus
    C9_BOT_Y = C9_Y + 3.81   # 83.82 — pin 2 (cathode -) drops to GND
    C9_GND_Y = 87.63

    # ===== C17: HF decoupling, 100nF ceramic =====
    C17_X = 138.43
    C17_Y = 80.01
    C17_TOP_Y = C17_Y - 3.81
    C17_BOT_Y = C17_Y + 3.81
    C17_GND_Y = 87.63

    # ===== R5 / R6: I²C bus pull-ups, 4.7 kΩ 1% 0603 =====
    # v0.22 — value dropped from 10 kΩ to 4.7 kΩ. The Sensirion SEN66
    # datasheet §3.1 *recommends* 10 kΩ but does not mandate it (lower
    # values are explicitly allowed). The realized I²C bus length on the
    # v0.21 PCB is ~60-100 mm (not the "<40 mm" originally claimed),
    # with ~100 pF total bus capacitance. At 10 kΩ the rise time τ =
    # RC = 1 µs / t_r(10-90%) ≈ 2.2 µs exceeds the I²C standard-mode
    # spec (t_r ≤ 1 µs at 100 kHz). 4.7 kΩ drops τ to ~470 ns / t_r ≈
    # 1.0 µs, comfortably within spec.
    R5_X = 121.92
    R6_X = 124.46
    R5_Y = 80.01                    # body center; pin1 = 76.20, pin2 = 83.82
    R6_Y = 80.01

    # ===== R7: GPIO 8 (WS2812_DIN) boot-strap pull-up, 10 kΩ 0603 =====
    # v0.22 — new in this revision (Task #18 M2). ESP32-C6 GPIO 8 is a
    # strap pin that must be HIGH at boot for SPI flash boot mode. The
    # DevKitM-1's onboard "pull-up" relies on VCC_5V powering the onboard
    # WS2812B, but in OAS we feed +3V3 directly into J5.1 and leave
    # VCC_5V floating — so that onboard pull-up doesn't exist. R7
    # replaces it with an explicit 10 kΩ from GPIO 8 (J5 pin 9 = the
    # WS2812_DIN net) to +3V3. Placed vertically in the gap between J5
    # body (east edge ~149.86) and J6 body (west edge ~154.94) at X=152.4.
    R7_X = 152.4
    R7_Y = 87.63                    # vertical resistor; pin1 top, pin2 bottom
    R7_TOP_Y = R7_Y - 3.81          # 83.82 — pin 1 (top, +3V3 side)
    R7_BOT_Y = R7_Y + 3.81          # 91.44 — pin 2 (bottom, WS2812 side)
    R7_3V3_BUS_X = R7_X             # +3V3 bus extension reaches R7's X column
    # Vertical drop from R7.pin2 (91.44) south to WS2812 wire (Y=113.03)
    # at X=R7_X. Clear of existing horizontal wires (RST/LD2410/NFC/etc.
    # all stop at HLABEL_LEFT_X=119.38 west of R7).

    # ===== +3V3 bus =====
    # Horizontal at Y=76.20 from R5 east through C9, C17, then on to an
    # L-corner at X=140.97 from where the bus drops south to J5.1 (3V3
    # pin) row at Y=92.71 and runs east to the J5.1 pin tip at X=139.70.
    BUS_3V3_Y       = 76.20
    BUS_3V3_X_LEFT  = R5_X         # 128.27 (one grid step west of C9)
    BUS_3V3_X_RIGHT = 140.97       # L-corner west of J5 body left edge
    PWR_3V3_X       = 134.62       # power flag between R6 and C17
    PWR_3V3_Y       = BUS_3V3_Y

    # ===== J2: SWD/UART recovery header, 6-pin, DNP =====
    # v0.21: rotated to angle=180 so its pin 3 (TX) / pin 4 (RX) order
    # matches J6's reversed pin Y order (J6.2 UART_TX at BOTTOM
    # Y=125.73, J6.3 UART_RX above at Y=123.19). With angle=180, J2
    # pin 1 (+3V3) lands at the BOTTOM (anchor_y + 5.08), pin 6 (BOOT)
    # at the TOP (anchor_y - 7.62). Pin tips on the RIGHT at
    # anchor_x + 5.08.
    J2_X = 189.23                # pin tips at 189.23 + 5.08 = 194.31 RIGHT
    J2_Y = J6_TX_Y               # 125.73 — pin 3 (TX) at this Y exactly
    J2_PIN_X = J2_X + 5.08       # 194.31 — pin tip column (angle=180)
    # Conn_01x06 lib pin Y per angle=180: schem_y = anchor_y + lib_y,
    # lib_y for pin n = (5.08 - 2.54*(n-1)) → pin 1 lib_y=+5.08, pin 6
    # lib_y=-7.62.
    J2_PIN_Y = {
        1: J2_Y + 5.08,          # 130.81 — BOTTOM (+3V3)
        2: J2_Y + 2.54,          # 128.27           (GND)
        3: J2_Y,                 # 125.73           (TX)  ← J6.2 UART_TX
        4: J2_Y - 2.54,          # 123.19           (RX)  ← J6.3 UART_RX
        5: J2_Y - 5.08,          # 120.65           (EN)
        6: J2_Y - 7.62,          # 118.11 — TOP    (BOOT)
    }

    # J2_PIN_MAP — recovery header pinout signal assignment. EN (= RST,
    # chip reset) and BOOT come in via hierarchical labels (v0.19; were
    # local labels in v0.18 and earlier).
    J2_PIN_MAP: dict[int, str] = {
        1: "+3V3",
        2: "GND",
        3: "TX",        # ← J6.2 GPIO16 ; continues east to UART_TX hier label
        4: "RX",        # ← J6.3 GPIO17 ; continues east to UART_RX hier label
        5: "EN",        # ← J5.2 RST    (hier label, v0.19 was "RST" local)
        6: "BOOT",      # ← J6.11 GPIO9 (hier label, v0.19 was local)
    }
    assert set(J2_PIN_MAP.values()) == {"+3V3", "GND", "EN", "BOOT", "TX", "RX"}
    J2_PIN_OF: dict[str, int] = {sig: pin for pin, sig in J2_PIN_MAP.items()}

    # ===== Hierarchical-label columns =====
    # LEFT-edge labels (sensor-bound nets): X=119.38.
    HLABEL_LEFT_X = 119.38
    # RIGHT-edge labels: X=222.25 (UART_TX, UART_RX, BOOT, USB_DP, USB_DM).
    HLABEL_RIGHT_X = 222.25

    # ===== Wires =====
    parts: list[str] = []

    # ---- +3V3 wiring ----
    # Horizontal bus from R5 (128.27) east to L-corner (140.97), drop
    # south to J5.1 row, run east to J5.1 (3V3) pin tip.
    parts.append(_sch_wire(BUS_3V3_X_LEFT,  BUS_3V3_Y, BUS_3V3_X_RIGHT, BUS_3V3_Y, "3v3-bus"))
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, BUS_3V3_Y, BUS_3V3_X_RIGHT, J5_3V3_Y,  "3v3-bus-down"))
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, J5_3V3_Y,  J5_PIN_X,        J5_3V3_Y,  "3v3-to-j5"))
    parts.append(_sch_junction(R6_X,      BUS_3V3_Y, "3v3-bus-tap-r6"))
    parts.append(_sch_junction(C9_X,      BUS_3V3_Y, "3v3-bus-tap-c9"))
    parts.append(_sch_junction(PWR_3V3_X, BUS_3V3_Y, "3v3-bus-tap-pwr"))
    parts.append(_sch_junction(C17_X,     BUS_3V3_Y, "3v3-bus-tap-c17"))

    # ---- R5 SDA-pull-up wire ----
    parts.append(_sch_wire(R5_X, R5_Y + 3.81, R5_X, J5_SDA_Y, "r5-pullup-to-sda"))
    parts.append(_sch_junction(R5_X, J5_SDA_Y, "r5-sda-tap"))
    # ---- R6 SCL-pull-up wire ----
    parts.append(_sch_wire(R6_X, R6_Y + 3.81, R6_X, J5_SCL_Y, "r6-pullup-to-scl"))
    parts.append(_sch_junction(R6_X, J5_SCL_Y, "r6-scl-tap"))

    # ---- R7 GPIO-8 boot-strap pull-up wires (v0.22) ----
    # Top side: R7.pin1 (Y=83.82) → vertical north to +3V3 bus extension
    # at Y=76.20 at X=R7_X.
    parts.append(_sch_wire(R7_X, R7_TOP_Y, R7_X, BUS_3V3_Y, "r7-pullup-to-3v3"))
    # +3V3 bus extension east from existing BUS_3V3_X_RIGHT (140.97) to R7_X.
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, BUS_3V3_Y, R7_X, BUS_3V3_Y, "3v3-bus-ext-r7"))
    parts.append(_sch_junction(BUS_3V3_X_RIGHT, BUS_3V3_Y, "3v3-bus-tap-r7-corner"))
    # Bottom side: R7.pin2 (Y=91.44) → vertical south to WS2812 wire at
    # Y=113.03 (J5_WS_Y), tapping the existing east-running WS2812 wire.
    parts.append(_sch_wire(R7_X, R7_BOT_Y, R7_X, J5_WS_Y, "r7-pullup-to-ws"))
    # The WS2812 wire currently runs from (J5_PIN_X=139.70, J5_WS_Y) west
    # to (HLABEL_LEFT_X=119.38, J5_WS_Y). Extend it EAST from J5_PIN_X
    # to R7_X so R7's pin 2 drop hits the WS2812 net.
    parts.append(_sch_wire(J5_PIN_X, J5_WS_Y, R7_X, J5_WS_Y, "ws2812-wire-ext-r7"))
    parts.append(_sch_junction(R7_X, J5_WS_Y, "r7-ws-tap"))

    # ---- C9.pin2 / C17.pin2 → local GND symbols ----
    parts.append(_sch_wire(C9_X,  C9_BOT_Y,  C9_X,  C9_GND_Y,  "c9-to-gnd"))
    parts.append(_sch_wire(C17_X, C17_BOT_Y, C17_X, C17_GND_Y, "c17-to-gnd"))

    # ---- I²C / interrupt signal wires (J5 LEFT-edge pins → LEFT hier labels) ----
    parts.append(_sch_wire(J5_PIN_X, J5_SDA_Y, HLABEL_LEFT_X, J5_SDA_Y, "sda-wire"))
    parts.append(_sch_wire(J5_PIN_X, J5_SCL_Y, HLABEL_LEFT_X, J5_SCL_Y, "scl-wire"))
    parts.append(_sch_wire(J5_PIN_X, J5_LDR_Y, HLABEL_LEFT_X, J5_LDR_Y, "ldr-wire"))
    parts.append(_sch_wire(J5_PIN_X, J5_NFC_Y, HLABEL_LEFT_X, J5_NFC_Y, "nfc-wire"))
    parts.append(_sch_wire(J5_PIN_X, J5_WS_Y,  HLABEL_LEFT_X, J5_WS_Y,  "ws2812-wire"))

    # ---- EN: J5.2 (RST) → hier label "EN" (LEFT side) ----
    RST_LABEL_X = J5_PIN_X - 2.54   # 137.16
    parts.append(_sch_wire(J5_PIN_X, J5_RST_Y, RST_LABEL_X, J5_RST_Y, "rst-j5-stub"))
    parts.append(_sch_hierarchical_label(
        name="EN", shape="output",
        x=RST_LABEL_X, y=J5_RST_Y, angle=180, justify="right",
        uuid_tag="en-j5",
    ))

    # ---- BOOT: J6.11 (GPIO9) → hier label "BOOT" (RIGHT side) ----
    BOOT_LABEL_X = J6_PIN_X + 2.54  # 167.64
    parts.append(_sch_wire(J6_PIN_X, J6_BOOT_Y, BOOT_LABEL_X, J6_BOOT_Y, "boot-j6-stub"))
    parts.append(_sch_hierarchical_label(
        name="BOOT", shape="output",
        x=BOOT_LABEL_X, y=J6_BOOT_Y, angle=0, justify="left",
        uuid_tag="boot-j6",
    ))

    # ---- UART: J6.2 (UART_TX) / J6.3 (UART_RX) → J2 → right hier labels ----
    j2_tx_y   = J2_PIN_Y[J2_PIN_OF["TX"]]    # 125.73 = J6_TX_Y
    j2_rx_y   = J2_PIN_Y[J2_PIN_OF["RX"]]    # 123.19 = J6_RX_Y
    j2_en_y   = J2_PIN_Y[J2_PIN_OF["EN"]]    # 120.65
    j2_boot_y = J2_PIN_Y[J2_PIN_OF["BOOT"]]  # 118.11

    # TX: straight east from J6.2 pin tip through J2.3 pin tip to UART_TX hier label.
    parts.append(_sch_wire(J6_PIN_X, J6_TX_Y, HLABEL_RIGHT_X, J6_TX_Y, "tx-bus"))
    parts.append(_sch_junction(J2_PIN_X, j2_tx_y, "tx-j2-tap"))
    # RX: straight east from J6.3 pin tip through J2.4 pin tip to UART_RX hier label.
    parts.append(_sch_wire(J6_PIN_X, J6_RX_Y, HLABEL_RIGHT_X, J6_RX_Y, "rx-bus"))
    parts.append(_sch_junction(J2_PIN_X, j2_rx_y, "rx-j2-tap"))

    # ---- USB_DP / USB_DM: J6.13 / J6.14 → right hier labels ----
    # J6.13 USB_DP at Y=97.79, J6.14 USB_DM at Y=95.25 — both well NORTH
    # (above) of J2's Y range (118.11..130.81), so wires pass clear.
    parts.append(_sch_wire(J6_PIN_X, J6_USB_DP_Y, HLABEL_RIGHT_X, J6_USB_DP_Y, "usb-dp-bus"))
    parts.append(_sch_hierarchical_label(
        name="USB_DP", shape="bidirectional",
        x=HLABEL_RIGHT_X, y=J6_USB_DP_Y, angle=0, justify="left",
        uuid_tag="usb-dp",
    ))
    parts.append(_sch_wire(J6_PIN_X, J6_USB_DM_Y, HLABEL_RIGHT_X, J6_USB_DM_Y, "usb-dm-bus"))
    parts.append(_sch_hierarchical_label(
        name="USB_DM", shape="bidirectional",
        x=HLABEL_RIGHT_X, y=J6_USB_DM_Y, angle=0, justify="left",
        uuid_tag="usb-dm",
    ))

    # ---- J2.5 (EN) and J2.6 (BOOT) hier labels via a west-going stub ----
    # The J2 body sits between J6.right tips (X=165.10) and the right
    # hier labels (X=222.25); J2 pin tips on the RIGHT (X=194.31).
    # Stubs hop EAST from each J2 pin tip and end at a hier label of
    # the matching name. KiCad joins them to the J5/J6-side hier labels
    # via name-matching, so the net spans J5/J6 ↔ J2 ↔ IO-sub-sheet
    # recovery header transparently.
    J2_EN_LABEL_X = J2_PIN_X + 2.54
    parts.append(_sch_wire(J2_PIN_X, j2_en_y, J2_EN_LABEL_X, j2_en_y, "j2-en-stub"))
    parts.append(_sch_hierarchical_label(
        name="EN", shape="output",
        x=J2_EN_LABEL_X, y=j2_en_y, angle=0, justify="left",
        uuid_tag="en-j2",
    ))
    J2_BOOT_LABEL_X = J2_PIN_X + 2.54
    parts.append(_sch_wire(J2_PIN_X, j2_boot_y, J2_BOOT_LABEL_X, j2_boot_y, "j2-boot-stub"))
    parts.append(_sch_hierarchical_label(
        name="BOOT", shape="output",
        x=J2_BOOT_LABEL_X, y=j2_boot_y, angle=0, justify="left",
        uuid_tag="boot-j2",
    ))

    # ---- J2.1 (+3V3) and J2.2 (GND) local power flags ----
    j2_3v3_y = J2_PIN_Y[J2_PIN_OF["+3V3"]]   # 130.81 (BOTTOM at angle=180)
    j2_gnd_y = J2_PIN_Y[J2_PIN_OF["GND"]]    # 128.27
    PWR_J2_3V3_Y = j2_3v3_y + 3.81           # flag SOUTH of pin
    parts.append(_sch_wire(J2_PIN_X, j2_3v3_y, J2_PIN_X, PWR_J2_3V3_Y, "j2-3v3-drop"))
    PWR_J2_GND_X = J2_PIN_X + 5.08
    parts.append(_sch_wire(J2_PIN_X, j2_gnd_y, PWR_J2_GND_X, j2_gnd_y, "j2-gnd-hop"))

    # ---- J5 GND pins → local GND symbols ----
    for gnd_pin in J5_GND_PINS:
        gy = j5_pin_y(gnd_pin)
        # J5 pin tips on LEFT — place GND symbol to the WEST.
        sym_x = J5_PIN_X - 3.81
        parts.append(_sch_wire(J5_PIN_X, gy, sym_x, gy, f"j5-gnd-hop-{gnd_pin}"))
        parts.append(_sch_power_flag(
            lib_id="power:GND", value="GND",
            x=sym_x, y=gy, angle=270,
            reference=f"#PWR_GND_J5_{gnd_pin}",
            value_offset_x=-3.81, value_offset_y=0.0,
            uuid_tag=f"pwr-gnd-j5-{gnd_pin}",
            sheet_key="mcu",
        ))
    # ---- J6 GND pins → local GND symbols ----
    for gnd_pin in J6_GND_PINS:
        gy = j6_pin_y(gnd_pin)
        # J6 pin tips on RIGHT — place GND symbol to the EAST.
        sym_x = J6_PIN_X + 3.81
        parts.append(_sch_wire(J6_PIN_X, gy, sym_x, gy, f"j6-gnd-hop-{gnd_pin}"))
        parts.append(_sch_power_flag(
            lib_id="power:GND", value="GND",
            x=sym_x, y=gy, angle=90,
            reference=f"#PWR_GND_J6_{gnd_pin}",
            value_offset_x=3.81, value_offset_y=0.0,
            uuid_tag=f"pwr-gnd-j6-{gnd_pin}",
            sheet_key="mcu",
        ))

    # ===== Hierarchical labels (LEFT side) =====
    parts.append(_sch_hierarchical_label(
        name="I2C_SDA", shape="bidirectional",
        x=HLABEL_LEFT_X, y=J5_SDA_Y, angle=180, justify="right",
        uuid_tag="i2c-sda",
    ))
    parts.append(_sch_hierarchical_label(
        name="I2C_SCL", shape="output",
        x=HLABEL_LEFT_X, y=J5_SCL_Y, angle=180, justify="right",
        uuid_tag="i2c-scl",
    ))
    parts.append(_sch_hierarchical_label(
        name="LD2410_OUT", shape="input",
        x=HLABEL_LEFT_X, y=J5_LDR_Y, angle=180, justify="right",
        uuid_tag="ld2410-out",
    ))
    parts.append(_sch_hierarchical_label(
        name="NFC_FD", shape="input",
        x=HLABEL_LEFT_X, y=J5_NFC_Y, angle=180, justify="right",
        uuid_tag="nfc-fd",
    ))
    parts.append(_sch_hierarchical_label(
        name="WS2812_DIN", shape="output",
        x=HLABEL_LEFT_X, y=J5_WS_Y, angle=180, justify="right",
        uuid_tag="ws2812-din",
    ))
    # ===== Hierarchical labels (RIGHT side) =====
    parts.append(_sch_hierarchical_label(
        name="UART_TX", shape="output",
        x=HLABEL_RIGHT_X, y=J6_TX_Y, angle=0, justify="left",
        uuid_tag="uart-tx",
    ))
    parts.append(_sch_hierarchical_label(
        name="UART_RX", shape="input",
        x=HLABEL_RIGHT_X, y=J6_RX_Y, angle=0, justify="left",
        uuid_tag="uart-rx",
    ))

    # ===== No-connect markers on J5 / J6 unused pins =====
    for nc_pin in J5_NC_PINS:
        ny = j5_pin_y(nc_pin)
        parts.append(_sch_no_connect(J5_PIN_X, ny, f"j5-pin-{nc_pin}"))
    for nc_pin in J6_NC_PINS:
        ny = j6_pin_y(nc_pin)
        parts.append(_sch_no_connect(J6_PIN_X, ny, f"j6-pin-{nc_pin}"))

    # ===== J5 + J6 symbols (Conn_01x15 each) =====
    parts.append(_sch_conn_01xn(
        pin_count=15,
        x=J5_ANCHOR_X, y=J5_ANCHOR_Y, angle=0,
        reference="J5",
        value="1x15 P2.54 mm female socket (ESP32 J1 antenna-side row)",
        uuid_tag="j5", sheet_key="mcu",
    ))
    parts.append(_sch_conn_01xn(
        pin_count=15,
        x=J6_ANCHOR_X, y=J6_ANCHOR_Y, angle=180,
        reference="J6",
        value="1x15 P2.54 mm female socket (ESP32 J3 USB-side row)",
        uuid_tag="j6", sheet_key="mcu",
    ))

    # ===== J2 symbol (SWD/UART recovery header, DNP) =====
    parts.append(_sch_conn_01x06(
        x=J2_X, y=J2_Y, angle=180,
        reference="J2", value="SWD/UART Recovery (DNP)",
        uuid_tag="j2", dnp=True,
    ))

    # ===== Capacitors (C9 bulk, C17 HF) =====
    # C9 voltage rating raised to 16 V (v0.5) — 10 V was too tight a
    # margin for a reliable 0402 / 3.3 V design.
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C9_X, y=C9_Y, angle=0,
        reference="C9", value="10uF 16V",
        uuid_tag="c9", sheet_key="mcu",
    ))
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C17_X, y=C17_Y, angle=0,
        reference="C17", value="100nF",
        uuid_tag="c17", sheet_key="mcu",
    ))

    # ===== Resistors (R5 SDA pull-up, R6 SCL pull-up) =====
    # v0.22 — R5/R6 value 10k → 4.7k. See R5/R6 comment block above.
    parts.append(_sch_resistor(
        x=R5_X, y=R5_Y, angle=0,
        reference="R5", value="4.7k 1%",
        uuid_tag="r5", sheet_key="mcu",
    ))
    parts.append(_sch_resistor(
        x=R6_X, y=R6_Y, angle=0,
        reference="R6", value="4.7k 1%",
        uuid_tag="r6", sheet_key="mcu",
    ))
    # ===== R7 — GPIO 8 boot-strap pull-up, 10 kΩ to +3V3 =====
    # v0.22 new resistor. See R7 comment block above.
    parts.append(_sch_resistor(
        x=R7_X, y=R7_Y, angle=0,
        reference="R7", value="10k 1%",
        uuid_tag="r7", sheet_key="mcu",
    ))

    # ===== Power flags =====
    # +3V3 on the bus between R6 and C17 (angle=0, triangle points UP).
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=PWR_3V3_X, y=PWR_3V3_Y, angle=0,
        reference="#PWR25",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr25-3v3-bus",
        sheet_key="mcu",
    ))
    # +3V3 above J2.1.
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=J2_PIN_X, y=PWR_J2_3V3_Y, angle=0,
        reference="#PWR26",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr26-3v3-j2",
        sheet_key="mcu",
    ))
    # GND below C9 (angle=0).
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C9_X, y=C9_GND_Y, angle=0,
        reference="#PWR27",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr27-gnd-c9",
        sheet_key="mcu",
    ))
    # GND below C17.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C17_X, y=C17_GND_Y, angle=0,
        reference="#PWR28",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr28-gnd-c17",
        sheet_key="mcu",
    ))
    # GND on J2's GND pin.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J2_GND_X, y=j2_gnd_y, angle=270,
        reference="#PWR30",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr30-gnd-j2",
        sheet_key="mcu",
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
        {MCU_LIB_SYMBOLS()}
        \t)
        {body}
        \t(embedded_fonts no)
        )
        """)


# -----------------------------------------------------------------------------
# 3d) Sensors sub-sheet — J3 (SEN66 JST-GH connector) + C10 decoupling cap
# -----------------------------------------------------------------------------
def _sk6812_side_lib_symbol() -> str:
    """Project-local `OAS:SK6812-SIDE` schematic symbol.

    Models the SK6812 SIDE-A LED with pin numbering matching the Normand /
    OPSCO datasheet (1=DIN, 2=VDD, 3=DOUT, 4=GND) — DIFFERENT from KiCad's
    stock `SK6812` symbol (which is the 5050 PLCC4 variant with a different
    numbering). Part spec lives in EXTERNAL_MODULES['SK6812-SIDE'].

    Geometry: square body 5.08 × 5.08 mm centered at the symbol anchor.
    Pin tips on each of the 4 sides:
        DIN  (pin 1, input)        — LEFT  edge,  at (-5.08, 0)
        VDD  (pin 2, power_in)     — TOP   edge,  at ( 0, -5.08)
        DOUT (pin 3, output)       — RIGHT edge,  at (+5.08, 0)
        GND  (pin 4, power_in)     — BOTTOM edge, at ( 0, +5.08)
    Each pin extends 2.54 mm from its body edge outward — standard 100-mil
    pin-tip extension. Total pin tip span is 10.16 mm.

    Indented to 2 tabs deep so the result drops straight into a sub-sheet's
    `(lib_symbols ...)` block.
    """
    return textwrap.dedent("""\
        \t\t(symbol "OAS:SK6812-SIDE"
        \t\t\t(pin_names
        \t\t\t\t(offset 0.508)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t\t(exclude_from_sim no)
        \t\t\t(in_bom yes)
        \t\t\t(on_board yes)
        \t\t\t(in_pos_files yes)
        \t\t\t(duplicate_pin_numbers_are_jumpers no)
        \t\t\t(property "Reference" "D"
        \t\t\t\t(at 0 -6.35 0)
        \t\t\t\t(show_name no)
        \t\t\t\t(do_not_autoplace no)
        \t\t\t\t(effects
        \t\t\t\t\t(font
        \t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t\t(property "Value" "SK6812-SIDE"
        \t\t\t\t(at 0 6.35 0)
        \t\t\t\t(show_name no)
        \t\t\t\t(do_not_autoplace no)
        \t\t\t\t(effects
        \t\t\t\t\t(font
        \t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t\t(property "Footprint" "oas:SK6812-SIDE"
        \t\t\t\t(at 0 0 0)
        \t\t\t\t(show_name no)
        \t\t\t\t(do_not_autoplace no)
        \t\t\t\t(hide yes)
        \t\t\t\t(effects
        \t\t\t\t\t(font
        \t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t\t(property "Datasheet" "http://www.normandled.com/upload/201810/SK6812%20SIDE-A%20LED%20Datasheet.pdf"
        \t\t\t\t(at 0 0 0)
        \t\t\t\t(show_name no)
        \t\t\t\t(do_not_autoplace no)
        \t\t\t\t(hide yes)
        \t\t\t\t(effects
        \t\t\t\t\t(font
        \t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t\t(property "Description" "SK6812 SIDE-A 4020 side-emit addressable RGB LED. Pinout 1=DIN, 2=VDD, 3=DOUT, 4=GND (Normand / OPSCO datasheets)."
        \t\t\t\t(at 0 0 0)
        \t\t\t\t(show_name no)
        \t\t\t\t(do_not_autoplace no)
        \t\t\t\t(hide yes)
        \t\t\t\t(effects
        \t\t\t\t\t(font
        \t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t\t(symbol "SK6812-SIDE_0_1"
        \t\t\t\t(rectangle
        \t\t\t\t\t(start -2.54 -2.54)
        \t\t\t\t\t(end 2.54 2.54)
        \t\t\t\t\t(stroke
        \t\t\t\t\t\t(width 0.254)
        \t\t\t\t\t\t(type default)
        \t\t\t\t\t)
        \t\t\t\t\t(fill
        \t\t\t\t\t\t(type background)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t\t(text "RGB"
        \t\t\t\t\t(at 0 0 0)
        \t\t\t\t\t(effects
        \t\t\t\t\t\t(font
        \t\t\t\t\t\t\t(size 0.8 0.8)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t\t(symbol "SK6812-SIDE_1_1"
        \t\t\t\t(pin input line
        \t\t\t\t\t(at -5.08 0 0)
        \t\t\t\t\t(length 2.54)
        \t\t\t\t\t(name "DIN"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t\t(number "1"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t\t(pin power_in line
        \t\t\t\t\t(at 0 5.08 270)
        \t\t\t\t\t(length 2.54)
        \t\t\t\t\t(name "VDD"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t\t(number "2"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t\t(pin output line
        \t\t\t\t\t(at 5.08 0 180)
        \t\t\t\t\t(length 2.54)
        \t\t\t\t\t(name "DOUT"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t\t(number "3"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t\t(pin power_in line
        \t\t\t\t\t(at 0 -5.08 90)
        \t\t\t\t\t(length 2.54)
        \t\t\t\t\t(name "GND"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t\t(number "4"
        \t\t\t\t\t\t(effects
        \t\t\t\t\t\t\t(font
        \t\t\t\t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t\t\t\t)
        \t\t\t\t\t\t)
        \t\t\t\t\t)
        \t\t\t\t)
        \t\t\t)
        \t\t)""")


def _sch_sk6812_side(
    *, x: float, y: float, reference: str, value: str, uuid_tag: str,
    sheet_key: str = "sensors",
) -> str:
    """Emit an OAS:SK6812-SIDE symbol instance.

    With angle=0 and the lib-symbol geometry above, pin tip positions are:
      Pin 1 DIN  (LEFT):  (x - 5.08, y)
      Pin 2 VDD  (TOP):   (x, y - 5.08)
      Pin 3 DOUT (RIGHT): (x + 5.08, y)
      Pin 4 GND  (BOT):   (x, y + 5.08)
    Reference text sits 7.62 mm north, Value 7.62 mm south.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 5)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS[sheet_key]}"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, 5)
    )
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "OAS:SK6812-SIDE")
        \t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 5.08)} {fmt(y - 6.35)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 5.08)} {fmt(y + 6.35)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" "oas:SK6812-SIDE"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "http://www.normandled.com/upload/201810/SK6812%20SIDE-A%20LED%20Datasheet.pdf"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" "SK6812 SIDE-A 4020 side-emit addressable RGB LED (Normand / OPSCO). Pinout 1=DIN, 2=VDD, 3=DOUT, 4=GND."
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        {pin_blocks}
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "{reference}")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def SENSORS_LIB_SYMBOLS() -> str:
    """Concatenated lib_symbols block for the sensors sub-sheet.

    Reuses `_MCU_LIB_SYMBOLS_TAIL` verbatim — it already contains
    Connector_Generic:Conn_01x06, Device:C, Device:C_Polarized,
    power:+3V3, and power:GND. The unused Device:C_Polarized
    declaration is harmless (KiCad only renders symbols that are
    actually instantiated in the schematic body). Keeping a single
    source for the embedded library symbols across sub-sheets means
    any future symbol-definition fix lands in exactly one place.

    Chunk #5b adds:
      - Connector_Generic:Conn_01x05  (5-pin connector for the HLK-LD2410B
                                       presence radar cable)
      - power:+5V                     (LD2410 module supply rail)

    Chunk #5c adds:
      - Connector_Generic:Conn_02x08_Top_Bottom  (16-pin 2-row connector
                                       representing the mikroBUS socket
                                       that mates with the MIKROE-2462
                                       NFC Tag 2 Click daughterboard.
                                       Pin numbering follows mikroBUS
                                       spec: pins 1-8 down the LEFT
                                       column (AN/RST/CS/SCK/MISO/MOSI/
                                       +3.3V/GND), pins 9-16 down the
                                       RIGHT column (PWM/INT/RX/TX/SCL/
                                       SDA/+5V/GND). The Top_Bottom
                                       variant of Conn_02x08 matches
                                       this convention exactly.)

    All extras are pulled verbatim from the KiCad 10 stock libraries at
    generation time via `_read_kicad_lib_symbol()`.
    """
    extras = "\n".join([
        _read_kicad_lib_symbol("Connector_Generic.kicad_sym", "Conn_01x05",
                               lib_nickname="Connector_Generic"),
        # v0.21 (M3): Conn_01x08 replaces the Conn_02x08_Top_Bottom U4
        # placeholder. The MIKROE-2462 NFC daughterboard mates with TWO
        # 1×8 PCB female pin sockets J7 (mikroBUS pins 1..8, left row)
        # and J8 (mikroBUS pins 9..16, right row), and each socket
        # carries its own Conn_01x08 schematic symbol whose pin numbers
        # (1..8) match the PCB pad numbers 1..8 of the corresponding
        # socket. This gives `sync_pcb_nets_from_schematic` a direct
        # (reference, pin) → net mapping for every J7/J8 pad. The old
        # Conn_02x08_Top_Bottom symbol is no longer instantiated but
        # is retained in the library for backward read compatibility.
        _read_kicad_lib_symbol("Connector_Generic.kicad_sym", "Conn_01x08",
                               lib_nickname="Connector_Generic"),
        _read_kicad_lib_symbol("Connector_Generic.kicad_sym", "Conn_02x08_Top_Bottom",
                               lib_nickname="Connector_Generic"),
        _read_kicad_lib_symbol("power.kicad_sym", "+5V",
                               lib_nickname="power"),
        # v0.16: project-local SK6812-SIDE symbol for the AQI status-LED
        # ring (chunk #5d below).
        _sk6812_side_lib_symbol(),
    ])
    return _MCU_LIB_SYMBOLS_TAIL + "\n" + extras


def gen_sensors_sch() -> str:
    """Sensors sub-sheet — chunks #5a + #5b.

    Chunk #5a — SEN66 connection (J3 + C10).
    Chunk #5b — HLK-LD2410B mmWave radar (J4 + C11). LD2410 mounts as a
                soldered daughterboard via a 5-pin 1.27 mm through-hole
                header at J4; mechanical retention is the solder joint.
                Antenna faces the AK-N-94 perforated cover (away from
                the OAS PCB) per the HiLink §5.5 antenna-clearance rule
                and the universal community pattern (Apollo MSR-2,
                jonnybergdahl, p2baron). PCB footprint chosen in
                chunk #7.
    Chunk #5c — MIKROE-2462 NFC Tag 2 Click (U4 + C12). NXP NT3H1101
                NTAG I²C plus + onboard PCB antenna, mounted as a
                mikroBUS daughterboard on a 2×8 female pin socket
                (P2.54 mm) on the OAS PCB. Pre-tuned antenna avoids
                the PCB-trace antenna design (NXP AN11203) sub-project.

    SEN66 pinout (Sensirion SEN6x datasheet v0.92 Dec 2025, Table 16
    on p. 15) — applies to the entire SEN6x family (SEN62, SEN63C,
    SEN65, SEN66, SEN68, SEN69C):

      Pin 1: VDD  — Supply voltage (3.15-3.6 V)
      Pin 2: GND  — Ground
      Pin 3: SDA  — Serial data input/output (I²C, open-drain)
      Pin 4: SCL  — Serial clock input         (I²C, open-drain)
      Pin 5: GND  — Ground or NC  (internally tied to pin 2)
      Pin 6: VDD  — Supply voltage or NC (internally tied to pin 1)

    The SEN6x is I²C-only — there is no SEL/UART-mode select pin on
    this family. (Earlier Sensirion modules had a SEL pin to choose
    between I²C and UART; SEN6x dropped UART entirely.) Pins 5 and 6
    duplicate pins 2 and 1 respectively, internally bonded together
    for current-carrying and contact redundancy.

    Wiring choice: tie pin 5 → GND and pin 6 → VDD (matching the
    internal pairing). This adds zero electrical risk (the pins are
    already tied internally) and gives better connector contact
    resilience than leaving pins 5/6 as no-connect on the JST-GH
    cable. A pin chafe or contact failure on either the VDD or GND
    line would otherwise interrupt the sensor; with both pins active,
    the second pin keeps the sensor running.

    Connector: SEN66 module side uses ACES 51468-0064N-001 (or
    51452-006H0H0-001), compatible with JST GHR-06V-S. PCB-side
    socket on OAS: JST SM06B-GHS-TB (1.25 mm pitch, horizontal entry,
    SMD), part of the JST GH series. Mating cable: any 6-pin JST GH
    cable, ~50 mm length recommended (datasheet §3 says max 10 cm to
    keep I²C crosstalk low — 50 mm is comfortable).

    Local decoupling: C10 (100 nF 0402 X7R) sits between VDD and GND
    of the SEN66 plug. SEN66 has internal regulation, but a local
    100 nF damps any cable transient ringing on the +3V3 rail at the
    JST-GH socket — cheap insurance.

    Inter-sheet nets imported via hierarchical_label (matching sheet
    pins are declared on the root sheet's Sensors block):
      I2C_SDA   (bidirectional, from MCU sub-sheet's GPIO 6)
      I2C_SCL   (input,         from MCU sub-sheet's GPIO 7)

    +3V3 and GND join via global power symbols, the same KiCad
    convention used in the MCU and power sub-sheets.
    """
    file_uuid = SHEET_FILE_UUIDS["sensors"]

    # ===== J3: SEN66 JST-GH 6-pin connector =====
    # All coordinates on the 1.27 mm KiCad connection grid (page-absolute
    # mm, KiCad +Y is down on screen).
    #
    # With angle=0 and the symbol's _sch_conn_01x06 layout, the lib pin
    # positions map to:
    #   Pin 1 (top):    (J3_X - 5.08, J3_Y - 5.08)
    #   Pin 2:          (J3_X - 5.08, J3_Y - 2.54)
    #   Pin 3:          (J3_X - 5.08, J3_Y)
    #   Pin 4:          (J3_X - 5.08, J3_Y + 2.54)
    #   Pin 5:          (J3_X - 5.08, J3_Y + 5.08)
    #   Pin 6 (bottom): (J3_X - 5.08, J3_Y + 7.62)
    # All pin tips on the LEFT side; body to the right (X = J3_X-1.27 to
    # J3_X+1.27).
    #
    # Place J3 in the upper-mid region of the sheet so all the wiring
    # has clearance to the page frame, and the C10 + the hier labels
    # fit comfortably to its left.
    J3_X = 180.34
    J3_Y = 110.49
    J3_PIN_X = J3_X - 5.08    # 175.26 — tip column for all 6 pin tips
    J3_PIN_Y = {
        1: J3_Y - 5.08,        # 105.41 — VDD (top)
        2: J3_Y - 2.54,        # 107.95 — GND
        3: J3_Y,               # 110.49 — SDA
        4: J3_Y + 2.54,        # 113.03 — SCL
        5: J3_Y + 5.08,        # 115.57 — GND (internally tied to pin 2)
        6: J3_Y + 7.62,        # 118.11 — VDD (internally tied to pin 1)
    }

    # ===== C10: 100 nF local decoupling cap =====
    # Sits to the LEFT of J3, between the VDD and GND rails. Its top pin
    # (anode in the schematic, no polarity for ceramic) wires to a +3V3
    # local power flag; its bottom pin to a local GND flag. C10's column
    # is offset west so it's clearly visually a separate component from
    # J3 but still close to the SEN66 plug (the principal target for the
    # decoupling).
    C10_X = 170.18
    C10_Y = 110.49
    C10_TOP_Y = C10_Y - 3.81   # 106.68 — pin 1 (top) → +3V3
    C10_BOT_Y = C10_Y + 3.81   # 114.30 — pin 2 (bottom) → GND

    # ===== Hierarchical labels (I²C bus signals from the MCU) =====
    # Placed on the LEFT edge of the page area so the sensor wires
    # naturally route west from J3's pin tips. The two labels share an
    # X column (159.39) two grid steps west of J3's pin tip column.
    HLABEL_LEFT_X = 160.02      # X column for both I²C hier labels
    HLABEL_SDA_Y = J3_PIN_Y[3]  # 110.49 — same row as J3 pin 3
    HLABEL_SCL_Y = J3_PIN_Y[4]  # 113.03 — same row as J3 pin 4

    parts: list[str] = []

    # ----- Pin 1 (VDD, top): wire UP to a local +3V3 flag -----
    PWR_J3P1_3V3_Y = J3_PIN_Y[1] - 3.81   # 101.60 — flag anchor above pin
    parts.append(_sch_wire(J3_PIN_X, PWR_J3P1_3V3_Y, J3_PIN_X, J3_PIN_Y[1], "j3-p1-vdd-up"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=J3_PIN_X, y=PWR_J3P1_3V3_Y, angle=0,
        reference="#PWR40",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr40-3v3-j3-p1",
        sheet_key="sensors",
    ))

    # ----- Pin 2 (GND): hop LEFT and place a local GND flag -----
    PWR_J3P2_GND_X = J3_PIN_X - 5.08      # 170.18 — flag anchor west of pin
    parts.append(_sch_wire(J3_PIN_X, J3_PIN_Y[2], PWR_J3P2_GND_X, J3_PIN_Y[2], "j3-p2-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J3P2_GND_X, y=J3_PIN_Y[2], angle=270,
        reference="#PWR41",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr41-gnd-j3-p2",
        sheet_key="sensors",
    ))

    # ----- Pin 3 (SDA): wire LEFT to I2C_SDA hier label -----
    parts.append(_sch_wire(J3_PIN_X, J3_PIN_Y[3], HLABEL_LEFT_X, J3_PIN_Y[3], "j3-p3-sda"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SDA", shape="bidirectional",
        x=HLABEL_LEFT_X, y=HLABEL_SDA_Y, angle=180, justify="right",
        uuid_tag="sda-j3",
    ))

    # ----- Pin 4 (SCL): wire LEFT to I2C_SCL hier label -----
    parts.append(_sch_wire(J3_PIN_X, J3_PIN_Y[4], HLABEL_LEFT_X, J3_PIN_Y[4], "j3-p4-scl"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SCL", shape="input",
        x=HLABEL_LEFT_X, y=HLABEL_SCL_Y, angle=180, justify="right",
        uuid_tag="scl-j3",
    ))

    # ----- Pin 5 (GND): hop LEFT and place a local GND flag -----
    PWR_J3P5_GND_X = J3_PIN_X - 5.08      # 170.18
    parts.append(_sch_wire(J3_PIN_X, J3_PIN_Y[5], PWR_J3P5_GND_X, J3_PIN_Y[5], "j3-p5-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J3P5_GND_X, y=J3_PIN_Y[5], angle=270,
        reference="#PWR42",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr42-gnd-j3-p5",
        sheet_key="sensors",
    ))

    # ----- Pin 6 (VDD, bottom): wire DOWN to a local +3V3 flag -----
    # Flag at angle=180 → tip points down, so its anchor sits BELOW the pin.
    PWR_J3P6_3V3_Y = J3_PIN_Y[6] + 3.81   # 121.92 — flag anchor below pin
    parts.append(_sch_wire(J3_PIN_X, J3_PIN_Y[6], J3_PIN_X, PWR_J3P6_3V3_Y, "j3-p6-vdd-down"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=J3_PIN_X, y=PWR_J3P6_3V3_Y, angle=180,
        reference="#PWR43",
        value_offset_x=0.0, value_offset_y=3.556,
        uuid_tag="pwr43-3v3-j3-p6",
        sheet_key="sensors",
    ))

    # ----- C10 decoupling: +3V3 (top) and GND (bottom) local flags -----
    C10_3V3_Y = C10_TOP_Y - 3.81          # 102.87 — flag anchor above C10
    parts.append(_sch_wire(C10_X, C10_3V3_Y, C10_X, C10_TOP_Y, "c10-top-3v3"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=C10_X, y=C10_3V3_Y, angle=0,
        reference="#PWR44",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr44-3v3-c10",
        sheet_key="sensors",
    ))
    C10_GND_Y = C10_BOT_Y + 3.81          # 118.11 — flag anchor below C10
    parts.append(_sch_wire(C10_X, C10_BOT_Y, C10_X, C10_GND_Y, "c10-bot-gnd"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C10_X, y=C10_GND_Y, angle=0,
        reference="#PWR45",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr45-gnd-c10",
        sheet_key="sensors",
    ))

    # ===== Component symbols =====
    # J3 SEN66 JST-GH 6-pin connector. Value field carries the MPN
    # (JST SM06B-GHS-TB) per the project's Module Identification rule
    # so the BOM exporter always picks up a real, sourceable part.
    parts.append(_sch_conn_01x06(
        x=J3_X, y=J3_Y, angle=0,
        reference="J3",
        value="JST SM06B-GHS-TB (SEN66-SIN-T, MPN 3.001.030; TME/Mouser)",
        uuid_tag="j3-sen66",
        sheet_key="sensors",
    ))
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C10_X, y=C10_Y, angle=0,
        reference="C10", value="100nF",
        uuid_tag="c10-sen66-decoupling",
        sheet_key="sensors",
    ))

    # =========================================================================
    # chunk #5b — HLK-LD2410B mmWave radar (J4 + C11)
    # =========================================================================
    # Mounting strategy: LD2410 module is soldered as a daughterboard
    # directly into J4 — a 5-pin 1.27 mm pitch THROUGH-HOLE pin header on
    # the OAS PCB. The HLK-LD2410B's onboard 1.27 mm pin row passes
    # through OAS J4 holes; the pins are then soldered from the OAS PCB
    # bottom side. The solder joint IS the mechanical retention — no
    # cable, no zip-tie, no bracket. The LD2410 sits flat above the OAS
    # PCB, antenna face oriented AWAY from the OAS PCB (towards the
    # AK-N-94 perforated cover) so the radar beam radiates straight out
    # through the cover into the room. This matches the universal
    # community pattern (Apollo MSR-2, jonnybergdahl Sensor_LD2410B,
    # p2baron Thingiverse 5782554) and the HiLink datasheet §5.5
    # "antenna facing the area to be detected, surrounding area open and
    # unobstructed" requirement.
    #
    # WHY through-hole (not the JST-GH cable variant): the HiLink
    # datasheet §5.5 prohibits "metal materials or materials with
    # shielding effect" in the radome path — a copper-pour FR4 PCB
    # between the antenna and the user counts as such. Mounting the
    # LD2410 as a vertical daughterboard with antenna pointing toward
    # the cover keeps the OAS main PCB *behind* the antenna (where
    # there is no detection requirement) and the antenna *front* face
    # clear to radiate through the ABS cover.
    #
    # Pin order per HiLink HLK-LD2410B Datasheet V1.04 (2022-06-29, FCC-filed),
    # Table 1 page 7. Pin 1 is nearest the silk "1" marker on the module's
    # short edge opposite the 1T2R antenna patches. (NOTE: the HLK-LD2410C
    # variant has a DIFFERENT pin order — see datasheet revisions for the
    # -C variant; OAS is wired strictly for -B.)
    #
    #   Pin 1: OUT   — digital presence output (HIGH = target detected,
    #                  3.3 V CMOS). Wires to MCU GPIO 2 via the LD2410_OUT
    #                  net so ESPHome can attach a binary_sensor without
    #                  polling the UART. Useful for fast wake-up; the UART
    #                  data still drives the full ESPHome ld2410 component.
    #   Pin 2: UART_Tx — UART output FROM the radar (data flowing → MCU GPIO 17).
    #                  Net name UART_RX in this sheet: the signal is the MCU's
    #                  RX, i.e. it ARRIVES at the MCU's RX pin, so we keep
    #                  the MCU-centric net name (matches the hier label
    #                  declared by the mcu sub-sheet).
    #   Pin 3: UART_Rx — UART input TO the radar (MCU GPIO 16 drives it).
    #                  Net name UART_TX (MCU-centric, see above).
    #   Pin 4: GND
    #   Pin 5: VCC   — 5 V supply (range 5-12 V). The HLK-LD2410B is a 5 V
    #                  module; TX/RX/OUT logic levels are 3.3 V TTL so the
    #                  ESP32-C6 UART and GPIO see compatible levels without
    #                  a level shifter. Power comes from the +5V rail
    #                  produced by U1 (LM2596S-5.0) in the power sheet.
    #
    # Local decoupling: C11 (100 nF 0402 X7R) between VCC and GND of the
    # LD2410 supply pins. The radar's switching draw can pull noticeable
    # transient current on the +5V rail; cheap insurance at the
    # daughterboard.
    #
    # Connector: J4 is a 5-pin 1.27 mm pitch through-hole pin header /
    # pin socket. The schematic symbol stays Conn_01x05 (same as the
    # JST-GH variant); the difference is purely in the PCB footprint
    # assignment, which is set in chunk #7 (PCB placement) to one of:
    #   Connector_PinHeader_1.27mm:PinHeader_1x05_P1.27mm_Vertical
    # or
    #   Connector_PinSocket_1.27mm:PinSocket_1x05_P1.27mm_Vertical
    # depending on whether the OAS PCB uses pin or socket geometry. The
    # decision (pin vs socket on the OAS side) is mechanical-only — the
    # net list is identical.

    # ===== J4: LD2410 JST-GH 5-pin connector =====
    # Placed below J3 in the schematic. With angle=0 + _sch_conn_01x05's
    # layout, lib pin positions map to (J4_X-5.08, J4_Y + 2.54*(n-3)) for
    # pin n = 1..5. Pin tips on the LEFT side.
    # J4_Y = 146.05 is on the 1.27 mm KiCad connection grid (1.27 × 115);
    # picking a non-grid Y (e.g. 145.00) triggers `endpoint_off_grid` ERC
    # warnings on every pin/wire of J4 + C11.
    #
    # Pin order per HiLink HLK-LD2410B datasheet V1.04 (FCC-filed),
    # Table 1 page 7. The PCB pad numbering of J4 (1..5) corresponds 1:1
    # with the LD2410 module's onboard pin row:
    #   Pin 1 = OUT (target-status digital output, 3.3 V level)
    #   Pin 2 = UART_Tx (output from LD2410 → MCU input UART_RX)
    #   Pin 3 = UART_Rx (input  to  LD2410 ← MCU output UART_TX)
    #   Pin 4 = GND
    #   Pin 5 = VCC (5 V supply, range 5-12 V)
    #
    # v0.15.8 fix: J4 pin-to-net mapping was reversed end-for-end vs the
    # datasheet (pin 1 was wired to VCC, pin 5 to OUT). Corrected here.
    J4_X = 180.34
    J4_Y = 146.05
    J4_PIN_X = J4_X - 5.08    # 175.26 — tip column for all 5 pin tips
    J4_PIN_Y = {
        1: J4_Y - 5.08,        # 140.97 — OUT (presence interrupt, top)
        2: J4_Y - 2.54,        # 143.51 — UART_Tx (LD2410 → MCU)
        3: J4_Y,               # 146.05 — UART_Rx (MCU → LD2410)
        4: J4_Y + 2.54,        # 148.59 — GND
        5: J4_Y + 5.08,        # 151.13 — VCC (bottom)
    }

    # ===== C11: 100 nF local decoupling cap =====
    # Sits to the LEFT of J4, BELOW the J4 pin row. After the v0.15.8
    # J4 pin-order end-for-end fix, VCC moved from pin 1 (top) to pin 5
    # (bottom, Y=151.13) and GND moved from pin 2 to pin 4 (Y=148.59).
    # C11 placed below J4 so its top pin aligns with J4 pin 5 (VCC) and
    # the cap's bottom pin terminates at a local GND flag.
    C11_X = 170.18
    C11_Y = 154.94            # = 1.27 × 122 (on connection grid). Top pin
                              # at 151.13 = J4 pin 5 (VCC).
    C11_TOP_Y = C11_Y - 3.81   # 151.13 — pin 1 (top) → +5V (= J4 pin 5)
    C11_BOT_Y = C11_Y + 3.81   # 158.75 — pin 2 (bottom) → GND

    # ----- Pin 1 (OUT, top): wire LEFT to LD2410_OUT hier label -----
    parts.append(_sch_wire(J4_PIN_X, J4_PIN_Y[1], HLABEL_LEFT_X, J4_PIN_Y[1], "j4-p1-out"))
    parts.append(_sch_hierarchical_label(
        name="LD2410_OUT", shape="output",
        x=HLABEL_LEFT_X, y=J4_PIN_Y[1], angle=180, justify="right",
        uuid_tag="ld2410-out-j4",
    ))

    # ----- Pin 2 (LD2410 Tx → MCU RX): wire LEFT to UART_RX hier label -----
    parts.append(_sch_wire(J4_PIN_X, J4_PIN_Y[2], HLABEL_LEFT_X, J4_PIN_Y[2], "j4-p2-tx"))
    parts.append(_sch_hierarchical_label(
        name="UART_RX", shape="output",
        x=HLABEL_LEFT_X, y=J4_PIN_Y[2], angle=180, justify="right",
        uuid_tag="uart-rx-j4",
    ))

    # ----- Pin 3 (LD2410 Rx ← MCU TX): wire LEFT to UART_TX hier label -----
    parts.append(_sch_wire(J4_PIN_X, J4_PIN_Y[3], HLABEL_LEFT_X, J4_PIN_Y[3], "j4-p3-rx"))
    parts.append(_sch_hierarchical_label(
        name="UART_TX", shape="input",
        x=HLABEL_LEFT_X, y=J4_PIN_Y[3], angle=180, justify="right",
        uuid_tag="uart-tx-j4",
    ))

    # ----- Pin 4 (GND): hop LEFT and place a local GND flag -----
    PWR_J4P4_GND_X = J4_PIN_X - 5.08      # 170.18 — flag anchor west of pin
    parts.append(_sch_wire(J4_PIN_X, J4_PIN_Y[4], PWR_J4P4_GND_X, J4_PIN_Y[4], "j4-p4-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J4P4_GND_X, y=J4_PIN_Y[4], angle=270,
        reference="#PWR47",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr47-gnd-j4-p4",
        sheet_key="sensors",
    ))

    # ----- Pin 5 (VCC, bottom): wire DOWN to a local +5V flag -----
    PWR_J4P5_5V_Y = J4_PIN_Y[5] + 3.81   # 154.94 — flag anchor below pin
    parts.append(_sch_wire(J4_PIN_X, J4_PIN_Y[5], J4_PIN_X, PWR_J4P5_5V_Y, "j4-p5-vcc-down"))
    parts.append(_sch_power_flag(
        lib_id="power:+5V", value="+5V",
        x=J4_PIN_X, y=PWR_J4P5_5V_Y, angle=180,
        reference="#PWR46",
        value_offset_x=0.0, value_offset_y=3.556,
        uuid_tag="pwr46-5v-j4-p5",
        sheet_key="sensors",
    ))

    # ----- C11 decoupling: top pin (+5V) shares J4 pin 5's flag via a
    # horizontal wire from C11 over to J4 pin 5; bottom pin gets a local
    # GND flag.
    parts.append(_sch_wire(C11_X, C11_TOP_Y, J4_PIN_X, C11_TOP_Y, "c11-top-to-j4-p5-5v"))
    C11_GND_Y = C11_BOT_Y + 3.81          # 162.56 — flag anchor below C11
    parts.append(_sch_wire(C11_X, C11_BOT_Y, C11_X, C11_GND_Y, "c11-bot-gnd"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C11_X, y=C11_GND_Y, angle=0,
        reference="#PWR49",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr49-gnd-c11",
        sheet_key="sensors",
    ))

    # ===== J4 + C11 symbols =====
    parts.append(_sch_conn_01x05(
        x=J4_X, y=J4_Y, angle=0,
        reference="J4",
        value="1x5 P1.27mm through-hole header (HLK-LD2410B daughterboard, soldered)",
        uuid_tag="j4-ld2410",
        sheet_key="sensors",
    ))
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C11_X, y=C11_Y, angle=0,
        reference="C11", value="100nF",
        uuid_tag="c11-ld2410-decoupling",
        sheet_key="sensors",
    ))

    # =========================================================================
    # chunk #5c — MIKROE-2462 NFC Tag 2 Click daughterboard (J7 + J8 + C12)
    # =========================================================================
    # v0.21 (M3): the 16-pin mikroBUS 2×8 placeholder U4 was replaced by
    # TWO `Connector_Generic:Conn_01x08` instances — J7 (mikroBUS pins
    # 1..8, LEFT column on the daughterboard's bottom-side header) and
    # J8 (mikroBUS pins 9..16, RIGHT column) — whose schematic pin
    # numbers 1..8 match the PCB pad numbers 1..8 of the corresponding
    # female pin socket footprints J7 / J8. This unblocks
    # `sync_pcb_nets_from_schematic` from propagating nets to the
    # otherwise-orphan PCB sockets.
    #
    # NFC tag is hosted on a MikroElektronika "NFC Tag 2 Click"
    # (MIKROE-2462) daughterboard: NXP NT3H1101 (NTAG I²C plus) +
    # onboard PCB antenna + 16-pin mikroBUS male header (2×8, 2.54 mm
    # pitch).
    #
    # mikroBUS standard pinout:
    #   LEFT column  (pins 1..8, top -> bottom):
    #     1=AN  2=RST 3=CS  4=SCK 5=MISO 6=MOSI 7=+3.3V 8=GND
    #   RIGHT column (pins 9..16, top -> bottom):
    #     9=PWM 10=INT 11=RX 12=TX 13=SCL  14=SDA  15=+5V  16=GND
    #
    # PCB ↔ schematic socket pin mapping:
    #     J7 pin n (n in 1..8)  = mikroBUS pin n
    #     J8 pin n (n in 1..8)  = mikroBUS pin (n+8)
    #
    # NFC Tag 2 Click electrically uses ONLY these mikroBUS pins:
    #   pin 7  (+3.3V) — VCC for NT3H1101                         → J7 pin 7
    #   pin 8  (GND)   — ground                                   → J7 pin 8
    #   pin 10 (INT)   — FD field-detect (open-drain), → NFC_FD   → J8 pin 2
    #   pin 13 (SCL)   — I²C clock                                → J8 pin 5
    #   pin 14 (SDA)   — I²C data, slave 0x55                     → J8 pin 6
    #   pin 16 (GND)   — ground                                   → J8 pin 8
    # All other mikroBUS pins (1, 2, 3, 4, 5, 6, 9, 11, 12, 15) are
    # unused by NFC Tag 2 Click; each gets a `(no_connect ...)` marker
    # so ERC stays quiet.

    # ===== J7: mikroBUS LEFT column (pins 1..8) =====
    # J7 at angle=0, anchor (115.57 + 5.08, 125.73) = (120.65, 125.73).
    # Pin tips on LEFT at X=115.57. Pin 1 (top, AN) at Y=118.11, pin 8
    # (bottom, GND) at Y=135.89.
    J7_ANCHOR_X = 120.65
    J7_ANCHOR_Y = 125.73
    J7_PIN_X    = 115.57            # pin tip column
    # ===== J8: mikroBUS RIGHT column (pins 9..16) =====
    # J8 at angle=180, anchor (133.35 - 5.08, 125.73) = (128.27, 125.73).
    # Pin tips on RIGHT at X=133.35. With angle=180, pin order reverses:
    # J8 pin 1 (= mikroBUS PWM pin 9) ends up at the BOTTOM Y=135.89,
    # J8 pin 8 (= mikroBUS GND pin 16) at the TOP Y=118.11.
    J8_ANCHOR_X = 128.27
    J8_ANCHOR_Y = 125.73
    J8_PIN_X    = 133.35            # pin tip column

    def j7_pin_y(pin_num: int) -> float:
        """Schematic Y of J7 pin tip n (n in 1..8). Angle=0."""
        x, y = _conn_01xn_pin_xy(pin_num, J7_ANCHOR_X, J7_ANCHOR_Y, 8)
        return y

    def j8_pin_y(pin_num: int) -> float:
        """Schematic Y of J8 pin tip n (n in 1..8). Angle=180 → reversed."""
        pin1_lib_y = _CONN_01XN_PIN1_LIB_Y[8]
        lib_y = pin1_lib_y - (pin_num - 1) * 2.54
        return J8_ANCHOR_Y + lib_y

    J7_3V3_Y = j7_pin_y(7)    # 133.35 — +3.3V
    J7_GND_Y = j7_pin_y(8)    # 135.89 — GND
    J8_FD_Y  = j8_pin_y(2)    # NFC_FD (mikroBUS pin 10)
    J8_SCL_Y = j8_pin_y(5)    # SCL    (mikroBUS pin 13)
    J8_SDA_Y = j8_pin_y(6)    # SDA    (mikroBUS pin 14)
    J8_GND_Y = j8_pin_y(8)    # GND    (mikroBUS pin 16)

    # ----- J7 pin 7 (+3.3V): wire WEST to +3V3 flag -----
    PWR_J7P7_3V3_X = J7_PIN_X - 5.08     # 110.49 — flag anchor west of pin
    parts.append(_sch_wire(J7_PIN_X, J7_3V3_Y, PWR_J7P7_3V3_X, J7_3V3_Y, "j7-p7-3v3-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=PWR_J7P7_3V3_X, y=J7_3V3_Y, angle=270,
        reference="#PWR50",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr50-3v3-j7-p7",
        sheet_key="sensors",
    ))

    # ----- J7 pin 8 (GND): wire WEST to GND flag -----
    PWR_J7P8_GND_X = J7_PIN_X - 5.08      # 110.49
    parts.append(_sch_wire(J7_PIN_X, J7_GND_Y, PWR_J7P8_GND_X, J7_GND_Y, "j7-p8-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J7P8_GND_X, y=J7_GND_Y, angle=270,
        reference="#PWR51",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr51-gnd-j7-p8",
        sheet_key="sensors",
    ))

    # ----- J8 pin 2 (INT/FD, mikroBUS pin 10): wire EAST to NFC_FD hier label -----
    NFC_HLABEL_X = HLABEL_LEFT_X       # 160.02 — shared column with J3/J4
    parts.append(_sch_wire(J8_PIN_X, J8_FD_Y, NFC_HLABEL_X, J8_FD_Y, "j8-p2-fd"))
    parts.append(_sch_hierarchical_label(
        name="NFC_FD", shape="output",
        x=NFC_HLABEL_X, y=J8_FD_Y, angle=0, justify="left",
        uuid_tag="nfc-fd-j8",
    ))

    # ----- J8 pin 5 (SCL, mikroBUS pin 13): wire EAST to I2C_SCL hier label -----
    parts.append(_sch_wire(J8_PIN_X, J8_SCL_Y, NFC_HLABEL_X, J8_SCL_Y, "j8-p5-scl"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SCL", shape="input",
        x=NFC_HLABEL_X, y=J8_SCL_Y, angle=0, justify="left",
        uuid_tag="scl-j8",
    ))

    # ----- J8 pin 6 (SDA, mikroBUS pin 14): wire EAST to I2C_SDA hier label -----
    parts.append(_sch_wire(J8_PIN_X, J8_SDA_Y, NFC_HLABEL_X, J8_SDA_Y, "j8-p6-sda"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SDA", shape="bidirectional",
        x=NFC_HLABEL_X, y=J8_SDA_Y, angle=0, justify="left",
        uuid_tag="sda-j8",
    ))

    # ----- J8 pin 8 (GND, mikroBUS pin 16): wire EAST to GND flag -----
    PWR_J8P8_GND_X = J8_PIN_X + 5.08   # 138.43
    parts.append(_sch_wire(J8_PIN_X, J8_GND_Y, PWR_J8P8_GND_X, J8_GND_Y, "j8-p8-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J8P8_GND_X, y=J8_GND_Y, angle=90,
        reference="#PWR52",
        value_offset_x=3.81, value_offset_y=0.0,
        uuid_tag="pwr52-gnd-j8-p8",
        sheet_key="sensors",
    ))

    # ----- No-connect markers on unused mikroBUS pins -----
    # J7 pins 1..6 (mikroBUS AN/RST/CS/SCK/MISO/MOSI — not used by NFC tag).
    for n in (1, 2, 3, 4, 5, 6):
        parts.append(_sch_no_connect(J7_PIN_X, j7_pin_y(n), f"j7-nc-{n}"))
    # J8 pins 1 (mikroBUS PWM), 3 (RX), 4 (TX), 7 (+5V) — not used.
    for n in (1, 3, 4, 7):
        parts.append(_sch_no_connect(J8_PIN_X, j8_pin_y(n), f"j8-nc-{n}"))

    # ===== C12: 100 nF local decoupling on the NFC daughterboard +3.3V supply =====
    # Sits WEST of J7 between J7 pin 7 (+3V3) and J7 pin 8 (GND).
    C12_X = 105.41
    C12_Y = (J7_3V3_Y + J7_GND_Y) / 2   # mid between J7 pin 7 (+3V3) and pin 8 (GND)
    C12_TOP_Y = C12_Y - 3.81
    C12_BOT_Y = C12_Y + 3.81
    C12_3V3_Y = C12_TOP_Y - 3.81
    parts.append(_sch_wire(C12_X, C12_3V3_Y, C12_X, C12_TOP_Y, "c12-top-3v3"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=C12_X, y=C12_3V3_Y, angle=0,
        reference="#PWR53",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr53-3v3-c12",
        sheet_key="sensors",
    ))
    C12_GND_Y = C12_BOT_Y + 3.81
    parts.append(_sch_wire(C12_X, C12_BOT_Y, C12_X, C12_GND_Y, "c12-bot-gnd"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C12_X, y=C12_GND_Y, angle=0,
        reference="#PWR54",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr54-gnd-c12",
        sheet_key="sensors",
    ))

    # ===== J7, J8, C12 symbols =====
    parts.append(_sch_conn_01xn(
        pin_count=8,
        x=J7_ANCHOR_X, y=J7_ANCHOR_Y, angle=0,
        reference="J7",
        value="1x8 P2.54 mm female socket (MIKROE-2462 mikroBUS pins 1..8 — AN/RST/CS/SCK/MISO/MOSI/+3V3/GND)",
        uuid_tag="j7-mikroe-row-a", sheet_key="sensors",
    ))
    parts.append(_sch_conn_01xn(
        pin_count=8,
        x=J8_ANCHOR_X, y=J8_ANCHOR_Y, angle=180,
        reference="J8",
        value="1x8 P2.54 mm female socket (MIKROE-2462 mikroBUS pins 9..16 — PWM/INT/RX/TX/SCL/SDA/+5V/GND)",
        uuid_tag="j8-mikroe-row-b", sheet_key="sensors",
    ))
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C12_X, y=C12_Y, angle=0,
        reference="C12", value="100nF",
        uuid_tag="c12-nfc-decoupling",
        sheet_key="sensors",
    ))

    # =========================================================================
    # chunk #5d — AQI status-LED ring (8 x SK6812-SIDE slots, 7 placed, +caps)
    # =========================================================================
    # 7 SK6812 SIDE-A LEDs (D11, D12, D14..D18; D13 skipped at J1 cable
    # area) form a ring around the central cable hole on the PCB, all
    # driven from MCU GPIO 8 (WS2812_DIN net) in a daisy chain. Each LED
    # has a 100 nF 0402 decoupling cap (C20, C21, C23..C27) bridging
    # its VDD <-> GND locally. The PCB places them on a Ø26 mm pitch
    # circle around the cable hole at 45 deg pitch; the schematic lays
    # them out as a tidy vertical column for legibility.
    #
    # Pin layout per Normand SK6812 SIDE-A datasheet (1=DIN, 2=VDD,
    # 3=DOUT, 4=GND); cross-checked against OPSCO 2021 rev A/1.
    # Each LED's DOUT (pin 3, RIGHT edge of symbol) → next LED's DIN
    # (pin 1, LEFT edge of symbol). VDD (pin 2, TOP edge) → local +5V
    # flag. GND (pin 4, BOTTOM edge) → local GND flag. The decoupling
    # cap (Device:C) sits to the EAST of each LED with its pin 1 on +5V
    # (above the cap, tying to the SAME local +5V power flag that feeds
    # the LED) and pin 2 on GND (below the cap, tying to the local GND
    # flag). Cap bridges the LED's supply locally.
    #
    # Layout: D11 at the TOP, D18 at the BOTTOM, vertically stacked at
    # X=40.64 with LED_RING_SCH_ROW_PITCH per-LED row pitch (enough for
    # the LED symbol's ±5.08 mm body + ±3.81 mm cap + power flag clearance).
    LED_RING_SCH_X = 40.64
    LED_RING_SCH_Y_START = 60.96
    LED_RING_SCH_ROW_PITCH = 25.40       # enough headroom for LED body
                                          # (±5.08 + ref/value text) + +5V
                                          # flag above (≥3.81) + chain wire
                                          # below + 2.54 mm visual breathing
    LED_RING_HLABEL_X = 27.94            # west of LED.DIN tip (X - 5.08 = 35.56)
    CHAIN_VERT_X = LED_RING_HLABEL_X + 1.27  # 29.21 — col for DOUT→DIN
                                               # chain bends. West of all
                                               # LED bodies (DIN tips at
                                               # 35.56, DOUT tips at 45.72).
    # Track the DOUT (pin 3) tip of the previous LED so we can wire it
    # to the current LED's DIN (pin 1) on each iteration.
    #
    # v0.17: LED slots in `LED_RING_SKIP_INDICES` are skipped (D20). The
    # chain skips over them — when the next non-skipped LED renders, its
    # DIN connects to the most recent prev_dout, leaving the schematic
    # row at the skipped index visually empty. The chain wire spans the
    # full multi-row gap (e.g. D19.DOUT → D21.DIN spans two row pitches
    # of vertical schematic distance).
    prev_dout_x: float | None = None
    prev_dout_y: float | None = None
    for i in range(LED_RING_COUNT):
        if i in LED_RING_SKIP_INDICES:
            continue
        led_ref = f"D{11 + i}"
        cap_ref = f"C{20 + i}"
        led_sch_x = LED_RING_SCH_X
        led_sch_y = LED_RING_SCH_Y_START + i * LED_RING_SCH_ROW_PITCH
        # SK6812-SIDE symbol pin tip positions.
        din_x  = led_sch_x - 5.08      # pin 1 LEFT tip
        din_y  = led_sch_y
        vdd_x  = led_sch_x             # pin 2 TOP tip
        vdd_y  = led_sch_y - 5.08
        dout_x = led_sch_x + 5.08      # pin 3 RIGHT tip
        dout_y = led_sch_y
        gnd_x  = led_sch_x             # pin 4 BOTTOM tip
        gnd_y  = led_sch_y + 5.08

        # ---- DIN: from previous LED's DOUT, or (D11) from the WS2812_DIN
        #      hierarchical label going up to the MCU sub-sheet.
        if i == 0:
            parts.append(_sch_wire(LED_RING_HLABEL_X, din_y, din_x, din_y,
                                    f"led-{led_ref}-din-from-hlabel"))
            parts.append(_sch_hierarchical_label(
                name="WS2812_DIN", shape="input",
                x=LED_RING_HLABEL_X, y=din_y, angle=180, justify="right",
                uuid_tag="ws2812-din-ring",
            ))
        else:
            assert prev_dout_x is not None and prev_dout_y is not None
            # 5-segment route to avoid passing horizontally through the
            # next LED's body (which would short DIN↔DOUT on that LED via
            # the pass-through wire). prev DOUT goes:
            #   1) SOUTH from prev_dout_y to a mid-row Y between the two LEDs
            #   2) WEST to CHAIN_VERT_X
            #   3) SOUTH to din_y
            #   4) EAST to din_x
            mid_y = (prev_dout_y + din_y) / 2.0
            parts.append(_sch_wire(prev_dout_x, prev_dout_y, prev_dout_x, mid_y,
                                    f"led-{led_ref}-chain-south1"))
            parts.append(_sch_wire(prev_dout_x, mid_y, CHAIN_VERT_X, mid_y,
                                    f"led-{led_ref}-chain-west"))
            parts.append(_sch_wire(CHAIN_VERT_X, mid_y, CHAIN_VERT_X, din_y,
                                    f"led-{led_ref}-chain-south2"))
            parts.append(_sch_wire(CHAIN_VERT_X, din_y, din_x, din_y,
                                    f"led-{led_ref}-chain-east"))

        # ---- VDD (pin 2, TOP): wire UP to a local +5V power flag ----
        pwr_vdd_y = vdd_y - 3.81
        parts.append(_sch_wire(vdd_x, pwr_vdd_y, vdd_x, vdd_y,
                                f"led-{led_ref}-vdd-up"))
        parts.append(_sch_power_flag(
            lib_id="power:+5V", value="+5V",
            x=vdd_x, y=pwr_vdd_y, angle=0,
            reference=f"#PWR_LED_5V_{led_ref}",
            value_offset_x=0.0, value_offset_y=-3.556,
            uuid_tag=f"pwr-5v-led-{led_ref}",
            sheet_key="sensors",
        ))

        # ---- GND (pin 4, BOTTOM): wire DOWN to a local GND power flag ----
        pwr_gnd_y = gnd_y + 3.81
        parts.append(_sch_wire(gnd_x, gnd_y, gnd_x, pwr_gnd_y,
                                f"led-{led_ref}-gnd-down"))
        parts.append(_sch_power_flag(
            lib_id="power:GND", value="GND",
            x=gnd_x, y=pwr_gnd_y, angle=0,
            reference=f"#PWR_LED_GND_{led_ref}",
            value_offset_x=0.0, value_offset_y=3.81,
            uuid_tag=f"pwr-gnd-led-{led_ref}",
            sheet_key="sensors",
        ))

        # ---- Decoupling cap (C20+i): bridges +5V ↔ GND just east of LED.
        # Cap body center at (vdd_x + 6.35, led_sch_y). With Device:C
        # angle=0, pin 1 (top) lands at (cap_x, led_sch_y - 3.81),
        # pin 2 (bottom) at (cap_x, led_sch_y + 3.81).
        cap_x = vdd_x + 6.35
        cap_y = led_sch_y
        cap_top_y = cap_y - 3.81
        cap_bot_y = cap_y + 3.81
        # Cap top → +5V flag (separate from the LED's +5V flag; KiCad
        # collapses both into the global +5V net).
        cap_5v_y = cap_top_y - 3.81
        parts.append(_sch_wire(cap_x, cap_5v_y, cap_x, cap_top_y,
                                f"led-{led_ref}-cap-top-5v"))
        parts.append(_sch_power_flag(
            lib_id="power:+5V", value="+5V",
            x=cap_x, y=cap_5v_y, angle=0,
            reference=f"#PWR_CAP_5V_{cap_ref}",
            value_offset_x=0.0, value_offset_y=-3.556,
            uuid_tag=f"pwr-5v-cap-{cap_ref}",
            sheet_key="sensors",
        ))
        # Cap bottom → GND flag.
        cap_gnd_y = cap_bot_y + 3.81
        parts.append(_sch_wire(cap_x, cap_bot_y, cap_x, cap_gnd_y,
                                f"led-{led_ref}-cap-bot-gnd"))
        parts.append(_sch_power_flag(
            lib_id="power:GND", value="GND",
            x=cap_x, y=cap_gnd_y, angle=0,
            reference=f"#PWR_CAP_GND_{cap_ref}",
            value_offset_x=0.0, value_offset_y=3.81,
            uuid_tag=f"pwr-gnd-cap-{cap_ref}",
            sheet_key="sensors",
        ))

        # ---- LED + cap symbol instances ----
        parts.append(_sch_sk6812_side(
            x=led_sch_x, y=led_sch_y,
            reference=led_ref,
            value="SK6812-SIDE",
            uuid_tag=f"led-ring-{led_ref}",
            sheet_key="sensors",
        ))
        parts.append(_sch_capacitor(
            lib_id="Device:C",
            x=cap_x, y=cap_y, angle=0,
            reference=cap_ref, value="100nF",
            uuid_tag=f"led-ring-cap-{cap_ref}",
            sheet_key="sensors",
        ))

        # Save DOUT for the next iteration's chain wire.
        prev_dout_x, prev_dout_y = dout_x, dout_y

    # D18 DOUT is intentionally unconnected (last link in the chain).
    # KiCad's SK6812-SIDE symbol pin 3 is `output` shape so KiCad will
    # warn "pin not driven" if we don't place a no_connect marker. Add
    # one matching the last LED's DOUT tip.
    if prev_dout_x is not None and prev_dout_y is not None:
        parts.append(_sch_no_connect(prev_dout_x, prev_dout_y, "led-ring-dout-end"))

    body = "\n".join(parts)
    return textwrap.dedent(f"""\
        (kicad_sch
        \t(version {SCH_VERSION})
        \t(generator "eeschema")
        \t(generator_version "{GEN_VERSION}")
        \t(uuid "{file_uuid}")
        \t(paper "A4")
        \t(lib_symbols
        {SENSORS_LIB_SYMBOLS()}
        \t)
        {body}
        \t(embedded_fonts no)
        )
        """)


# -----------------------------------------------------------------------------
# 3e) IO sub-sheet — chord-east case-wall connectors (v0.19)
# -----------------------------------------------------------------------------
def IO_LIB_SYMBOLS() -> str:
    """Concatenated lib_symbols block for the IO sub-sheet.

    Reuses `_MCU_LIB_SYMBOLS_TAIL` (Conn_01x06, Device:C / C_Polarized,
    power:+3V3, power:GND) and pulls in two stock symbols:
      - Connector_Generic:Conn_01x04  (4-pin Qwiic / Stemma QT JST SH)
      - Connector_Generic:Conn_01x06  (already in the tail)
    """
    extras = "\n".join([
        _read_kicad_lib_symbol("Connector_Generic.kicad_sym", "Conn_01x04",
                               lib_nickname="Connector_Generic"),
    ])
    return _MCU_LIB_SYMBOLS_TAIL + "\n" + extras


def gen_io_sch() -> str:
    """IO sub-sheet — chord-east case-wall connectors (v0.19).

    The IO sub-sheet hosts the two connectors that live on the OAS PCB's
    chord-east cutouts (C3 / C5; C4 stays as a v2 expansion placeholder):

      J9 — Qwiic / Stemma QT expansion port (always populated)
        4-pin JST SH 1.0 mm pitch horizontal SMD socket. Standard Qwiic
        pinout (GND, +3.3V, SDA, SCL). Mates with any Sparkfun Qwiic
        or Adafruit Stemma QT cable. Connector mouth faces the chord
        edge so the cable plugs in from outside the case after pulling
        a service finger through the C5 cutout.

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

    Inter-sheet nets imported via hierarchical_label (matching sheet pins
    are declared on the root sheet's IO block, exported by the MCU sub-
    sheet which sources the underlying ESP32-C6 GPIOs):
      I2C_SDA      (bidirectional, J9 pin 3) — shared bus, MCU GPIO 6
      I2C_SCL      (input,         J9 pin 4) — shared bus, MCU GPIO 7
      USB_DM       (bidirectional, J10 pin 3) — MCU GPIO 12 (USB D-)
      USB_DP       (bidirectional, J10 pin 4) — MCU GPIO 13 (USB D+)
      EN           (input,         J10 pin 5) — MCU RST pin
      BOOT         (input,         J10 pin 6) — MCU GPIO 9 BOOT strap

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


# -----------------------------------------------------------------------------
# 4) Project file
# -----------------------------------------------------------------------------
def gen_pro() -> str:
    project = {
        "meta": {"filename": "oas.kicad_pro", "version": 3},
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {
                    "apply_defaults_to_fp_fields": False,
                    "apply_defaults_to_fp_shapes": False,
                    "apply_defaults_to_fp_text": False,
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.2,
                    "copper_text_italic": False,
                    "copper_text_size_h": 1.5,
                    "copper_text_size_v": 1.5,
                    "copper_text_thickness": 0.3,
                    "copper_text_upright": False,
                    "courtyard_line_width": 0.05,
                    "dimension_precision": 4,
                    "dimension_units": 3,
                    "dimensions": {
                        "arrow_length": 1270000,
                        "extension_offset": 500000,
                        "keep_text_aligned": True,
                        "suppress_zeroes": False,
                        "text_position": 0,
                        "units_format": 1,
                    },
                    "fab_line_width": 0.1,
                    "fab_text_italic": False,
                    "fab_text_size_h": 1.0,
                    "fab_text_size_v": 1.0,
                    "fab_text_thickness": 0.15,
                    "fab_text_upright": False,
                    "other_line_width": 0.15,
                    "other_text_italic": False,
                    "other_text_size_h": 1.0,
                    "other_text_size_v": 1.0,
                    "other_text_thickness": 0.15,
                    "other_text_upright": False,
                    "pads": {"drill": 0.762, "height": 1.524, "width": 1.524},
                    "silk_line_width": 0.15,
                    "silk_text_italic": False,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                    "silk_text_upright": False,
                    "zones": {"45_degree_only": False, "min_clearance": 0.5},
                },
                "rules": {
                    # JLCPCB-compatible (1-2 layer "minimum" capability)
                    "allow_blind_buried_vias": False,
                    "allow_microvias": False,
                    "max_error": 0.005,
                    # v0.39: kept at 0.15 mm (KiCad-clean). JLCPCB's DFM
                    # scanner warned about 4 sub-0.20 mm clearances in v0.34,
                    # but their fab capability IS 0.15 mm - the warning is a
                    # yield hint, not a defect. Bumping to 0.20 mm would
                    # trigger 121 DRC violations + require re-routing every
                    # autoroute-packed trace. Cost is not justified for the
                    # 5-prototype quantity.
                    "min_clearance": 0.15,
                    "min_connection": 0.0,
                    "min_copper_edge_clearance": 0.3,
                    "min_groove_width": 0.0,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.5,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    # v0.28d: lowered from 2 → 1. The autoroute pass blocked
                    # some thermal spokes on dense GND pads (J3.5, C14.2,
                    # D21.4, U2.1, C20.2), leaving each pad with only 1
                    # spoke to the F.Cu GND pour. A single spoke (0.5 mm
                    # wide × 0.5 mm thermal gap) carries ~1 A continuous
                    # without thermal-relief failure; OAS GND current at
                    # the busiest of these pads (J3 SEN66 return) peaks
                    # at ~0.2 A. Relaxing min_resolved_spokes to 1 is
                    # safe at the OAS power envelope. Reconsider if a
                    # future high-current GND pad (e.g. >2 A continuous)
                    # is added.
                    "min_resolved_spokes": 1,
                    # v0.39 tried 0.20 mm hoping to surface the 17 silk-to-pad
                    # DFM warnings in KiCad DRC. KiCad found 0 violations at
                    # 0.20 mm - the offending silk drawings are inside stock
                    # library footprints which KiCad treats as authoritative.
                    # Reverted to KiCad default 0.15.
                    "min_silk_clearance": 0.15,
                    "min_text_height": 1.0,
                    "min_text_thickness": 0.15,
                    "min_through_hole_diameter": 0.3,
                    "min_track_width": 0.15,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.5,
                    "solder_mask_to_copper_clearance": 0.0,
                    "use_height_for_length_calcs": True,
                },
                # v0.40 audit-16: rule_severities removed (was demoting
                # lib_footprint_mismatch to "ignore" for Q1 pad-name
                # remap). Audit-16 reverses that compromise — instead
                # of suppressing the warning, we eliminate the cause by
                # creating a project-local `OAS:Q_PMOS_GDS` symbol with
                # NUMERIC pin numbers 1/2/3 that bind to the canonical
                # stock SOT-23 pads "1"/"2"/"3" with no remap. Pad NAMES
                # in the manufactured PCB now match stock verbatim, so
                # KiCad's lib_footprint_mismatch is silent without
                # severity override.
                "rule_severities": {},
            },
            "ipc2581": {"dist": "", "distpn": "", "internal_id": "", "mfg": "", "mpn": ""},
            "layer_pairs": [],
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {
            "erc_exclusions": [],
            "meta": {"version": 0},
            "pin_map": [],
            # `rule_severities` is intentionally an empty object: it carries
            # explicit overrides only. KiCad's `kicad-cli sch erc` falls back
            # to its built-in default severity list for every ERC category
            # NOT present here (e.g. "Global label only appears once",
            # "Four connection points are joined together", "SPICE model
            # issue", "Assigned footprint doesn't match footprint filters" —
            # all of which the ERC report shows as "ignored" categories).
            # If a future maintainer wonders where those default-ignores
            # come from: they are not in this file, they are baked into
            # kicad-cli (v0.23 review Nt1).
            "rule_severities": {},
        },
        "libraries": {
            "pinned_footprint_libs": ["oas"],
            "pinned_symbol_libs": [],
        },
        "net_settings": {
            "classes": [
                {
                    "name": "Default",
                    "bus_width": 12,
                    "clearance": 0.15,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.2,
                    "line_style": 0,
                    "microvia_diameter": 0.3,
                    "microvia_drill": 0.1,
                    "priority": 2147483647,
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.25,
                    "via_diameter": 0.6,
                    "via_drill": 0.3,
                    "wire_width": 6,
                },
                {
                    "name": "Power",
                    "bus_width": 12,
                    "clearance": 0.2,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.2,
                    "line_style": 0,
                    "microvia_diameter": 0.3,
                    "microvia_drill": 0.1,
                    "priority": 100,
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.5,
                    "via_diameter": 0.8,
                    "via_drill": 0.4,
                    "wire_width": 6,
                },
            ],
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [],
        },
        "pcbnew": {
            "last_paths": {"gencad": "", "idf": "", "netlist": "", "plot": "",
                           "pos_files": "", "specctra_dsn": "", "step": "", "svg": "", "vrml": ""},
            "page_layout_descr_file": "",
        },
        "schematic": {
            "annotate_start_num": 0,
            "bom_export_filename": "${PROJECTNAME}.csv",
            "bom_settings": {},
            "connection_grid_size": 50.0,
            "drawing": {},
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
            "ngspice": {},
            "spice_adjust_passive_values": False,
            "subpart_first_id": 65,
            "subpart_id_separator": 0,
        },
        "sheets": [
            [ROOT_SHEET_UUID, "Root"],
            *[
                [SHEET_BLOCK_UUIDS[name], SUBSHEET_DISPLAY_NAMES[name]]
                for name in SUBSHEETS
            ],
        ],
        "text_variables": {},
        "tuning_profiles": [],
    }
    return json.dumps(project, indent=2)

# -----------------------------------------------------------------------------
# 5) Footprint library table
# -----------------------------------------------------------------------------
def gen_fp_lib_table() -> str:
    return textwrap.dedent("""\
        (fp_lib_table
        \t(version 7)
        \t(lib (name "oas") (type "KiCad") (uri "${KIPRJMOD}/libraries/oas.pretty") (options "") (descr "Project-local footprints"))
        )
        """)

def gen_sym_lib_table() -> str:
    """Project-local symbol-library table.

    Maps the `OAS` library name (used as `OAS:ESP32-C6_DevKitM-1` lib_id
    inside mcu.kicad_sch) to the project-local `libraries/OAS.kicad_sym`
    file. Without this entry, KiCad ERC raises `lib_symbol_issues` on the
    U3 symbol ("Obecna konfiguracja nie zawiera biblioteki symboli 'OAS'").
    """
    return textwrap.dedent("""\
        (sym_lib_table
        \t(version 7)
        \t(lib
        \t\t(name "OAS")
        \t\t(type "KiCad")
        \t\t(uri "${KIPRJMOD}/libraries/OAS.kicad_sym")
        \t\t(options "")
        \t\t(descr "OAS project-local symbols (ESP32-C6 DevKitM-1, ...)")
        \t)
        )
        """)


def gen_oas_symbol_library() -> str:
    """Project-local symbol library file `OAS.kicad_sym`.

    Mirrors the embedded `(symbol "OAS:ESP32-C6_DevKitM-1" ...)` inside
    mcu.kicad_sch so KiCad can resolve the OAS library reference from
    the sym-lib-table. The embedded copy in mcu.kicad_sch is what gets
    rendered; this file exists primarily to silence the
    `lib_symbol_issues` ERC warning on U3.

    v0.16 adds `OAS:SK6812-SIDE` for the AQI status-LED ring (D11..D22).
    """
    # v0.40 audit-16: extract OAS:Q_PMOS_GDS from POWER_LIB_SYMBOLS so
    # the standalone libraries/OAS.kicad_sym carries the same Q_PMOS_GDS
    # definition that's embedded in power.kicad_sch. Required because
    # the Q1 schematic instance references `OAS:Q_PMOS_GDS` (NOT
    # Device:Q_PMOS — would trigger lib_symbol_mismatch since our pin
    # numbers 1/2/3 differ from stock D/G/S).
    import re as _re
    m = _re.search(
        r'(\(symbol "OAS:Q_PMOS_GDS"[\s\S]*?\(embedded_fonts no\)\s*\))',
        POWER_LIB_SYMBOLS,
    )
    assert m is not None, "could not extract OAS:Q_PMOS_GDS from POWER_LIB_SYMBOLS"
    q_pmos_gds_block = m.group(1)
    bodies = [
        _esp32c6_devkitm1_lib_symbol(),
        _sk6812_side_lib_symbol(),
        # Wrap in two leading tabs to match the convention expected by
        # _strip_one_tab below.
        "\t\t" + q_pmos_gds_block,
    ]
    # The two helpers return content indented with two leading tabs (one
    # tab inside the schematic file, one inside `lib_symbols`). In the
    # standalone `.kicad_sym` file the `(symbol ...)` blocks are nested
    # ONCE inside `(kicad_symbol_lib ...)`, so strip one tab from each
    # line.
    def _strip_one_tab(s: str) -> str:
        return "\n".join(
            (line[1:] if line.startswith("\t") else line)
            for line in s.split("\n")
        )
    body_text = "\n".join(_strip_one_tab(b) for b in bodies)
    return textwrap.dedent("""\
        (kicad_symbol_lib
        \t(version 20251024)
        \t(generator "kicad_symbol_editor")
        \t(generator_version "10.0")
        """) + body_text + "\n)\n"

# -----------------------------------------------------------------------------
# Netlist post-processor (Option A from pre-routing-review v0.19 / C1)
# -----------------------------------------------------------------------------
#
# After generate.py emits oas.kicad_pcb (with every pad on net 0), we re-run
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
def main():
    (HERE / "libraries" / "oas.pretty").mkdir(parents=True, exist_ok=True)

    (HERE / "libraries" / "oas.pretty" / "MountingHole_3.8mm_M3.kicad_mod").write_text(
        gen_mounting_hole_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "SEN66_Mechanical_Reference.kicad_mod").write_text(
        gen_sen66_mechanical_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "ZipTieHole_3mm_NPTH.kicad_mod").write_text(
        gen_ziptie_hole_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "LD2410_Mechanical_Reference.kicad_mod").write_text(
        gen_ld2410_mechanical_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "ESP32-C6-DevKitM-1_Reference.kicad_mod").write_text(
        gen_daughterboard_mech_lib_file(
            name="ESP32-C6-DevKitM-1_Reference",
            descr="Espressif ESP32-C6-DevKitM-1-N4 daughterboard mechanical reference (no pads). EAN 5904422385651. Body 25.4×48.26×8.6 mm. Mounts on 2× 1x15 P2.54 mm female pin sockets; antenna at one short edge, dual USB-C at the other. Pin block offset 0.98 mm toward antenna end per Espressif dimensions PDF.",
            body_w=ESP32_BODY_W, body_l=ESP32_BODY_L,
            pin_row_inset=ESP32_PIN_ROW_INSET,
            pin_pitch=ESP32_PIN_PITCH,
            pin_count_per_row=ESP32_PIN_COUNT_PER_ROW,
            body_label="ESP32-C6 DevKitM-1",
            antenna_label="ant",
            usb_label="USB",
            uuid_tag="esp32-devkitm1",
            pin_start_offset=ESP32_PIN_START_OFFSET,
        ),
        encoding="utf-8",
    )
    (HERE / "libraries" / "oas.pretty" / "MIKROE-2462_Reference.kicad_mod").write_text(
        gen_daughterboard_mech_lib_file(
            name="MIKROE-2462_Reference",
            descr="MikroElektronika NFC Tag 2 Click (NT3H1101 NTAG I²C plus + onboard PCB antenna) daughterboard mechanical reference (no pads). Body 25.4×57.15×7 mm per mikroBUS size L spec. Pin block offset 2.54 mm toward pin-1 short edge; NFC antenna spiral on the ~36.83 mm strip past pin 8.",
            body_w=MIKROE2462_BODY_W, body_l=MIKROE2462_BODY_L,
            pin_row_inset=MIKROE2462_PIN_ROW_INSET,
            pin_pitch=MIKROE2462_PIN_PITCH,
            pin_count_per_row=MIKROE2462_PIN_COUNT_PER_ROW,
            body_label="MIKROE-2462",
            antenna_label=None,
            usb_label=None,
            uuid_tag="mikroe2462",
            pin_start_offset=MIKROE2462_PIN_START_OFFSET,
        ),
        encoding="utf-8",
    )
    (HERE / "libraries" / "oas.pretty" / "SK6812-SIDE.kicad_mod").write_text(
        gen_sk6812_side_footprint(), encoding="utf-8",
    )
    (HERE / "oas.kicad_pcb").write_text(gen_pcb(), encoding="utf-8")
    (HERE / "oas.kicad_sch").write_text(gen_root_sch(), encoding="utf-8")

    # v0.26: Z-clearance guardrail. Audit-driven regression check that
    # asserts every component placed under a daughterboard's body shadow
    # has a height <= that daughterboard's under-board clearance budget.
    # DRC has no third-dimension awareness; the daughterboard mech-refs
    # intentionally carry no F.CrtYd so SMD parts CAN go under them.
    # Without this check, tall THT parts (electrolytic caps, TO-263-5
    # buck) slip through DRC + ERC + visual review even when they would
    # physically prevent the daughterboard from seating into its sockets.
    # See FOOTPRINT_HEIGHT / DAUGHTERBOARD_Z_CLEARANCE / commentary above.
    print()
    print("Checking daughterboard Z-clearance violations…")
    violations = check_z_clearance_violations()
    if violations:
        print()
        print("ERROR: Z-clearance violations under daughterboards:")
        for v in violations:
            print(v)
        print()
        sys.exit(
            "Aborting: relocate the offending components out of the "
            "daughterboard body shadow, or update DAUGHTERBOARD_Z_CLEARANCE "
            "if the socket spec has changed."
        )
    print(f"  OK — no Z-clearance violations (checked {len(_parse_footprint_placements())} placed footprints).")

    # v0.23: build Reference → Footprint map from the freshly-written PCB,
    # used to back-fill every schematic symbol's Footprint property (review
    # Mn3 — empty Footprint property triggered a "no footprint assigned"
    # warning when running the schematic-driven netlist / Update-PCB path).
    pcb_ref_to_fp = _build_pcb_ref_to_footprint()

    # v0.38: load lcsc-mapping.csv to inject Manufacturer/MPN/LCSC
    # properties into every schematic symbol (closes audit-16 "projekt
    # sobie, BOM sobie" finding — embedded supply-chain metadata makes
    # the schematic self-sufficient for BOM export).
    lcsc_metadata_map = _build_lcsc_metadata_map()

    for name in SUBSHEETS:
        # sheet_context auto-namespaces every U() call made by the per-sheet
        # generator (and the _sch_* helpers it invokes) under `name:`, so two
        # sheets that emit the same logical wire / junction / label tag do not
        # collide on UUIDs.
        with sheet_context(name):
            if name == "power":
                content = gen_power_sch()
            elif name == "mcu":
                content = gen_mcu_sch()
            elif name == "sensors":
                content = gen_sensors_sch()
            elif name == "io":
                content = gen_io_sch()
            else:
                content = gen_subsheet_sch(name)
        # Back-fill Footprint property for every real-component symbol so
        # the schematic-side netlist export carries the same footprint
        # reference the PCB does (v0.23 fix for review Mn3).
        content = _apply_schematic_footprints(content, pcb_ref_to_fp)
        # v0.38: inject Manufacturer/MPN/LCSC properties on each symbol
        # whose (Value, Footprint) matches a row in lcsc-mapping.csv.
        # MUST run AFTER _apply_schematic_footprints so the Footprint
        # property is populated and the (Value, Footprint) lookup key
        # works.
        content = _apply_schematic_lcsc_metadata(content, lcsc_metadata_map)
        (HERE / f"{name}.kicad_sch").write_text(content, encoding="utf-8")
    (HERE / "oas.kicad_pro").write_text(gen_pro(), encoding="utf-8")
    (HERE / "fp-lib-table").write_text(gen_fp_lib_table(), encoding="utf-8")
    (HERE / "sym-lib-table").write_text(gen_sym_lib_table(), encoding="utf-8")
    (HERE / "libraries").mkdir(parents=True, exist_ok=True)
    (HERE / "libraries" / "OAS.kicad_sym").write_text(
        gen_oas_symbol_library(), encoding="utf-8",
    )

    # ---- v0.20 C1 fix: sync electrical nets from schematic to PCB ----
    # After all files are written, parse the schematic netlist and inject
    # (net code "name") clauses into every PCB pad whose footprint
    # reference + pad number matches a schematic node. Bridges the gap
    # between PCB geometry placement (this script) and electrical
    # connectivity (pcbnew's F8 Update PCB from Schematic). See
    # sync_pcb_nets_from_schematic above and the pre-routing-review v0.19
    # finding C1.
    print()
    print("Syncing PCB nets from schematic netlist…")
    assigned = sync_pcb_nets_from_schematic()
    if assigned:
        print(f"  {assigned} pad net assignments applied.")

    # ---- v0.28: copper routing — emit tracks + vias + GND pour zones ----
    # Routes are computed AFTER `sync_pcb_nets_from_schematic` because
    # `_routing_pad_db()` needs every pad to carry its net assignment.
    # `ROUTING_CHUNKS` is filled per-chunk during the v0.28 work — each
    # chunk in v0.28a..v0.28e adds a name to the tuple as routing for
    # that subsystem becomes correct. Final state (v0.28e) routes every
    # chunk.
    print()
    print("Applying copper routing…")
    n_tracks = apply_routing_to_pcb(chunks=ROUTING_CHUNKS)
    print(f"  {n_tracks} track records emitted (chunks: {', '.join(ROUTING_CHUNKS) or '(none)'}).")

    # v0.39 attempted to lift silk strokes 0.12 -> 0.15 mm here to fix
    # the JLCPCB DFM "Silkscreen line width" warning (50 occurrences in
    # v0.34). v0.40 live DFM scan revealed this REGRESSED silk-to-pad
    # clearance from 17 W -> 20 DANGER + 19 W (wider strokes consume
    # clearance margin) without actually fixing the line-width warning
    # (JLCPCB still flags 0.15 mm as Warning - their "Good" threshold
    # for silk line width is >= 0.20 mm). Reverted; the silk-line-width
    # fix would require BOTH wider strokes AND moving labels further
    # from pads, which is invasive for stock-library footprints.

    # Geometry summary for the human
    print(f"Half-chord: {HALF_CHORD:.4f} mm")
    print(f"Y_chord (from centre): {Y_CHORD:.4f} mm")
    print(f"Chord endpoints: (±{HALF_CHORD:.4f}, +{Y_CHORD:.4f})")
    print(f"Arc mid-point: (0, -{R_OUTLINE:.4f})")
    print(f"Hole positions:")
    for x, y in HOLE_POSITIONS:
        print(f"  ({x:+.4f}, {y:+.4f})")
    print()
    print("Files written:")
    for p in [
        "oas.kicad_pro", "oas.kicad_sch", "oas.kicad_pcb",
        "power.kicad_sch", "mcu.kicad_sch", "sensors.kicad_sch", "io.kicad_sch",
        "fp-lib-table", "sym-lib-table",
        "libraries/OAS.kicad_sym",
        "libraries/oas.pretty/MountingHole_3.8mm_M3.kicad_mod",
        "libraries/oas.pretty/SEN66_Mechanical_Reference.kicad_mod",
        "libraries/oas.pretty/ZipTieHole_3mm_NPTH.kicad_mod",
        "libraries/oas.pretty/LD2410_Mechanical_Reference.kicad_mod",
        "libraries/oas.pretty/ESP32-C6-DevKitM-1_Reference.kicad_mod",
        "libraries/oas.pretty/MIKROE-2462_Reference.kicad_mod",
        "libraries/oas.pretty/SK6812-SIDE.kicad_mod",
    ]:
        full = HERE / p
        print(f"  {p}  ({full.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
