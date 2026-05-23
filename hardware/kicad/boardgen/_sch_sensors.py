"""boardgen/_sch_sensors.py - sensors.kicad_sch generator."""
from __future__ import annotations

import textwrap

from boardgen._common import U, fmt, sheet_context, SCH_VERSION, GEN_VERSION, SHEET_FILE_UUIDS, ROOT_SHEET_UUID, SUBSHEET_DISPLAY_NAMES
from boardgen._project import fx, fy, PROJECT_SHORTNAME, LED_RING_COUNT, LED_RING_SKIP_INDICES
from boardgen._lib_symbols import SENSORS_LIB_SYMBOLS
from boardgen._sch_helpers import (
    _sch_wire, _sch_junction, _sch_power_flag,
    _sch_capacitor, _sch_hierarchical_label, _sch_no_connect,
    _sch_local_label, _sch_sk6812_side,
    _sch_conn_01x06, _sch_conn_02x08_top_bottom, _sch_conn_01x04,
    _sch_conn_01x05, _sch_conn_01xn, _conn_01xn_pin_xy,
    _CONN_01XN_PIN1_LIB_Y,
)


# -----------------------------------------------------------------------------
# gen_sensors_sch
# -----------------------------------------------------------------------------
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
    # This schematic pad-to-net mapping (pad 1 = OUT … pad 5 = VCC) is
    # CORRECT and matches the datasheet — do not touch it. The v0.15.8
    # "fix" that reversed these nets was misdiagnosed: the real defect was
    # the J4 PCB footprint placement (rotation put pad 1 at the wrong
    # physical end vs where the LD2410 module's OUT pin lands). That was
    # corrected at the footprint layer in v0.43 — see the J4_PCB_* block in
    # _project.py. The schematic stays as-is.
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

