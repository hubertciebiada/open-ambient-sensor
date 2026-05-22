"""boardgen/_project.py — OAS-specific constants and geometry.

This module holds everything that DEFINES the OAS board as a specific
electronic product:

  - Project identity (name, repo, license, revision)
  - External-module metadata (EXTERNAL_MODULES — Espressif devkit, SEN66,
    LD2410, MIKROE-2462, AK-N-94 enclosure)
  - ESP32-C6 GPIO pin assignments (GPIO_ASSIGNMENTS, GPIO_RESERVED,
    GPIO_SPARE — single source of truth for the pinout)
  - Assembly + verification metadata (ASSEMBLY_INSTRUCTIONS,
    CASE_VERIFICATION_CHECKLIST, LOCALLY_SOURCED_PARTS)
  - PCB geometry (Ø120 mm D-shape outline, mounting holes, cable hole,
    case-wall cutouts)
  - Daughterboard placements: SEN66 + zip-tie holes + J3 socket;
    LD2410 + J4 socket; ESP32-C6 DevKitM-1; MIKROE-2462 NFC click;
    J1 24 V terminal block; J9 Qwiic; J10 recovery header
  - AQI LED ring (8 × SK6812-SIDE on 45° pitch)
  - Local-to-PCB coordinate transforms (`_sen66_local_to_pcb`,
    `_ld2410_local_to_pcb`, `_led_local_to_pcb`)
  - Page-centring formatters fx/fy

Project-AGNOSTIC framework helpers (UUID system, `fmt`, `Context`,
sub-sheet IDs, KiCad format versions) live in `boardgen/_common.py`.
"""
from __future__ import annotations

import math

from boardgen._common import fmt

# =============================================================================
# PROJECT METADATA
# =============================================================================
# Single source of truth for project identity, external modules, GPIO map,
# and board revision. Consumed by:
#   - boardgen stages themselves (title block / silk text; legacy
#     constants like OAS_VERSION_LINE still drive existing renders today)
#   - pipeline/oas/06_check_boot.py (could cross-check GPIO_ASSIGNMENTS)
#   - downstream documentation (CLAUDE.md references constants by name)
#
# Update HERE FIRST when changing identity / revision / pinout / external
# modules. Other places (CLAUDE.md quick-reference tables, schematic
# generators) follow this dict.

# Project identity --------------------------------------------------------
PROJECT_NAME = "Open Ambient Sensor"
PROJECT_SHORTNAME = "OAS"
PROJECT_DESCRIPTION = (
    "DIY multi-sensor environmental monitor for indoor spaces. "
    "Measures air quality (CO2, PM, VOC, NOx, T, RH via SEN66) and presence "
    "(LD2410 mmWave). 24 V DC input, ESPHome firmware, Home Assistant "
    "integration. Mounts on a standard wall-recessed electrical box "
    "(60 mm screw pitch)."
)
PROJECT_REPO = "https://github.com/hubertciebiada/open-ambient-sensor"
PROJECT_LICENSE_HW = "CERN-OHL-S v2"
PROJECT_LICENSE_FW = "MIT"

# Board revision (manual update on significant geometry / netlist changes).
# Also drives existing OAS_VERSION_LINE silk text in _common.py.
BOARD_REVISION = "v0.40"
BOARD_RELEASE_DATE = "2026-05-17"

# External modules (manual-source / 3rd-party — NOT in lcsc-mapping.csv
# because they go through THT hand-solder, separate procurement, or are
# mechanical). Each entry: full identification metadata for re-procurement.
EXTERNAL_MODULES = {
    "ESP32-C6-DevKitM-1-N4": {
        "manufacturer": "Espressif",
        "mpn": "ESP32-C6-DevKitM-1-N4",
        "ean": "5904422385651",
        "supplier_pl": "Botland",
        "datasheet": (
            "https://docs.espressif.com/projects/esp-dev-kits/en/latest/"
            "esp32c6/esp32-c6-devkitm-1/index.html"
        ),
        "note": (
            "Official Espressif devkit (ESP32-C6-MINI-1 SoM + 2x USB-C). "
            "NOT compatible with generic 'SuperMini' clones (different pinout)."
        ),
    },
    "SEN66-SIN-T": {
        "manufacturer": "Sensirion",
        "material": "3.001.030",
        "supplier_global": "Sensirion direct",
        "supplier_eu": "LaskaKit / ThePiHut",
        "datasheet": "https://sensirion.com/resource/datasheet/SEN66",
        "accessory": (
            "JST GH 6-pin cable (50 cm AWG26) - separately ordered; "
            "Sensirion ships SEN66 without cable."
        ),
        "note": (
            "Combo sensor: NDIR CO2 + laser PM + MOX VOC/NOx + SHT (T/RH) "
            "in single ~25 x 55 x 21.5 mm module."
        ),
    },
    "HLK-LD2410B": {
        "manufacturer": "Hi-Link",
        "mpn": "HLK-LD2410B",
        "supplier": "HiLink direct / TME / AliExpress",
        "datasheet": "https://www.hlktech.net (search LD2410B)",
        "note": (
            "Specifically -B variant. -C variant has different pin order "
            "and body dims; NOT interchangeable. Connector pinout (HLK "
            "datasheet Figure 1 + Table 1): pins 1..5 = OUT, UART_Tx, "
            "UART_Rx, GND, VCC. Physical board order (antenna end -> "
            "connector tip) = VCC, GND, Rx, Tx, OUT — drives the J4 "
            "footprint orientation (see J4_PCB_* block)."
        ),
    },
    "MIKROE-2462": {
        "manufacturer": "MikroElektronika",
        "mpn": "MIKROE-2462",
        "description": "NFC Tag 2 Click (NXP NT3H1101 + onboard PCB antenna)",
        "supplier": "MikroE direct / TME",
        "datasheet": "https://www.mikroe.com/nfc-tag-2-click",
        "form_factor": "mikroBUS L (25.4 x 57.15 x 7 mm)",
        "note": (
            "Pinout verified against the NFC Tag 2 Click schematic v101: "
            "of the 16 mikroBUS pins only +3.3V (pin 7) + GND (pin 8) on "
            "the left header and INT/FD (pin 10), SCL (pin 13), SDA "
            "(pin 14), GND (pin 16) on the right header are connected; the "
            "rest are NC. NT3H1101 I2C slave address 0x55."
        ),
    },
    "SZOMK AK-N-94": {
        "manufacturer": "SZOMK",
        "mpn": "AK-N-94",
        "description": (
            "Ø128 mm perforated white ABS enclosure "
            "(smoke-detector form factor)"
        ),
        "supplier": "SZOMK direct (chinaenclosure.com)",
        "datasheet_note": (
            "Manufacturer DXF / datasheet are 3rd-party and NOT "
            "redistributable via this repo (CLAUDE.md Rule 6). Keep "
            "locally; gitignored."
        ),
        "derived_dimensions": (
            "PCB Ø120 D-shape, 3x M3 mounting (Ø3.8 NPTH) on Ø110 pitch, "
            "Ø12 central cable pass-through, 17 mm front clearance / "
            "22 mm in SEN66 zone, 5 mm back."
        ),
    },
}

# ESP32-C6-DevKitM-1-N4 GPIO assignments (single source of truth for pinout).
# Each entry: {net: <name>, desc: <description>}. Update HERE first when
# re-pinning, then the schematic generators below pick up via the table.
# Cross-checked by pipeline/oas/06_check_boot.py.
GPIO_ASSIGNMENTS = {
    1:  {"net": "BTN",        "sheet": "/IO/",  "desc": "Tactile push-button SW1 (short press = LED dim cycle, long press = ESP32 restart); safe non-strap input"},
    2:  {"net": "LD2410_OUT", "sheet": "/MCU/", "desc": "LD2410 presence interrupt (safe non-strap input)"},
    3:  {"net": "NFC_FD",     "sheet": "/MCU/", "desc": "NT3H1101 NFC field-detect interrupt (safe non-strap)"},
    6:  {"net": "I2C_SDA",    "sheet": "/IO/",  "desc": "Shared I2C bus: SEN66 0x6B, NT3H1101 0x55, J9 Qwiic"},
    7:  {"net": "I2C_SCL",    "sheet": "/IO/",  "desc": "Shared I2C bus, 4.7 kOhm pull-ups on MCU side (220 mm bus)"},
    8:  {"net": "WS2812_DIN", "sheet": "/MCU/", "desc": "SK6812-SIDE AQI ring data line. STRAP PIN - R7 10 kOhm pull-up to +3V3 required (DevKitM-1 onboard pull-up runs off VCC_5V which is unpowered in OAS)"},
    12: {"net": "USB_DM",     "sheet": "/IO/",  "desc": "Native USB-Serial-JTAG D-"},
    13: {"net": "USB_DP",     "sheet": "/IO/",  "desc": "Native USB-Serial-JTAG D+"},
    16: {"net": "UART_TX",    "sheet": "/MCU/", "desc": "UART1 TX -> LD2410 RX at 256000 baud"},
    17: {"net": "UART_RX",    "sheet": "/MCU/", "desc": "UART1 RX <- LD2410 TX at 256000 baud"},
}

GPIO_RESERVED = {
    4:  "MTMS (JTAG mode) - strap pin, avoid for general I/O",
    5:  "MTDI (VDD_SPI voltage select) - strap pin, avoid for general I/O",
    9:  "BOOT button on DevKitM-1 - strap pin (NC or /IO/BOOT recovery only)",
    10: "NOT BONDED on ESP32-C6FH4 (internal SiP flash uses this pad)",
    11: "NOT BONDED on ESP32-C6FH4 (internal SiP flash uses this pad)",
    15: "Boot-mode select / JTAG signal source select - strap pin",
}

# Safe-non-strap spare GPIOs for future expansion.
GPIO_SPARE = [0, 1, 14, 18, 19, 20, 21, 22, 23]

# Assembly + post-fab procedures (assembler-facing SOP) ------------------
ASSEMBLY_INSTRUCTIONS = """\
High-level assembly order:
  1. Receive PCB (JLCPCB SMT-assembled with Basic + Extended Library parts).
  2. Hand-solder THT parts that JLCPCB cannot stock — Phoenix terminal J1,
     pin sockets J4..J8, radial bulk capacitors C1/C3/C4. See
     LOCALLY_SOURCED_PARTS below.
  3. Connect SEN66 module to PCB via JST GH 6-pin cable (~50 cm; ordered
     separately, Sensirion ships SEN66 without cable).
  4. Snap PCB into SZOMK AK-N-94 enclosure (PCB rests on cover screws / posts,
     M3 with 2 mm washers under each screw).
  5. Wire 24 V DC SELV to input terminal J1; mount the unit on a standard
     wall-recessed electrical box (60 mm screw pitch).
  6. Power on; flash via either DevKitM-1 USB-C port (see firmware/README.md).

Tools: soldering iron (THT), Phillips M3 screwdriver, USB-C cable for first flash.

Safety:
  - 24 V DC SELV only — never connect mains directly to J1.
  - TVS (D1 SMBJ24A) + PTC (F1 2920L075/60MR) on the input protect against
    transients and reverse polarity; do NOT bypass.
"""

CASE_VERIFICATION_CHECKLIST = """\
Verified at v0.40 against the physical AK-N-94 sample (SZOMK).

Mechanical envelope:
  - Front-side component height: 17 mm default, 22 mm allowed in the SEN66
    zone (per physical-sample measurement).
  - Back-side height: 5 mm max (with 2 mm washers under each M3 mounting screw
    lifting the PCB off the bosses).
  - PCB outline: Ø120 mm D-shape (arc R = 60 mm, flat chord 82.6545 mm at
    the bottom edge).
  - Mounting holes: 3 x M3 (Ø3.8 mm NPTH) on Ø110 mm pitch circle at
    +/-47.631, +27.500 and 0, -55.000 (PCB-local coords, +Y = down).
  - Central cable pass-through: Ø12 mm.

When the enclosure DXF / manufacturer documentation evolves, re-verify each
constant above against a fresh physical sample before locking the next
board revision.
"""

# Locally-sourced parts (NOT in lcsc_mapping.py; not JLCPCB-assemblable) ---
LOCALLY_SOURCED_PARTS = {
    "SZOMK AK-N-94 enclosure": {
        "qty_per_unit": 1,
        "source": "https://www.chinaenclosure.com",
        "notes": "Ø128 mm perforated white ABS, smoke-detector form factor.",
    },
    "Sensirion SEN66-SIN-T module": {
        "qty_per_unit": 1,
        "source": "Sensirion direct / Mouser / Digi-Key",
        "notes": (
            "Combo air-quality sensor (CO2, PM, VOC, NOx, T, RH). See "
            "EXTERNAL_MODULES['SEN66-SIN-T'] for material code + accessory note."
        ),
    },
    "Hi-Link HLK-LD2410B module": {
        "qty_per_unit": 1,
        "source": "AliExpress / HiLink direct / TME",
        "notes": (
            "mmWave presence radar. Specifically -B variant. See "
            "EXTERNAL_MODULES['HLK-LD2410B']."
        ),
    },
    "JST GH 6-pin cable (50 cm AWG26)": {
        "qty_per_unit": 1,
        "source": "Sensirion accessory or generic AWG26 JST GH",
        "notes": (
            "Connects SEN66 module to PCB J3 socket. Reference length 50 cm; "
            "actual run length inside AK-N-94 is <100 mm."
        ),
    },
    "24 V DC PSU": {
        "qty_per_unit": "1 shared across deployment",
        "source": "generic",
        "notes": "Bus power for multi-unit deployments.",
    },
}

# =============================================================================
# (geometry / footprints / schematic generators follow)
# =============================================================================

# -----------------------------------------------------------------------------
# Geometry (mm)
# -----------------------------------------------------------------------------
# Page setup: A4 = 297 x 210 mm. Origin (0,0) in KiCad page space is the
# top-left corner of the sheet, so we centre the PCB on the page. The
# aux_axis_origin and grid_origin are also set to the PCB centre so the
# user-facing coordinate display in pcbnew still reads (0, 0) at the
# geometric centre of the board.
PAGE_CENTRE_X = 148.5              # A4 width / 2
PAGE_CENTRE_Y = 105.0              # A4 height / 2

R_OUTLINE = 60.0                   # PCB outline radius
CHORD = 82.6545                    # flat chord length (from DXF line measurement)
HALF_CHORD = CHORD / 2.0
Y_CHORD = math.sqrt(R_OUTLINE**2 - HALF_CHORD**2)  # ≈ 43.5237 mm
# Pitch circle for mounting holes
R_PITCH = 55.0
# Three mounting holes: at angles 30°, 150°, 270° in DXF math coords.
# In KiCad screen coords (Y inverted relative to math) we just use the DXF
# delta-from-centroid values directly: +Y = visually down = bottom of board.
HOLE_OFFSET_X = R_PITCH * math.cos(math.radians(30.0))   # 47.631
HOLE_OFFSET_Y = R_PITCH * math.sin(math.radians(30.0))   # 27.500
HOLE_POSITIONS = [
    ( HOLE_OFFSET_X,  HOLE_OFFSET_Y),   # bottom-right of board (near chord)
    (-HOLE_OFFSET_X,  HOLE_OFFSET_Y),   # bottom-left of board (near chord)
    ( 0.0,           -R_PITCH),         # top of board (opposite chord)
]
EDGE_CUTS_WIDTH = 0.1
HOLE_DIAMETER = 3.8                # Ø3.8 mm per manufacturer DXF
# Mounting holes are NPTH (non-plated). The screws go into plastic bosses in
# the AK-N-94 enclosure — no metal chassis to bond to, so a copper pad here
# would just be floating copper.
COURTYARD_RADIUS = HOLE_DIAMETER * 0.75   # ~1.5× hole diameter

# -----------------------------------------------------------------------------
# PCB layout — soft functional grouping (NOT enforced geometrically)
# -----------------------------------------------------------------------------
# As a starting heuristic, the PCB roughly resembles a clock face with power
# on the upper-left, MCU on the upper-right and sensors filling the bottom
# half — 24 V enters through the central cable hole and power flows roughly
# clockwise. This is a hint to keep rails short, not a hard constraint:
# components may cross any imagined boundary if the layout needs it (the
# SEN66 in particular is large and may span what would otherwise be the
# "sensors" region). No separator lines or sector labels are drawn on the
# PCB — the hierarchical schematic sub-sheets (power / mcu / sensors / io)
# are a functional grouping, not a geographic mapping.

# Cable pass-through hole in the centre of the PCB.
# 24 V (and optional PE) wires enter the case from the rear (electrical box
# behind the unit) and pass through this hole to a terminal block mounted on
# the front side of the PCB. Keeping the entry inside the PCB outline
# physically shields the bare wires — they are inaccessible from outside the
# enclosure, even though 24 V DC is nominally SELV.
# Sized for 3× 1.5 mm² conductors (e.g. YDY 3×1.5, outer Ø ≈ 8-9 mm) with
# ample margin for strain-relief / grommet if desired.
CABLE_HOLE_DIAMETER = 12.0

# -----------------------------------------------------------------------------
# Connector cutouts in the enclosure wall along the flat chord
# -----------------------------------------------------------------------------
# The SZOMK AK-N-94 has 5 rectangular openings in the case wall along the
# flat chord. The manufacturer DXF is a bottom-of-enclosure view, so its X
# axis is mirror-flipped relative to the PCB's top-view coordinate frame.
# The C2 RJ45 / Ethernet opening X range below has been mirror-corrected
# about X=0: it now sits on the +X (right) side, X +1.1..+16.8 / 15.7 mm
# wide, hosting J9. Order along the chord, top-of-enclosure view left to
# right: single round hole | two round holes | USB-C | RJ45 Ethernet |
# square (microSD).
#
# Only openings that host a real OAS connector are emitted as keepout
# zones. The others stay physical in the enclosure, but the PCB ends below
# the case wall so an empty keepout would only sterilise routing space.
#
# Tuple: (name, x_min, x_max, y_min, y_max, allow_pads). PCB-local mm,
# +Y toward the chord. y_max = Y_CHORD means the opening runs past the
# chord and the keepout is clipped to the PCB edge. allow_pads=True drops
# `(pads not_allowed)` so a connector's solder pads may live inside the
# opening area (connector body + accessible pads sit in the case-wall
# opening).
CUTOUTS = [
    # name, x_min, x_max, y_min, y_max, allow_pads  (PCB-local mm, +Y = toward chord)
    # v0.50-rework: the C2 cutout (RJ45 / Ethernet wall opening) is
    # removed. It only ever hosted J9 (Qwiic), now relocated INTERNAL
    # (see J9_PCB_* above). An empty case-wall keepout only sterilises
    # routing space — and exported to Freerouting as a HARD keepout that
    # trapped the J1 reverse-polarity protection cluster's pads — so the
    # opening is dropped from CUTOUTS entirely.
    # USB-C opening — immediately LEFT (-X) of the (removed) RJ45 opening in the
    # top-of-enclosure view (chord order: round | two-round | USB-C | RJ45 |
    # square). Hosts SW1, the side-actuated tactile push-button. The X range
    # is an ESTIMATE — the AK-N-94 manufacturer DXF is third-party (Rule 6)
    # and not committed; VERIFY x_min / x_max (and the SW1_PCB_* constants)
    # against a physical AK-N-94 sample before locking a board revision.
    ("USBC", -13.000, -2.000, +27.198, +Y_CHORD, True),  # USB-C opening (~11 mm) — hosts SW1 push-button
]


# Page-centre formatters --------------------------------------------------
def fx(x: float) -> str:
    """Format X with PCB-centre-to-page-centre offset."""
    return fmt(x + PAGE_CENTRE_X)


def fy(y: float) -> str:
    """Format Y with PCB-centre-to-page-centre offset."""
    return fmt(y + PAGE_CENTRE_Y)


# -----------------------------------------------------------------------------
# SEN66 PCB placement (mechanical reference + zip-tie holes + J3 socket)
# -----------------------------------------------------------------------------
# v0.6: SEN66 mounts DIRECTLY ON THE PCB (face-up, body 21.3 mm above
# PCB, openings facing UP through the AK-N-94 perforated cover).
# Hard constraint #1 has a SEN66-zone exception (≥22 mm) for this. The
# PCB carries:
#   1. A no-pad mechanical-reference footprint (`SEN66_Mechanical_Reference`)
#      drawn on F.Fab / F.SilkS — marks where the SEN66 body sits and
#      delineates the openings + sealing-divider hint so neighbouring
#      components (LD2410, MIKROE-2462) stay clear.
#   2. Four NPTH zip-tie holes (Ø 3.0 mm) that pinch the SEN66 flat
#      against the PCB. Cut the zip-ties to remove or replace the module.
#   3. The PCB-side JST GH 6-pin socket (J3) that mates with the SEN66's
#      JST GH cable (50 cm reference cable per Sensirion, separate
#      accessory).
#
# Placement (PCB-local mm, origin = PCB centroid; +Y = down on screen =
# toward the chord):
#
#   SEN66 reference: anchor at (SEN66_ANCHOR_X, SEN66_ANCHOR_Y),
#   rotation SEN66_ROTATION. Long axis runs RADIALLY (6:00 direction)
#   so cable runs are short; connector edge points toward
#   PCB center (cable hole) so the JST GH cable has the shortest run.
#
# Rotation 90° in KiCad's convention maps footprint-local +X (long
# axis, connector edge direction) to PCB -Y (upward, toward 12:00 /
# PCB center) and footprint-local +Y (short axis) to PCB +X (rightward,
# toward 3:00). Anchor (0, 0) in footprint coords is the corner of the
# 55.2 × 25.6 mm body face; placing this anchor at PCB (cx, cy) puts
# the body in PCB X = cx..cx+25.6, Y = cy-55.2..cy.
SEN66_ANCHOR_X = 23.5   # v0.9: pushed near max-right. Body right edge X=49.1
                        # leaves ~0.8 mm to PCB outline at body top (Y=-33.2,
                        # PCB outline x_max=49.98). H1 courtyard cleared in Y
                        # since body bottom now sits above H1 zone.
SEN66_ANCHOR_Y = 22.0   # v0.9: lifted up 3 mm (was 25). Body bottom Y=22 clears
                        # H1 courtyard top (Y=24.65) by 2.65 mm so the body
                        # right edge is free to enter H1's X range without
                        # courtyard collision. Also opens 3 mm of room
                        # between SEN66 body bottom and J3 north edge.
SEN66_ROTATION = 90   # degrees; long axis radial, connector toward PCB center


def _sen66_local_to_pcb(lx: float, ly: float) -> tuple[float, float]:
    """Transform a footprint-local SEN66 coordinate to PCB-local mm.

    Applies rotation `SEN66_ROTATION` around the footprint anchor, then
    translates so the anchor lands at (SEN66_ANCHOR_X, SEN66_ANCHOR_Y).
    Used to compute the global PCB coordinates of the 4 zip-tie holes
    given their SEN66-local positions.
    """
    a = math.radians(SEN66_ROTATION)
    # Standard 2D rotation, but KiCad +Y is screen-down, so we apply the
    # same matrix as KiCad does internally for footprint rotation.
    cos_a, sin_a = math.cos(a), math.sin(a)
    rx =  cos_a * lx + sin_a * ly
    ry = -sin_a * lx + cos_a * ly
    return (SEN66_ANCHOR_X + rx, SEN66_ANCHOR_Y + ry)


# Zip-tie hole positions in SEN66-local mm (relative to the body corner
# at (0, 0)). v0.7: both pinch-points now inside the "safe corridor"
# X ∈ [19.22, 31.03] (between inlet-zone X≤18.22 and outlet X≥32.03), so
# a 2 mm zip-tie band centred at each X passes over the body without
# covering any inlet or outlet on the air-side face.
# X = 22 (~40% of 55.2) and X = 30 (~54% of 55.2). Previously the second
# pair was at X=50 which sits inside the outlet circle (X=32..53) and
# would have blocked ~8% of outlet area — fixed.
# Y = -3 and Y = body_y + 3 = 28.6 (3 mm clearance past each long edge).
SEN66_ZIPTIE_LOCAL = [
    ("ZT1", 22.0, -3.0),
    ("ZT2", 22.0, 28.6),
    ("ZT3", 30.0, -3.0),
    ("ZT4", 30.0, 28.6),
]

# J3 (JST GH 6-pin board-side socket — SM06B-GHS-TB, horizontal SMD).
# Placed below the SEN66 body shadow (PCB +Y direction past body bottom
# edge at Y=22). With v0.6 the SEN66 is PCB-mounted directly (no enclosure
# cover mount), so the JST GH cable run is purely on-PCB. The SEN66's
# JST GH connector is on its +X short edge at PCB Y=-33.2 (the body's
# NORTH edge after the SEN66's rotation 90°); the cable enters J3 from
# PCB -Y (north). With J3_ROTATION=0 (v0.15.8 fix), the J3 cable opening
# also faces PCB -Y so the cable enters straight without a U-turn.
# Verified clear of mounting hole H1 at (+47.6, +27.5) and clear of
# cutout C5 at (X 27.9..35.4, Y 36.5..42.5).
J3_X = 38.0   # Pre-routing rework 2: shifted +2 mm east (was 36.0). User
              #   asked for +5mm but H1's custom F.CrtYd radius 2.85 mm
              #   puts its west boundary at +44.78. J3 JST GH stock
              #   courtyard extends ~5-6 mm east of anchor. +3 mm
              #   (J3_X=39) still tripped DRC; +2 mm (J3_X=38) is the
              #   max safe shift before H1 courtyard collision.
              # on body mid-X = SEN66_ANCHOR_X + SEN66_BODY_Y/2 = 23.5 + 12.8
              # = 36.3 -> rounded to 36.
J3_Y = 27.0   # v0.9: sits 3 mm south (PCB +Y) of SEN66 body bottom (Y=22).
              # With J3_ROTATION=0 (v0.15.8), J3 body extends south of pads
              # (pads at PCB Y = J3_Y - 1.85 = 25.15), so the J3 body south
              # edge sits ~Y=29. Cable opening (pads side) faces NORTH
              # toward SEN66, eliminating the 180° U-turn.
J3_ROTATION = 0    # v0.15.8: flipped 180 -> 0 so the cable opening (pad-side,
                   # native "north" of footprint) faces PCB -Y (north, toward
                   # the SEN66 body). Eliminates the 180° U-turn the cable
                   # previously had to make when J3 opened south (away from
                   # SEN66). Per independent code review M1: SEN66 connector
                   # sits on body +X short edge at PCB Y=-33.2 (north side
                   # of body); cable now runs SOUTH from SEN66 → into J3
                   # opening (no U-turn).

# -----------------------------------------------------------------------------
# LD2410 PCB placement (mechanical reference + J4 pin header) — chunk #5b
# -----------------------------------------------------------------------------
# HLK-LD2410B mounts as a soldered daughterboard:
#   - LD2410's onboard 1.27 mm pin row passes through J4's 5 plated
#     through-holes on the OAS PCB.
#   - Pins are soldered from the OAS PCB bottom side; the solder joints
#     provide BOTH electrical and mechanical retention.
#   - LD2410 lies face-up ABOVE the OAS PCB (pin-header standoff ~3-5 mm),
#     antenna patches pointing AWAY from the OAS PCB (toward the AK-N-94
#     perforated cover); 24 GHz beam radiates straight through the ABS
#     cover into the room.
#   - Orientation (v0.11): VERTICAL — long axis along OAS Y. Connector
#     short edge faces SOUTH (PCB +Y, toward the chord; "piny u dołu");
#     antenna short edge faces NORTH (PCB -Y, toward 12:00). LD2410
#     ROTATION = 270° (mathematical CCW; visually maps local +X to
#     PCB +Y so the connector edge ends up at body bottom).
#   - Position (v0.15): body pushed against the LEFT wall — body
#     left edge at PCB X=-54.90, ~2 mm from PCB outline at the
#     bottom-left corner (Y=+19.05 → x_min=-56.90). Body right edge
#     at PCB X=-39.66 → 33.66 mm clear from cable hole +X edge.
#
# Dimensions: LD2410B body ~30-33 × 15-16 mm in datasheet (varies by
# revision). LD2410_BODY_W/H below are slightly enlarged + grid-aligned
# (multiples of 1.27 mm) for keep-out planning. The mechanical-reference
# footprint claims this rectangle so future PCB components (NT3H1101 NFC,
# Qwiic, decoupling caps) keep clear of the LD2410 shadow.
LD2410_BODY_W = 35.56            # mm, long axis (28 × 1.27). Matches the
                                  # HLK-LD2410B datasheet V1.04 §4.1
                                  # "Module size: 7mm × 35mm", with a small
                                  # margin (0.56 mm) for silkscreen breathing
                                  # room.
LD2410_BODY_H = 7.62             # mm, short axis (6 × 1.27). v0.15.8 fix:
                                  # corrected from 15.24 — datasheet V1.04
                                  # §4.1 specifies 7 mm; the older 15.24 mm
                                  # value matched the LD2410C (16 × 22 mm,
                                  # different variant) or a dev-kit carrier
                                  # board, NOT the bare HLK-LD2410B. Gives
                                  # silk breathing room over the 7 mm spec.
LD2410_BODY_Z = 7.0              # mm, approx height above PCB (pin-header
                                  # standoff + LD2410 PCB + onboard SMD).
                                  # Well within the 17 mm front-side limit.
LD2410_SILK_INSET = 0.2          # F.SilkS inset from F.Fab outline (top/
                                  # bottom/left).
LD2410_SILK_INSET_CONN = 1.8     # v0.15.9: inset on the connector-side short
                                  # edge needs to be large enough that the
                                  # two LD2410 long-edge silk lines stop
                                  # BEFORE entering the J4 silk frame zone.
                                  # J4's stock silk frame spans PCB Y =
                                  # +17.50..+20.21 (rotated 270° from lib
                                  # Y = -1.14..+6.22). LD2410 long edges end
                                  # at LD2410-local X = 35.56 - 1.8 = 33.76,
                                  # which maps to PCB Y = -16.51 + 33.76 =
                                  # +17.25 — leaving a ~0.25 mm gap before
                                  # the J4 silk frame starts at PCB Y=+17.50.
LD2410_EMIT_SILK_OUTLINE = True   # v0.15.9: F.SilkS U-shaped silk RESTORED.
                                  # Earlier (v0.15.8) the body silk was
                                  # dropped because a body-extent rect
                                  # collided with J4's stock silk frame.
                                  # Now we emit 3 fp_line elements instead of
                                  # a closed fp_rect: antenna short edge +
                                  # 2 long edges. The connector-side short
                                  # edge is omitted so the U opens toward
                                  # the J4 pin row (which has its own silk
                                  # frame from the stock footprint). Net
                                  # result: the LD2410 body silhouette is
                                  # visible on the assembled PCB silkscreen,
                                  # plus the board-level "HLK-LD2410B"
                                  # gr_text label that already reads
                                  # horizontally regardless of footprint
                                  # rotation.
LD2410_ANTENNA_X_END = 12.7      # mm — LD2410-local X end of antenna zone
                                  # (patches sit at LD2410-local X ≈ 0..12 mm,
                                  # at the short edge OPPOSITE the connector).
LD2410_CONNECTOR_X = 35.56       # mm — LD2410-local X of the pin row (the
                                  # +X short edge, the connector end).
LD2410_CONNECTOR_Y = LD2410_BODY_H / 2.0   # mm — LD2410-local Y center of
                                            # the 5-pin row (centred on the
                                            # short edge). v0.15.8: derived
                                            # from LD2410_BODY_H so the pin
                                            # row marker remains centred on
                                            # the short edge for any body_h.

# Placement on OAS PCB (v0.11 — vertical, left side, pins south).
# Anchored at the LD2410-local (0, 0) corner. With rotation 270°,
# LD2410-local +X maps to PCB +Y and LD2410-local +Y maps to PCB -X.
# So body extends in +Y and -X from the anchor.
#
# Body shadow on OAS PCB (v0.15.8, after LD2410_BODY_H 15.24 → 7.62 fix):
#   X range: anchor_x - LD2410_BODY_H .. anchor_x  =  -51.09 .. -43.47
#   Y range: anchor_y .. anchor_y + LD2410_BODY_W  =  -16.51 .. +19.05
# Body centre X = anchor_x - LD2410_BODY_H/2 = -47.28 — aligned with
# J4 pin 3 (middle of the 5-pin row) at PCB X=-47.28. The pin row
# stays at OAS PCB X = -44.74..-49.82 (J4_PCB_X=-44.74 unchanged).
#
# Clearance checks vs the rest of the PCB (post-shrink, with body_h=7.62):
#   - PCB outline at body bottom-left corner Y=+19.05: x_min=-56.90,
#     body left at -51.09 → 5.81 mm clear (more than v0.15's 2.0 mm).
#   - PCB outline at body top-left corner Y=-16.51:    x_min=-57.68,
#     body left at -51.09 → 6.59 mm clear.
#   - H2 mounting hole at (-47.6, +27.5) — H2 at X=-47.6 sits within
#     body X range [-51.09, -43.47] but Y separation 5.6 mm.
#     No overlap.
#   - Cutout zone C1 at (X -33.8..-21.8, Y 31.5..42.5) — body Y < +19.05
#     < 31.5; no Y overlap.
#   - Cable hole at PCB centre (Ø12 / radius 6) — body right edge
#     at X=-43.47 → 37.47 mm clear from the cable hole +X edge at X=-6.
LD2410_ANCHOR_X = -43.47         # v0.15.8: shifted +3.81 mm from -39.66
                                  # to recentre the (now smaller) body
                                  # shadow on the J4 pin row at PCB X=-47.28.
                                  # = -39.66 + (15.24 - 7.62)/2; body
                                  # centerline X = anchor - body_h/2 = -47.28.
                                  # Body X range -51.09..-43.47.
LD2410_ANCHOR_Y = -16.51         # mm — OAS PCB Y of LD2410-local (0, 0).
                                  # = -1.27 × 13 (on 1.27 mm grid).
LD2410_ROTATION = 270            # degrees; long axis along PCB Y. With
                                  # this rotation, LD2410-local +X → PCB +Y
                                  # (so the connector short edge at
                                  # LD2410-local X=W lands at PCB Y=+19.05),
                                  # and LD2410-local +Y → PCB -X.


def _ld2410_local_to_pcb(lx: float, ly: float) -> tuple[float, float]:
    """Transform a footprint-local LD2410 coordinate to PCB-local mm.

    Mirrors _sen66_local_to_pcb. With LD2410_ROTATION = 270 (v0.11+,
    vertical daughterboard mount), LD2410-local +X maps to PCB +Y and
    LD2410-local +Y maps to PCB -X; the resulting coordinate is then
    translated by the LD2410_ANCHOR_X / Y placement. The rotation matrix
    below stays generic in case orientation needs to change to fit other
    components.
    """
    a = math.radians(LD2410_ROTATION)
    cos_a, sin_a = math.cos(a), math.sin(a)
    rx =  cos_a * lx + sin_a * ly
    ry = -sin_a * lx + cos_a * ly
    return (LD2410_ANCHOR_X + rx, LD2410_ANCHOR_Y + ry)


# -----------------------------------------------------------------------------
# ESP32-C6 DevKitM-1-N4 + MIKROE-2462 NFC Tag 2 Click — PCB shadow reservations
# -----------------------------------------------------------------------------
# Both are daughterboards mounted on FEMALE pin sockets ("goldpiny żeńskie")
# on the OAS PCB. The boards sit ~3-7 mm above the PCB on the standoff of
# their pin headers, so SMD components on the OAS PCB CAN be placed under
# their shadow (within the standoff Z budget of ~3-5 mm).
#
# This chunk just RESERVES the shadow areas with mechanical-reference
# footprints (F.Fab body outline + F.SilkS marker + pin-row hints + labels).
# The actual electrical female pin sockets land in chunk #7 (PCB routing).
#
# Layout (v0.15.6):
#
#   ESP32-C6 DevKitM-1-N4    MIKROE-2462 (NFC Tag 2 Click)
#   body: 48.26 × 25.4 mm     body: 25.4 × 57.15 mm (size L)
#   anchor (-27.76, -24.70)   anchor (-12.76, +40.64) rot 180°
#   body X=-27.76..+20.50     body X=-38.16..-12.76
#   body Y=-50.10..-24.70     body Y=-16.51..+40.64
#   center X = -3.63          NFC center X = -25.46
#   horizontal at TOP-CENTER  vertical, flipped 180° (pins at PCB +Y)
#   antenna LEFT (-X)         pins on long edges (J7+J8 at PCB Y=+20.32..+38.10)
#   USB-C RIGHT (+X)          NFC antenna spiral at PCB Y=-16.51..+18.64 (top half)
#
# LD2410 + NFC share the same top edge at Y=-16.51 (left side group).
# C1 and C2 AUX cutouts removed in v0.15.6 to free bottom-left region
# for the NFC body (which is 57.15 mm long — size L mikroBUS).
# SEN66 (right side, anchor +23.5/+22.0) unchanged. See per-constant
# comments below for clearance breakdowns.

# Dimensions per Espressif official dimensions drawing
# https://dl.espressif.com/dl/schematics/esp32-c6-devkitm-1-dimensions.pdf
# Body 25.40 × 48.26 mm. Pin headers 2×1×15 P2.54 mm, row spacing 22.86 mm.
# Pin block is OFFSET along the long axis: pin 1 is 5.37 mm from the
# antenna short edge; the opposite (USB-C) short edge has 7.33 mm of
# board beyond pin 15. The two rows are symmetric about the long axis.
ESP32_BODY_W = 25.4
ESP32_BODY_L = 48.26
ESP32_BODY_Z = 8.6                # approx Z above OAS PCB (module + std-off)
ESP32_PIN_ROW_INSET = 1.27         # = (25.40 - 22.86) / 2
ESP32_PIN_PITCH = 2.54
ESP32_PIN_COUNT_PER_ROW = 15
ESP32_PIN_START_OFFSET = 5.37      # distance from antenna short edge
                                    # (LIB Y=0) to pin 1; per Espressif
                                    # dimensions drawing.

# Placement (v0.15): ESP32 HORIZONTAL, UPPER-LEFT. User instruction:
# "ESP mocno w dół i w lewo" — after NFC moved down to share LD2410's
# Y band (Y=-13.03..+15.57), ESP32 cannot move further "down" (toward
# +Y) without colliding with NFC in the X overlap range -33.21..-7.81.
# The achievable interpretation: ESP32 stays horizontal, shifts LEFT,
# and drops as far down as the NFC top edge allows. Body Y bottom edge
# anchor_y = -14.03 sits 1 mm above NFC top at Y=-13.03. Body X range
# -37.16..+11.10 leaves a 2.5 mm gap to LD2410's new right edge at
# X=-39.66 and 12.4 mm to SEN66's left edge at X=+23.5. Helper rotation
# 90° unchanged (body lies down 48.26 × 25.4).
ESP32_ANCHOR_X = -27.76            # v0.15.3: -2 mm LEFT of v0.15.2.
                                    # Body X range -27.76..+20.50, center
                                    # X = -3.63. Right edge clearance to
                                    # SEN66 (+23.5) grows to 3.00 mm
                                    # (was 1.00 in v0.15.2).
ESP32_ANCHOR_Y = -24.70            # v0.15.3: +2 mm DOWN from v0.15.2's
                                    # -26.70. Body Y range -50.10..-24.70.
                                    # Top edge 3.00 mm above H3 hole top
                                    # at Y=-53.1 (was 1.0 mm). Top-left
                                    # corner (-27.76, -50.10): distance
                                    # √(770.6+2510.0)=57.27 → 2.73 mm
                                    # clearance to PCB outline.
                                    # v0.18: REVERTED the v0.17 1.5 mm
                                    # north-shift (was -26.20) back to
                                    # the pre-v0.17 -24.70 value. J1
                                    # moved to the SOUTH side of the
                                    # cable hole in v0.18, so the
                                    # central north strip no longer
                                    # needs to make room for J1's
                                    # courtyard depth.
ESP32_ROTATION = 90                # KiCad rotation applied to helper output

# Dimensions per mikroBUS Standard Specifications v2.00 (June 2015), size L.
# https://download.mikroe.com/documents/standards/mikrobus/mikrobus-standard-specification-v200.pdf
# NFC Tag 2 Click is mikroBUS size L — 25.4 × 57.15 mm (v0.15.5 fix; the
# earlier "size S, 28.6 mm" assumption was wrong per the MikroE product
# datasheet). Pin headers 2×1×8 P2.54 mm, row spacing 22.86 mm. Pin block
# OFFSET 2.54 mm toward pin-1 short edge: pin 1 is 2.54 mm from the top
# short edge; the NFC PCB antenna spiral fills the long strip past pin 8
# (~36.83 mm of extra board length, the difference between size L and
# the 8-pin block).
MIKROE2462_BODY_W = 25.4
MIKROE2462_BODY_L = 57.15           # v0.15.5: CORRECTED to mikroBUS size L
                                     # per MikroE datasheet (was 28.6 size S,
                                     # WRONG). NFC PCB antenna spiral fills
                                     # the strip past pin 8 (~36.83 mm long).
                                     # Layout collision with chord / AUX zone
                                     # accepted for v0.15.5 — user wants to
                                     # see visual overlap before deciding
                                     # next layout move.
MIKROE2462_BODY_Z = 7.0
MIKROE2462_PIN_ROW_INSET = 1.27    # = (25.4 - 22.86) / 2
MIKROE2462_PIN_PITCH = 2.54
MIKROE2462_PIN_COUNT_PER_ROW = 8
MIKROE2462_PIN_START_OFFSET = 2.54  # pin 1 at 2.54 mm from pin-1 short edge

# Placement (v0.15): vertical, transverse axis (= horizontal centerline
# through the body) aligned with LD2410's transverse axis at PCB Y=+1.27.
# User instruction: "Oś poprzeczna NFC w tej samej osi co Oś czujnika
# obecności" — NFC and LD2410 share the same horizontal Y band.
# Body Y range -13.03..+15.57 (center Y=+1.27 matches LD2410 center Y).
# Body X range -33.21..-7.81 (unchanged from v0.14): 6.45 mm gap to
# LD2410's new right edge at X=-39.66, and 1.81 mm gap to cable hole
# left edge at X=-6 (Ø12 hole at origin).
#
# The 5.74 mm antenna spiral strip at the bottom of the MIKROE body
# is now at PCB Y=+9.83..+15.57 — well clear of the cable hole zone
# and aimed outward toward the AK-N-94 perforated cover.
MIKROE2462_ANCHOR_X = -14.76       # v0.15.7: rotated 180° around body
                                    # center. Anchor now at body BOTTOM-RIGHT
                                    # corner in PCB (was top-left in v0.15.6).
                                    # Pre-routing rework: shifted west -2 mm
                                    # so MOD2 east silk edge (X=-14.76) clears
                                    # the new LED-ring outer edge at R=14
                                    # (D17 outer body edge at PCB X=-14) by
                                    # 0.76 mm. New body PCB range:
                                    # X=-40.16..-14.76. C11 at (-42, +14)
                                    # west silk edge at -42.8 → 2.64 mm clear
                                    # of new MOD2 west silk at -40.16.
MIKROE2462_ANCHOR_Y = +40.64       # v0.15.7: bottom edge of body in PCB
                                    # (was top edge -16.51 in v0.15.6).
                                    # Body PCB range unchanged: Y=-16.51..+40.64.
                                    # 2.86 mm above PCB chord at +43.5.
MIKROE2462_ROTATION = 180           # v0.15.7: flipped 180° per user request
                                    # "nfc przerzuc w pionie. piny na dole".
                                    # Pin block now at PCB Y=+20.32..+38.10
                                    # (was -13.97..+3.81). NFC antenna spiral
                                    # now at PCB Y=-16.51..+18.64 — radiates
                                    # toward UPPER part of cover (was lower).


# -----------------------------------------------------------------------------
# J4 — stock KiCad PinHeader_1x05_P1.27mm_Vertical at the LD2410 connector
# short edge. With LD2410 in its vertical orientation (LD2410_ROTATION=270
# in the .kicad_pcb file, which puts the connector edge at PCB Y=+19.05),
# the 5 pads run along a HORIZONTAL line at Y=+19.05.
#
# Pad-end orientation (v0.43 fix — the pre-v0.43 state was WRONG end-for-end):
#   The LD2410 module's own 5-pin row, per HLK datasheet Figure 1, is
#   physically ordered VCC, GND, Rx, Tx, OUT (antenna-side end → connector
#   tip). LD2410 sits antenna-NORTH / connector-SOUTH (ROTATION=270), which
#   maps the module's OUT pin to the WEST end of the J4 row and VCC to the
#   EAST end (see _ld2410_local_to_pcb: larger LD2410-local Y → more
#   negative PCB X). J4 pad 1 carries the LD2410_OUT net, so pad 1 MUST
#   land at the WEST end of the row.
#
# Rotation convention (empirical, from rendered output): a stock footprint
# native pad at local (0, +5.08) ends up at PCB (anchor_x + 5.08, anchor_y)
# under rotation 90° and at (anchor_x - 5.08, anchor_y) under rotation 270°.
# rotation 90° therefore puts pad 1 at the anchor (WEST) and pad 5 at
# anchor_x + 5.08 (EAST) — the orientation we need.
#
# anchor_x = -49.82 → pad 1 (OUT) at PCB X=-49.82 (WEST), pad 5 (+5V) at
# X=-44.74 (EAST). Pin row spans X=-49.82..-44.74, centre X=-47.28 =
# LD2410 body long-axis centerline (LD2410_ANCHOR_X - LD2410_BODY_H/2). ✓
#
# WHY this was wrong before: the pre-v0.43 comment reasoned "we want pin 5
# WEST of pin 1 → rotation 270" — backwards. The v0.15.8 "fix" then papered
# over the symptom by reversing the SCHEMATIC net order instead of the
# footprint. v0.43 reverses the FOOTPRINT (rotation 270→90, anchor X) and
# leaves the schematic net mapping (pad 1 = OUT) untouched and correct.
J4_PCB_X = -49.82            # mm — v0.43: pad 1 (OUT) at the WEST end of
                              # the row, where the LD2410 module's OUT pin
                              # physically lands. Row spans -49.82..-44.74,
                              # centred X=-47.28 on the LD2410 body centerline.
J4_PCB_Y = +19.05            # mm — OAS PCB Y of the pin row (unchanged).
J4_PCB_ROTATION = 90         # degrees — v0.43: was 270 (end-for-end wrong);
                              # 90 puts pad 1 at the anchor (WEST end).

# -----------------------------------------------------------------------------
# J1 PCB placement (v0.18; supersedes v0.17) — 24 V Phoenix MSTBA terminal block
# -----------------------------------------------------------------------------
# v0.17 placed J1 in the NORTH-of-cable-hole zone (replacing AQI LED D20).
# v0.18 FLIPS J1 to the SOUTH-of-cable-hole zone (replacing AQI LED D14
# instead): the south side has more open space because ESP32 occupies the
# north corridor, while the south corridor between the cable hole and the
# chord-edge cutouts is largely empty (the chord cutouts C3/C4/C5 are
# narrow X strips that don't block the central Y=0..+25 region). D20 is
# restored; D14 is now the missing LED. The ESP32 north-shift made in
# v0.17 is reverted.
#
# The 24 V supply cable enters from the rear of the enclosure (electrical
# wall box behind the unit), passes through the central hole, bends ~90°
# on the front side, and enters the terminal-block clamp from its NORTH
# face (clamp opening now faces the cable hole from the south side).
#
# Footprint: Connector_Phoenix_MSTB :
#   PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal
# (matches the schematic's "Phoenix_MSTBA_2,5/3-G-5,08" library symbol).
# Stock footprint geometry (footprint-local):
#   - Pin 1 at (0, 0), pin 2 at (+5.08, 0), pin 3 at (+10.16, 0)
#   - F.Fab body: X = -3.54..+13.70, Y = -2.00..+10.00
#   - Courtyard:  X = -4.04..+14.21, Y = -2.50..+10.50
#   - Cable-entry face on the body's LIB +Y side (body bulk side,
#     with terminal-screw indicators at LIB Y = +8.61..+10.11 marking
#     each pin's cable insertion guide). The LIB -Y side (Y = -2.31..
#     -2.91) carries the small pin-1 indicator triangle but no cable
#     features — that's the PCB-edge / pin-solder side.
#
# Placement (v0.18, south flip): PCB anchor (pin 1 PCB position) is offset
# so pin 2 (middle pin) lands at PCB X = 0. Rotation 180° places the
# cable-entry face (LIB +Y, the side carrying the trapezoidal cable-
# insertion indicators per pin) on PCB -Y (NORTH, facing the cable hole),
# and the body's +Y bulk (terminal screws) extends NORTH from the pin
# row toward the cable hole. The pin solder side (LIB -Y, Y = -2..0)
# maps to PCB +Y (SOUTH), where it occupies 2 mm of the gap between the
# pin row and the chord cutouts.
#
# Clearance budget (rotation 180°, pin 2 centred at PCB X=0):
#   - Courtyard PCB Y range = [pin_y − 10.5, pin_y + 2.5] (13 mm depth)
#   - Courtyard PCB X range = [−9.13, +9.12]
#   - At pin_y = +22.4:
#       Courtyard Y = [+11.90, +24.90]
#       Nearest LED-courtyard south corner (D13/D15 at PCB Y = +11.67):
#         0.23 mm clearance to J1 courtyard north edge.
#       Cutout C3 north edge at PCB Y = +28.998: 4.10 mm clearance to
#         J1 courtyard south edge.
#       SEN66 body west edge at PCB X = +23.5: 14.38 mm X clearance to
#         J1 courtyard east edge at PCB X = +9.12.
#       J3 (SEN66 socket) courtyard west edge at PCB X = +30.02:
#         20.90 mm X clearance.
#
# Cable bend geometry: the cable enters the connector through the NORTH
# (cable-hole-facing) face at PCB Y = pin_y − 10.11 = +12.29 (F.SilkS
# edge) or pin_y − 10.5 = +11.90 (courtyard edge). The cable hole's
# SOUTH edge sits at PCB Y = +6 (Ø12 mm hole, radius 6). Effective
# horizontal travel for the cable bend: 12.29 − 6.00 = 6.29 mm. Each
# 1.5 mm² conductor enters its own screw clamp; the three conductors
# fan out from the hole exit, so each bends independently rather than
# as a bundle. A single 1.5 mm² insulated wire (OD ~3 mm) has a typical
# minimum bend radius of ~10 mm — slightly larger than the available
# travel, so the cable will bend somewhat aggressively at the hole
# exit. Acceptable for a low-flex installation (the cable is fixed at
# both ends and is not manipulated after assembly). Identical magnitude
# to the v0.17 north-side placement (mirror geometry).
J1_PCB_X = +5.08             # PCB X of pin 1. With rotation 180°, pin 2
                              # (middle) lands at PCB X = J1_PCB_X −
                              # 5.08 = 0. Pin row spans PCB X = +5.08
                              # (pin 1, +24V) .. −5.08 (pin 3, PE),
                              # centred on the PCB X axis and aligned
                              # with the LED slot at θ=90° now vacated
                              # (D13 at 8x45° ring; was D14 at 12x30° ring).
                              # Note: pin 1 (+24V) lands on PCB +X (east
                              # side); compare to v0.17 where pin 1 sat
                              # on -X (west). The user sees pins in
                              # left-to-right order PE, GND, +24V when
                              # looking at the south face (cable insert
                              # side).
J1_PCB_Y = +32.0             # PCB Y of pin row (footprint-local Y = 0).
                              # v0.45: 0.4 mm north (+32.4 -> +32.0). J1.1,
                              # the easternmost 24 V THT pad, sat only
                              # 2.98 mm diagonally from J9.1 (Qwiic SMD
                              # pad) — a JLCDFM "tht to smd" warning
                              # (>3.05 mm rule). +0.4 mm north lifts the
                              # gap to ~3.3 mm. J1 has 7.8 mm of open
                              # space north (nearest is LED D12), so the
                              # move is fully unconstrained.
                              # v0.41-followup-2 (2026-05-19): +5 mm south
                              # to widen the no-go rectangle between J1's
                              # mating face and the central cable hole, so
                              # the cable-terminal plug has more clearance.
                              # Y was +27.4 since the pre-routing rework.
                              # With rot 180, courtyard extends NORTH from
                              # pin row; body bulk (terminal screws)
                              # recedes from cable hole. J10 chord cutout
                              # C3 may intersect — accept temporarily.
                              # See clearance budget above for derivation.
                              # At pin_y = +22.4 with rot 180:
                              #   J1 courtyard Y = (+11.90, +24.90)
                              #   J1 F.SilkS south edge (incl. pin-1
                              #     indicator triangle at LIB Y = -2.91
                              #     → PCB Y = +25.31) vs C3 cutout
                              #     north edge at PCB Y = +28.998:
                              #     3.69 mm clearance.
                              #   J1 F.SilkS north edge at PCB Y = +12.29
                              #     vs D13/D15 south F.Fab corner at
                              #     PCB Y = +11.67: 0.62 mm clearance.
J1_PCB_ROTATION = 180        # Rotation 180° places the cable-entry face
                              # of the body (LIB +Y) on PCB -Y (north,
                              # facing the cable hole). Pin 1 (+24V) at
                              # PCB +X (east), pin 3 (PE) at PCB -X
                              # (west).

# -----------------------------------------------------------------------------
# J9 — Qwiic / Stemma QT JST SH 4-pin horizontal SMD socket (v0.19)
# -----------------------------------------------------------------------------
# J9 lives in the C2 case-wall opening — the RJ45 / Ethernet-jack cutout in
# the AK-N-94 wall (X +1.1..+16.8, 15.7 mm wide, clipped at the chord). The
# C2 X range was mirror-corrected about X=0 — the source DXF is a bottom-of-
# enclosure view, so J9 / C2 belong on the +X (right) side of the board.
#
# Stock JST_SH_SM04B-SRSS-TB footprint: a 1.0 mm-pitch signal pad row
# (3 mm total width) plus two MP mech-pin tabs anchoring the body; body
# courtyard ~7.8 mm wide. The connector mouth (cable-entry slot) is on the
# pad side and faces the chord (+Y) so the cable plugs in from outside the
# case. J9_PCB_Y and J9_PCB_ROTATION are unaffected by the X mirror.
#
# Placement (routing-rework relocation): J9 moved OFF the C2 chord-side
# wall cutout and INTERNAL, east of the J10 recovery header. An external
# Qwiic cable threaded through the AK-N-94 wall cutout conflicts with
# design Pillar #2 (aesthetic acceptability — no exposed wiring); the
# Qwiic / Stemma QT expansion port is realistically an INTERNAL header
# used only when a future daughterboard is added inside the enclosure, so
# the connector belongs internal. The former cutout position also left
# the J9 +3V3 / SDA / SCL trio unroutable (Freerouting could not escape
# the chord-edge corridor). New anchor (+17.0, -19.5): courtyard spans
# X +13.08..+20.92, Y -22.81..-16.19 — 1.6 mm clear of the "J10 flash"
# board-silk label, 2.3 mm to the SEN66 zone west edge, 1.36 mm to the
# J5 courtyard. Recovers the J9 +3V3/SDA/SCL trio for the autoroute.
J9_PCB_X = +17.0             # PCB X — internal, east of the J10 header
J9_PCB_Y = -19.5             # PCB Y — internal row, north of the J5 socket
J9_PCB_ROTATION = 0          # orientation unchanged from prior C5 placement

# -----------------------------------------------------------------------------
# SW1 — side-actuated tactile push-button (v0.42)
# -----------------------------------------------------------------------------
# C&K PTS645VK392LFS, right-angle THT SPST tactile. Footprint
# `Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx39-2LFS` (verbatim
# KiCad stock). SW1 lives at the chord edge in the AK-N-94 USB-C case-wall
# opening (CUTOUTS "USBC", immediately left of C2). Same chord-edge
# pattern as J9: the actuator faces PCB +Y (chord side) so the user
# presses it from outside the case.
#
# Rotation 180°: the footprint actuator / cap protrudes toward footprint
# LIB -Y, so rotation 180 maps LIB -Y -> PCB +Y (toward the chord). The
# two signal pads sit at LIB Y=0 -> PCB Y = SW1_PCB_Y; the cap F.Fab tip
# reaches PCB Y = SW1_PCB_Y + 3.85 (past the chord, into the wall opening).
# Body (rotation 180) spans PCB X ≈ -11.0..-3.5, courtyard X ≈ -12.05..-2.5
# — inside the CUTOUTS "USBC" X range. Signal pads at PCB Y=+41.0, pad
# outer edge +41.875, ~1.6 mm clear of the chord at Y≈+43.52.
#
# ESTIMATE — VERIFY against a physical AK-N-94 sample: the USB-C cutout
# position AND the actuator Z height vs the wall-opening slot (C&K PTS645
# datasheet). The board is DRC-clean regardless of these values; only the
# physical case alignment depends on them.
SW1_PCB_X = -5.0
SW1_PCB_Y = +41.0
SW1_PCB_ROTATION = 180

# -----------------------------------------------------------------------------
# J10 — Native-USB recovery header (v0.19) — DNP 6-pin 2.54 mm THT
# -----------------------------------------------------------------------------
# J10 sits in the C3 case-wall cutout (X +4.9..+13.9, Y +28.998..+43.5,
# 9 × 14.5 mm). Stock `PinHeader_1x06_P2.54mm_Vertical` footprint:
#   - Pad 1 (rectangle) at LIB (0, 0), pads 2..6 at LIB (0, +n*2.54)
#     for n in 1..5. Pad row total 12.7 mm long in LIB +Y direction.
#   - Body silk X = -1.38..+1.38, Y = +1.27..+14.08
#   - Body courtyard X = -1.77..+1.77, Y = -1.77..+14.47
#
# Desired layout: pin 1 (rect-pad marker, easy to identify by eye when
# using a pogopin jig) sits at the chord side. Cable / pogopin jig
# enters from outside the case at PCB +Y. So we want LIB +Y (pins 2..6
# pad row direction) to map to PCB -Y (away from chord, into PCB
# interior), meaning rotation 180°.
#
# With rotation 180° (LIB +Y → PCB -Y):
#   - Pad 1 at LIB (0, 0)        → PCB (anchor_x, anchor_y)
#   - Pad 2 at LIB (0, +2.54)    → PCB (anchor_x, anchor_y - 2.54)
#   - …
#   - Pad 6 at LIB (0, +12.7)    → PCB (anchor_x, anchor_y - 12.7)
#   - Body extents: PCB X = anchor_x - 1.38..anchor_x + 1.38;
#                   PCB Y = anchor_y - 14.08..anchor_y - 1.27
#   - Courtyard:   PCB X = anchor_x - 1.77..anchor_x + 1.77;
#                  PCB Y = anchor_y - 14.47..anchor_y + 1.77
#
# C3 cutout X = +4.9..+13.9, Y = +28.998..+43.5. Centre header on
# cutout midpoint X = +9.4. Pad 1 (south, closest to chord) at
# anchor_y = +41.5 → pad outer edge at PCB Y = +42.35 (pad radius 0.85,
# circle diameter 1.7 mm), 1.17 mm clear of the chord at +43.5 (passes
# min_copper_edge_clearance 0.3 mm). Pad 6 at PCB Y = +28.8 — slightly
# north of the cutout north edge (+28.998). That's intentional — pin 6
# (BOOT, the least frequently accessed in a recovery scenario) extends
# beyond the cutout into the PCB-side keepout-free region, where the
# silk label can describe what it is.
#
# Wait — actually we want ALL 6 pads ACCESSIBLE through the cutout.
# Re-anchor: pad 1 at anchor_y = +42.0, pad 6 at anchor_y - 12.7 = +29.3.
# Pad 6 inside cutout? +29.3 > +28.998 → YES, all pads inside cutout.
# Pad 1 outer edge at +42.85 → 0.65 mm clear of chord. OK.
J10_PCB_X = -10.96            # PCB X of pad 1 (west end). Pre-routing
                              # rework 3: switched to HORIZONTAL on the
                              # transverse axis 3.5 mm south of J5 row
                              # (Y=-25.97). Pad row spreads east at
                              # 2.54 mm pitch: pad 6 at PCB X = -10.96 +
                              # 5*2.54 = +1.74. Centred roughly on J5
                              # span (X ∈ [-22.39, +13.17], midpoint
                              # ≈ -4.61). J5 silk designator label sits
                              # at PCB X=-17.02 (J5 row anchor + 5.37),
                              # 4.79 mm west of J10 body silk west edge
                              # (anchor + (-1.27) = -12.23 at rotation 90)
                              # → no overlap.
J10_PCB_Y = -21.0            # PCB Y of pad row. 4.97 mm south of J5 row
                              # A (Y=-25.97). v0.43: nudged 1 mm NORTH
                              # (from -20.0) so the per-pin F.SilkS labels
                              # placed south of the row clear LED D17 of
                              # the AQI ring.
J10_PCB_ROTATION = 90        # LIB +Y → PCB +X (horizontal pad row east).
                              # Rotation 90 swaps the dict half-extent
                              # tuple (1.5, 7.6) → effective (7.6, 1.5);
                              # the Z-clearance check handles this via
                              # the rotation flag captured by
                              # _parse_footprint_placements.

# -----------------------------------------------------------------------------
# J2 — UART/Boot recovery header (DNP), 1x06 P2.54 mm
# -----------------------------------------------------------------------------
# v0.43: relocated from the cramped NW corner to the free pocket NORTH of
# the LD2410 presence sensor, and rotated HORIZONTAL (pad row along PCB +X,
# like J10). The cramped NW corner could not host printed F.SilkS per-pin
# labels; the LD2410-north pocket can. C2 and C3 were evicted from this
# pocket (see gen_power_pcb_footprints). With rotation 90 the 1x06 row runs
# +X from pin 1 (west) to pin 6 (east); the row is centred above the
# LD2410 body (X centre ≈ -47.3) and sits ~4.5 mm north of the LD2410 top
# edge (Y=-16.51). Per-pin signal labels go on F.SilkS just NORTH of the
# row (gen_silk_labels).
J2_PCB_X = -51.0             # PCB X of pad 1 (west end); row spans
                              # -51.0..-38.3 (6 pins, 2.54 mm pitch).
                              # Shifted east of dead-centre over the
                              # LD2410 so the pin-1 per-pin label clears
                              # the curving west board edge.
J2_PCB_Y = -21.0             # PCB Y of the pad row.
J2_PCB_ROTATION = 90         # LIB +Y → PCB +X (horizontal pad row east).

# -----------------------------------------------------------------------------
# Connector pin maps — single source of truth for per-pin silkscreen labels
# -----------------------------------------------------------------------------
# Each dict maps a 1-based pin number to the short label printed next to that
# pad on the PCB. The PCB silkscreen generator (gen_silk_labels) and the
# schematic generators consume the SAME dict, so a silk label can never drift
# from the netlist. Verified against the schematic sub-sheets:
#   J1     — _sch_power.py    (J1.1 VIN / J1.2 GND / J1.3 PE)
#   J2     — _sch_mcu.py      (UART/Boot recovery header)
#   J7/J8  — _sch_sensors.py  (MIKROE-2462 mikroBUS socket, rows A/B)
#   J9     — _sch_io.py       (standard Qwiic: GND / +3V3 / SDA / SCL)
#   J10    — _sch_io.py       (native-USB recovery header)
J1_PIN_MAP: dict[int, str] = {1: "24V", 2: "GND", 3: "PE"}
J2_PIN_MAP: dict[int, str] = {1: "+3V3", 2: "GND", 3: "TX", 4: "RX",
                              5: "EN", 6: "BOOT"}
J9_PIN_MAP: dict[int, str] = {1: "GND", 2: "+3V3", 3: "SDA", 4: "SCL"}
J10_PIN_MAP: dict[int, str] = {1: "GND", 2: "+3V3", 3: "USB-", 4: "USB+",
                               5: "EN", 6: "BOOT"}
# J7/J8 — MIKROE-2462 mikroBUS socket, full per-pin names (mikroBUS Standard
# Specifications v2.00, page 6). J7 = row A / mikroBUS pins 1..8 (left
# header), J8 = row B / mikroBUS pins 9..16 (right header). The socket
# carries the mikroBUS pin names regardless of which pins the NFC Tag 2
# Click actually uses (NFC uses only +3V3/GND on J7 and INT-FD/SCL/SDA/GND
# on J8 — see _sch_sensors.py chunk #5c).
J7_PIN_MAP: dict[int, str] = {1: "AN", 2: "RST", 3: "CS", 4: "SCK",
                              5: "MISO", 6: "MOSI", 7: "+3V3", 8: "GND"}
J8_PIN_MAP: dict[int, str] = {1: "PWM", 2: "INT", 3: "RX", 4: "TX",
                              5: "SCL", 6: "SDA", 7: "+5V", 8: "GND"}

# Module socket end-pin signal names — printed at the EXTREME pads of each
# daughterboard row so the module can be oriented during hand-assembly.
# Signal names (not bare pin numbers) are used: they tell the assembler at
# a glance which way round the module goes. Only the first + last pad of a
# row carry a label (see gen_silk_labels). Keyed by footprint pad number.
# Used for J4/J5/J6 only — J7/J8 carry FULL per-pin labels (J7/J8_PIN_MAP)
# in the gap between the two mikroBUS rows, not just end labels.
#   ESP32-C6-DevKitM-1 — verified vs _lib_symbols.ESP32C6_DEVKITM1_PINS:
#     J5 = module header J1 (pad 1 = 3V3 … pad 15 = GND)
#     J6 = module header J3 (pad 1 = GND … pad 15 = GND — both rails GND
#          at the J3 header ends; J5's 3V3/GND orients the module)
#   HLK-LD2410B — HiLink datasheet V1.04 Table 1 (see _sch_sensors.py):
#     J4 (pad 1 = OUT … pad 5 = VCC)
J4_END_SIGNALS: dict[int, str] = {1: "OUT", 5: "VCC"}
J5_END_SIGNALS: dict[int, str] = {1: "3V3", 15: "GND"}
J6_END_SIGNALS: dict[int, str] = {1: "GND", 15: "GND"}

# Polarity-sensitive designators — components whose orientation matters and
# which therefore MUST carry a polarity / pin-1 silkscreen mark. Consumed by
# pipeline/oas/21_check_polarity_silk.py, which fails the build if any of
# these footprints loses its F.SilkS polarity primitive.
#   D1/D2/D3 — diodes (TVS / Schottky / Zener): stock cathode bar
#   Q1       — AO3401A P-MOSFET (SOT-23): stock pin-1 mark
#   U1/U2    — buck ICs (TO-263-5 / SOT-583): stock pin-1 mark
#   C1/C4    — polarized radial electrolytics: stock "+" / pad-1 mark
#   D11..D18 — SK6812-SIDE LEDs (oas custom footprint): pin-1 dot
#              (D13 is skipped at the J1 cable slot — not placed).
POLARIZED_DESIGNATORS: frozenset[str] = frozenset({
    "D1", "D2", "D3", "Q1", "U1", "U2", "C1", "C4",
    "D11", "D12", "D14", "D15", "D16", "D17", "D18",
})

# -----------------------------------------------------------------------------
# AQI status LED ring — 8 x SK6812-SIDE side-emit addressable RGB (45 deg pitch)
# -----------------------------------------------------------------------------
# Eight side-emit RGB LEDs (one skipped at the J1 cable-area position
# leaves seven placed) on a Ø26 mm pitch circle around the central
# Ø12 mm cable hole. Each LED radiates LIGHT RADIALLY OUTWARD into the
# AK-N-94 perforated cover where it scatters and reads as a soft glowing
# halo (no per-perforation hot-spot dotting). Side-emit geometry chosen
# over top-emit after a research pass on the diffuse-ring options.
#
# LED chip: SK6812 SIDE-A (Shenzhen Normand / OPSCO Optoelectronics).
# Package 4.0 (L) × 1.6 (W) × 2.0 (H) mm. Pinout 1=DIN, 2=VDD, 3=DOUT,
# 4=GND (verified against Normand 2018 rev 01 + OPSCO 2021 rev A/1
# datasheets; land pattern from EasyEDA C5378721 — see SK6812SIDE_PADS).
# See EXTERNAL_MODULES['SK6812-SIDE'] entry above for the verified part spec.
#
# Geometry:
#   - 8 LEDs at θ = 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315° (KiCad-screen
#     +Y is down, so θ=0 is at PCB +X, θ=90 is at PCB +Y / SOUTH, etc.)
#   - LED center at (R·cos θ, R·sin θ) with R = LED_RING_RADIUS.
#   - Body local frame: +X = long axis (pad row); +Y = short axis pointing
#     toward the pad-row face (away from emission). The emission face is
#     at body-local -Y. To make each LED's emission face point radially
#     OUTWARD, we set its KiCad rotation R = (90 - θ) mod 360 so that
#     body-local (0, -1) maps to PCB (cos θ, sin θ).
#   - Daisy-chain order: D11 at θ=0, D12 at θ=45, … D18 at θ=315.
#     D18 DOUT terminates open (NeoPixel chains do not loop back).
#   - One 100 nF 0402 decoupling cap (C20…C27) per LED, placed adjacent
#     to the LED's VDD pad on the PCB-interior side of the ring.
#
# Why 45° pitch and not 30°: SMT assembly machines orient parts in
# standard multiples (0/45/90/135 deg); non-standard angles (30/60/etc.)
# can add per-part placement overhead at JLCPCB. Going from 12 LEDs
# at 30° to 8 LEDs at 45° trades 4 LEDs (negligible AQI-halo visual
# difference at this radius) for assembly simplicity. Audit-19
# (2026-05-19).
#
# LED_RING_RADIUS = 13.0 mm (pre-routing rework: bumped from 11.0 → 13.0
# to free up the cable-hole / centre routing channel). LED centres on
# a Ø26 mm pitch circle. Inner-most LED body edge at R = 12.2 mm (body
# half-extent 0.8 mm radially); 6.2 mm radial clearance to the Ø12 mm
# cable hole edge at R=6. Outer-most LED body edge at R = 13.8 mm.
# Chord distance between adjacent 45° LEDs: 2·R·sin(22.5°) = 9.95 mm,
# giving 2.98 mm gap per side of the 4 mm LED body (was 1.37 mm at 30°).
LED_RING_RADIUS = 13.0    # v0.41 2026-05-19 (rev 3): back to 13.0 base after
                            # user request. D12 (i=1, theta=45°) and D14 (i=3,
                            # theta=135°) get a per-index override to R=15 mm
                            # (see LED_RING_RADIUS_OVERRIDE below) — these two
                            # LEDs sit closest to the J1 24 V terminal block
                            # on the chord side; at R=13 their bodies would
                            # protrude into the J1 mating-plug clearance zone.
LED_RING_RADIUS_OVERRIDE = {
    0: 11.0,    # D11 — mirrored with D15 (also R=11). User wanted radial
                # symmetry on the east-west axis through the ring centre,
                # since D15 was forced to R=11 by MOD2 silk constraint and
                # we don't want the silk-labelled reference LED (D11) to look
                # bigger than its opposite-axis counterpart.
    1: 16.5,    # D12 — bumped 15 → 16.5 (v0.41-followup-2). At R=16.5 cap C21
                # mask west edge at PCB X=+8.745 leaves 0.21 mm clearance for
                # a silk-no-go vertical line at PCB X=+8.50. R upper bound is
                # set by D14 pin-1 dot vs MOD2 silk east edge (silk_overlap):
                # with stroke widths, pin1 dot circle (radius 0.19) west edge
                # must clear MOD2 silk east edge (X=+134.30 global) by 0.15.
                # Strict bound: R ≤ 16.48; chose 16.5 as the prior known-good
                # value (margin 0.32 mm at R=16.5).
    3: 16.5,    # D14 — bumped 15 → 16.5. Mirror of D12.
    4: 11.0,    # D15 — unchanged; pulled INWARD to clear MOD2 (MIKROE-2462)
                # silk east edge. After the LED rotation fix (emission outward
                # → pad row now on OUTWARD body face), D15 pads at R=13 land
                # 0.09 mm inside MOD2 silk shadow (silk east edge at PCB X=
                # -14.26, pad west edge at -14.35). R=11 pulls body inward
                # enough that pads are at PCB X~-11.85, 2.4 mm clear of
                # MOD2 silk.
}
LED_RING_COUNT = 8
LED_RING_THETA_START_DEG = 0.0       # first LED (D11) sits on PCB +X axis
LED_RING_THETA_STEP_DEG = 360.0 / LED_RING_COUNT   # = 45°

# J1 (24 V terminal block) sits on the SOUTH side of the cable hole
# with courtyard Y ∈ [+11.9, +24.9] mm — directly colliding with the
# LED slot at θ=90° (PCB (0, +13)). At 45° pitch that slot is index
# i=2, so we skip i=2 (was i=3 at 30° pitch). Skipped designator
# becomes D13 (and its decoupling cap C22). Daisy-chain wires the
# schematic generator emits already skip routing across this gap.
# Final ring: 7 LEDs (D11, D12, D14..D18) + 7 caps (C20, C21, C23..C27).
LED_RING_SKIP_INDICES = (2,)         # i=2 → D13 (and C22) at θ=90°

# Decoupling cap radial offset from LED centre: cap sits ~3.4 mm radially
# INWARD from the LED centre (so total radius = LED_RING_RADIUS - 3.4 =
# 7.6 mm). At inner cap edge (R = 7.6 - 0.5 = 7.1 mm), 1.1 mm clearance
# to the cable hole at R = 6. The cap's "north" pad lands directly under
# the LED's VDD pad row.
LED_RING_CAP_RADIAL_OFFSET = 3.4
# Per-LED override: a LARGER offset pulls the cap toward the ring centre
# (closer to the Ø12 cable hole); a SMALLER offset keeps it near the LED.
#
# i=1 (C21) / i=3 (C23): SMALLER offset 2.6 — D12/D14 sit closest to the
# J1 24 V terminal on the chord side; their caps must stay OUTSIDE the J1
# mating-plug no-go zone (silk rect PCB X ∈ [-8.73, +8.73]). With LED
# R=16.5 and offset 2.6, cap radius = 13.9 → cap PCB X = ±9.83, clear of
# the no-go silk + cap mask + DRC silk_clearance budget.
#
# i=0,4,5,6,7 (C20/C24/C25/C26/C27): v0.50 routing rework — LARGER offset
# so every one of these five caps lands at cap radius 7.0 mm (inner edge
# ~6.66 mm, ~0.66 mm clear of the Ø12 cable hole at R=6). Pulling them in
# toward the hole vacates the annulus just inside the LED ring, giving the
# SK6812 data-chain hops a clear lane — the autorouter could not close
# D14-DOUT / D16-DOUT in the v0.50 87/89 run. C20/C24 LED R=11 → offset
# 4.0; C25/C26/C27 LED R=13 → offset 6.0. C21/C23 stay out (J1 no-go).
LED_RING_CAP_RADIAL_OFFSET_OVERRIDE = {0: 4.0, 1: 2.6, 3: 2.6,
                                       4: 4.0, 5: 6.0, 6: 6.0, 7: 6.0}

# SK6812-SIDE package + pad geometry (body-local frame; +X = long-axis,
# +Y = short-axis pointing toward the pad-row face; emission face at -Y).
#
# Body + land pattern are taken from the LCSC/EasyEDA footprint of the
# exact ordered part C5378721 (OPSCO SK6812SIDE-A) -- the same data
# JLCPCB's DFM resolves "Pin without a pad" against -- cross-checked
# against the Normand SPC/SK6812 SIDE-A Rev.01 datasheet section 4.
#
# The package is 4.0 (L) x 1.6 (W, PCB plane) x 2.0 (H) mm. NOTE the
# datasheet marketing string "4.0x2.0x1.6mm" is L x H x W -- earlier
# boardgen revisions mis-read it as L x W x H, producing a 4.0x2.0 body
# and a SYMMETRIC 4 x 0.60 mm land. The real part terminals are
# ASYMMETRIC, so JLCPCB's part model did not land on that copper -> a
# DANGER "Pin without a pad" on the two outer pins in JLCPCB DFM.
SK6812SIDE_BODY_W = 4.0              # mm, long axis (pad row direction)
SK6812SIDE_BODY_H = 1.6             # mm, short axis (radial / emission-perp)
SK6812SIDE_BODY_Z = 2.0             # mm, height standing above PCB (<< 17 mm)
SK6812SIDE_PAD_HEIGHT = 1.2         # mm along short axis (Y) -- all 4 pads
SK6812SIDE_PAD_Y = 0.15             # mm, body-local +Y of pad-row centerline.
# This is the COPPER pad-row position, re-centred on where JLCPCB lands
# the part pins -- NOT the raw EasyEDA pad-vs-body offset (0.575 mm).
# JLCPCB places the part by its footprint ORIGIN; for C5378721 that
# origin (EasyEDA "head", y=3001.7715) sits on the pad row, ~0.56 mm off
# the body centre that our footprint anchors on. With the copper at the
# raw 0.575 mm the JLCPCB DFM "pin inner edge" check flagged every ring
# LED pin 0.2 mm past the pad inner edge. 0.15 mm re-centres the copper
# on the pins (~0.225 mm fillet all round). Emission face at body-local -Y.
# Per-pad land geometry -- (body-local center X, pad width) in mm; pad
# heights are uniform (SK6812SIDE_PAD_HEIGHT). Pad 1 = DIN (leftmost),
# 2 = VDD, 3 = DOUT, 4 = GND. Asymmetric: the outer pads are the widest,
# pad 3 (DOUT) the narrowest.
#
# Pads 2 / 3 are verbatim EasyEDA C5378721. Pads 1 / 4 (the L-shaped end
# terminals) are EasyEDA + 0.10 mm extension on the INNER edge only.
# Reason: EasyEDA's own C5378721 land draws pads 1/4 flush with the
# part's pin inner edge (pad inner edge == pin inner edge, 0 mm margin) —
# which trips JLCPCB DFM DANGER "pin right edge" / "pin left edge" (a pin
# edge level with the pad edge leaves no solder-fillet margin; only the
# 90/180/270-deg ring LEDs flag, but the condition is rotation-agnostic).
# Extending the inner edge 0.10 mm toward the body centre gives the pin a
# 0.10 mm margin (pads 2/3 already clear the check at 0.05 mm). Outer
# edges (X = +/-2.30) are unchanged, so the courtyard extent is
# unaffected; the pin-1 dot (derived from pad 1's inner edge) shifts
# 0.10 mm toward centre, away from the daughterboard silk.
SK6812SIDE_PADS: tuple[tuple[float, float], ...] = (
    (-1.750, 1.10),   # pad 1 = DIN  (EasyEDA 1.00 + 0.10 mm inner margin)
    (-0.450, 0.70),   # pad 2 = VDD
    (+0.575, 0.45),   # pad 3 = DOUT
    (+1.750, 1.10),   # pad 4 = GND  (EasyEDA 1.00 + 0.10 mm inner margin)
)
# Derived: body-local center X of each pad (pin-1 dot, silk labels).
SK6812SIDE_PAD_X_OFFSETS = tuple(x for x, _w in SK6812SIDE_PADS)

# Littelfuse 1812L-series PTC fuse — land pattern + body geometry.
#
# F1 (the 24 V input PTC) is the Littelfuse 1812L075/33DR (LCSC C151170,
# 33 V / 750 mA hold / 1.5 A trip). KiCad stock `Fuse:Fuse_1812_4532Metric`
# is a GENERIC IPC-7351 1812 chip-fuse land (pad pitch 4.275 mm, gap
# 3.15 mm) — it does NOT match this part's terminal geometry. The
# Littelfuse 1812L termination bands are wide, so the recommended land is
# tighter: pad pitch 3.707 mm, gap 2.30 mm. On the generic stock land the
# part's pin inner edge sat 0.43 mm past the copper -> JLCPCB DFM DANGER
# "pin inner edge". The numbers below are the verbatim EasyEDA F1812
# footprint of C151170 (1 EasyEDA unit = 0.254 mm) — the exact data
# JLCPCB's DFM resolves against. Consumed by oas:Fuse_1812L_4532Metric.
#
# (An earlier revision carried LCSC C262023 here, believed to be the
# Littelfuse part — it is actually TLC-MSMD050, a 15 V / 500 mA fuse,
# under-rated for the 24 V rail. Caught by the EasyEDA cross-check before
# any order was placed, per CLAUDE.md Lesson 5.)
FUSE1812L_BODY_W = 4.55      # mm, body long axis  (X) — EasyEDA gge999 span
FUSE1812L_BODY_H = 3.24      # mm, body short axis (Y) — EasyEDA gge999 span
FUSE1812L_BODY_Z = 1.10     # mm, max height above PCB (Littelfuse 1812L)
FUSE1812L_PAD_W = 1.4067    # mm, pad width  (X) — EasyEDA 5.5381 u
FUSE1812L_PAD_H = 3.4992    # mm, pad height (Y) — EasyEDA 13.7764 u
FUSE1812L_PAD_X = 1.8534    # mm, |body-local centre X| of each pad — 7.297 u


def _led_ring_position(index: int) -> tuple[float, float, float]:
    """Return (PCB_x, PCB_y, kicad_rotation_deg) for the i-th LED on the ring.

    i = 0 → D11 at θ = 0° (PCB +X axis), i = 1 → D12 at θ = 30°, etc.
    The rotation is set so the LED's emission face (body-local -Y) points
    radially OUTWARD from the PCB origin.
    """
    theta_deg = LED_RING_THETA_START_DEG + index * LED_RING_THETA_STEP_DEG
    theta_rad = math.radians(theta_deg)
    r = LED_RING_RADIUS_OVERRIDE.get(index, LED_RING_RADIUS)
    px = r * math.cos(theta_rad)
    py = r * math.sin(theta_rad)
    # KiCad rotation = (90 - θ) mod 360. KiCad uses CCW rotation for
    # positive angles. At θ=0 (D11 on +X axis), rot=90 maps body-local
    # emission (0, -1) CCW to PCB (+1, 0) = OUTWARD. At θ=180 (D15 on
    # -X axis), rot=270 maps (0, -1) CCW to (-1, 0) = OUTWARD. (v0.41
    # 2026-05-19: previous formula was (270 - θ) which produced INWARD
    # emission — verified visually on 3D render after SK6812-SIDE-A.step
    # was added.) Because (90 - θ) already differs from the old
    # (270 - θ) by 180°, the placement formula itself now carries the
    # JLCPCB tape-feeder compensation: the SK6812-SIDE entry in
    # JLCPCB_ROTATIONS_OAS (pipeline/jlcpcb/_rotations.py) is therefore
    # 0°. Adding a +180° there on top of (90 - θ) double-compensates
    # and lands every LED 180° off on JLCPCB DFM (emission inward,
    # pin-outer-edge danger). Keep that entry at 0°.
    # body-local emission face is at -Y; to point that face RADIALLY OUTWARD
    # from the ring center for an LED placed at angle theta_deg, we need
    # rotation = 90deg - theta_deg (mod 360). Earlier formula used
    # (270 - theta_deg) which pointed emission INWARD (180deg flipped).
    rot = int(round((90.0 - theta_deg) % 360.0))
    return (px, py, rot)


def _led_cap_position(index: int) -> tuple[float, float, float]:
    """Return (PCB_x, PCB_y, kicad_rotation_deg) for the i-th LED's
    decoupling cap (C20 + index).

    The cap sits radially INWARD from the LED, at radius
    LED_RING_RADIUS - LED_RING_CAP_RADIAL_OFFSET. The cap's KiCad
    rotation matches the LED's rotation so the cap body lies tangentially
    (consistent visual orientation around the ring).
    """
    theta_deg = LED_RING_THETA_START_DEG + index * LED_RING_THETA_STEP_DEG
    theta_rad = math.radians(theta_deg)
    led_r = LED_RING_RADIUS_OVERRIDE.get(index, LED_RING_RADIUS)
    cap_offset = LED_RING_CAP_RADIAL_OFFSET_OVERRIDE.get(
        index, LED_RING_CAP_RADIAL_OFFSET)
    cap_r = led_r - cap_offset
    px = cap_r * math.cos(theta_rad)
    py = cap_r * math.sin(theta_rad)
    # body-local emission face is at -Y; to point that face RADIALLY OUTWARD
    # from the ring center for an LED placed at angle theta_deg, we need
    # rotation = 90deg - theta_deg (mod 360). Earlier formula used
    # (270 - theta_deg) which pointed emission INWARD (180deg flipped).
    rot = int(round((90.0 - theta_deg) % 360.0))
    return (px, py, rot)


def _led_local_to_pcb(index: int, lx: float, ly: float) -> tuple[float, float]:
    """Transform a body-local SK6812-SIDE coordinate to PCB-local mm for
    the i-th LED on the ring. Mirrors `_sen66_local_to_pcb` / `_ld2410_local_to_pcb`.
    """
    px, py, rot = _led_ring_position(index)
    a = math.radians(rot)
    cos_a, sin_a = math.cos(a), math.sin(a)
    rx =  cos_a * lx + sin_a * ly
    ry = -sin_a * lx + cos_a * ly
    return (px + rx, py + ry)
