"""boardgen/_lib_symbols.py - schematic library-symbol blocks.

KiCad embeds the symbols a schematic uses inside the schematic's
`(lib_symbols ...)` section so the .kicad_sch file is self-contained
(no external library lookups). This module exports those embedded
blocks as Python strings or as functions that return them.

  - `POWER_LIB_SYMBOLS` - stock KiCad symbols used by power.kicad_sch
    (terminal blocks, polarized caps, power flags, OAS:Q_PMOS_GDS,
    etc.). Pasted verbatim from KiCad 10 stock libraries.

Future additions (as per-sheet generators get extracted into
_sch_mcu.py / _sch_sensors.py / _sch_io.py): MCU_LIB_SYMBOLS,
SENSORS_LIB_SYMBOLS, IO_LIB_SYMBOLS plus the helper functions
_esp32c6_devkitm1_lib_symbol and _sk6812_side_lib_symbol.
"""
from __future__ import annotations

from pathlib import Path

import textwrap

from boardgen._common import fmt, U
from boardgen._footprints import _read_kicad_lib_symbol


# Verbatim KiCad-stock lib_symbols content lives next door under
# `boardgen/data/*.kicad_sym_inline`. These are GPL upstream excerpts of
# `Connector.kicad_sym`, `power.kicad_sym`, `Connector_Generic.kicad_sym`,
# and `Device.kicad_sym` from KiCad 10's installed symbol libraries,
# embedded into our schematic files for self-containment.
_DATA = Path(__file__).parent / "data"


def _read_data(name: str) -> str:
    """Load a verbatim KiCad-stock lib-symbol blob from `boardgen/data/`.

    Round-trip is identity: `Path.write_text(s, encoding="utf-8")` followed
    by `Path.read_text(encoding="utf-8")` returns the exact same `s`.
    No trailing newline added, no escape-sequence re-interpretation."""
    return (_DATA / name).read_text(encoding="utf-8")



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
POWER_LIB_SYMBOLS = _read_data("power_lib_symbols.kicad_sym_inline")


# -----------------------------------------------------------------------------
# Extracted: esp32_mcu
# -----------------------------------------------------------------------------
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
_DEVICE_R_LIB_SYMBOL = _read_data("device_r_lib_symbol.kicad_sym_inline")


# The lib-symbol block continued below is a multi-symbol literal that
# wraps the Conn_01x06 / Device:C / Device:C_Polarized / power symbols
# inherited from KiCad's stock library. Combined at usage time with
# the dynamic ESP32-C6 symbol via MCU_LIB_SYMBOLS().
_MCU_LIB_SYMBOLS_TAIL = _read_data("mcu_lib_symbols_tail.kicad_sym_inline")


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
# Extracted: sk6812
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




# -----------------------------------------------------------------------------
# Extracted: sensors_lib
# -----------------------------------------------------------------------------
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




# -----------------------------------------------------------------------------
# Extracted: io_lib
# -----------------------------------------------------------------------------
def IO_LIB_SYMBOLS() -> str:
    """Concatenated lib_symbols block for the IO sub-sheet.

    Reuses `_MCU_LIB_SYMBOLS_TAIL` (Conn_01x06, Device:C / C_Polarized,
    power:+3V3, power:GND) and pulls in stock symbols:
      - Connector_Generic:Conn_01x04  (4-pin Qwiic / Stemma QT JST SH)
      - Connector_Generic:Conn_01x06  (already in the tail)
      - Switch:SW_Push                (SW1 tactile push-button)
    """
    extras = "\n".join([
        _read_kicad_lib_symbol("Connector_Generic.kicad_sym", "Conn_01x04",
                               lib_nickname="Connector_Generic"),
        # v0.42: SW1 — side-actuated tactile push-button. Stock SW_Push
        # has numeric pins "1"/"2" that bind natively to the footprint
        # pads "1"/"2" — no pin_name_map remap needed (Lesson 8).
        _read_kicad_lib_symbol("Switch.kicad_sym", "SW_Push",
                               lib_nickname="Switch"),
    ])
    return _MCU_LIB_SYMBOLS_TAIL + "\n" + extras




# -----------------------------------------------------------------------------
# ESP32-C6 DevKitM-1-N4 pin map + lib geometry constants
# -----------------------------------------------------------------------------
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

