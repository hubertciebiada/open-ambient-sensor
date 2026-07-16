"""boardgen/_sch_root.py - oas.kicad_sch (root sheet) + generic sub-sheet fallback.

Emits the top-level schematic with 4 hierarchical (sheet ...) blocks for
power / mcu / sensors / io, plus the inter-sheet wire connections for shared
nets. Per-sheet content comes from boardgen/_sch_power.py, _sch_mcu.py,
_sch_sensors.py, _sch_io.py.
"""
from __future__ import annotations

import textwrap

from boardgen._common import (
    U, fmt,
    SCH_VERSION, GEN_VERSION,
    ROOT_SHEET_UUID, SHEET_BLOCK_UUIDS, SHEET_FILE_UUIDS,
    SUBSHEET_DISPLAY_NAMES, SUBSHEET_POSITIONS, SUBSHEET_SIZE,
    SUBSHEETS,
)


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
