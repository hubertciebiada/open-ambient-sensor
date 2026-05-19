"""boardgen/_sch_mcu.py - mcu.kicad_sch generator."""
from __future__ import annotations

import math
import textwrap

from boardgen._common import U, fmt, sheet_context, SCH_VERSION, GEN_VERSION, SHEET_FILE_UUIDS, ROOT_SHEET_UUID, SUBSHEET_DISPLAY_NAMES
from boardgen._project import fx, fy, PROJECT_SHORTNAME, GPIO_ASSIGNMENTS, GPIO_RESERVED
from boardgen._lib_symbols import (
    MCU_LIB_SYMBOLS,
    ESP32C6_DEVKITM1_PINS,
    ESP32C6_DEVKITM1_SIGNAL_PIN,
    ESP32C6_DEVKITM1_NC_PINS,
    ESP32C6_DEVKITM1_GND_PINS,
    ESP32C6_DEVKITM1_PIN_PITCH,
    ESP32C6_DEVKITM1_PIN_ROW_HALF,
    ESP32C6_DEVKITM1_LIB_X_LEFT,
    ESP32C6_DEVKITM1_LIB_X_RIGHT,
    ESP32C6_DEVKITM1_LIB_PIN_LEN,
    ESP32C6_DEVKITM1_LIB_BODY_X,
    ESP32C6_DEVKITM1_LIB_BODY_Y,
)
from boardgen._sch_helpers import (
    _sch_wire, _sch_junction, _sch_power_flag, _sch_capacitor,
    _sch_resistor,
    _sch_hierarchical_label, _sch_no_connect, _sch_local_label,
    _sch_esp32c6_devkitm1, _mcu_pin_xy,
    _sch_conn_01x06, _sch_conn_02x08_top_bottom, _sch_conn_01x04,
    _sch_conn_01x05, _sch_conn_01xn, _conn_01xn_pin_xy,
    _CONN_01XN_PIN1_LIB_Y,
)


# -----------------------------------------------------------------------------
# gen_mcu_sch
# -----------------------------------------------------------------------------
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
from boardgen._lib_symbols import _sk6812_side_lib_symbol
