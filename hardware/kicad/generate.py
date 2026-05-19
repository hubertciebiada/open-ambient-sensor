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


from boardgen._lib_symbols import POWER_LIB_SYMBOLS


# -----------------------------------------------------------------------------
# Helpers for symbol/wire/junction emission in power.kicad_sch
# -----------------------------------------------------------------------------
from boardgen._sch_helpers import (
    _sch_wire, _sch_junction, _sch_power_flag,
    _sch_q_pmos, _sch_resistor, _sch_polyfuse, _sch_diode_tvs,
    _sch_capacitor, _sch_inductor, _sch_diode_schottky,
    _sch_diode_zener, _sch_buck_lm2596_5, _sch_buck_tps62933,
)
from boardgen._sch_power import gen_power_sch
from boardgen._sch_helpers import (
    _sch_hierarchical_label, _sch_no_connect, _sch_local_label,
    _sch_esp32c6_devkitm1, _mcu_pin_xy,
    _sch_conn_01x06, _sch_conn_02x08_top_bottom, _sch_conn_01x04,
    _sch_conn_01x05, _sch_conn_01xn, _conn_01xn_pin_xy,
)
from boardgen._sch_mcu import gen_mcu_sch
from boardgen._sch_helpers import _sch_sk6812_side
from boardgen._sch_sensors import gen_sensors_sch
from boardgen._sch_io import gen_io_sch

from boardgen._project_files import (
    gen_pro,
    gen_fp_lib_table,
    gen_sym_lib_table,
    gen_oas_symbol_library,
)
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
