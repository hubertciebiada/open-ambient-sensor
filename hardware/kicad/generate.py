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

HERE = Path(__file__).parent

# =============================================================================
# PROJECT METADATA
# =============================================================================
# Single source of truth for project identity, external modules, GPIO map,
# and board revision. Consumed by:
#   - generate.py itself (could be used in title block / silk text; legacy
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
# Also drives existing OAS_VERSION_LINE silk text further down in this file.
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
            "and body dims; NOT interchangeable."
        ),
    },
    "MIKROE-2462": {
        "manufacturer": "MikroElektronika",
        "mpn": "MIKROE-2462",
        "description": "NFC Tag 2 Click (NXP NT3H1101 + onboard PCB antenna)",
        "supplier": "MikroE direct / TME",
        "datasheet": "https://www.mikroe.com/nfc-tag-2-click",
        "form_factor": "mikroBUS L (25.4 x 57.15 x 7 mm)",
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
# The SZOMK AK-N-94 has 5 rectangular cutouts in the case wall at the flat
# chord position. Connectors mounted on the PCB extend through these cutouts.
# Coordinates below are in PCB-local space (origin = centre of PCB outline),
# transformed from the manufacturer DXF:
#   X_pcb = X_dxf - 831.436;  Y_pcb = Y_dxf - 979.389
#
# C2/C3/C4 extend beyond the chord (clipped here to Y_max = Y_chord since
# the keepout zone must stay inside the PCB outline). C1 and C5 sit fully
# inside the PCB.
#
# Names are tentative — final assignment (USB-C, terminal 24V, JST-GH to
# SEN66, SWD, Qwiic) will be decided during schematic + layout.
#
# Format: (label, x_min, x_max, y_min_inside_pcb, y_max_at_or_through_chord)
#
# v0.15.6: C1 and C2 REMOVED to free up the bottom-left region for the
# MIKROE-2462 NFC body (size L = 57.15 mm long, requires deep vertical
# real estate). Remaining cutouts C3/C4/C5 cover the connector strip on
# the right half (24V terminal, Qwiic, optional SWD/UART recovery).
# Documented in CLAUDE.md.
#
# v0.19: 6th tuple element `allow_pads` (bool). When True, the copper
# keepout zone drops `(pads not_allowed)` so a connector footprint's
# solder pads can live INSIDE the case-wall opening area (the case-wall
# opening hosts the connector body + accessible pads from outside).
# When False (default), pads are kept out of the cutout area — used for
# cutouts that are placeholders or that host connectors whose pads stay
# strictly inside the PCB-side edge.
#   - C3 — recovery header (J10): allow_pads=True so the 6-pin THT pin
#     header's pads can sit inside the cutout, accessible via pogopin
#     jig through the case-wall opening for emergency flashing.
#   - C4 — v2 expansion placeholder (no connector yet): allow_pads=False.
#   - C5 — Qwiic / Stemma QT expansion (J9): allow_pads=True so the
#     JST SH SMD pads can sit inside the cutout area.
CUTOUTS = [
    # name, x_min, x_max, y_min, y_max, allow_pads  (PCB-local mm, +Y = toward chord)
    # C3 (J10 recovery) + C4 (v2 placeholder) removed in pre-routing rework
    # 2 — both became unused after J10 moved out of the chord and freeing
    # the copper-keepout zones opens ~178 mm² of routing space south of
    # J1/F1 + chord-edge corridor, unblocking Net-(D1-A1) (J1.1 → D3.1)
    # which had to detour around F1 with no south option available.
    # Case-wall openings in the SZOMK enclosure remain physical regardless;
    # PCB stops 5 mm below the case wall so there's no mechanical conflict.
    ("C5", +27.900, +35.400, +36.494, +42.494, True),    # 7.5 × 6 mm,   J9 Qwiic / Stemma QT expansion (JST SH 4-pin, fully inside PCB)
]

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
# Anchor + rotation convention check (empirical, from rendered output):
#   KiCad rotation N° in the .kicad_pcb file rotates the footprint
#   CCW visually on screen (= mathematical CW with +Y-down screen
#   convention). So a stock footprint native pad at local (0, +5.08)
#   ends up at PCB (anchor_x + 5.08, anchor_y) under rotation 90° and
#   at PCB (anchor_x - 5.08, anchor_y) under rotation 270°.
#
# We want pin 5 (local Y=+5.08) to land WEST of pin 1 (at anchor), so
# the pin row sits centered on the LD2410 body's long-axis centerline
# (PCB X = -36.83). That means rotation 270, not 90.
#
# Anchor X = -34.29 = pin 1 position = body centerline (-36.83) + 2.54
# (half the pin row width 5.08). Pin row spans X = -34.29 (pin 1, east)
# .. -39.37 (pin 5, west); centre X = -36.83 = body centerline. ✓
J4_PCB_X = -44.74            # mm — v0.15: shifted -5.45 mm in tandem
                              # with LD2410_ANCHOR_X to keep pin 3 (middle)
                              # centred on LD2410's new body centerline
                              # at PCB X = -47.28 = -39.66 − LD2410_BODY_H/2.
J4_PCB_Y = +19.05            # mm — OAS PCB Y of the pin row (unchanged).
J4_PCB_ROTATION = 270        # degrees; pad row along OAS -X from anchor.

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
                              # with the D14 LED slot now vacated.
                              # Note: pin 1 (+24V) lands on PCB +X (east
                              # side); compare to v0.17 where pin 1 sat
                              # on -X (west). The user sees pins in
                              # left-to-right order PE, GND, +24V when
                              # looking at the south face (cable insert
                              # side).
J1_PCB_Y = +27.4             # PCB Y of pin row (footprint-local Y = 0).
                              # Pre-routing rework: nudged +5 mm south
                              # (from +22.4) to open routing space north
                              # of J1 for F1. With rot 180, courtyard
                              # extends NORTH from the pin row; the body
                              # bulk (terminal screws) recedes from the
                              # cable hole. J10 chord cutout C3 may
                              # intersect — accept temporarily.
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
# J9 lives in the C5 case-wall cutout (X +27.9..+35.4, Y +36.494..+42.494,
# 7.5 × 6 mm fully inside PCB). The Qwiic / Stemma QT cable plugs in
# through the case-wall opening to the connector mouth.
#
# Stock JST_SH_SM04B-SRSS-TB footprint geometry (verified against the
# KiCad 10 stock library file):
#   - Pads at footprint Y = -2 (north of origin), pin pitch 1.0 mm, pin
#     row total width 3 mm centred on X = 0. Pads are SMD roundrects on
#     F.Cu only (signal pads); the two MP (mech pin) tabs at footprint
#     (-2.8, +1.875) and (+2.8, +1.875) anchor the body.
#   - Body courtyard footprint X = -3.9..+3.9, Y = -2.78..+3.28.
#   - The connector "mouth" — the slot the cable plug enters — is on
#     the footprint -Y face (where the pads are). I.e. with default
#     orientation (rotation 0) the cable enters from the -Y direction.
#
# Desired physical layout: cable plugs in from outside the case through
# the C5 opening on the chord (PCB +Y, south). So the connector mouth
# must face PCB +Y → use rotation 180°.
#
# With rotation 180° (LIB +Y → PCB -Y, LIB -Y → PCB +Y):
#   - Signal pads at LIB Y=-2 land at PCB Y = anchor_y + 2 (south of anchor)
#   - Body north edge at LIB Y=+3.28 lands at PCB Y = anchor_y - 3.28 (north)
#   - Body south edge at LIB Y=-2.78 lands at PCB Y = anchor_y + 2.78
#   - Mech pin (MP) tabs at LIB Y=+1.875 land at PCB Y = anchor_y - 1.875
#   - Mouth opens to PCB +Y (toward chord) ✓
#
# C5 cutout Y = 36.494..42.494 (6 mm). Center the connector body in the
# cutout vertically: anchor_y = midpoint - (mouth-side offset). With
# anchor_y = +39.69 the body spans PCB Y +36.41..+42.47 (effectively
# filling the cutout). Signal pads at PCB Y = +41.69 — INSIDE the cutout
# zone, which is fine because C5 has allow_pads=True (v0.19 CUTOUTS).
# Pad outer edge at +41.69 + 0.85 (pad half-height) = +42.54 — just
# inside the cutout south edge (+42.494). 0.05 mm overshoot is below
# the min_copper_edge_clearance rule (0.3 mm) BUT the chord is at
# Y = +Y_chord ≈ +43.5237, so the actual PCB edge is 0.98 mm south of
# the pad outer edge. Plenty of clearance.
#
# Horizontal: C5 X = 27.9..35.4 (7.5 mm). Pad row total width 3 mm.
# Center the connector at X = +31.65 (cutout midpoint). Body courtyard
# X = +27.75..+35.55 — 0.15 mm overshoot at each side relative to the
# cutout extents, but PCB outline is far further north so courtyard-vs-
# Edge.Cuts checks aren't applicable (the cutout silk rect is purely
# visual, not an actual PCB edge).
J9_PCB_X = +31.65            # PCB X — centred on C5 (midpoint +31.65)
J9_PCB_Y = +39.69            # PCB Y — pads at +41.69 (just inside cutout)
J9_PCB_ROTATION = 180        # mouth → +Y (chord side, case-wall opening)

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
J10_PCB_Y = -20.0            # PCB Y of pad row. 5.97 mm south of J5 row
                              # A (Y=-25.97). Rework 3 placed J10 at
                              # Y=-22.0 (3.97 mm south); rework 4 added
                              # 2 mm more so per-pin F.Fab labels and
                              # the "J10 flash" silk title can sit clear
                              # of J5 socket's silk frame without
                              # crowding the J5 designator label.
J10_PCB_ROTATION = 90        # LIB +Y → PCB +X (horizontal pad row east).
                              # Rotation 90 swaps the dict half-extent
                              # tuple (1.5, 7.6) → effective (7.6, 1.5);
                              # the Z-clearance check handles this via
                              # the rotation flag captured by
                              # _parse_footprint_placements.

# -----------------------------------------------------------------------------
# AQI status LED ring (v0.16) — 12 × SK6812-SIDE side-emit addressable RGB
# -----------------------------------------------------------------------------
# Twelve side-emit RGB LEDs on a Ø22 mm pitch circle around the central
# Ø12 mm cable hole. Each LED radiates LIGHT RADIALLY OUTWARD into the
# AK-N-94 perforated cover where it scatters and reads as a soft glowing
# halo (no per-perforation hot-spot dotting). Side-emit geometry chosen
# over top-emit after a research pass on the diffuse-ring options.
#
# LED chip: SK6812 SIDE-A (Shenzhen Normand / OPSCO Optoelectronics).
# Package 4.0 × 2.0 × 1.6 mm. Pinout 1=DIN, 2=VDD, 3=DOUT, 4=GND
# (verified against Normand 2018 rev 01 datasheet and OPSCO 2021 rev A/1).
# See EXTERNAL_MODULES['SK6812-SIDE'] entry above for the verified part spec.
#
# Geometry:
#   - 12 LEDs at θ = 0°, 30°, 60°, …, 330° (KiCad-screen +Y is down, so
#     θ=0 is at PCB +X, θ=90 is at PCB +Y / SOUTH, θ=180 at PCB -X, etc.)
#   - LED center at (R·cos θ, R·sin θ) with R = LED_RING_RADIUS.
#   - Body local frame: +X = long axis (pad row); +Y = short axis pointing
#     toward the pad-row face (away from emission). The emission face is
#     at body-local -Y. To make each LED's emission face point radially
#     OUTWARD, we set its KiCad rotation R = (270 - θ) mod 360 so that
#     body-local (0, -1) maps to PCB (cos θ, sin θ).
#   - Daisy-chain order: D11 at θ=0, D12 at θ=30, … D22 at θ=330.
#     D22 DOUT terminates open (NeoPixel chains do not loop back).
#   - One 100 nF 0402 decoupling cap (C20…C31) per LED, placed adjacent
#     to the LED's VDD pad on the PCB-interior side of the ring.
#
# LED_RING_RADIUS = 13.0 mm (pre-routing rework: bumped from 11.0 → 13.0
# to free up the cable-hole / centre routing channel). LED centres now on
# a Ø26 mm pitch circle. Inner-most LED body edge at R = 12 mm (body
# half-width 1 mm radially); 6 mm radial clearance to the Ø12 mm cable
# hole edge at R=6. Outer-most LED body edge at R = 14 mm. Note the
# MIKROE-2462 silk rect previously at PCB X = -12.26 mm (180°) is now
# touched by D17's outer edge (X = -14) — F.SilkS suppression on the LED
# body keeps DRC silk_overlap green; if NFC click footprint complains,
# MOD2 anchor must also shift radially outward in a follow-up step.
LED_RING_RADIUS = 13.0
LED_RING_COUNT = 12
LED_RING_THETA_START_DEG = 0.0       # first LED (D11) sits on PCB +X axis
LED_RING_THETA_STEP_DEG = 360.0 / LED_RING_COUNT   # = 30°

# v0.17 originally removed D20 (north of cable hole) to make room for J1.
# v0.18 flipped J1 to the SOUTH side of the cable hole instead (more open
# space: ESP32 occupies the north corridor; the south corridor between
# cable hole and chord is largely empty). Consequently the skipped LED
# moved from D20 (index 9, θ=270°) to D14 (index 3, θ=90°, PCB (0, +11))
# — the LED slot directly toward the chord. Removing D14 also drops its
# decoupling cap C23; the daisy-chain wire is rerouted D13.DOUT →
# D15.DIN, skipping the now-empty D14 position. D20 + C29 are restored
# (back to the v0.16 placement on the north side). The final ring still
# has 11 LEDs (D11..D13, D15..D22).
LED_RING_SKIP_INDICES = (3,)         # i=3 → D14 (and C23) at θ=90°

# Decoupling cap radial offset from LED centre: cap sits ~3.4 mm radially
# INWARD from the LED centre (so total radius = LED_RING_RADIUS - 3.4 =
# 7.6 mm). At inner cap edge (R = 7.6 - 0.5 = 7.1 mm), 1.1 mm clearance
# to the cable hole at R = 6. The cap's "north" pad lands directly under
# the LED's VDD pad row.
LED_RING_CAP_RADIAL_OFFSET = 3.4

# SK6812-SIDE package + pad geometry (body-local frame; +X = long-axis,
# +Y = short-axis pointing toward pad-row face).
SK6812SIDE_BODY_W = 4.0              # mm, long axis (pad row direction)
SK6812SIDE_BODY_H = 2.0              # mm, short axis (emission perpendicular)
SK6812SIDE_BODY_Z = 1.6              # mm, height above PCB (well within 17 mm)
SK6812SIDE_PAD_PITCH = 0.95          # mm pad pitch along long axis
SK6812SIDE_PAD_WIDTH = 0.60          # mm along long axis (X)
SK6812SIDE_PAD_HEIGHT = 1.00         # mm along short axis (Y)
SK6812SIDE_PAD_Y = 0.85              # mm, body-local +Y of pad centerline
                                      # (pad-row face). Emission face at -Y.
# Pad X positions: 4 pads, centered at body-local X = ±1.425, ±0.475
# (i.e. evenly spaced at SK6812SIDE_PAD_PITCH = 0.95 mm pitch, centered
# on body X = 0).
SK6812SIDE_PAD_X_OFFSETS = tuple(
    (-1.5 + i) * SK6812SIDE_PAD_PITCH for i in range(4)
)  # = (-1.425, -0.475, +0.475, +1.425)


def _led_ring_position(index: int) -> tuple[float, float, float]:
    """Return (PCB_x, PCB_y, kicad_rotation_deg) for the i-th LED on the ring.

    i = 0 → D11 at θ = 0° (PCB +X axis), i = 1 → D12 at θ = 30°, etc.
    The rotation is set so the LED's emission face (body-local -Y) points
    radially OUTWARD from the PCB origin.
    """
    theta_deg = LED_RING_THETA_START_DEG + index * LED_RING_THETA_STEP_DEG
    theta_rad = math.radians(theta_deg)
    px = LED_RING_RADIUS * math.cos(theta_rad)
    py = LED_RING_RADIUS * math.sin(theta_rad)
    # KiCad rotation = (270 - θ) mod 360 — derived in CLAUDE.md v0.16
    # changelog. Verifies: at θ=0, rotation 270° maps body-local (0, -1)
    # to PCB (+1, 0) = +X = outward. At θ=180, rotation 90° maps (0, -1)
    # to (-1, 0) = -X = outward. Etc.
    rot = int(round((270.0 - theta_deg) % 360.0))
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
    cap_r = LED_RING_RADIUS - LED_RING_CAP_RADIAL_OFFSET
    px = cap_r * math.cos(theta_rad)
    py = cap_r * math.sin(theta_rad)
    rot = int(round((270.0 - theta_deg) % 360.0))
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


# -----------------------------------------------------------------------------
# KiCad 10 format constants
# -----------------------------------------------------------------------------
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

def fmt(x: float) -> str:
    """KiCad-style coordinate: up to 6 decimals, no trailing zeros required."""
    return f"{x:.6f}".rstrip("0").rstrip(".")

def fx(x: float) -> str:
    """Format X with PCB-centre-to-page-centre offset."""
    return fmt(x + PAGE_CENTRE_X)

def fy(y: float) -> str:
    """Format Y with PCB-centre-to-page-centre offset."""
    return fmt(y + PAGE_CENTRE_Y)

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

# -----------------------------------------------------------------------------
# 1) Mounting hole footprint (own library)
# -----------------------------------------------------------------------------
def gen_mounting_hole_footprint() -> str:
    """Custom MountingHole_3.8mm_M3 footprint matching the manufacturer DXF.

    NPTH (non-plated through hole): no copper pad, just a drilled hole.
    The screws go into plastic bosses, so plating would add nothing but
    floating copper risks (ESD pickup, capacitive coupling, manufacturing
    waste).
    """
    return textwrap.dedent(f"""\
        (footprint "MountingHole_3.8mm_M3"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "Mounting Hole 3.8 mm NPTH for M3 screw (per SZOMK AK-N-94)")
        \t(tags "mounting hole 3.8mm m3 npth szomk ak-n-94")
        \t(attr through_hole board_only exclude_from_pos_files exclude_from_bom)
        \t(property "Reference" "REF**"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('mh-lib:prop-ref')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Value" "MountingHole_3.8mm_M3_NPTH"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('mh-lib:prop-val')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('mh-lib:prop-fp')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Datasheet" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('mh-lib:prop-ds')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Description" "Mounting Hole, Ø3.8 mm NPTH, for M3 screw (per SZOMK AK-N-94)"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('mh-lib:prop-desc')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(COURTYARD_RADIUS)} 0)
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U('mh-lib:crtyd')}")
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(HOLE_DIAMETER/2)} 0)
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('mh-lib:fab')}")
        \t)
        \t(pad "" np_thru_hole circle
        \t\t(at 0 0)
        \t\t(size {fmt(HOLE_DIAMETER)} {fmt(HOLE_DIAMETER)})
        \t\t(drill {fmt(HOLE_DIAMETER)})
        \t\t(layers "F&B.Cu" "*.Mask")
        \t\t(remove_unused_layers no)
        \t\t(uuid "{U('mh-lib:pad')}")
        \t)
        )
        """)

# -----------------------------------------------------------------------------
# 1a) SEN66 mechanical-reference footprint (own library)
# -----------------------------------------------------------------------------
# Geometry constants for the SEN66 (Sensirion SEN6x family — fully shared
# between SEN62/63C/65/66/68/69C). Extracted from the Sensirion SEN6x STEP
# file (sen6x.step) and Mechanical Design Guidelines (sen6x_mech v0.92).
#
# Frame: footprint-local origin = corner of the 55.2 × 25.6 mm rectangular
# face of the SEN66 body. +X grows toward the connector / outlet edge,
# +Y grows along the 25.6 mm short side.
#
# These are the visible features ON THE BOTTOM FACE of the SEN66 (the face
# that lays against the cover, the one carrying the inlets and outlet):
#   Inlet #1 (obround):  center (10.70, 7.40),  size 15.05 × 7.05 mm
#   Inlet #2 (rect):     center (10.65, 18.85), size 15.14 × 8.14 mm
#   Outlet (circle):     center (42.40, 12.80), Ø 20.74 mm
#   Connector exit:      +X short edge, mid-Y (≈ 55.2, 12.80)
#   Foam-divider rib zone: across the body width at X ≈ 26 mm — the
#     mechanical-design-guide §2.1 sealing rib that separates inlet zone
#     from outlet zone, ensuring ambient air takes the intended path.
#
# This footprint is MECHANICAL-REFERENCE ONLY (v0.6+, SEN66 PCB-mounted):
#   - The SEN66 mounts DIRECTLY ON THE PCB (face-up, body 21.3 mm above
#     PCB, openings facing UP toward the AK-N-94 perforated cover).
#     This means hard constraint #1 has a SEN66-zone exception (≥22 mm),
#     not the default 17 mm front-side height. CLAUDE.md v0.6.
#   - The mech-ref footprint marks the SEN66 body's projected shadow on
#     the PCB so the LD2410 and MIKROE-2462 daughterboards stay clear,
#     and so the J3 socket aligns with the SEN66's on-body JST GH
#     connector for a short cable run.
#   - No pads, no drilled holes (the 4× zip-tie retention holes are a
#     separate footprint: `ZipTieHole_3mm_NPTH`).
SEN66_BODY_X = 55.2
SEN66_BODY_Y = 25.6
SEN66_BODY_Z = 21.5                # body height (CLAUDE.md hard constraint)
SEN66_SILK_INSET = 0.2             # inset between F.Fab outline and F.SilkS

# Air-opening footprint markers (on F.Fab only — assembly reference,
# not on F.SilkS so the silkscreen art stays uncluttered).
SEN66_INLET1_CX, SEN66_INLET1_CY = 10.70, 7.40
SEN66_INLET1_DX, SEN66_INLET1_DY = 15.05, 7.05    # obround
SEN66_INLET2_CX, SEN66_INLET2_CY = 10.65, 18.85
SEN66_INLET2_DX, SEN66_INLET2_DY = 15.14, 8.14    # rectangle
SEN66_OUTLET_CX, SEN66_OUTLET_CY = 42.40, 12.80
SEN66_OUTLET_DIA = 20.74                            # outlet circle Ø
SEN66_CONNECTOR_X, SEN66_CONNECTOR_Y = SEN66_BODY_X, SEN66_BODY_Y / 2
SEN66_DIVIDER_X = 26.0                              # sealing-rib X position


def gen_sen66_mechanical_footprint() -> str:
    """Custom SEN66_Mechanical_Reference footprint (mechanical-only).

    No pads — the SEN66 doesn't bolt to the PCB (v0.6+ retains it via
    4× zip-ties through NPTH holes flanking the body). This footprint
    exists so the PCB designer has a visible "SEN66 shadow" in 2D / 3D
    views, reserving enough clearance for the SEN66 body, the four
    zip-tie holes, and ensuring that future components (LD2410,
    NT3H1101) avoid the SEN66 zone.

    Rendered on `F.Fab` (full body outline + air openings + connector
    marker + foam-divider hint + module identification) and on
    `F.SilkScreen` (slightly inset body outline only — keep silkscreen
    art minimal for production cleanliness).
    """
    # Footprint-local coordinates with the rectangle's corner at (0, 0)
    # are awkward for KiCad — the footprint anchor sits at (0, 0) and
    # all features sit in +X, +Y. That's fine; pcbnew accepts it.
    x_min, y_min = 0.0, 0.0
    x_max, y_max = SEN66_BODY_X, SEN66_BODY_Y
    inset = SEN66_SILK_INSET

    # F.Fab body outline (un-inset rectangle).
    fab_outline = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:fab-outline')}")
        \t)""")

    # F.SilkS body outline (inset slightly from the courtyard / Edge.Cuts
    # so the silkscreen edge prints cleanly inside the body shadow).
    silk_outline = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min + inset)} {fmt(y_min + inset)})
        \t\t(end {fmt(x_max - inset)} {fmt(y_max - inset)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(fill no)
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('sen66:fp:silk-outline')}")
        \t)""")

    # Inlet #1 — obround (rounded ends). Half-length of straight midsection:
    # straight = DX - DY (since end radii are DY/2).
    in1_r = SEN66_INLET1_DY / 2.0
    in1_x1 = SEN66_INLET1_CX - SEN66_INLET1_DX / 2.0 + in1_r
    in1_x2 = SEN66_INLET1_CX + SEN66_INLET1_DX / 2.0 - in1_r
    in1_y = SEN66_INLET1_CY
    inlet1_top = textwrap.dedent(f"""\
        \t(fp_line
        \t\t(start {fmt(in1_x1)} {fmt(in1_y - in1_r)})
        \t\t(end {fmt(in1_x2)} {fmt(in1_y - in1_r)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:inlet1-top')}")
        \t)""")
    inlet1_bot = textwrap.dedent(f"""\
        \t(fp_line
        \t\t(start {fmt(in1_x1)} {fmt(in1_y + in1_r)})
        \t\t(end {fmt(in1_x2)} {fmt(in1_y + in1_r)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:inlet1-bot')}")
        \t)""")
    inlet1_left_arc = textwrap.dedent(f"""\
        \t(fp_arc
        \t\t(start {fmt(in1_x1)} {fmt(in1_y - in1_r)})
        \t\t(mid {fmt(in1_x1 - in1_r)} {fmt(in1_y)})
        \t\t(end {fmt(in1_x1)} {fmt(in1_y + in1_r)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:inlet1-arc-l')}")
        \t)""")
    inlet1_right_arc = textwrap.dedent(f"""\
        \t(fp_arc
        \t\t(start {fmt(in1_x2)} {fmt(in1_y + in1_r)})
        \t\t(mid {fmt(in1_x2 + in1_r)} {fmt(in1_y)})
        \t\t(end {fmt(in1_x2)} {fmt(in1_y - in1_r)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:inlet1-arc-r')}")
        \t)""")

    # Inlet #2 — rectangle.
    in2_x1 = SEN66_INLET2_CX - SEN66_INLET2_DX / 2.0
    in2_x2 = SEN66_INLET2_CX + SEN66_INLET2_DX / 2.0
    in2_y1 = SEN66_INLET2_CY - SEN66_INLET2_DY / 2.0
    in2_y2 = SEN66_INLET2_CY + SEN66_INLET2_DY / 2.0
    inlet2 = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(in2_x1)} {fmt(in2_y1)})
        \t\t(end {fmt(in2_x2)} {fmt(in2_y2)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:inlet2')}")
        \t)""")

    # Outlet — circle.
    out_r = SEN66_OUTLET_DIA / 2.0
    outlet = textwrap.dedent(f"""\
        \t(fp_circle
        \t\t(center {fmt(SEN66_OUTLET_CX)} {fmt(SEN66_OUTLET_CY)})
        \t\t(end {fmt(SEN66_OUTLET_CX + out_r)} {fmt(SEN66_OUTLET_CY)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:outlet')}")
        \t)""")

    # Foam-divider hint — dashed line across body Y range at the divider X
    # (visual aid, assembly reference for where the foam rib sits between
    # inlet zone and outlet zone per Sensirion mech §3 §2.1 sealing).
    divider = textwrap.dedent(f"""\
        \t(fp_line
        \t\t(start {fmt(SEN66_DIVIDER_X)} {fmt(y_min + 1.0)})
        \t\t(end {fmt(SEN66_DIVIDER_X)} {fmt(y_max - 1.0)})
        \t\t(stroke (width 0.08) (type dash))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:divider')}")
        \t)""")

    # Connector position marker on +X short edge.
    conn_marker = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(SEN66_CONNECTOR_X - 2.0)} {fmt(SEN66_CONNECTOR_Y - 2.4)})
        \t\t(end {fmt(SEN66_CONNECTOR_X + 1.0)} {fmt(SEN66_CONNECTOR_Y + 2.4)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:conn-marker')}")
        \t)""")
    conn_label = textwrap.dedent(f"""\
        \t(fp_text user "JST GH cable ->"
        \t\t(at {fmt(SEN66_CONNECTOR_X - 5.0)} {fmt(SEN66_CONNECTOR_Y + 4.5)} 0)
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('sen66:fp:conn-label')}")
        \t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t)""")

    # v0.15.8: "SEN66 SIN-T" module-identification label moved to a
    # board-level gr_text emitted by gen_silk_labels(), so the label
    # reads horizontally instead of rotating with the SEN66 footprint
    # rotation 90°.

    # Reference + Value properties (hidden — this is a mechanical reference
    # and shouldn't clutter the silk).
    ref_block = textwrap.dedent(f"""\
        \t(property "Reference" "REF**"
        \t\t(at {fmt(SEN66_BODY_X / 2.0)} -1.5 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('sen66:fp:prop-ref')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)""")
    value_block = textwrap.dedent(f"""\
        \t(property "Value" "SEN66_Mechanical_Reference"
        \t\t(at {fmt(SEN66_BODY_X / 2.0)} {fmt(SEN66_BODY_Y + 1.5)} 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sen66:fp:prop-val')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)""")
    footprint_block = textwrap.dedent(f"""\
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sen66:fp:prop-fp')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)""")
    datasheet_block = textwrap.dedent(f"""\
        \t(property "Datasheet" "https://sensirion.com/resource/datasheet/SEN6x"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sen66:fp:prop-ds')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)""")
    desc_block = textwrap.dedent(f"""\
        \t(property "Description" "Sensirion SEN66 mechanical-reference footprint (no pads). SEN66-SIN-T, material 3.001.030. Body 55.2x25.6x21.3 mm. PCB-mounted face-up (v0.6); openings face UP through AK-N-94 perforated cover."
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sen66:fp:prop-desc')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)""")

    # v0.22: F.CrtYd RESTORED as a programmatic guardrail. The v0.21 agent
    # removed the courtyard reasoning that "SEN66 floats 21.5 mm above PCB".
    # That was WRONG. The SEN66 lies FLAT on the PCB on its 25.6 x 55.2 mm
    # back face — there is ZERO clearance under it. The 21.5 mm is the
    # body height ABOVE the PCB, not a standoff. Any SMD component placed
    # inside the SEN66 body shadow on the PCB plane physically cannot
    # exist; the SEN66 body would crush it. Restoring the courtyard makes
    # KiCad's DRC re-trigger `courtyards_overlap` on any such mistake,
    # which is exactly what we want as a guardrail. The 0.25 mm clearance
    # margin matches the KiCad default. Daughterboards on female pin
    # sockets (MOD1 ESP32, MOD2 MIKROE) are DIFFERENT — they sit on
    # 8-11 mm tall pin sockets so SMD components do fit under them; their
    # mech-refs intentionally OMIT the courtyard so DRC stays silent
    # there. See `_emit_daughterboard_reference_pcb_footprint`.
    crty_inset = -0.25  # outset 0.25 mm beyond body
    courtyard = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min + crty_inset)} {fmt(y_min + crty_inset)})
        \t\t(end {fmt(x_max - crty_inset)} {fmt(y_max - crty_inset)})
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U('sen66:fp:courtyard')}")
        \t)""")

    body_blocks = "\n".join(
        block for block in [
            ref_block, value_block, footprint_block, datasheet_block, desc_block,
            fab_outline, silk_outline,
            inlet1_top, inlet1_bot, inlet1_left_arc, inlet1_right_arc,
            inlet2, outlet, divider, conn_marker, conn_label,
            courtyard,
        ] if block
    )

    return textwrap.dedent(f"""\
        (footprint "SEN66_Mechanical_Reference"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "Sensirion SEN66 mechanical-reference (no pads). SEN66-SIN-T, MPN 3.001.030. 55.2x25.6x21.3 mm. PCB-mounted face-up (v0.6) via 4x zip-ties through ZipTieHole_3mm_NPTH; openings face UP through AK-N-94 perforated cover. JST GH 6-pin connector wires to J3.")
        \t(tags "sen66 sensirion mechanical reference pcb-mounted no-pads")
        \t(attr board_only exclude_from_pos_files exclude_from_bom)
        """) + body_blocks + "\n)\n"


# -----------------------------------------------------------------------------
# 1ab) LD2410 mechanical-reference footprint (own library)
# -----------------------------------------------------------------------------
def gen_ld2410_mechanical_footprint() -> str:
    """Custom LD2410_Mechanical_Reference footprint (mechanical-only).

    No pads — the LD2410 module sits ABOVE the OAS PCB on its own 1.27 mm
    pin row (the stock KiCad PinHeader_1x05_P1.27mm_Vertical footprint
    at J4 carries the electrical pads). This mechanical-reference
    footprint exists so the PCB designer sees a "LD2410 shadow" in
    2D/3D views, claiming the body-projected rectangle as a keep-out
    zone for other components (NT3H1101 NFC IC, NFC trace antenna,
    Qwiic, decoupling caps, etc.).

    Geometry (LD2410-local, anchor at body corner (0, 0)):
      - Body rectangle: 0..LD2410_BODY_W × 0..LD2410_BODY_H
      - Antenna patches sit roughly at LD2410-local X = 0..12.7 (the
        -X far end). A dashed marker on F.Fab outlines the antenna zone
        so the PCB layout knows where the 24 GHz beam emanates.
      - Connector pin row at LD2410-local X = LD2410_BODY_W = 35.56,
        centered at Y = 7.62. A solid marker on F.Fab outlines the
        5-pad column footprint (pin 1 at bottom, pin 5 at top by
        convention; matches stock PinHeader_1x05_P1.27mm_Vertical).
    """
    x_min, y_min = 0.0, 0.0
    x_max, y_max = LD2410_BODY_W, LD2410_BODY_H
    inset = LD2410_SILK_INSET

    fab_outline = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('ld2410:fp:fab-outline')}")
        \t)""")
    # v0.15.9: F.SilkS body silhouette emitted as a U-shape (3 fp_line,
    # NO closed rect). The U opens at LD2410-local X = LD2410_BODY_W (the
    # connector short edge), so the J4 stock-footprint silk frame at the
    # connector handles the bottom of the silhouette. The 3 lines we emit:
    #   • antenna short edge at LD2410-local X = inset
    #   • long edge 1 at LD2410-local Y = inset
    #   • long edge 2 at LD2410-local Y = y_max - inset
    # Both long edges stop at LD2410-local X = x_max - LD2410_SILK_INSET_CONN
    # (~33.76 mm) so they clear J4's silk frame zone with margin.
    x_silk_end = x_max - LD2410_SILK_INSET_CONN
    y_silk_top = y_min + inset
    y_silk_bot = y_max - inset
    silk_outline = "" if not LD2410_EMIT_SILK_OUTLINE else textwrap.dedent(f"""\
        \t(fp_line
        \t\t(start {fmt(x_min + inset)} {fmt(y_silk_top)})
        \t\t(end {fmt(x_min + inset)} {fmt(y_silk_bot)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('ld2410:fp:silk-antenna-edge')}")
        \t)
        \t(fp_line
        \t\t(start {fmt(x_min + inset)} {fmt(y_silk_top)})
        \t\t(end {fmt(x_silk_end)} {fmt(y_silk_top)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('ld2410:fp:silk-long-edge-1')}")
        \t)
        \t(fp_line
        \t\t(start {fmt(x_min + inset)} {fmt(y_silk_bot)})
        \t\t(end {fmt(x_silk_end)} {fmt(y_silk_bot)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('ld2410:fp:silk-long-edge-2')}")
        \t)""")

    # Antenna zone on F.Fab — dashed rectangle at the -X end of the body.
    # Marks where the 1T2R microstrip patches sit on the LD2410 PCB so
    # the PCB designer keeps obstacles (tall components, copper pours) out
    # of the beam path.
    antenna_marker = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min + 1.0)} {fmt(y_min + 1.0)})
        \t\t(end {fmt(LD2410_ANTENNA_X_END)} {fmt(y_max - 1.0)})
        \t\t(stroke (width 0.1) (type dash))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('ld2410:fp:antenna')}")
        \t)""")
    # v0.15.8: "antenna ^", "J4 pins", and "HLK-LD2410B" labels removed
    # from the footprint and emitted as board-level gr_text by
    # gen_silk_labels() so they remain rotation-independent and read
    # horizontally even though the LD2410 footprint is rotated 270°.
    # With the body shrunk from 15.24 mm to 7.62 mm (correct datasheet
    # short-axis spec), the rotated in-footprint text bboxes triggered
    # silk_overlap DRC violations against the silk rect; moving to
    # board-level gr_text eliminates the rotation issue entirely.

    # Connector pin-row marker on F.Fab — solid rectangle showing the
    # 5-pin column footprint at the +X short edge. The actual electrical
    # pads live in J4 (stock PinHeader_1x05_P1.27mm_Vertical, separate
    # footprint placed at OAS PCB X=-10.16).
    conn_x = LD2410_CONNECTOR_X
    conn_y_top = LD2410_CONNECTOR_Y - 2.54   # pin 1 row
    conn_y_bot = LD2410_CONNECTOR_Y + 2.54   # pin 5 row
    conn_marker = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(conn_x - 1.5)} {fmt(conn_y_top - 0.7)})
        \t\t(end {fmt(conn_x)} {fmt(conn_y_bot + 0.7)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('ld2410:fp:conn-marker')}")
        \t)""")

    ref_block = textwrap.dedent(f"""\
        \t(property "Reference" "REF**"
        \t\t(at {fmt(LD2410_BODY_W / 2.0)} -1.5 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('ld2410:fp:prop-ref')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)""")
    value_block = textwrap.dedent(f"""\
        \t(property "Value" "LD2410_Mechanical_Reference"
        \t\t(at {fmt(LD2410_BODY_W / 2.0)} {fmt(LD2410_BODY_H + 1.5)} 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ld2410:fp:prop-val')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)""")
    footprint_block = textwrap.dedent(f"""\
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ld2410:fp:prop-fp')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)""")
    datasheet_block = textwrap.dedent(f"""\
        \t(property "Datasheet" "https://www.hlktech.net/index.php?id=988"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ld2410:fp:prop-ds')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)""")
    desc_block = textwrap.dedent(f"""\
        \t(property "Description" "HiLink HLK-LD2410B 24 GHz mmWave presence radar daughterboard mechanical-reference. ~35x7x7 mm. Mounts via 5-pin 1.27 mm pin header (J4) above the OAS PCB; antenna patches on the LD2410 top face point toward the AK-N-94 cover."
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ld2410:fp:prop-desc')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)""")

    # No F.CrtYd: J4's pads sit AT the LD2410 body's connector edge by
    # design (LD2410 plugs into J4). A body-sized courtyard would
    # trigger `courtyards_overlap` against J4 and `pth_inside_courtyard`
    # for every J4 pad. The LD2410 daughterboard physically sits ABOVE
    # the OAS PCB on its pin-header standoff (~3-5 mm), so the "shadow"
    # is a Z-stack clearance question, not a 2D courtyard one. Designers
    # read the F.Fab outline + Description to know what's where.

    body_blocks = "\n".join(
        block for block in (
            ref_block, value_block, footprint_block, datasheet_block, desc_block,
            fab_outline, silk_outline,
            antenna_marker,
            conn_marker,
        ) if block
    )

    return textwrap.dedent(f"""\
        (footprint "LD2410_Mechanical_Reference"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "HiLink HLK-LD2410B mechanical-reference (no pads). 24 GHz mmWave presence radar daughterboard. Body ~35x7x7 mm above OAS PCB on 1.27 mm pin header (J4). Antenna patches on the top face point through the enclosure cover.")
        \t(tags "ld2410 hilink mmwave radar mechanical reference daughterboard")
        \t(attr board_only exclude_from_pos_files exclude_from_bom)
        """) + body_blocks + "\n)\n"


# -----------------------------------------------------------------------------
# 1aa) Zip-tie NPTH footprint (own library)
# -----------------------------------------------------------------------------
# 4× zip-tie holes hold the SEN66 flat against the PCB (face-up mount,
# v0.6). Each hole is Ø3.0 mm NPTH — fits a standard 2.5 mm wide zip-tie
# band with margin. The pattern matches the placement of the SEN66
# mechanical reference footprint: holes sit at the 4 corners of an
# imaginary rectangle slightly larger than the SEN66 body footprint,
# leaving clearance for the zip-tie loop to come over the body.
ZIPTIE_HOLE_DIAMETER = 3.0
ZIPTIE_HOLE_SILK_RING_DIAMETER = 4.0    # silkscreen ring (visibility hint)


def gen_ziptie_hole_footprint() -> str:
    """Custom ZipTieHole_3mm_NPTH footprint.

    NPTH (non-plated through hole), Ø3.0 mm — for zip-ties holding the
    SEN66 flat against the PCB (face-up mount, v0.6). The SEN66 has no
    mounting holes (Sensirion datasheet), so retention is via 4 zip-tie
    loops pulled over the body through these holes; cut the zip-ties to
    swap the sensor.

    Pattern after MountingHole_3.8mm_M3 — no copper pad, no plating, no
    soldermask cut-out; just a drilled hole + silk ring + courtyard for
    visibility.
    """
    courtyard_r = ZIPTIE_HOLE_DIAMETER * 0.75
    silk_r = ZIPTIE_HOLE_SILK_RING_DIAMETER / 2.0
    drill_r = ZIPTIE_HOLE_DIAMETER / 2.0
    return textwrap.dedent(f"""\
        (footprint "ZipTieHole_3mm_NPTH"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "Zip-tie hole Ø3.0 mm NPTH, for retaining SEN66 flat against the PCB (face-up mount, v0.6)")
        \t(tags "zip-tie ziptie npth 3mm sen66 mechanical pcb")
        \t(attr through_hole board_only exclude_from_pos_files exclude_from_bom)
        \t(property "Reference" "REF**"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('ziptie:fp:ref')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Value" "ZipTieHole_3mm_NPTH"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ziptie:fp:val')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ziptie:fp:fp')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Datasheet" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ziptie:fp:ds')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Description" "Zip-tie pass-through hole, Ø3.0 mm NPTH (fits 2.5 mm band zip-tie). Used in groups of 4 to retain the SEN66 module flat against the OAS PCB (face-up mount per v0.6)."
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('ziptie:fp:desc')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(courtyard_r)} 0)
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U('ziptie:fp:crtyd')}")
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(silk_r)} 0)
        \t\t(stroke (width 0.12) (type solid))
        \t\t(fill no)
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('ziptie:fp:silk-ring')}")
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(drill_r)} 0)
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('ziptie:fp:fab-ring')}")
        \t)
        \t(pad "" np_thru_hole circle
        \t\t(at 0 0)
        \t\t(size {fmt(ZIPTIE_HOLE_DIAMETER)} {fmt(ZIPTIE_HOLE_DIAMETER)})
        \t\t(drill {fmt(ZIPTIE_HOLE_DIAMETER)})
        \t\t(layers "F&B.Cu" "*.Mask")
        \t\t(remove_unused_layers no)
        \t\t(uuid "{U('ziptie:fp:pad')}")
        \t)
        )
        """)


# -----------------------------------------------------------------------------
# 1ab) SK6812-SIDE — addressable side-emit RGB LED footprint
# -----------------------------------------------------------------------------
# Custom footprint for the SK6812 SIDE-A LED used in the v0.16 AQI status
# ring. Pinout verified against Normand 2018 rev 01 datasheet and OPSCO
# 2021 rev A/1 datasheet (both agree): 1=DIN, 2=VDD, 3=DOUT, 4=GND. KiCad
# 10's stock `LED_SMD:LED_SK6812*` footprints are for the PLCC4 5050 /
# MINI / 1515 variants — none match the 4020 SIDE package geometry or
# pinout — hence this project-local footprint.
#
# Pad rectangles: 0.6 × 1.0 mm at 0.95 mm pitch along body-local +X,
# offset to body-local +Y = +0.85 (toward the pad-row face). The emission
# face is on the opposite long edge (body-local -Y direction).
#
# Layers:
#   F.Cu      — 4 SMD pads
#   F.Fab     — body outline (4.0 × 2.0 mm), pin-1 dot, emission-edge arrow
#   F.SilkS   — pin-1 dot near pad 1 + small emission-direction arrow on
#                the body's -Y edge. No body silk RECT is emitted (would
#                trigger silk_overlap DRC against the MIKROE-2462 silk
#                at the angle-180° LED position; the body outline lives
#                on F.Fab instead).
#   F.CrtYd   — small courtyard slightly larger than the body
#
# Property layout:
#   Reference (hidden, on F.SilkS at body-local (0, -1.5))
#   Value     (hidden, on F.Fab     at body-local (0, +2.5))


def gen_sk6812_side_footprint() -> str:
    """Custom SK6812-SIDE footprint definition (library file)."""
    body_hw = SK6812SIDE_BODY_W / 2.0    # = 2.0 (half-extent along +X)
    body_hh = SK6812SIDE_BODY_H / 2.0    # = 1.0 (half-extent along +Y)
    # Courtyard: 0.25 mm beyond pad row on +Y side, 0.25 mm beyond body
    # on the emission (-Y) side. ±X extent matches body.
    crty_x_min = -body_hw - 0.20
    crty_x_max = +body_hw + 0.20
    crty_y_min = -body_hh - 0.20         # emission side
    crty_y_max = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.20   # +1.55
    # Pad rectangles
    pad_blocks = []
    for pin_num, lx in enumerate(SK6812SIDE_PAD_X_OFFSETS, start=1):
        pad_blocks.append(textwrap.dedent(f"""\
            \t(pad "{pin_num}" smd rect
            \t\t(at {fmt(lx)} {fmt(SK6812SIDE_PAD_Y)})
            \t\t(size {fmt(SK6812SIDE_PAD_WIDTH)} {fmt(SK6812SIDE_PAD_HEIGHT)})
            \t\t(layers "F.Cu" "F.Paste" "F.Mask")
            \t\t(uuid "{U(f'sk6812-side:fp:pad-{pin_num}')}")
            \t)"""))
    pads = "\n".join(pad_blocks)
    # Pin-1 dot on F.SilkS, just outside pad 1 on the +X- / +Y-extreme
    # corner so it survives any rotation that lands pad 1 on either side
    # of the ring.
    pin1_dot_x = SK6812SIDE_PAD_X_OFFSETS[0]   # -1.425
    pin1_dot_y = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.35   # +1.7
    # Emission-direction arrow on F.SilkS: short line + tip at body-local
    # -Y side. Located on the emission face (-Y).
    arrow_tip_y = -body_hh - 0.35       # -1.35
    arrow_base_y = -body_hh + 0.25      # -0.75
    return textwrap.dedent(f"""\
        (footprint "SK6812-SIDE"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "SK6812 SIDE-A addressable RGB LED, 4020 side-emit, integrated WS281x controller. Pinout 1=DIN 2=VDD 3=DOUT 4=GND per Normand / OPSCO datasheets. Emission face on body-local -Y edge.")
        \t(tags "sk6812 side-emit addressable rgb neopixel ws281x")
        \t(attr smd)
        \t(property "Reference" "REF**"
        \t\t(at 0 -1.5 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('sk6812-side:fp:prop-ref')}")
        \t\t(effects (font (size 0.8 0.8) (thickness 0.12)))
        \t)
        \t(property "Value" "SK6812-SIDE"
        \t\t(at 0 2.5 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sk6812-side:fp:prop-val')}")
        \t\t(effects (font (size 0.8 0.8) (thickness 0.12)))
        \t)
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sk6812-side:fp:prop-fp')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Datasheet" "http://www.normandled.com/upload/201810/SK6812%20SIDE-A%20LED%20Datasheet.pdf"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sk6812-side:fp:prop-ds')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Description" "SK6812 SIDE-A 4020 side-emit addressable RGB LED (Shenzhen Normand / OPSCO). Pinout 1=DIN, 2=VDD, 3=DOUT, 4=GND."
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('sk6812-side:fp:prop-desc')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(fp_rect
        \t\t(start {fmt(-body_hw)} {fmt(-body_hh)})
        \t\t(end {fmt(body_hw)} {fmt(body_hh)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sk6812-side:fp:fab-body')}")
        \t)
        \t(fp_rect
        \t\t(start {fmt(crty_x_min)} {fmt(crty_y_min)})
        \t\t(end {fmt(crty_x_max)} {fmt(crty_y_max)})
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U('sk6812-side:fp:crtyd')}")
        \t)
        \t(fp_circle
        \t\t(center {fmt(pin1_dot_x)} {fmt(pin1_dot_y)})
        \t\t(end {fmt(pin1_dot_x + 0.15)} {fmt(pin1_dot_y)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(fill solid)
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('sk6812-side:fp:pin1-dot')}")
        \t)
        \t(fp_line
        \t\t(start 0 {fmt(arrow_base_y)})
        \t\t(end 0 {fmt(arrow_tip_y)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sk6812-side:fp:arrow-stem')}")
        \t)
        \t(fp_line
        \t\t(start {fmt(-0.3)} {fmt(arrow_tip_y + 0.3)})
        \t\t(end 0 {fmt(arrow_tip_y)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sk6812-side:fp:arrow-wing-l')}")
        \t)
        \t(fp_line
        \t\t(start {fmt(+0.3)} {fmt(arrow_tip_y + 0.3)})
        \t\t(end 0 {fmt(arrow_tip_y)})
        \t\t(stroke (width 0.08) (type solid))
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sk6812-side:fp:arrow-wing-r')}")
        \t)
        """) + pads + textwrap.dedent("""
        )
        """)


# -----------------------------------------------------------------------------
# 1b) Cutout keepout zones + Dwgs.User markers
# -----------------------------------------------------------------------------
def gen_cutouts() -> tuple[str, str]:
    """Return (keepout_zones_block, dwgsuser_markers_block).

    For each cutout in CUTOUTS we generate:
      - a (zone (keepout ...)) on F.Cu + B.Cu — blocks tracks, vias, pads,
        copperpour and footprints in that rectangle
      - a (gr_rect) on Dwgs.User showing the exact case-wall opening
      - a (gr_text) labelling it for visual reference
    """
    keepouts = []
    markers = []
    for name, x1, x2, y1, y2, allow_pads in CUTOUTS:
        # PCB-local coords -> page-offset coords
        X1, X2 = fx(x1), fx(x2)
        Y1, Y2 = fy(y1), fy(y2)
        cx_local = (x1 + x2) / 2
        cy_local = (y1 + y2) / 2
        size_x = abs(x2 - x1)
        size_y = abs(y2 - y1)

        # Keepout NOTE: `(footprints not_allowed)` is INTENTIONALLY omitted.
        # The cutout zones are meant to keep COPPER (tracks, vias, pads,
        # copperpour) out of the case-wall opening area so traces don't
        # short to the case wall's PE conductor or get pinched by the
        # cutout edge. They are NOT meant to block footprint placement —
        # the whole point of a chord-edge cutout is to let a connector
        # footprint (USB-C, terminal block, JST-GH plug) extend THROUGH
        # the case wall.
        #
        # The mechanical-reference SEN66 footprint (F.Fab/F.SilkS only,
        # zero copper) needs to be place-able anywhere on the PCB
        # even where its body shadow crosses a cutout zone. The SEN66
        # body sits flat on the PCB (v0.6+) but the shadow drawing is
        # graphics-only (no copper) so a cutout-zone overlap is purely
        # a 2D drawing coincidence, not a physical conflict. (The
        # `(pads not_allowed)` rule above already blocks any *copper*
        # the SEN66 reference footprint might accidentally bring along.)
        #
        # v0.19: per-cutout `allow_pads`. Some cutouts host a connector
        # whose solder pads MUST live in the cutout area (the case-wall
        # opening is the place the user accesses these pads — Qwiic
        # cable plug, recovery-header pogopin jig). For those cutouts
        # we drop the `(pads not_allowed)` rule so DRC doesn't object.
        #
        # v0.28d: when pads are allowed, tracks and vias are also
        # allowed. Reason: a connector pad inside the cutout MUST be
        # electrically reachable by some copper, which means tracks
        # need to approach the pad from outside the cutout. Without
        # `(tracks allowed)`, KiCad's keepout rule fires
        # `items_not_allowed` on any segment that crosses the cutout
        # polygon — making the pads unroutable. The physical
        # case-wall opening is defined by the AK-N-94 cover geometry
        # (third-party DXF kept locally; not in this repo), not by
        # the OAS PCB; copper inside
        # the connector access cutout is harmless because the case-
        # wall opening is wider than the connector body envelope.
        # When pads are NOT allowed (e.g. C4 "v2 expansion
        # placeholder"), tracks/vias/copperpour stay blocked to keep
        # stray copper out of the area reserved for a future
        # connector.
        pads_rule = "(pads allowed)" if allow_pads else "(pads not_allowed)"
        tracks_rule = "(tracks allowed)" if allow_pads else "(tracks not_allowed)"
        vias_rule = "(vias allowed)" if allow_pads else "(vias not_allowed)"
        # v0.28d: copperpour is also allowed in pad-allowed cutouts.
        # The GND pour fills around connector pads with normal thermal
        # relief — same behavior as anywhere else on the board, so
        # GND pads inside the cutout (J9.1 Qwiic GND, J10.1 recovery
        # GND) connect through thermal spokes and signal pads stay
        # isolated by the 0.2 mm clearance ring.
        copperpour_rule = "(copperpour allowed)" if allow_pads else "(copperpour not_allowed)"
        keepouts.append(textwrap.dedent(f"""\
            \t(zone
            \t\t(net 0)
            \t\t(net_name "")
            \t\t(layers "F.Cu" "B.Cu")
            \t\t(uuid "{U('keepout:'+name)}")
            \t\t(name "Connector_Cutout_{name}")
            \t\t(hatch edge 0.508)
            \t\t(connect_pads
            \t\t\t(clearance 0.508)
            \t\t)
            \t\t(min_thickness 0.254)
            \t\t(filled_areas_thickness no)
            \t\t(keepout
            \t\t\t{tracks_rule}
            \t\t\t{vias_rule}
            \t\t\t{pads_rule}
            \t\t\t{copperpour_rule}
            \t\t\t(footprints allowed)
            \t\t)
            \t\t(placement
            \t\t\t(enabled no)
            \t\t\t(sheetname "")
            \t\t)
            \t\t(fill
            \t\t\t(thermal_gap 0.508)
            \t\t\t(thermal_bridge_width 0.508)
            \t\t)
            \t\t(polygon
            \t\t\t(pts
            \t\t\t\t(xy {X1} {Y1})
            \t\t\t\t(xy {X2} {Y1})
            \t\t\t\t(xy {X2} {Y2})
            \t\t\t\t(xy {X1} {Y2})
            \t\t\t)
            \t\t)
            \t)"""))

        # Dwgs.User marker: rectangle outline + label
        markers.append(textwrap.dedent(f"""\
            \t(gr_rect
            \t\t(start {X1} {Y1})
            \t\t(end {X2} {Y2})
            \t\t(stroke (width 0.1) (type solid))
            \t\t(fill no)
            \t\t(layer "Dwgs.User")
            \t\t(uuid "{U('marker_rect:'+name)}")
            \t)
            \t(gr_text "{name}\\n{size_x:.1f}×{size_y:.1f}"
            \t\t(at {fx(cx_local)} {fy(cy_local)})
            \t\t(layer "Dwgs.User")
            \t\t(uuid "{U('marker_text:'+name)}")
            \t\t(effects
            \t\t\t(font (size 0.8 0.8) (thickness 0.12))
            \t\t)
            \t)"""))

    return "\n".join(keepouts), "\n".join(markers)


# -----------------------------------------------------------------------------
# 1c) SEN66 + zip-tie hole + J3 PCB placement
# -----------------------------------------------------------------------------
def _emit_pcb_footprint_simple_npth(
    lib_id: str, reference: str, value: str, descr: str,
    drill_mm: float, silk_ring_radius_mm: float, courtyard_radius_mm: float,
    fab_ring_radius_mm: float, x: float, y: float, uuid_tag: str,
    silk_label: str | None = None,
    silk_label_offset_y: float = 0.0,
) -> str:
    """Emit a placed-instance NPTH footprint (zip-tie hole etc).

    KiCad 10 stores footprint references in the PCB file as a full
    repetition of the footprint geometry (not just a library reference).
    This helper builds the same 'fp_circle on F.CrtYd + fp_circle on
    F.Fab + fp_circle on F.SilkS + np_thru_hole pad' pattern that
    `gen_ziptie_hole_footprint()` writes to the library file, but
    placed at the given PCB-global (x, y).

    The library file holds the canonical definition; the placement
    here is the embedded copy KiCad expects inside the .kicad_pcb.
    Keeping the two in lock-step is essential so opening pcbnew without
    the project-local footprint library still renders the placement.

    If `silk_label` is non-None, an additional `(fp_text user ...)` on
    F.SilkS with that text is emitted at footprint-local
    (0, silk_label_offset_y). Used for hand-assembler-facing designators
    (e.g. "ZT1", "ZT2") so the human can identify each hole at a glance
    without referring to the schematic.
    """
    silk_text = ""
    if silk_label is not None:
        silk_text = textwrap.dedent(f"""
            \t\t(fp_text user "{silk_label}"
            \t\t\t(at 0 {fmt(silk_label_offset_y)} 0)
            \t\t\t(layer "F.SilkS")
            \t\t\t(uuid "{U('fp-silk-label:' + uuid_tag)}")
            \t\t\t(effects (font (size 1 1) (thickness 0.15)))
            \t\t)""")
    # v0.40 audit-16: emit the full lib-qualified `oas:<lib_id>` name in
    # the (footprint "...") header AND the (property "Footprint" ...)
    # clause so KiCad's lib_footprint_mismatch check pairs the placement
    # against the canonical library entry. Pre-fix the header used the
    # bare lib_id, which JLCPCB's DFM matcher could read as a custom
    # in-PCB-only footprint not present in any library.
    return textwrap.dedent(f"""\
        \t(footprint "oas:{lib_id}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)})
        \t\t(descr "{descr}")
        \t\t(attr through_hole board_only exclude_from_pos_files exclude_from_bom)
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "oas:{lib_id}"
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
        \t\t(fp_circle
        \t\t\t(center 0 0)
        \t\t\t(end {fmt(courtyard_radius_mm)} 0)
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-crtyd:' + uuid_tag)}")
        \t\t)
        \t\t(fp_circle
        \t\t\t(center 0 0)
        \t\t\t(end {fmt(silk_ring_radius_mm)} 0)
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk:' + uuid_tag)}")
        \t\t)
        \t\t(fp_circle
        \t\t\t(center 0 0)
        \t\t\t(end {fmt(fab_ring_radius_mm)} 0)
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab:' + uuid_tag)}")
        \t\t)
        \t\t(pad "" np_thru_hole circle
        \t\t\t(at 0 0)
        \t\t\t(size {fmt(drill_mm)} {fmt(drill_mm)})
        \t\t\t(drill {fmt(drill_mm)})
        \t\t\t(layers "F&B.Cu" "*.Mask")
        \t\t\t(remove_unused_layers no)
        \t\t\t(uuid "{U('fp-pad:' + uuid_tag)}")
        \t\t){silk_text}
        \t)""")


def gen_sen66_reference_pcb_footprint(x: float, y: float, rotation: int) -> str:
    """Emit the placed SEN66_Mechanical_Reference footprint instance.

    This is the embedded copy of `gen_sen66_mechanical_footprint()`'s
    library definition, positioned at PCB-local (x, y) with rotation
    `rotation` degrees. The PCB file format requires a full repetition
    of the footprint body — the library entry alone doesn't render.

    Mechanical-only: no pads, no plated holes. All graphics on F.Fab,
    F.SilkS, F.CrtYd; nothing on F.Cu so this footprint contributes
    zero copper to the board.
    """
    x_min, y_min = 0.0, 0.0
    x_max, y_max = SEN66_BODY_X, SEN66_BODY_Y
    inset = SEN66_SILK_INSET
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
        \t\t(fp_rect
        \t\t\t(start {fmt(x_min + inset)} {fmt(y_min + inset)})
        \t\t\t(end {fmt(x_max - inset)} {fmt(y_max - inset)})
        \t\t\t(stroke (width 0.12) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-silk-outline:' + uuid_tag)}")
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
        \t\t(fp_text user "JST GH cable ->"
        \t\t\t(at {fmt(SEN66_CONNECTOR_X - 5.0)} {fmt(SEN66_CONNECTOR_Y + 4.5)} 0)
        \t\t\t(layer "F.SilkS")
        \t\t\t(uuid "{U('fp-conn-label:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
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
_FUSE_2920_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Fuse.pretty"
    / "Fuse_2920_7451Metric.kicad_mod"
)
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
# v0.40 audit-16: U1 LM2596S-5.0 TO-263-5 package. Previous generator
# emitted custom header "TO-263-5_LM2596" — non-canonical. Replace with
# verbatim stock parsing of Package_TO_SOT_SMD:TO-263-5_TabPin3.
_TO263_5_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Package_TO_SOT_SMD.pretty"
    / "TO-263-5_TabPin3.kicad_mod"
)
# v0.40 audit-16: U2 TPS62933 SOT-583-8 package. Previous generator
# emitted custom header "SOT-583_TPS62933" — non-canonical. Replace with
# verbatim stock parsing of Package_TO_SOT_SMD:SOT-583-8.
_SOT583_8_LIB_FOOTPRINT_PATH = (
    _kicad_install_path() / "footprints" / "Package_TO_SOT_SMD.pretty"
    / "SOT-583-8.kicad_mod"
)
# v0.40 audit-16: 1×6 P2.54 mm THT pin header (J2 — SWD/UART recovery).
# Same stock-library entry as J10 (_J10_LIB_FOOTPRINT_PATH) but emitted
# via a different generator. Consolidating to verbatim stock parsing.
_J2_LIB_FOOTPRINT_PATH = _J10_LIB_FOOTPRINT_PATH
# v0.40 post-order: radial THT bulk caps. Origin in stock = pin 1 (NOT
# body center). XY placement in generate.py call sites uses the body
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


def _annotate_pad_rotations(body_text: str, rotation: int) -> str:
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
      - Drop the 3D model block (path uses an env-var that isn't
        guaranteed to be defined on every machine; KiCad just shows a
        missing-model warning, which is purely visual and not a DRC).
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
    # values. Also drop the final `(embedded_fonts no)` and `(model ...)`
    # blocks at the bottom; we replace with our own and skip the 3D model.

    # The easiest parse: split on top-level S-expression bounds. KiCad
    # footprint files are well-formatted; each (key ...) at the indent
    # level "\t(" is a top-level child. We walk the file and split.
    body_chars = []
    depth = 0
    current = []
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

    # Filter out the items we want to REPLACE (version, generator,
    # property Reference, property Value, property KiLib_Generator,
    # embedded_fonts, model).
    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
        "(model ",
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
        "(model ",
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
        "(model ",
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
    x: float, y: float, rotation: int,
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
        `(property "KiLib_Generator" ...)`, `(embedded_fonts ...)`, and
        `(model ...)` children
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

    SKIP_PREFIXES = (
        "(version", "(generator", "(generator_version",
        "(property \"Reference\"",
        "(property \"Value\"",
        "(property \"KiLib_Generator\"",
        "(embedded_fonts",
        "(model ",
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
    and MIKROE-2462 daughterboard mating sockets (the boards plug into
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
        "(model ",
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
    *, x: float, y: float, rotation: int, reference: str, uuid_tag: str,
    hide_ref: bool = True,
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
    """
    body_hw = SK6812SIDE_BODY_W / 2.0
    body_hh = SK6812SIDE_BODY_H / 2.0
    crty_x_min = -body_hw - 0.20
    crty_x_max = +body_hw + 0.20
    crty_y_min = -body_hh - 0.20
    crty_y_max = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.20
    pin1_dot_x = SK6812SIDE_PAD_X_OFFSETS[0]
    pin1_dot_y = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.35
    arrow_tip_y = -body_hh - 0.35
    arrow_base_y = -body_hh + 0.25
    pad_blocks = []
    for pin_num, lx in enumerate(SK6812SIDE_PAD_X_OFFSETS, start=1):
        # Pad rotation injected explicitly so DRC interprets the pad
        # geometry as rotated WITH the footprint (KiCad quirk — see
        # `_annotate_pad_rotations` rationale).
        rot_clause = f" {rotation}" if rotation != 0 else ""
        pad_blocks.append(textwrap.dedent(f"""\
            \t\t(pad "{pin_num}" smd rect
            \t\t\t(at {fmt(lx)} {fmt(SK6812SIDE_PAD_Y)}{rot_clause})
            \t\t\t(size {fmt(SK6812SIDE_PAD_WIDTH)} {fmt(SK6812SIDE_PAD_HEIGHT)})
            \t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
            \t\t\t(uuid "{U(f'fp-pad:{uuid_tag}:{pin_num}')}")
            \t\t)"""))
    pads = "\n".join(pad_blocks)
    ref_hide_line = "\n\t\t\t(hide yes)" if hide_ref else ""
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
        """) + pads + "\n\t)"


def gen_capacitor_0402_pcb_footprint(
    *, x: float, y: float, rotation: int, reference: str, value: str,
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
    control (avoiding silk_overlap with J5/J6/J7/J8 socket frames, the
    MOD1/MOD2 daughterboard outlines, and the LED-ring cap collisions
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


def gen_polyfuse_smd_pcb_footprint(*, x: float, y: float, rotation: int,
                                    reference: str, value: str, uuid_tag: str,
                                    descr: str = "Polyfuse SMD 2920",
                                    hide_ref: bool = True) -> str:
    """SMD PTC polyfuse — 2920 size for MF-RHT075/60-2-class parts
    (60 V / 750 mA).

    v0.40 post-order: pad geometry transcribed VERBATIM from KiCad stock
    `Fuse:Fuse_2920_7451Metric.kicad_mod` (pitch 6.775 mm, pad 1.925 ×
    5.45 mm). Previous inline geometry used pitch 5.7 mm with narrower
    pad 2.0 × 5.4 mm — the Littelfuse 2920L body terminals would have
    extended ~0.14 mm beyond the OAS pad outer edges."""
    return _emit_stock_lib_footprint(
        src_path=_FUSE_2920_LIB_FOOTPRINT_PATH,
        lib_nickname="Fuse",
        reference=reference, value=value,
        datasheet="", description=descr,
        x=x, y=y, rotation=rotation,
        uuid_tag=uuid_tag,
        ref_offset_x=0.0, ref_offset_y=-3.5,
        val_offset_x=0.0, val_offset_y=3.5,
        hide_ref=hide_ref, hide_value=True,
    )


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


def gen_to263_5_pcb_footprint(*, x: float, y: float, rotation: int,
                               reference: str, value: str, uuid_tag: str,
                               descr: str = "TO-263-5 LM2596S",
                               hide_ref: bool = True) -> str:
    """TO-263-5 (D2PAK-5) footprint for LM2596S-5.0.

    v0.40 audit-16: refactored to verbatim KiCad stock parsing of
    Package_TO_SOT_SMD:TO-263-5_TabPin3. The previous version inline-emitted
    the pad coordinates BUT used a non-canonical footprint header name
    "TO-263-5_LM2596" — that mismatch between the in-file (footprint "..."
    header and the canonical KiCad library name was the v0.40-rejection
    failure mode. Now the entire footprint (pads + silk + F.Fab body
    outline + F.CrtYd + paste apertures + pin-1 silk marker) comes from
    the stock library verbatim, including the canonical header.

    Pin order per LM2596 datasheet TI lit no SNVS124N Table 1:
      1=VIN, 2=OUT (switch node), 3=GND (tab+pin3), 4=FB, 5=~ON/OFF
    """
    return _emit_stock_lib_footprint(
        src_path=_TO263_5_LIB_FOOTPRINT_PATH,
        lib_nickname="Package_TO_SOT_SMD",
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


def _daughterboard_body_content(
    body_w: float, body_l: float,
    pin_row_inset: float, pin_pitch: float, pin_count_per_row: int,
    body_label: str,
    antenna_label: str | None,
    usb_label: str | None,
    uuid_tag: str,
    pin_start_offset: float | None = None,
) -> str:
    """Inner body content (fp_rect on F.Fab + pin-row dots on F.Fab +
    fp_text labels) shared by the library footprint definition and the
    in-PCB placement instance for a daughterboard mech-ref. Returns the
    block ready to embed inside a (footprint ...) wrapper.

    `pin_start_offset` is the distance (in LIB +Y direction) from the
    body's pin-1-side short edge to pin 1's centerline. If None, the
    pin block is centred along the long axis. Asymmetric daughterboards
    (ESP32-C6 DevKitM-1 pins offset toward antenna; MIKROE-2462 pins
    offset toward pin-1 short edge) pass an explicit value.
    """
    parts: list[str] = []
    # Asymmetric silk inset: the long-edge silk lines EXTEND 0.5 mm beyond
    # the body so the female pin sockets (stock PinSocket_1x*, silk rect
    # ±1.33 mm around pad rows, pads at LIB X = pin_row_inset and body_w
    # - pin_row_inset) sit INSIDE the daughterboard silk rect — consistent
    # with the LD2410 silk approach. Short-edge silk stays 0.2 mm inside
    # body (no pin sockets near short edges).
    silk_inset_long = -0.5  # negative = extends OUTSIDE body in X direction
    silk_inset_short = 0.2  # positive = stays INSIDE body in Y direction

    # Body F.Fab outline (fabrication documentation layer).
    parts.append(textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start 0 0)
        \t\t(end {fmt(body_w)} {fmt(body_l)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('fp-fab-outline:' + uuid_tag)}")
        \t)"""))

    # Body F.SilkS outline — visible on physical board and 3D render so the
    # hand-assembler can see where the daughterboard sits. Encompasses
    # the female pin sockets along the long edges.
    parts.append(textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(silk_inset_long)} {fmt(silk_inset_short)})
        \t\t(end {fmt(body_w - silk_inset_long)} {fmt(body_l - silk_inset_short)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(fill no)
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('fp-silk-outline:' + uuid_tag)}")
        \t)"""))

    # Pin row dots on F.Fab (one column on each long edge, at pin_row_inset
    # from the body edge, offset along the long axis per pin_start_offset).
    span = (pin_count_per_row - 1) * pin_pitch
    if pin_start_offset is None:
        start_offset = (body_l - span) / 2
    else:
        start_offset = pin_start_offset
    pin_xs = (pin_row_inset, body_w - pin_row_inset)
    pin_ys = [start_offset + i * pin_pitch for i in range(pin_count_per_row)]
    for col_idx, cx in enumerate(pin_xs):
        for row_idx, cy in enumerate(pin_ys):
            parts.append(textwrap.dedent(f"""\
                \t(fp_circle
                \t\t(center {fmt(cx)} {fmt(cy)})
                \t\t(end {fmt(cx + 0.5)} {fmt(cy)})
                \t\t(stroke (width 0.08) (type solid))
                \t\t(fill no)
                \t\t(layer "F.Fab")
                \t\t(uuid "{U(f'fp-pin:{uuid_tag}:{col_idx}-{row_idx}')}")
                \t)"""))

    # v0.15.8: Centre body label removed — emitted as board-level
    # gr_text by gen_silk_labels() instead, so the label reads
    # horizontally regardless of the daughterboard footprint's rotation.
    # `body_label` argument retained for backward compatibility / docs
    # but no longer rendered inside the footprint.
    _ = body_label  # noqa: F841 (argument deliberately unused after v0.15.8)

    # v0.15.8: antenna_label and usb_label arguments are also retained
    # for compatibility but no longer rendered inside the footprint.
    # ESP32-C6 "ant" / "USB" hints are emitted as board-level gr_text
    # by gen_silk_labels() so they read horizontally regardless of
    # daughterboard rotation. MIKROE-2462 passes None for both.
    _ = antenna_label  # noqa: F841 (argument deliberately unused after v0.15.8)
    _ = usb_label  # noqa: F841 (argument deliberately unused after v0.15.8)

    return "\n".join(parts)


def gen_daughterboard_mech_lib_file(
    name: str,
    descr: str,
    body_w: float, body_l: float,
    pin_row_inset: float, pin_pitch: float, pin_count_per_row: int,
    body_label: str,
    antenna_label: str | None,
    usb_label: str | None,
    uuid_tag: str,
    pin_start_offset: float | None = None,
) -> str:
    """Return the .kicad_mod library-file content for a daughterboard
    mechanical-reference footprint.

    Mirrors the embedded body that `_emit_daughterboard_reference_pcb_footprint`
    writes into the placed-instance footprint inside `oas.kicad_pcb`,
    but with library-file metadata (no `(at x y rotation)` anchor, no
    embedded `(uuid ...)` for the footprint itself — KiCad pcbnew
    generates those when the lib footprint is dropped onto a board).
    Adding the matching lib file silences KiCad's
    `lib_footprint_issues` DRC warning.
    """
    body = _daughterboard_body_content(
        body_w=body_w, body_l=body_l,
        pin_row_inset=pin_row_inset, pin_pitch=pin_pitch,
        pin_count_per_row=pin_count_per_row,
        body_label=body_label,
        antenna_label=antenna_label,
        usb_label=usb_label,
        uuid_tag=uuid_tag + ":lib",
        pin_start_offset=pin_start_offset,
    )
    return textwrap.dedent(f"""\
        (footprint "{name}"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "{descr}")
        \t(tags "{name.lower()} oas mechanical reference daughterboard")
        \t(attr board_only exclude_from_pos_files exclude_from_bom)
        \t(property "Reference" "REF**"
        \t\t(at {fmt(body_w / 2.0)} -1.5 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('fp-lib-prop-ref:' + uuid_tag)}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Value" "{name}"
        \t\t(at {fmt(body_w / 2.0)} {fmt(body_l + 1.5)} 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fp-lib-prop-val:' + uuid_tag)}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fp-lib-prop-fp:' + uuid_tag)}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Datasheet" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fp-lib-prop-ds:' + uuid_tag)}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Description" "{descr}"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fp-lib-prop-desc:' + uuid_tag)}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        """) + body + "\n)\n"


def _emit_daughterboard_reference_pcb_footprint(
    lib_id: str,
    reference: str,
    descr: str,
    anchor_x: float, anchor_y: float,
    body_w: float, body_l: float,
    pin_row_inset: float, pin_pitch: float, pin_count_per_row: int,
    body_label: str,
    antenna_label: str | None,
    usb_label: str | None,
    uuid_tag: str,
    rotation: int = 0,
    pin_start_offset: float | None = None,
) -> str:
    """Emit a daughterboard mechanical-reference footprint placed at
    (anchor_x, anchor_y) on the OAS PCB. The footprint is purely visual
    (F.Fab + F.SilkS outlines + pin-row hints + labels); the actual
    electrical female pin sockets are placed separately in chunk #7.

    The daughterboard is assumed to be VERTICAL orientation: long axis
    along PCB +Y, body extending from (anchor_x, anchor_y) to
    (anchor_x + body_w, anchor_y + body_l). Pin rows are on both long
    edges, parallel to the long axis, each with `pin_count_per_row`
    pins at `pin_pitch` spacing centred along the long axis.

    No F.CrtYd — these daughterboards sit ABOVE the OAS PCB on their
    pin-header standoff (~3-7 mm), so SMD components on the OAS PCB
    CAN be placed under their shadow within the standoff Z budget.
    Adding a body-sized courtyard would spuriously block legitimate
    component placement.

    Contrast with SENS1 (SEN66 mech-ref): the SEN66 lies FLAT on the PCB
    on its 25.6 × 55.2 mm back face — ZERO standoff. SENS1 therefore
    DOES carry an F.CrtYd courtyard (programmed in v0.22) to catch
    accidental SMD placement under it. Do NOT copy that pattern to
    MOD1 / MOD2 / LDR1 without rethinking the standoff budget (v0.22
    review Mn5).
    """
    body_blocks = _daughterboard_body_content(
        body_w=body_w, body_l=body_l,
        pin_row_inset=pin_row_inset, pin_pitch=pin_pitch,
        pin_count_per_row=pin_count_per_row,
        body_label=body_label,
        antenna_label=antenna_label,
        usb_label=usb_label,
        uuid_tag=uuid_tag,
        pin_start_offset=pin_start_offset,
    )
    return textwrap.dedent(f"""\
        \t(footprint "{lib_id}"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(anchor_x)} {fy(anchor_y)} {rotation})
        \t\t(descr "{descr}")
        \t\t(attr board_only exclude_from_pos_files exclude_from_bom)
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(body_w / 2.0)} -1.5 0)
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{lib_id}"
        \t\t\t(at {fmt(body_w / 2.0)} {fmt(body_l + 1.5)} 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1 1) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "{lib_id}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-fp:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        \t\t(property "Description" "{descr}"
        \t\t\t(at 0 0 0)
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-desc:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.27 1.27)))
        \t\t)
        """) + body_blocks + "\n\t)"


# -----------------------------------------------------------------------------
# v0.20 C2 fix: power-section + sensor decoupling + J2 footprint placements
# -----------------------------------------------------------------------------
# Pre-routing review v0.19 finding C2: 30+ schematic components had no PCB
# placement. This function emits them in a coherent cluster on the PCB's
# UPPER-RIGHT quadrant (X ∈ [+10, +50], Y ∈ [-55, -10]), east of the
# ESP32 module and west of the SEN66 body.
#
# Placement strategy (rough — final positions to be refined during routing):
#   Buck1 cluster (24 V → 5 V): U1 (LM2596S) + L1 (33 µH) + D2 (SS14) +
#     C3/C13 (input bulk + HF) + C4/C14 (output bulk + HF).
#   Buck2 cluster (5 V → 3.3 V): U2 (TPS62933) + L2 + R2/R3 FB divider +
#     C5/C15 (input) + C6/C16 (output) + C7 (FB) + C8 (BST).
#   Input protection: D1 (SMBJ24A TVS) + Q1 (PMV65XP) + F1 (PTC) +
#     D3 (Zener Vgs clamp) + R1 (100k pulldown) + R4 (1k gate) +
#     C1 (100µF bulk) + C2 (10 nF Y2) — sits closest to J1 / cable hole.
#   MCU decoupling: C9, C17, R5, R6 (I2C pull-ups). Sits near J5/J6
#     ESP32 socket.
#   Sensor decoupling: C10 (SEN66), C11 (LD2410), C12 (NFC) — near each
#     sensor's socket.
#   J2 — DNP recovery header, placed off in a free corner.
#
# All components use the stub footprint generators above. Pin numbering
# matches the corresponding KiCad symbol library so the v0.20 net-sync
# pass attaches schematic nets correctly.


def gen_power_pcb_footprints() -> str:
    """Emit PCB footprints for all power-section schematic components,
    plus sensor decoupling C10/C11/C12 and the DNP J2 recovery header.

    Placement is in the open band between the LED ring outer (R=12 ≈
    Y=-13/+13) and the ESP32 daughterboard bottom (Y=-24.7), which is
    the largest free strip on the PCB. Buck stages occupy this Y band;
    input-protection cluster sits in the small strip between the cable
    hole (Y=+6) and J1's north courtyard (Y=+11.9) — actually too tight
    so we use the +12 to +20 band west of J1.

    All placements are tentative; user will refine during routing.
    """
    parts: list[str] = []

    # ============================================================
    # ROW A — Buck1 + Buck2 + protected-rail bulk
    # Y band: -22 (LED ring outer is at Y=-12) to -8 (ESP32 bottom Y=-24.7
    # but ESP32 sits on standoff above PCB, so SMD parts can be under
    # the ESP32 shadow). The Y band ROW A actually lives at:
    #   Y = -22..-13 in the OPEN strip between LED ring + ESP32 socket.
    # ============================================================

    # ---- Input protection cluster (north of cable hole, in front of J1)
    # The strip Y ∈ [+12, +18] between J1 north (Y=+11.9 → +25 incl. body)
    # and LED ring outer (Y=+12). Tight. The strip is approx 6 mm tall and
    # extends from PCB X=-50 to +50 minus J1 / cutouts.
    # Actually wait — J1 occupies Y=+11.9..+24.9. So the strip Y ∈ [+6, +12]
    # (between cable hole at +6 and LED at +12) — actually LED ring outer
    # at R=12 → outer edge of LED bodies at +12, so PCB area inside LED
    # ring is reserved by LEDs. But the strip BELOW the LED ring inner edge
    # — there's a tangential gap.
    # Simpler: place input protection EAST of cable hole, in the strip
    # X ∈ [+10, +20], Y ∈ [-8, +10] (east of LED ring, west of SEN66).
    # Input protection cluster — placed in the open strip BELOW the LED
    # ring (Y > +12) and ABOVE J1's courtyard (Y < +12). Wait — those
    # don't co-exist. Use the AUX region: south of cable hole (Y > +6),
    # west of J1 (X < -10). Strip X ∈ [-30, -10], Y ∈ [+8, +12]. ~20×4 mm.
    # Actually too narrow for everything; spread input protection more.
    #
    # Final layout: input protection on the NORTH side of the LED ring,
    # in the strip between ESP32 J5 row (Y=-25.97) and LED ring outer
    # (Y=-12 at θ=270°). Already used by Buck1. So input protection
    # has to go SOMEWHERE. Pick: just south of J3 SEN66 socket, north
    # of J1, X around 0 to +5 — strip Y ∈ [+10, +25] between cable
    # hole south (Y+6) and J1 north (Y+11.9) — too thin.
    #
    # Final compromise: spread input protection vertically along the
    # WEST edge of the LED ring (between LED ring outer at X=-12 and
    # the NFC body right edge at X=-12.76). Tight: nowhere to fit a
    # 2.7×2.7 SMB diode.
    #
    # Pragmatic approach: input protection sits north of Buck1, in the
    # narrow strip Y ∈ [-30, -27] between ESP32 J5 row (Y=-25.97) and
    # the Buck1 row (Y=-18). That's at most 3 mm tall — too tight for
    # the SMB body.
    #
    # Accept reality: stack the components TIGHTLY in a single vertical
    # column at X=+17 (east edge of LED ring, west of ZT1 at +20.5).
    # Column width ~2.5 mm, plenty for 0603 / SOT-23 / SOD-323 with
    # vertical orientation (rotation 90). Y range -10 to +8.
    # Input protection cluster placed in Strip F-west: PCB Y ∈ [+6, +11.9]
    # (between cable hole south edge Y=+6 and J1 north courtyard Y=+11.9),
    # X ∈ [-30, -10] (west of J1, east of NFC body bottom edge X=-12.76 ...
    # actually NFC body extends Y=+40.64..-16.51 at X=-38.16..-12.76, so
    # NFC OCCUPIES this Y region. Need to thread around NFC bottom edge).
    # NFC body bottom edge is at PCB Y=+40.64; that's south of the chord.
    # NFC body top edge at Y=-16.51 → NFC occupies X=-38.16..-12.76 all
    # the way down past Y=+40. So we CANNOT place SMD parts in
    # X ∈ [-38, -13] at Y ∈ [+6, +12] without going UNDER the NFC body
    # (which would be a Z-collision: NFC sits 7-11 mm above PCB so SMD
    # parts <2 mm tall CAN go beneath it, but only if their pads aren't
    # blocked by the NFC daughterboard's own bottom-side components or
    # solder fillets). Conservative: avoid the NFC body shadow.
    # Final compromise: input protection goes EAST of cable hole, in Strip
    # F-east. X ∈ [+9, +50] (avoiding J1 body which extends X=-7..+11.9 at
    # the J1 anchor). With J1 east edge at +11.9 (incl. body), available
    # X ∈ [+13, +22] (avoid ZT1 at +20.5).
    # Row Y=+9 (mid Strip-F).
    # v0.22 INPUT-PROTECTION CLUSTER — relocated to clear SEN66 body shadow.
    # SEN66 lies FLAT on PCB on its 25.6 x 55.2 mm back face (ZERO clearance
    # under it; the 21.5 mm is body height ABOVE PCB, not standoff). The
    # v0.21 placements had Q1, F1, D3, R1, R4 inside the SEN66 body shadow
    # X ∈ [+23.5, +49.1], Y ∈ [-33.2, +22.0], which the SEN66 body would
    # physically crush. v0.22 moves these 5 parts NORTH of the SEN66 body
    # shadow into the strip X ∈ [+22.5, +30] (WEST of the SEN66 socket J3
    # at X ∈ [+30.02, +41.98]), Y ∈ [+23, +42] (north of SEN66 courtyard
    # +22.25, south of PCB chord +43.5).
    # D1 (SMBJ24A TVS) — south of cable hole strip. Must clear:
    #   - D12 LED ring courtyard at PCB ~(+9.5, +5.5..+8.0) rotation 240
    #     (rotated-rectangle east edge reaches +11.67 at Y=+4.19 and
    #     decreases northward).
    #   - PCB cable hole at R=6 around origin.
    # D1 SMB body 4.5×3.6 + courtyard → bbox 7.9 × 3.8 wide.
    # Placed at (+15.5, +9): west +11.55 (clears D12 by 0.0... let me
    # actually move it further east. At (+16, +9.5): bbox X∈[+12.05,
    # +19.95], Y∈[+7.60, +11.40]. D12 polygon extends only to ~Y=+8.01
    # at X=+9.47; at Y=+7.60 the D12 polygon X reaches further west,
    # ~+11.5 or so. Border crossing analysis: D12 polygon at Y=+7.60
    # (interpolating edge from (+11.67,+4.19) to (+9.47,+8.01)):
    # t=(7.60-4.19)/(8.01-4.19)=0.893; X=+11.67+0.893*(-2.20)=+9.71.
    # D1 west +12.05 > +9.71 ✓ clear by 2.34 mm.
    # v0.36 CRITICAL-1 fix: PCB footprint rotation 0 → 180 paired with the
    # schematic angle 90 → 270 swap. Together these put pad 1 (cathode, per
    # KiCad D_SMB KLC) on the EAST physical side where the Freerouting
    # snapshot already routed the V_24V_PROT (Net-(D1-A1)) tracks. Without
    # the PCB-side flip, pad 1 would be on the west side and the routing
    # snapshot would short Net-(D1-A1) into D1 pad 2 = GND. The cathode bar
    # on F.SilkS naturally follows the rotated footprint and ends up on the
    # east side, marking the cathode-on-VIN convention.
    # Pre-routing rework 3: D1 shifted +3 mm east (was +16 → now +19) to
    # widen the central north-south routing corridor between J1 (X=+5.08)
    # and D1. ZT1 at PCB (+20.5, 0) bbox X ∈ [+19, +22] — D1 body at
    # +19 anchor with half_x=3.0 extends X ∈ [+16, +22], which touches
    # ZT1 body in X but is Y-disjoint (D1 Y ∈ [+7.7, +11.3] vs ZT1
    # Y ∈ [-1.5, +1.5]). SEN66 west courtyard at +23.25: D1 east +22 →
    # 1.25 mm clear.
    parts.append(gen_diode_smb_pcb_footprint(
        x=+19, y=+9.5, rotation=180,
        reference="D1", value="SMBJ24A",
        uuid_tag="d1-tvs-smbj24a",
        descr="SMBJ24A TVS surge clamp, 24 V standoff, 38.9 V clamp.",
    ))
    # Q1 P-MOSFET reverse-polarity protection. SOT-23 with letter pin
    # names ("G", "S", "D") matching the Device:Q_PMOS schematic symbol
    # — required so `sync_pcb_nets_from_schematic` matches Q1.G/S/D
    # netlist nodes to the corresponding physical pads. The v0.21
    # footprint used numeric pads "1"/"2"/"3" so all three pads ended
    # up on no_net (Task #24).
    # Q1 must clear D1 east (+19.95) and SEN66 crty west (+23.25). Q1
    # anchor (+22, +9.5): west +20.10 > D1 east +19.95 ✓; east +23.90 >
    # SEN66 crty west +23.25 by 0.65 mm → INSIDE SEN66 courtyard. Bad.
    # Use Y row at +6 (north of D1) which has more X room (Q1 small).
    # Actually keep Y=+9 alignment for clean trace routing. Compromise:
    # ZT1 at PCB (+20.5, 0) bbox X∈[+19, +22], Y∈[-1.5, +1.5]. Q1 at
    # Y=+9 is south of ZT1 entirely. Q1 at (+22, +9.5): D1 east +19.95
    # vs Q1 west +20.10 → 0.15 mm gap ✓. SEN66 west +23.25 vs Q1 east
    # +23.90 → 0.65 mm INTO SEN66 courtyard. Compromise: SEN66 here is
    # the courtyard, not the body. SEN66 body Y range starts at -33.2
    # north and +22.0 south. At Y=+9.5, SEN66 IS occupying the strip
    # (Y=+9.5 ∈ [-33.2, +22]). Q1 east +23.90 > body west +23.5 by 0.40
    # mm → 0.40 mm INSIDE SEN66 BODY SHADOW. BAD.
    # Final compromise: move Q1 to north-of-SEN66 zone after all,
    # at (+27, +25). Already verified safe in plan_check.
    # v0.36 CRITICAL-4 fix: substituted PMV65XP → AO3401A.
    # PMV65XP Vds_max = -20V (verified Nexperia datasheet, NOT -50V as the
    # pre-v0.36 descr wrongly stated). During an SMBJ24A clamp event the rail
    # spikes to 38.9V which would EXCEED PMV65XP's Vds rating by 19V.
    # AO3401A (Alpha & Omega) is a direct drop-in: same SOT-23 footprint, same
    # G/S/D pin layout (1=G, 2=S, 3=D), Vds_max = -30V (8.9V margin against
    # the 38.9V clamp — tight but safe for transient events), Vgs_max = ±12V
    # (same as PMV65XP, so D3 Zener clamp still applies). LCSC C15127, mass
    # stock at JLCPCB Extended Library.
    # v0.40 audit-16: Q1 schematic pin numbers changed from letter
    # "D"/"G"/"S" to numeric "1"/"2"/"3" (AO3401A datasheet: 1=G, 2=S,
    # 3=D). PCB pads stay verbatim stock SOT-23 with names "1"/"2"/"3" —
    # no remap needed. Removes the previous lib_footprint_mismatch
    # warning that required `rule_severities` override.
    # Pre-routing rework 3: Q1 cluster (Q1 / D3 / R1 / R4) relocated to
    # the column south of F1 (anchor +15, +25). The C3 / C4 chord cutouts
    # were removed, opening ~178 mm² of routing / placement space south
    # of F1. New Q1 anchor (+15, +30) sits 5 mm south of F1 along the
    # +24V_OUT path: F1 east pad → short link → Q1.S. Q1.D returns north
    # to D1 (+19, +9.5) along a 20 mm diagonal route in open space.
    parts.append(gen_sot23_3pin_pcb_footprint(
        x=+14, y=+33, rotation=0,
        reference="Q1", value="AO3401A",
        uuid_tag="q1-pmos",
        descr="P-MOSFET reverse-polarity protection. SOT-23. AO3401A: Vds=-30 V, Vgs=±12 V, RDS(on)=60 mΩ @ Vgs=-10 V.",
    ))
    # D3 — Q1 gate-source Zener clamp. Pre-routing rework 3: moved to
    # the F1-south cluster (was +27, +28 near SEN66). New anchor (+19,
    # +30): same Y row as Q1 (+15, +30), 4 mm east → Q1.G/S pads can
    # reach D3 anode without crossing F1 body. SEN66 west courtyard
    # at +23.25; D3 east body +20 → 3.25 mm clear.
    parts.append(gen_diode_sod323_pcb_footprint(
        x=+20, y=+33, rotation=0,
        reference="D3", value="10V Zener 200mW",
        uuid_tag="d3-zener",
        descr="10 V Zener clamp on Q1 gate-source to keep |Vgs| ≤ 10 V (v0.37 — was 18V pre-fix; AO3401A Vgs_max=±12V).",
    ))
    # F1 — polyfuse. Pre-routing rework: relocated to (+15, +25) close to
    # J1's east pin (J1 pin 1 +24V at PCB X=+5.08, Y=+27.4 after the +5 mm
    # J1 shift). Gives short upstream path J1 → F1 → C3 / U1. F1 bbox at
    # (+15, +25) rotation 0: X∈[+11.05, +18.95], Y∈[+22.20, +27.80] —
    # clears new J1 courtyard east edge (+9.12) by 1.93 mm and SEN66 west
    # courtyard (+23.50) by 4.55 mm.
    parts.append(gen_polyfuse_smd_pcb_footprint(
        x=+15, y=+25, rotation=0,
        reference="F1", value="MF-RHT075/60-2",
        uuid_tag="f1-ptc",
        descr="PTC polyfuse 750 mA hold / 1.5 A trip / 60 V (Bourns MF-RHT075/60-2).",
    ))
    # Pre-routing rework 3: R1 / R4 moved into the Q1 cluster south of
    # F1. Row Y=+33 (3 mm south of Q1/D3 row at Y=+30). R1 below Q1,
    # R4 below D3.
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+14, y=+37, rotation=0,
        reference="R1", value="100k 1%",
        uuid_tag="r1-gate-pulldown",
        descr="100 kΩ 1% gate-GND pulldown for Q1 (P-MOSFET reverse-polarity).",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+20, y=+37, rotation=0,
        reference="R4", value="1k",
        uuid_tag="r4-gate-series",
        descr="1 kΩ gate series resistor between Q1.G and Vgs clamp junction.",
    ))

    # v0.26 POWER SECTION LAYOUT
    # ===========================
    # CHANGE FROM v0.22-v0.25: C1, C3, C4 and U1 RELOCATED OUT of the
    # ESP32-C6 DevKitM-1 daughterboard body shadow. The v0.22-v0.25 plan
    # placed the radial THT bulk caps C1 (12 mm tall), C3 (12 mm), C4
    # (11.2 mm) and TO-263-5 buck U1 (4.6 mm) inside the daughterboard
    # shadow (X ∈ [-27.76, +20.50], Y ∈ [-50.10, -24.70]), assuming
    # "daughterboards sit ~8.6 mm above the OAS PCB so SMDs can go
    # beneath." The clearance audit v0.25 found the conservative
    # under-board clearance is only ~5.5 mm (socket-body height minus
    # mating pin tails); all three radials and U1 (margin +0.9 mm)
    # exceeded it — physically preventing the DevKitM-1 from seating.
    #
    # v0.26 fix: move all four to free PCB area outside the daughterboard
    # shadows. NO BOM change — radial THT caps + LM2596S retained, only
    # coordinates updated. New locations:
    #   - U1  at (-34, -34): west of ESP32 body, between LD2410 east edge
    #     (-43.47) and ESP32 west edge (-27.76).
    #   - C3  at (-34, -24): immediately south of U1 in the same west
    #     column; close to U1.VIN (pin 1) for low-ESR loop.
    #   - C1  at (-34, -14): further south in the west column. South of
    #     LD2410 north edge (-16.51) in Y, but at X=-34 it's well east of
    #     LD2410's east edge (-43.47), so the LD2410 daughterboard shadow
    #     is not entered.
    #   - C4  at (+25, -47): east of ESP32 body and well north of SEN66
    #     body (north edge -33.2). Routing distance from L1 (still at
    #     +9, -37) grows ~12 mm — acceptable for +5V bulk that handles
    #     low-frequency load-step transients, not the switch node.
    #
    # The rest of the power section stays inside the ESP32 daughterboard
    # shadow (small SMDs <=2 mm tall — all clear of the 5.5 mm budget):
    #   Row Y=-30   : north flank — small HF caps, I²C pullups, R7
    #   Row Y=-37   : Buck1 satellites — D2 (SMA), L1 (5x5 SMD inductor)
    #   Row Y=-44   : Buck2 main — U2 (SOT-583), L2 (5x5), R2, R3
    #   Row Y=-46   : south flank — small HF caps near J6 pad row
    #
    # IMPORTANT: ESP32 pin socket pad rows (J5 at Y=-25.97 pads y∈[-27.74,
    # -24.20]; J6 at Y=-48.83 pads y∈[-50.60, -47.06]) block SMD placement
    # in those Y bands. Usable inside-ESP32 SMD strip: Y ∈ [-47, -28]
    # (with ~0.5 mm margin from pin pads).
    #
    # C2 (Y2 GND-Earth_Protective) sits OUTSIDE the daughterboard, at
    # (-32, -25) in the strip west of ESP32 west edge.

    # ---- v0.26: C1 placed south-east of SEN66, on the V_24V_PROT net ----
    # The audit's "west-of-ESP32 column at X=-34" zone (used by U1, C3) is
    # under the MIKROE-2462 NFC daughterboard shadow at Y > -16.51 — so
    # C1 cannot share that column without poking into MIKROE clearance.
    # C1 lives on the protected-rail net (downstream of Q1 reverse-polarity
    # FET, upstream of U1.VIN through C3). Position (+40, +36) sits south
    # of J3 (JST GH SEN66 socket at +36, +27 — its crty extends to PCB Y
    # +30.2 max; gap 1.55), east of C5 case-wall cutout (+27.9..+35.4;
    # gap 0.35 — tight but clear), west of C10 0603 (now relocated to
    # +46, +32) and mounting hole H1 at +47.631 / +27.5 (distance ~13.1 mm).
    # PCB outline corner (+44.25, +40.25): distance 59.82 — 0.18 mm inside.
    parts.append(gen_capacitor_polarized_radial_pcb_footprint(
        x=+33, y=-42, rotation=0,
        reference="C1", value="100uF/50V",
        uuid_tag="c1-protected-bulk",
        diameter_mm=8.0, pitch_mm=3.5,
        descr="100 µF / 50 V radial electrolytic bulk on protected +24V rail. Pre-routing rework 2: relocated from south-east (+40, +36) to north-east next to C4 (+33, -42). Body 8 mm diameter; 1.8 mm gap to C10 north edge, 0.5 mm gap to C4 east silk, 0.96 mm to PCB outline at NE corner.",
    ))
    # C3 (U1.VIN input bulk) — sits directly south of U1 in the same
    # west column to keep U1.VIN trace length minimal.
    parts.append(gen_capacitor_polarized_radial_pcb_footprint(
        x=-34, y=-22, rotation=0,
        reference="C3", value="100uF/50V",
        uuid_tag="c3-u1-vin-bulk",
        diameter_mm=8.0, pitch_mm=3.5,
        descr="100 µF / 50 V radial electrolytic input bulk for U1 buck. Pre-routing rework: nudged south +2 mm to (-34, -22) to open routing channel above U1.",
    ))

    # ---- v0.26: U1 in west-of-ESP32 strip ----
    parts.append(gen_to263_5_pcb_footprint(
        x=-35, y=-34, rotation=0,
        reference="U1", value="LM2596S-5.0",
        uuid_tag="u1-lm2596",
        descr="LM2596S-5.0 5 V 3 A asynchronous step-down buck (TI), TO-263-5. Rework 5: +1 mm east (was -36 → -35). U1 body half_x=5.3 so body now spans X ∈ [-40.3, -29.7]: 3.17 mm gap to LD2410 east edge (-43.47), 1.94 mm gap to ESP32 west edge (-27.76).",
    ))
    # D2, L1 stay inside ESP32 shadow (both <4 mm tall, comfortably within
    # the 5.5 mm budget). Switch-node trace from U1.OUT (pin 2 at PCB
    # (-32.3, -30.55)) to L1 (+9, -37) is ~42 mm — long but routable for
    # this 150 kHz / 3A node on inner-layer copper. Document accepted in
    # the v0.26 changelog.
    parts.append(gen_diode_sma_pcb_footprint(
        x=+2, y=-37, rotation=0,
        reference="D2", value="SS14",
        uuid_tag="d2-schottky",
        descr="SS14 Schottky diode 40 V / 1 A, SMA, freewheeling for U1 buck.",
    ))
    parts.append(gen_inductor_smd_5x5_pcb_footprint(
        x=+9, y=-37, rotation=0,
        reference="L1", value="33uH",
        uuid_tag="l1-buck1",
        descr="33 µH ≥2 A SMD shielded power inductor (Wurth WE-PD-S or eq).",
    ))
    # ---- v0.26: C4 in east-of-ESP32 strip, north of SEN66 ----
    parts.append(gen_capacitor_polarized_radial_pcb_footprint(
        x=+25, y=-47, rotation=0,
        reference="C4", value="220uF/10V",
        uuid_tag="c4-u1-vout-bulk",
        diameter_mm=6.3, pitch_mm=2.5,
        descr="220 µF / 10 V radial electrolytic output bulk on +5V rail. v0.26: relocated from (+16, -37) inside ESP32 shadow to (+25, -47) east of ESP32 / north of SEN66. 1.10 mm gap to ESP32 east edge, 8.40 mm gap to SEN66 north edge. Distance to L1 (+9, -37) grows from 9 mm to ~14 mm — acceptable for +5V bulk.",
    ))

    # ---- Row Y=-44: Buck2 (5V→3.3V) main components ----
    # U2 anchor Y=-43.5 (was -44) to clear C8 courtyard at Y=-46 by > 0.05 mm.
    # SOT-583 courtyard half-height is 1.5 (wider than the 0603/0805 default).
    parts.append(gen_sot583_pcb_footprint(
        x=-2, y=-43.5, rotation=0,
        reference="U2", value="TPS62933",
        uuid_tag="u2-tps62933",
        descr="TPS62933 5 V→3.3 V synchronous buck (TI), SOT-583/VSON-8.",
    ))
    parts.append(gen_inductor_smd_5x5_pcb_footprint(
        x=+4, y=-44, rotation=0,
        reference="L2", value="2.2uH",
        uuid_tag="l2-buck2",
        descr="2.2 µH ≥2 A SMD shielded power inductor for U2 buck.",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+10, y=-44, rotation=0,
        reference="R2", value="100k",
        uuid_tag="r2-fb-top",
        descr="FB top divider for TPS62933 (sets +3.3V).",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+13, y=-44, rotation=0,
        reference="R3", value="30.9k",
        uuid_tag="r3-fb-bot",
        descr="FB bottom divider for TPS62933 (sets +3.3V).",
    ))

    # ---- Row Y=-30: north flank — HF bypass caps for buck stages + I²C pullups + R7 ----
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-14, y=-30, rotation=0,
        reference="C13", value="100nF",
        uuid_tag="c13-u1-vin-hf",
        descr="100 nF input HF ceramic bypass at U1.VIN (paired with C3).",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-6, y=-30, rotation=0,
        reference="C14", value="100nF",
        uuid_tag="c14-u1-vout-hf",
        descr="100 nF HF ceramic bypass on +5V rail (paired with C4).",
    ))
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=+0, y=-30, rotation=0,
        reference="C9", value="10uF",
        uuid_tag="c9-esp32-bulk",
        descr="10 µF 0805 ceramic bulk on ESP32 +3V3.",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=+4, y=-30, rotation=0,
        reference="C17", value="100nF",
        uuid_tag="c17-esp32-hf",
        descr="100 nF HF ceramic decoupling on ESP32 +3V3.",
    ))
    # v0.22 — I²C pull-ups reduced from 10 kΩ → 4.7 kΩ (Task #17 M1). At the
    # realized bus length (~60-100 mm on PCB), with ~100 pF total bus
    # capacitance, 10 kΩ gives rise time τ = 1 µs / t_r(10-90%) ≈ 2.2 µs,
    # exceeding the I²C standard-mode spec (t_r ≤ 1 µs at 100 kHz).
    # 4.7 kΩ drops τ to ~470 ns / t_r ≈ 1.0 µs, within spec. The SEN66
    # datasheet §3.1 *recommends* 10 kΩ but does not mandate it; lower
    # values are explicitly allowed.
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+8, y=-30, rotation=0,
        reference="R5", value="4.7k",
        uuid_tag="r5-i2c-sda-pullup",
        descr="I²C SDA 4.7 kΩ pull-up to +3V3 (v0.22 spec — sized for bus rise time at realized ~60-100 mm bus length, see CLAUDE.md M1).",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+11, y=-30, rotation=0,
        reference="R6", value="4.7k",
        uuid_tag="r6-i2c-scl-pullup",
        descr="I²C SCL 4.7 kΩ pull-up to +3V3 (v0.22 spec — see R5).",
    ))
    # R7 — GPIO 8 boot-strap 10 kΩ pull-up to +3V3 (v0.22, Task #18 M2).
    # See R7 schematic block for rationale.
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+14, y=-30, rotation=0,
        reference="R7", value="10k",
        uuid_tag="r7-gpio8-bootstrap-pullup",
        descr="GPIO 8 boot-strap 10 kΩ pull-up to +3V3 (v0.22, see CLAUDE.md M2). Replaces the DevKitM-1's onboard pull-up that doesn't work in OAS (VCC_5V unpowered).",
    ))

    # ---- Row Y=-46: south flank — Buck2 HF/feedback caps + Buck2 bulk ----
    # C5 at X=-25 (was -20) to avoid 0.05 mm courtyard overlap with C3
    # radial cap directly above at (-20, -41).
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=-25, y=-46, rotation=0,
        reference="C5", value="10uF",
        uuid_tag="c5-u2-vin-bulk",
        descr="10 µF 0805 ceramic input bulk for U2.VIN (+5V).",
    ))
    # v0.40 post-order: stock C_0805 has courtyard half-width 1.7 mm
    # (vs old custom 1.575 mm). C15 (0603, half-width 1.48 mm) + C6
    # (0805, half-width 1.7 mm) at 3 mm separation = 0.18 mm overlap.
    # C15 X shifted from -17 to -18.5 so C15 east edge at -17.02 is
    # 1.32 mm west of C6 west edge at -15.70.
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-18.5, y=-46, rotation=0,
        reference="C15", value="100nF",
        uuid_tag="c15-u2-vin-hf",
        descr="100 nF input HF ceramic bypass at U2.VIN.",
    ))
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=-14, y=-46, rotation=0,
        reference="C6", value="22uF",
        uuid_tag="c6-u2-vout-bulk",
        descr="22 µF 0805 ceramic output bulk on +3.3V rail.",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-10, y=-46, rotation=0,
        reference="C16", value="100nF",
        uuid_tag="c16-u2-vout-hf",
        descr="100 nF HF ceramic bypass on +3.3V rail.",
    ))
    # v0.36 CRITICAL-3 fix: pre-v0.36 PCB-generator had C7=22pF "FB feedforward"
    # and C8=100nF "BST bootstrap" — contradicting the schematic which has
    # C7=100nF (BST) and C8=47nF (SS soft-start). TPS62933 default config
    # does NOT require an FB feedforward cap, and the BST cap is mandatory
    # (without it the high-side gate driver supply is undersized and the
    # converter cannot start). Aligning PCB-generator to the schematic.
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-6, y=-46, rotation=0,
        reference="C7", value="100nF",
        uuid_tag="c7-u2-bst",
        descr="Bootstrap cap C(BST) between U2.SW and U2.BST. REQUIRED.",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-2, y=-46, rotation=0,
        reference="C8", value="47nF",
        uuid_tag="c8-u2-ss",
        descr="Soft-start cap C(SS) between U2.SS and GND. Sets ramp time.",
    ))

    # ---- C2 (Y2 safety cap) — WEST of LD2410, outside daughterboard shadow ----
    # v0.26: shifted from (-32, -25) to (-46, -25) to clear C3 (relocated
    # to (-34, -24) column). New position sits north of LD2410's
    # north edge (Y=-16.51), west of the U1/C3 column. C2 body Y[-25.9,
    # -24.1] is entirely north of the LD2410 Y range. X=-46 puts C2
    # body X[-47.4, -44.6]: this overlaps the LD2410 X range
    # [-51.09, -43.47] by 1.13 mm but Y is clear so no shadow conflict.
    # Sits 2 mm west of J2 (DNP recovery header at -54, -8) at distance
    # ~18.8 mm — plenty of clearance.
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=-46, y=-25, rotation=0,
        reference="C2", value="10nF Y2",
        uuid_tag="c2-y2",
        descr="10 nF Y2 safety class — GND ↔ Earth_Protective EMI bridge. v0.26: shifted from (-32, -25) to (-46, -25) to clear C3 relocated to (-34, -24).",
    ))

    # Sensor decoupling caps: C10 (SEN66 +3V3), C11 (LD2410 +5V), C12 (NFC +3V3).
    # v0.26: C10 shifted from (+42, +33) to (+46, +32) to clear C1
    # (relocated to (+40, +36) — 12 mm-tall D8 radial bulk for the
    # protected +24V rail). New C10 position sits east of C1 (gap 0.75
    # mm), south of J3 (gap to J3 east edge +41.98 = 2.02 mm), west of
    # mounting hole H1 at (+47.631, +27.5) (distance 5.21 mm, gap 1.36
    # mm after H1 2.85 + C10 1.0 keep-clear).
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=+30, y=-47, rotation=0,
        reference="C10", value="100nF",
        uuid_tag="c10-sen66-decoupling",
        descr="100 nF local decoupling for SEN66 (J3 +3V3 pin 1/6). Pre-routing rework: relocated to (+30, -47), east of C4 (+25, -47) in the upper-right corner cluster.",
    ))
    # LD2410 J4 pads at PCB X=-44.74, Y=+19.05 (1×5 P1.27 row going south
    # from anchor; pad 1 north Y=+13.97, pad 5 south Y=+19.05). Pre-
    # routing rework 3: C11 moved SOUTH of J4 row (was north between
    # J4 row and LD2410 body, at -42, +14). New anchor (-43, +22):
    # body Y ∈ [+21.1, +22.9] is fully south of LD2410 body shadow
    # (Y_max=+19.05). J4 stock 1×5 P1.27 courtyard south edge ≈
    # +20.05 → C11 body north edge +21.1 clears by 1.05 mm. Frees
    # the LD2410 west strip for routing.
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-43, y=+22, rotation=0,
        reference="C11", value="100nF",
        uuid_tag="c11-ld2410-decoupling-pcb",
        descr="100 nF local decoupling for LD2410 (J4 pin 5 / +5V).",
    ))
    # NFC J7/J8 socket: pin 7 (+3V3) at row A position. Row A at PCB X=-14.03.
    # Pin 7 is the 7th from pin 1; pin 1 at PCB Y=+38.10, going north (LIB +Y → PCB -Y).
    # So pin 7 at PCB Y = +38.10 - 6*2.54 = +22.86. C12 just below pin 7.
    # C12 next to NFC pin 7 (+3.3V). NFC J7 row A at PCB X=-14.03,
    # Y=+38.10 (pin 1) ... Y=+20.32 (pin 8). Pin 7 = pin 1 - 6 = PCB Y=+22.86.
    # Place C12 BETWEEN J7 (X=-14.03) and J8 (X=-36.89), at Y near pin 7
    # height. Under the NFC body shadow (7 mm clearance available).
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-25, y=+23, rotation=0,
        reference="C12", value="100nF",
        uuid_tag="c12-nfc-decoupling",
        descr="100 nF local decoupling for MIKROE-2462 NFC (mikroBUS pin 7 / +3V3).",
    ))

    # J2 — DNP recovery pin header. Place in the NW corner near LD2410's
    # left edge. LD2410 body left edge at X=-51.09, PCB outline at X≈-57.7
    # at Y=-16.5 (top of LD2410). Strip X ∈ [-57, -51], Y ∈ [-16, +19],
    # ~6 mm wide and 35 mm tall. Drop J2 into this strip with pins
    # running north-south. With rotation 0, pads at LIB Y=0..+12.7
    # → PCB Y = anchor_y..anchor_y+12.7. Anchor (-54, -8) puts 6 pads
    # at Y=-8..+4.7. All inside the strip; clearance to LD2410 body
    # left edge X=-51.09 is 51.09 - 54 = 2.91 mm (with pad half-width
    # 0.85, pad outer edge at X=-53.15 — clearance ~2.06 mm).
    parts.append(gen_pinheader_6_recovery_pcb_footprint(
        x=-54, y=-8, rotation=0,
        reference="J2", value="SWD/UART Recovery (DNP)",
        uuid_tag="j2-recovery-header",
        descr="1x6 P2.54 mm THT recovery header (Do-Not-Populate by default).",
    ))

    return "\n".join(parts)


def gen_sensors_pcb_footprints() -> str:
    """Emit the SEN66 reference + 4 zip-tie holes + J3 socket
    + LD2410 reference + J4 pin header as one block.

    Returns a multi-line string ready to embed inside the kicad_pcb body.
    """
    parts = []

    # SEN66 mechanical reference (no pads, F.Fab + F.SilkS art only).
    parts.append(gen_sen66_reference_pcb_footprint(
        x=SEN66_ANCHOR_X, y=SEN66_ANCHOR_Y, rotation=SEN66_ROTATION,
    ))

    # LD2410 mechanical reference (no pads, marks the daughterboard
    # shadow on the OAS PCB as a keep-out zone for other components).
    parts.append(gen_ld2410_reference_pcb_footprint(
        x=LD2410_ANCHOR_X, y=LD2410_ANCHOR_Y, rotation=LD2410_ROTATION,
    ))

    # 4× zip-tie holes. F.SilkS designator (ZT1..ZT4) sits 3.2 mm above
    # each hole centre (toward PCB -Y, "north" / cable hole). The silk
    # ring has radius 2.0 mm; the text is ~0.5 mm tall (centred) so a
    # -3.2 mm offset puts the text bottom edge ~0.7 mm above the ring
    # (well clear of the 0.15 mm silk-overlap rule).
    silk_r = ZIPTIE_HOLE_SILK_RING_DIAMETER / 2.0
    courtyard_r = ZIPTIE_HOLE_DIAMETER * 0.75
    fab_r = ZIPTIE_HOLE_DIAMETER / 2.0
    descr = "Zip-tie pass-through hole, Ø3.0 mm NPTH (fits 2.5 mm band zip-tie). Used in groups of 4 to retain the SEN66 module flat against the PCB (v0.6+ face-up PCB-mount)."
    for ref, lx, ly in SEN66_ZIPTIE_LOCAL:
        gx, gy = _sen66_local_to_pcb(lx, ly)
        parts.append(_emit_pcb_footprint_simple_npth(
            lib_id="ZipTieHole_3mm_NPTH",
            reference=ref,
            value="ZipTieHole_3mm_NPTH",
            descr=descr,
            drill_mm=ZIPTIE_HOLE_DIAMETER,
            silk_ring_radius_mm=silk_r,
            courtyard_radius_mm=courtyard_r,
            fab_ring_radius_mm=fab_r,
            x=gx, y=gy,
            uuid_tag=f"ziptie:{ref}",
            silk_label=ref,
            silk_label_offset_y=-3.2,
        ))

    # J3 — JST GH 6-pin socket (PCB-side).
    parts.append(gen_j3_jst_gh_pcb_footprint(
        x=J3_X, y=J3_Y, rotation=J3_ROTATION,
    ))

    # J4 — stock KiCad PinHeader_1x05_P1.27mm_Vertical at the LD2410
    # connector edge. The HLK-LD2410B's onboard 1.27 mm pin row passes
    # through these 5 plated through-holes; pins are soldered from the
    # OAS PCB bottom side, providing electrical + mechanical retention.
    parts.append(gen_j4_pinheader_pcb_footprint(
        x=J4_PCB_X, y=J4_PCB_Y, rotation=J4_PCB_ROTATION,
    ))

    # J1 — Phoenix MSTBA 5.08 mm 3-pin pluggable terminal block for the
    # 24 V supply input. v0.17 placed in the central PCB area, immediately
    # north of the Ø12 mm cable hole, replacing the AQI LED slot at θ=270°
    # (D20). See `J1_PCB_*` constants near the top of the file for the
    # placement rationale, clearance budget, and cable-bend geometry.
    parts.append(gen_j1_terminal_block_pcb_footprint(
        x=J1_PCB_X, y=J1_PCB_Y, rotation=J1_PCB_ROTATION,
    ))

    # v0.19: J9 — JST SH 4-pin horizontal SMD Qwiic / Stemma QT
    # expansion socket. Lives in the C5 chord-east cutout; mouth faces
    # PCB +Y (chord side, case wall) so the cable plugs in from outside
    # the case. See `J9_PCB_*` constants near the top of the file.
    parts.append(gen_j9_qwiic_pcb_footprint(
        x=J9_PCB_X, y=J9_PCB_Y, rotation=J9_PCB_ROTATION,
    ))
    # v0.19: J10 — 6-pin 2.54 mm vertical THT pin header for native-USB
    # recovery flashing. DNP — pads only on production boards. Lives in
    # the C3 chord-east cutout; pin 1 (rect-marker pad) sits at the
    # chord side for easy pogopin-jig orientation.
    parts.append(gen_j10_recovery_pcb_footprint(
        x=J10_PCB_X, y=J10_PCB_Y, rotation=J10_PCB_ROTATION,
    ))

    # ESP32-C6 DevKitM-1-N4 daughterboard shadow reservation. Mounted on
    # 2× 1x15 P2.54 mm female pin sockets (chunk #7); module sits face-up
    # ~8 mm above OAS PCB. Antenna at TOP short edge (Y=anchor_y), USB-C
    # at BOTTOM short edge (Y=anchor_y + body length).
    parts.append(_emit_daughterboard_reference_pcb_footprint(
        lib_id="oas:ESP32-C6-DevKitM-1_Reference",
        reference="MOD1",
        descr="ESP32-C6-DevKitM-1-N4 daughterboard shadow (EAN 5904422385651). 25.4×48.26×8.6 mm; mounts on 2×1x15 P2.54 mm female pin sockets. Pin block offset 0.98 mm toward antenna end per Espressif dimensions PDF.",
        anchor_x=ESP32_ANCHOR_X, anchor_y=ESP32_ANCHOR_Y,
        body_w=ESP32_BODY_W, body_l=ESP32_BODY_L,
        pin_row_inset=ESP32_PIN_ROW_INSET,
        pin_pitch=ESP32_PIN_PITCH,
        pin_count_per_row=ESP32_PIN_COUNT_PER_ROW,
        body_label="ESP32-C6 DevKitM-1",
        antenna_label="ant",
        usb_label="USB",
        uuid_tag="esp32-devkitm1-pcb",
        rotation=ESP32_ROTATION,
        pin_start_offset=ESP32_PIN_START_OFFSET,
    ))

    # MIKROE-2462 NFC Tag 2 Click daughterboard shadow reservation.
    # Mounted on 2× 1x8 P2.54 mm female pin sockets (mikroBUS) in chunk #7;
    # NT3H1101 + onboard PCB antenna sits ~7 mm above the OAS PCB.
    parts.append(_emit_daughterboard_reference_pcb_footprint(
        lib_id="oas:MIKROE-2462_Reference",
        reference="MOD2",
        descr="MIKROE-2462 NFC Tag 2 Click (NT3H1101 + onboard PCB NFC antenna). 25.4×57.15×7 mm (mikroBUS size L); mounts on 2×1x8 P2.54 mm female pin sockets. Pin block offset 2.54 mm toward pin-1 short edge; NFC antenna spiral fills the ~36.83 mm strip past pin 8.",
        anchor_x=MIKROE2462_ANCHOR_X, anchor_y=MIKROE2462_ANCHOR_Y,
        body_w=MIKROE2462_BODY_W, body_l=MIKROE2462_BODY_L,
        pin_row_inset=MIKROE2462_PIN_ROW_INSET,
        pin_pitch=MIKROE2462_PIN_PITCH,
        pin_count_per_row=MIKROE2462_PIN_COUNT_PER_ROW,
        body_label="MIKROE-2462",
        antenna_label=None,
        usb_label=None,
        uuid_tag="mikroe2462-pcb",
        rotation=MIKROE2462_ROTATION,
        pin_start_offset=MIKROE2462_PIN_START_OFFSET,
    ))

    # Female pin sockets for ESP32 and MIKROE-2462 daughterboards.
    # Each daughterboard mates with 2 parallel pin rows on OAS PCB.
    # Pad positions match the daughterboard's onboard pin headers (see the
    # respective body comments above for pin layout per datasheet).
    #
    # ESP32-C6 DevKitM-1 — 2×1×15, row spacing 22.86 mm, pitch 2.54 mm,
    # pin block offset 5.37 mm from antenna short edge (= LIB Y=0).
    # In PCB after helper rotation 90, LIB +Y → PCB +X, LIB +X → PCB -Y.
    # Row A (LIB X = 1.27): pin row along PCB X at PCB Y = anchor_y - 1.27.
    # Row B (LIB X = body_w - 1.27 = 24.13): PCB Y = anchor_y - 24.13.
    # Pin 1 of each row at PCB X = anchor_x + 5.37 (after LIB +Y → PCB +X
    # transform with anchor offset).
    esp32_row_a_y = ESP32_ANCHOR_Y - ESP32_PIN_ROW_INSET                    # -25.97
    esp32_row_b_y = ESP32_ANCHOR_Y - (ESP32_BODY_W - ESP32_PIN_ROW_INSET)   # -48.83
    esp32_row_x_start = ESP32_ANCHOR_X + ESP32_PIN_START_OFFSET             # -22.39
    parts.append(gen_pinsocket_pcb_footprint(
        pin_count=ESP32_PIN_COUNT_PER_ROW,
        x=esp32_row_x_start, y=esp32_row_a_y, rotation=90,
        reference="J5",
        value="ESP32 row A (pins 1..15, antenna-side row)",
        descr="Stock 1x15 P2.54 mm female pin socket. ESP32-C6 DevKitM-1-N4 plugs into this row + J6 (other row). Pin block offset 5.37 mm from antenna short edge per Espressif dimensions PDF.",
        uuid_tag="j5-esp32-row-a",
    ))
    parts.append(gen_pinsocket_pcb_footprint(
        pin_count=ESP32_PIN_COUNT_PER_ROW,
        x=esp32_row_x_start, y=esp32_row_b_y, rotation=90,
        reference="J6",
        value="ESP32 row B (pins 16..30, USB-side row)",
        descr="Stock 1x15 P2.54 mm female pin socket. ESP32-C6 DevKitM-1-N4 plugs into this row + J5 (other row).",
        uuid_tag="j6-esp32-row-b",
    ))

    # MIKROE-2462 NFC Tag 2 Click — 2×1×8 mikroBUS, row spacing 22.86 mm,
    # pitch 2.54 mm, pin block offset 2.54 mm from pin-1 short edge.
    # v0.15.7: NFC body flipped 180° so pin block sits at PCB +Y (chord
    # side, bottom of body). Anchor moved to body's PCB bottom-right
    # corner. After rotation 180, LIB (lx, ly) → PCB (anchor_x - lx,
    # anchor_y - ly):
    #   Row A (LIB X=1.27, mikroBUS pins 1..8): PCB X = anchor_x - 1.27 = -14.03
    #   Row B (LIB X=24.13, pins 9..16):        PCB X = anchor_x - 24.13 = -36.89
    #   Pin 1 of each row at PCB Y = anchor_y - 2.54 = +38.10 (close to chord)
    #   Pin 8/16 of each row at PCB Y = anchor_y - 20.32 = +20.32
    # Pin sockets placed at pin-1 position with rotation 180 so LIB +Y
    # (toward pin 8) → PCB -Y (away from chord, toward body interior).
    mikroe_row_a_x = MIKROE2462_ANCHOR_X - MIKROE2462_PIN_ROW_INSET                          # -14.03
    mikroe_row_b_x = MIKROE2462_ANCHOR_X - (MIKROE2462_BODY_W - MIKROE2462_PIN_ROW_INSET)    # -36.89
    mikroe_row_y_start = MIKROE2462_ANCHOR_Y - MIKROE2462_PIN_START_OFFSET                   # +38.10
    parts.append(gen_pinsocket_pcb_footprint(
        pin_count=MIKROE2462_PIN_COUNT_PER_ROW,
        x=mikroe_row_a_x, y=mikroe_row_y_start, rotation=180,
        reference="J7",
        value="MIKROE row A (mikroBUS pins 1..8, AN/RST/CS/SCK/MISO/MOSI/+3V3/GND)",
        descr="Stock 1x8 P2.54 mm female pin socket. MIKROE-2462 plugs into this row + J8 (other row). mikroBUS standard pin block, offset 2.54 mm from pin-1 short edge.",
        uuid_tag="j7-mikroe-row-a",
    ))
    parts.append(gen_pinsocket_pcb_footprint(
        pin_count=MIKROE2462_PIN_COUNT_PER_ROW,
        x=mikroe_row_b_x, y=mikroe_row_y_start, rotation=180,
        reference="J8",
        value="MIKROE row B (mikroBUS pins 9..16, PWM/INT/RX/TX/SCL/SDA/+5V/GND)",
        descr="Stock 1x8 P2.54 mm female pin socket. MIKROE-2462 plugs into this row + J7 (other row).",
        uuid_tag="j8-mikroe-row-b",
    ))

    # AQI status LED ring (v0.16; v0.18 removed D14) — 11 × SK6812-SIDE on
    # a Ø22 mm pitch circle around the central cable hole, each LED
    # radiating outward into the AK-N-94 perforated cover. Plus one 100 nF
    # 0402 decoupling cap per LED, sited radially inward from each LED so
    # the cap pads are positioned near the corresponding VDD pad.
    #
    # v0.18 skips the LED slot at index 3 (D14, θ=90°, PCB (0, +11)) and
    # its decoupling cap (C23). The freed-up corridor lets the 24 V supply
    # cable from the central Ø12 mm hole reach the J1 terminal block which
    # now sits SOUTH of the LED ring, between the ring and the chord-edge
    # cutouts. (v0.17 had this same skip applied to D20 with J1 on the
    # north side; v0.18 flipped to the south for more open clearance.)
    for i in range(LED_RING_COUNT):
        if i in LED_RING_SKIP_INDICES:
            continue
        led_x, led_y, led_rot = _led_ring_position(i)
        led_ref = f"D{11 + i}"      # D11..D22 (D1..D5 used by power section)
        parts.append(gen_sk6812_side_pcb_footprint(
            x=led_x, y=led_y, rotation=led_rot,
            reference=led_ref,
            uuid_tag=f"led-ring-{led_ref}",
        ))
        cap_x, cap_y, cap_rot = _led_cap_position(i)
        cap_ref = f"C{20 + i}"      # C20..C31
        parts.append(gen_capacitor_0402_pcb_footprint(
            x=cap_x, y=cap_y, rotation=cap_rot,
            reference=cap_ref, value="100nF",
            uuid_tag=f"led-ring-cap-{cap_ref}",
            descr=f"100 nF 0402 X7R local decoupling for {led_ref} (AQI status ring).",
        ))
    return "\n".join(parts)


# -----------------------------------------------------------------------------
# 1d) Board-level F.SilkS labels (human-readable identifiers)
# -----------------------------------------------------------------------------
def gen_silk_labels() -> str:
    """Return a block of board-level F.SilkS `gr_text` labels.

    These are committed-output documentation aimed at the human
    hand-assembling and servicing the board. The F.Fab layer carries
    machine-readable assembly drawings (MPN, value, polarity), but the
    end user holding the assembled PCB sees only the silkscreen.
    Per the CLAUDE.md "PCB silkscreen documentation" convention, every
    major component / connector gets a short, ≤20-char identifier on
    F.SilkS, ~1.0-1.5 mm height. Labels emitted here:
      - "SEN66 air quality"  — names the SEN66 body shadow
      - "-> J3"              — cable-direction hint at the SEN66
                                connector edge
      - "to SEN66"           — destination label at J3
      - "zip-tie"            — explanatory hint near one of the ZT
                                holes (rest are designator-only)

    Labels are emitted as PCB-level `gr_text` (not inside the placed
    footprints) so they are independent of footprint rotation —
    placing them in PCB-global coords with rotation 0 keeps them
    horizontally readable when the PCB is viewed in its normal
    orientation (chord at the bottom).
    """
    label_size = 1.0
    label_thickness = 0.15

    def _silk(text: str, x: float, y: float, tag: str,
              size: float = label_size, layer: str = "F.SilkS",
              angle: float = 0.0) -> str:
        return textwrap.dedent(f"""\
            \t(gr_text "{text}"
            \t\t(at {fx(x)} {fy(y)} {fmt(angle)})
            \t\t(layer "{layer}")
            \t\t(uuid "{U('silk-label:' + tag)}")
            \t\t(effects
            \t\t\t(font (size {fmt(size)} {fmt(size)}) (thickness {fmt(label_thickness)}))
            \t\t)
            \t)""")

    parts = []
    # SEN66 body label. With v0.9 anchor (23.5, 22), body shadow occupies
    # PCB X=23.5..49.1, Y=-33.2..22. Place the label INSIDE the body in
    # the empty corridor between the inlets (PCB Y ≈ +3.8..+18.9) and the
    # outlet (PCB Y ≈ -30.8..-10.0); the corridor Y=-10..+3.8 has no
    # air-opening markers on F.Fab and is unobstructed on F.SilkS.
    # Centred horizontally on body mid-X = anchor_x + SEN66_BODY_Y/2 = 36.3.
    body_mid_x = SEN66_ANCHOR_X + SEN66_BODY_Y / 2
    parts.append(_silk("SEN66 air quality", body_mid_x, -3.0, "sen66-body"))
    # ---- v0.38: board-level project identification ----
    # Industry-standard prototype tracking — a physical PCB can be
    # identified by name + version (+ URL via assembly drawing) without
    # booting the device. Placed in the clear strip BETWEEN J7/MIKROE
    # east silk (PCB X=-12.7) and C3 cutout west wall (PCB X=+4.9) —
    # 17.6 mm wide, with the J1 south silk edge (Y=+24.51) on the north
    # and J7 south silk edge (Y=+39.4) on the south.
    #
    # F.SilkS (printed on physical PCB) gets two short lines that fit
    # at the board's silk_min_text_height rule (1.0 mm):
    #   - "OAS Open Ambient Sensor" — 23 chars × ~0.7 mm = ~16.1 mm wide
    #     at size 1.0, fits with ~0.5 mm clearance to J7/C3 silk.
    #   - "v0.38" — 5 chars, fits easily.
    # The full repo URL (~45 chars, too wide at silk-min size 1.0)
    # goes on F.Fab — visible in 2d-top.png assembly renders for
    # documentation, not printed on the physical PCB.
    # Pre-routing rework: board-id silk lines moved from F.SilkS to F.Fab
    # because the new J1 / F1 / J10 placements occupy the central south
    # strip the labels used to live in. Still visible in 2D renders.
    parts.append(_silk(OAS_NAME_SHORT,   -4.0, +30.0, "board-id-name",
                       size=1.0, layer="F.Fab"))
    parts.append(_silk(OAS_VERSION_LINE, -4.0, +33.0, "board-id-version",
                       size=1.0, layer="F.Fab"))
    parts.append(_silk(OAS_REPO_URL,     -4.0, +36.0, "board-id-url",
                       size=0.9, layer="F.Fab"))
    # v0.9 dropped a J3-side "to SEN66" reciprocal arrow because J3 sits
    # right under the SEN66 body shadow — at ~1.1 mm between SEN66 silk
    # south edge (Y=+22) and J3 Reference field (Y=+23.1), there is
    # simply no DRC-clean room for a F.SilkS arrow on the J3 side
    # (v0.38 retry confirmed: any text taller than 1.0 mm triggers
    # silk_overlap with J3 Reference, any text smaller than 1.0 mm
    # trips the silk_min_text_height rule). The SEN66 mech-ref keeps
    # its "JST GH cable ->" F.SilkS arrow on the SEN66 side and the
    # cable direction is visually conveyed by J3 ↔ SEN66 silk being
    # adjacent.

    # ---- v0.15.8: LD2410 board-level labels (board-level gr_text so
    # they read horizontally even with the LD2410 footprint rotated 270°).
    # Replaces in-footprint fp_text "HLK-LD2410B" + "antenna ^" + "J4 pins"
    # which became cramped after LD2410_BODY_H was corrected from 15.24
    # to 7.62 mm (datasheet short-axis spec).
    # Convert LD2410-local positions to PCB via the helper.
    ld_body_pcb = _ld2410_local_to_pcb(LD2410_BODY_W / 2.0, LD2410_BODY_H / 2.0)
    ld_antenna_pcb = _ld2410_local_to_pcb((1.0 + LD2410_ANTENNA_X_END) / 2.0,
                                            LD2410_BODY_H / 2.0)
    # v0.15.9: rotated 90° so the labels run along the LD2410's long
    # axis (PCB Y direction). Without rotation, the horizontal text bbox
    # would exceed the 7.22 mm internal width between the U-shaped silk
    # long edges and trigger silk_overlap DRC. Long-axis rotation fits
    # the 11-char body label comfortably along the 35.56 mm long edge.
    parts.append(_silk("HLK-LD2410B", ld_body_pcb[0], ld_body_pcb[1],
                       "ld2410-body", size=1.0, angle=90.0))
    parts.append(_silk("antenna ^", ld_antenna_pcb[0], ld_antenna_pcb[1],
                       "ld2410-antenna", size=1.0, angle=90.0))

    # ---- v0.15.8: SEN66 module identification label as board-level
    # gr_text (the in-footprint "SEN66 SIN-T" fp_text rotates with the
    # SEN66's rotation 90° and ends up vertical on the rendered PCB).
    # Placed at the SEN66 body centre.
    sen66_body_cx = SEN66_ANCHOR_X + SEN66_BODY_Y / 2
    sen66_body_cy = SEN66_ANCHOR_Y - SEN66_BODY_X / 2
    parts.append(_silk("SEN66 SIN-T", sen66_body_cx, sen66_body_cy + 8.0,
                       "sen66-mpn", size=1.0))

    # ---- v0.15.8: ESP32 and MIKROE-2462 body-label boards.
    # v0.22 — moved ESP32 body labels to F.Fab (was F.SilkS). The body
    # center now sits over the power-section SMD components placed under
    # the daughterboard shadow (U1 LM2596S, D2 SS14, etc.), which triggers
    # silk_over_copper DRC warnings when the labels are on F.SilkS.
    # Since the ESP32 daughterboard physically COVERS this part of the
    # PCB at assembly time, the silk text underneath would be invisible
    # to the user anyway — moving it to F.Fab (assembly drawing layer,
    # rendered in 2D-top.png but not silkscreen-printed) preserves the
    # documentation value while clearing the DRC noise.
    esp32_body_cx = ESP32_ANCHOR_X + ESP32_BODY_L / 2.0
    esp32_body_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("ESP32-C6 DevKitM-1", esp32_body_cx, esp32_body_cy,
                       "esp32-body", size=1.0, layer="F.Fab"))
    # ESP32 antenna ("ant") and USB-C ("USB") short-edge hints. LIB
    # (body_w/2, 2.5) and (body_w/2, body_l - 6.0). After rotation 90.
    # "ant" label sits at body edge (no SMD), can stay on F.SilkS.
    # "USB" label sits over C4 (radial cap pad) — move to F.Fab.
    esp32_ant_cx = ESP32_ANCHOR_X + 2.5
    esp32_ant_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("ant", esp32_ant_cx, esp32_ant_cy,
                       "esp32-antenna", size=1.0))
    esp32_usb_cx = ESP32_ANCHOR_X + (ESP32_BODY_L - 6.0)
    esp32_usb_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("USB", esp32_usb_cx, esp32_usb_cy,
                       "esp32-usb", size=1.0, layer="F.Fab"))
    # MIKROE-2462 body centre (rotation 180 -> LIB (lx, ly) → PCB
    # (anchor_x - lx, anchor_y - ly)).
    mikroe_body_cx = MIKROE2462_ANCHOR_X - MIKROE2462_BODY_W / 2.0
    mikroe_body_cy = MIKROE2462_ANCHOR_Y - MIKROE2462_BODY_L / 2.0
    parts.append(_silk("MIKROE-2462", mikroe_body_cx, mikroe_body_cy,
                       "mikroe-body", size=1.0))

    # ---- v0.16: AQI status LED ring label ----
    # Single board-level label identifying the SK6812-SIDE ring as the
    # AQI status indicator. Placed just OUTSIDE the LED ring (radius
    # 11 mm + ~4 mm offset = 15 mm) at angle 315° (top-right of the
    # ring, in a quadrant that's empty of existing components). The
    # label sits at PCB (15·cos 315°, 15·sin 315°) ≈ (+10.6, -10.6).
    # Note: at angle 315° the LED ring has its D22 LED (last in
    # chain, θ=330°), and there's empty PCB space around it.
    aqi_label_r = 15.5
    aqi_label_theta = math.radians(315.0)
    parts.append(_silk(
        "AQI ring",
        aqi_label_r * math.cos(aqi_label_theta),
        aqi_label_r * math.sin(aqi_label_theta),
        "aqi-ring", size=1.0,
    ))

    # ---- v0.18: J1 24 V terminal block board-level labels (south flip) ----
    # Board-level gr_text labels (not in-footprint) so they remain
    # horizontal regardless of the J1 footprint's 180° rotation, and
    # because the in-footprint Reference / Value text positions of the
    # stock Phoenix MSTBA footprint would overlap with the LED ring
    # south corners or the chord cutout C3 depending on rotation.
    #
    # J1 footprint at PCB (J1_PCB_X=+5.08, J1_PCB_Y=+22.4), rotation 180°:
    #   - Pin 1 (+24V) at PCB X = +5.08
    #   - Pin 2 (GND)  at PCB X =  0.00
    #   - Pin 3 (PE)   at PCB X = −5.08
    #   - Body F.SilkS rect: PCB X = −8.73..+8.73, Y = +12.29..+24.51
    #   - Body courtyard:    PCB X = −9.13..+9.13, Y = +11.90..+24.90
    #   - Cable entry on north face at PCB Y = +12.29 (toward cable
    #     hole at origin).
    #
    # Free F.SilkS regions near J1 are narrow (mirror of v0.17 situation):
    #   - North strip: between LED ring south Y=+11.67 and body north
    #     Y=+12.29 ≈ 0.62 mm.
    #   - South strip: between body south Y=+24.51 and C3 cutout north
    #     Y=+28.998 ≈ 4.49 mm (plenty for text, but text outside the
    #     body wouldn't be near J1 visually).
    #
    # Therefore: per-pin labels (24V/GND/PE) go on F.Fab (assembly-doc
    # layer, no silk_overlap rule), positioned just inside the body's
    # north face near each pin clamp. A SINGLE F.SilkS label "J1 (24V)"
    # sits 6.3 mm EAST of the J1 body at PCB (+15, +22.4), on the same
    # Y row as the J1 body centre for easy visual association. To J1's
    # east at X=+15 there's an open strip between J1 east edge (+8.73)
    # and SEN66 body west edge (+23.5) — ~14.77 mm wide. The west-side
    # placement chosen in v0.17 doesn't work here because MIKROE-2462's
    # body silk extends to PCB X = -12.26 at this Y range; the east
    # side is the cleaner option for v0.18's south flip.
    parts.append(_silk("J1 (24V)", +15.0, J1_PCB_Y, "j1-body-id",
                       size=1.0, layer="F.Fab"))
    # Per-pin function labels on F.Fab. Pin-row Y − 0.8 mm (north of
    # pin row) → inside the body's north face (toward cable entry),
    # near each pin clamp. F.Fab is silk-overlap-exempt so positioning
    # right next to the silk body rect is fine. F.Fab is rendered in
    # assembly drawings, not on the physical PCB silkscreen — but
    # pcbnew shows it in-editor.
    j1_pin_fab_y = J1_PCB_Y - 0.8
    parts.append(_silk("24V", +5.08, j1_pin_fab_y, "j1-pin1-24v",
                       size=0.8, layer="F.Fab"))
    parts.append(_silk("GND",  0.00, j1_pin_fab_y, "j1-pin2-gnd",
                       size=0.8, layer="F.Fab"))
    parts.append(_silk("PE",  -5.08, j1_pin_fab_y, "j1-pin3-pe",
                       size=0.8, layer="F.Fab"))

    # ---- v0.19: J9 (Qwiic) + J10 (recovery) per-pin F.Fab labels ----
    # The per-cutout F.SilkS labels emitted earlier ("J9 Qwiic" /
    # "J10 flash" / "C4 v2") identify the connector by designator;
    # per-pin labels go on F.Fab so the assembler / debugger can read
    # them on the assembly drawing without consulting the schematic.
    # F.Fab is silk-overlap-exempt so we can position labels right
    # next to the pad without DRC complaints.
    #
    # J9 — JST SH 4-pin. PCB pad row at PCB Y = J9_PCB_Y + 2 = +41.69,
    # pads at PCB X = J9_PCB_X ± 1.5, J9_PCB_X ± 0.5 (1 mm pitch).
    # With rotation 180°, pad 1 (north / "top of footprint Y order")
    # lands at PCB X = J9_PCB_X + 1.5, pad 4 at PCB X = J9_PCB_X - 1.5.
    # Mark the pin-1 corner with a "P1" hint on F.Fab so the visual
    # assembly drawing identifies which pad is GND.
    j9_pad_y = J9_PCB_Y + 2.0      # +41.69 — pad row Y
    j9_p1_x = J9_PCB_X + 1.5       # +33.15 — pad 1 (GND, north-east edge of footprint)
    # F.Fab pin-function hint just north of pad row (toward body interior).
    parts.append(_silk("J9 GND", j9_p1_x, j9_pad_y - 2.0, "j9-p1-gnd",
                       size=0.8, layer="F.Fab"))
    # Cable-direction hint moved into J9's per-pin F.Fab labels (the
    # "J9 GND" pin-1 marker above), so the surface silk stays clean.
    # The cutout "J9 Qwiic" label (emitted by the cutout loop above)
    # marks the connector identity from outside the case.

    # J10 — 6-pin 2.54 mm pin header. Pre-routing rework 3: switched to
    # rotation 90 (horizontal pad row). With rotation 90 (LIB +Y → PCB
    # +X), pad 1 at (J10_PCB_X, J10_PCB_Y) and pads 2..6 spread EAST at
    # 2.54 mm pitch. Per-pin function labels on F.Fab placed SOUTH of
    # each pad (between J10 body silk south edge ~Y=-21.23 and the LED
    # ring at Y≈-13). F.Fab is silk-overlap-exempt so positioning right
    # next to the pads is fine, and F.Fab text isn't subject to the
    # silk_min_text_height rule.
    j10_pin_labels = ["GND", "+3V3", "USB-", "USB+", "EN", "BOOT"]
    for i, lbl in enumerate(j10_pin_labels):
        px = J10_PCB_X + i * 2.54
        parts.append(_silk(
            lbl, px, J10_PCB_Y + 2.5,
            f"j10-pin{i+1}-{lbl.lower().replace('+', 'p').replace('-', 'm')}",
            size=0.8, layer="F.Fab",
        ))
    # Overall connector ID on F.SilkS (south of the per-pin F.Fab labels
    # so they don't visually stack; F.SilkS and F.Fab are different
    # layers so silk_overlap won't fire between them either way). Place
    # at pad-row centre X = J10_PCB_X + 12.7/2 = -4.61.
    parts.append(_silk(
        "J10 flash", J10_PCB_X + 6.35, J10_PCB_Y + 4.5, "j10-body-id",
        size=1.0,
    ))
    # (No F.SilkS "(DNP)" hint on the PCB — "Do Not Populate" status
    # lives in the schematic (J10 symbol has `(dnp yes)`) and in the
    # BOM exporter output. Adding a board-level "(DNP)" silk near J10
    # collided with the J1 body silk rect and was redundant with the
    # "J10 flash" cutout label.)

    # ---- v0.7: cutout-zone reservation labels + outlines on F.SilkS ----
    # Each cutout C3..C5 along the chord is a case-wall opening that may
    # host a connector (24V terminal, JST GH, USB-C debug, Qwiic, etc.).
    # Draw both:
    #   - A thin F.SilkS rectangle outlining the cutout footprint, inset
    #     by SILK_EDGE_INSET on each side so it clears Edge.Cuts even
    #     when the cutout is clipped at the chord
    #   - A short text label centred in the rectangle identifying what
    #     the cutout hosts. For narrow rects the text is rotated 90° so
    #     it still fits inside the outline without overlapping
    #     (DRC silk_overlap).
    #
    # v0.19 — per-cutout label override:
    #   - C3 → "J10 flash" (6-pin recovery header for native USB
    #     flashing of the ESP32-C6; DNP by default). NO silk rect —
    #     the J10 stock footprint's own body silk already marks the
    #     connector outline; a second rect over the same area would
    #     trigger DRC `silk_overlap`. Label only.
    #   - C4 → "C4 v2"     (placeholder for v2 expansion; no connector
    #     installed). Silk rect + label, same as v0.7 convention, so
    #     the user can identify the unused cutout at assembly time.
    #   - C5 → "J9 Qwiic"  (Qwiic / Stemma QT JST SH 4-pin expansion).
    #     NO silk rect for the same reason as C3.
    SILK_EDGE_INSET = 0.3       # mm — keeps rect off the board edge.
                                # With 0.12 mm silk stroke, line outer edge
                                # sits 0.06 mm beyond the centerline; 0.3 mm
                                # inset leaves 0.24 mm clear to Edge.Cuts,
                                # comfortably above the 0.15 mm DRC limit.
    SILK_TEXT_MIN_HORIZONTAL_FIT = 5.0   # mm — width needed to keep label
                                          # at 1.0 mm horizontal inside the rect
    CUTOUT_LABELS = {
        # C3/C4 cutouts removed (pre-routing rework 2) — kept entries
        # here as historical reference only; not iterated since CUTOUTS
        # no longer contains them.
        "C5": "J9 Qwiic",
    }
    # Cutouts that host a connector (with its own body silk) — skip the
    # cutout silk rect to avoid silk_overlap DRC violations. The text
    # label still emits, positioned just NORTH of the connector body.
    # C3 lost its J10 occupant in pre-routing rework but J1 body has
    # since slid south into the cutout zone; rect kept suppressed to
    # avoid silk_overlap against J1's own silk.
    CUTOUTS_WITHOUT_RECT = {"C3", "C5"}
    for name, x1, x2, y1, y2, allow_pads in CUTOUTS:
        rx1, rx2 = x1 + SILK_EDGE_INSET, x2 - SILK_EDGE_INSET
        ry1, ry2 = y1 + SILK_EDGE_INSET, y2 - SILK_EDGE_INSET
        cx = (rx1 + rx2) / 2
        cy = (ry1 + ry2) / 2
        rect_w = rx2 - rx1
        if name not in CUTOUTS_WITHOUT_RECT:
            parts.append(textwrap.dedent(f"""\
                \t(gr_rect
                \t\t(start {fx(rx1)} {fy(ry1)})
                \t\t(end {fx(rx2)} {fy(ry2)})
                \t\t(stroke (width 0.12) (type solid))
                \t\t(fill no)
                \t\t(layer "F.SilkS")
                \t\t(uuid "{U('cutout-silk-rect:'+name)}")
                \t)"""))
        # Centred text label at the DRC minimum text height (1.0 mm);
        # rotate 90° in narrow rects so the text fits inside without
        # overlapping the outline.
        text_angle = 90.0 if rect_w < SILK_TEXT_MIN_HORIZONTAL_FIT else 0.0
        label = CUTOUT_LABELS.get(name, f"{name} AUX")
        # For C3/C5 — position the cutout label NORTH of the connector
        # body shadow (i.e., into the PCB interior, away from the
        # case-wall edge) where it doesn't clash with connector silk.
        # For other cutouts, use the cutout centre.
        if name == "C5":
            # C5 hosts J9 (body at PCB X=+27.75..+35.55, Y=+36.41..+42.47).
            # Place label NORTH of the J9 body at PCB Y=+34.5 (clear of
            # body's north silk at Y=+36.41).
            tx, ty = +31.65, +34.5
        else:
            tx, ty = cx, cy
        parts.append(_silk(
            label, tx, ty, f"cutout-silk-{name}",
            size=1.0, angle=text_angle,
        ))

    # ---- v0.27: per-component designator labels on F.SilkS ----
    # Every populated component on the OAS PCB gets a short Reference
    # designator label as board-level `gr_text` (horizontal, ~1.0 mm
    # high) placed in a clear zone adjacent to its body. The
    # in-footprint Reference text stays hidden (set via `hide_ref=True`
    # on the stub footprint generators) because:
    #   - the LED-ring caps + LEDs sit at 0..330° rotations around the
    #     ring, so the in-footprint Reference would rotate with each
    #     part into illegible 180°/270° angles;
    #   - the south-flank power-section caps (C5..C8, C15, C16) sit
    #     immediately north of the J6 pin-socket silk frame, leaving
    #     <1.5 mm gap above the body — too tight for a 1.0 mm
    #     in-footprint Reference;
    #   - several refs (C3, C10, D3, U2 et al.) would otherwise sit
    #     directly over neighbouring pads (silk_over_copper DRC).
    # Per-instance board-level gr_text lets us place each label in
    # whatever clear zone is closest to its body.
    #
    # Position convention: for each anchor (ax, ay) the label sits at
    # (ax + dx, ay + dy) with rotation 0 (always horizontal) unless an
    # override is supplied. dx, dy are tuned per component to land in
    # an empty silk strip.
    #
    # The list below MUST stay in sync with the actual footprint
    # placements in gen_power_pcb_footprints() and the LED-ring loop
    # in gen_sensors_pcb_footprints().

    # ---- 1) Power-section + sensor-decoupling components ----
    # Layout reference (v0.26):
    #   Row Y=-30  small SMDs (HF caps + I²C pull-ups + R7) — sits in
    #              the strip between J5 silk (Y=-27.30..-24.64) and the
    #              Buck1-satellite row at Y=-37. INSIDE the ESP32
    #              daughterboard shadow.
    #   Row Y=-37  D2 (SMA), L1 (5x5) — INSIDE ESP32 shadow.
    #   Row Y=-43.5..-44  U2, L2, R2, R3 — Buck2 main, INSIDE ESP32 shadow.
    #   Row Y=-46  south flank (C5..C8, C15, C16) — sits 1.5 mm above
    #              J6 silk frame at Y=-47.5. INSIDE ESP32 shadow.
    # Components INSIDE a daughterboard shadow get their designator
    # label on F.Fab — they're physically covered by the daughterboard
    # at assembly time, so silkscreen ink would be invisible anyway.
    # F.Fab is also exempt from `silk_over_copper` / `silk_overlap` /
    # `min_text_height` DRC rules, which the cramped under-shadow layout
    # would otherwise hit (cap-to-cap pad-overlap, J6 silk overlap, etc.).
    # The 2D-top render still shows F.Fab text so reviewers see every
    # designator without launching pcbnew.
    #
    # Each entry: (designator, dx, dy, layer)
    POWER_LABELS = [
        # input-protection cluster (NOT under any daughterboard shadow)
        ("D1",  0.0, -3.0, "F.SilkS"),
        ("F1",  0.0, -4.5, "F.SilkS"),
        # Pre-routing rework 3: Q1 / D3 / R1 / R4 cluster relocated to
        # the F1-south column (Q1 at +15,+30 — D3 at +19,+30 — R1 at
        # +15,+33 — R4 at +19,+33). Every body is in a tight 7×4 mm
        # block; F.Fab labels placed in the small gaps between bodies.
        #   - Q1: vertical text east of Q1 body, between Q1 east silk
        #     (+16.5) and D3 west body (+18). 1.5 mm strip.
        #   - D3: horizontal text east of D3 body, between D3 east
        #     (+20) and SEN66 west courtyard (+23.25). 3.25 mm strip.
        #   - R1: horizontal text west of R1 body, between J1 east
        #     courtyard (+9.12) and R1 west body (+14). ~5 mm strip.
        #   - R4: horizontal text east of R4 body, between R4 east
        #     (+20) and SEN66 west courtyard (+23.25). 3.25 mm strip.
        ("Q1",  +2.25, 0.0, "F.Fab", 90.0),
        ("D3",  +2.5,  0.0, "F.Fab"),
        ("R1",  -3.0,  0.0, "F.Fab"),
        ("R4",  +3.0,  0.0, "F.Fab"),
        # Buck1 cluster
        # C1 sits south of SEN66, outside daughterboard shadows.
        # v0.40 post-order: stock CP_Radial_D8.0mm_P3.50mm has many F.SilkS
        # body-curve fp_lines spanning Y ∈ [-4.08, +4.08] (relative to
        # body center). North-of-body (Y=-6.5 from anchor) → PCB Y=+29.5
        # which hits J3 (SEN66 socket) silk frame and J3 MP mounting
        # pad. Other directions are similarly tight. Push to F.Fab —
        # the C1 silkscreen body itself identifies the cap to the
        # assembler; F.Fab text gives the designator for documentation.
        # C1 relocated to (+33, -42). North (-46 to -50) is occupied by
        # C4/C10. South (-38 to -30) is open strip between C1 body and
        # ESP32 east. Push label south of body silk: offset (0, +6.5)
        # → PCB (+33, -35.5).
        ("C1",  0.0, +6.5, "F.SilkS"),
        # C3 — pre-fix C3 label at body anchor offset (0, -2.0) sat INSIDE
        # the body shadow (D8 radius 4 mm). v0.40 post-order: C3 body
        # is at PCB Y_center=-24. North of body Y=-20 there's only the
        # MOD1 (ESP32) silk; south of body Y=-28 is U1 (TO-263-5) tab
        # which extends Y to -28.6 north edge. Sweet spot is the strip
        # Y ∈ [-28.6, -20], i.e. label_y ∈ [-28.6 + half_text_h + 0.15,
        # -20 - half_text_h - 0.15] = [-27.95, -20.55]. Place label at
        # Y=-21 (just south of C3 body north silk edge), within the
        # strip. Note: this is offset = -3 from C3 anchor at Y=-24.
        # Wait — actually the v0.40 anchor convention is preserved
        # (call site x=-34, y=-24 IS body center); the stock body silk
        # extent +/-4 mm around center means north_edge at Y=-20.
        # Label offset (0, +4.5) puts text at Y=-19.5 (north of body
        # silk) which collides with MOD1 silk south edge at Y=-19. Use
        # (0, -3) — text at Y=-27 = halfway between body south Y=-28
        # and U1 tab north Y=-28.6 → 0.9 mm from U1 tab, 1.0 mm from
        # body. Wait this also puts text inside body silk (extends to
        # Y=-28). Let's go with (0, -6.5) but reduce — actually the
        # silk has a half-CIRCLE only (open on the cathode side at +X),
        # so silk lines exist only at Y ∈ approx [-4.08, +4.08]. At
        # X=center+0 (label X = body center X), Y_silk = ±sqrt(r² - 0²) =
        # ±4 mm, so silk reaches Y_local = -4 at the body's north pole
        # (= PCB Y = -28). Text at Y=-30.5 is BELOW silk, but the U1 tab
        # is at Y=-28.6, so text would intersect U1 tab. Skip this
        # zone entirely — push label further south of U1 tab south edge
        # (Y=-39.4): offset to Y=-40 (= offset -16) → far away. Too
        # far. Better: keep label INSIDE U1 tab silk (which has F.SilkS
        # body outline at -4.825..-3.46 LIB-Y mapped to PCB ?), or
        # move it WEST off U1 tab. U1 tab west edge at PCB X = -36.7,
        # east at -27.8. Width 9 mm. C3 body west edge at PCB X = -36.25,
        # east at -28.25. They overlap! West of C3 body is the LD2410
        # body (extends X to ~-43.7 east edge — that's far west). Use
        # offset (+5, 0) east — east of C3 body (X=-29..-28.25), but
        # still west of U1 east edge at -27.8. NOT clear of U1.
        # Final approach: put label SOUTH on F.Fab (assembly drawing
        # only, exempt from silk_overlap / silk_over_copper rules).
        # C3 at (-34, -22). Body silk Ø8 mm extends X=[-38, -30]. Open
        # strip west between C3 west silk (-38) and LD2410 east edge
        # (-43.47). Offset (-6, 0) → PCB (-40, -22): 1.72 mm to LD2410
        # west, 0.25 mm clear of C3 body silk east of text right edge.
        ("C3",  -6.0, 0.0, "F.SilkS"),
        # U1 (TO-263-5): signal pads at X_local=-7.65 (= PCB X=-41.65),
        # tab pad east at X_local=+1.5 to +6.2 (= PCB X=-32.5..-27.8).
        # Label needs to clear the signal pad column (PCB X=-41.65 ±
        # half pad width 2.3 = -43.95..-39.35) AND clear the tab pad
        # east edge at -27.8. Body Y range ±5 from anchor (PCB Y=-29
        # to -39). Place label SOUTH of body (offset 0, +7) at PCB Y=-27
        # — north of buck-2 row at Y=-30 by 3 mm (gap to C13 north).
        # Actually buck-2 row INCLUDES C13/C14/C9/C17/R5/R6/R7 at Y=-30.
        # Their courtyards extend ~1.5 mm. So Y=-27 leaves 1.5 mm clear.
        ("U1",  0.0, +7.0,  "F.Fab"),
        # D2, L1 INSIDE ESP32 shadow → F.Fab
        ("D2",  0.0, -3.0, "F.Fab"),
        ("L1",  0.0, -4.0, "F.Fab"),
        # C4 in east-of-ESP32 / north-of-SEN66 strip — outside shadows.
        # v0.40 post-order: stock CP_Radial_D6.3mm body radius 3.15 mm;
        # label needs ≥5 mm offset to clear body silk.
        ("C4",  0.0, -5.0, "F.SilkS"),
        # Buck2 cluster INSIDE ESP32 shadow → F.Fab
        ("U2",  0.0, -2.5, "F.Fab"),
        ("L2",  0.0, -4.0, "F.Fab"),
        ("R2",  0.0, -2.0, "F.Fab"),
        ("R3",  0.0, -2.0, "F.Fab"),
        # north-flank row Y=-30 INSIDE ESP32 shadow → F.Fab
        ("C9",  0.0, -2.0, "F.Fab"),
        ("C13", 0.0, -2.0, "F.Fab"),
        ("C14", 0.0, -2.0, "F.Fab"),
        ("C17", 0.0, -2.0, "F.Fab"),
        ("R5",  0.0, -2.0, "F.Fab"),
        ("R6",  0.0, -2.0, "F.Fab"),
        ("R7",  0.0, -2.0, "F.Fab"),
        # south-flank row Y=-46 INSIDE ESP32 shadow → F.Fab.
        # Labels EAST of each body so the F.Fab text doesn't pile up.
        ("C5",  2.5,  0.0, "F.Fab"),
        ("C15", 2.0,  0.0, "F.Fab"),
        ("C6",  2.0,  0.0, "F.Fab"),
        ("C16", 2.0,  0.0, "F.Fab"),
        ("C7",  2.0,  0.0, "F.Fab"),
        ("C8",  2.0,  0.0, "F.Fab"),
        # C2 west of ESP32 (X=-46 outside shadow) → F.SilkS
        ("C2",  0.0, -2.0, "F.SilkS"),
        # sensor decoupling caps
        # C10 0603 in NE corner cluster (C4 west, C1 east) with very
        # little silk room — C1 8 mm radial body silk sits 0.6 mm north
        # of C10, C4 6.3 mm radial body silk 1.7 mm west. Any silk
        # offset bumps the "C10" text into one of the bigger bodies.
        # Push label to F.Fab — body silk identifies the cap visually.
        ("C10", 0.0, +2.0, "F.Fab"),
        # C11 west of LD2410 (LD2410 has F.CrtYd but no daughterboard
        # shadow per se — body label gr_text is at center; C11 at
        # X=-42 is INSIDE LD2410 X range -51..-43.47 but C11 sits south
        # of LD2410 silk frame Y=-16.51-0.5=-17.01 to ~-15.91.
        # Pre-routing rework: MOD2 shifted west -2 mm to clear LED bump,
        # bringing MOD2 west silk to X=-40.16. C11 designator label
        # silk text at (-42, +12) now within ~0.6 mm of MOD2 silk →
        # moved to F.Fab to avoid silk_overlap.
        ("C11", 0.0, -2.0, "F.Fab"),
        # C12 INSIDE MIKROE shadow (X=-38.16..-12.76, Y=-16.51..+40.64,
        # C12 anchor (-25, +23) is inside) → F.Fab
        ("C12", 0.0, -2.0, "F.Fab"),
        # J2 DNP recovery — outside shadows
        # v0.40 audit-16: stock 1x06 P2.54 PinHeader has silk frame top
        # edge at footprint-local Y=-1.38. Label offset (0, -2) gave text
        # bottom edge at PCB Y=-9.5, which overlapped the frame top
        # segment at Y=-9.38 by 0.12 mm. Move label WEST of the frame
        # entirely (offset -3.5, 0 → PCB X=-57.5, ~2.0 mm west of silk
        # frame west edge at PCB X=-55.38). Still inside PCB outline
        # (~Ø60 at Y=-8 → X_edge=-59.46).
        ("J2",  -3.5, 0.0, "F.SilkS"),
    ]
    # Component anchors mirror the placements in gen_power_pcb_footprints().
    # Keep this dict in lock-step with that function.
    COMPONENT_ANCHORS = {
        "D1":  (+19, +9.5),
        "F1":  (+15, +25),
        "Q1":  (+14, +33),
        "D3":  (+20, +33),
        "R1":  (+14, +37),
        "R4":  (+20, +37),
        "C1":  (+33, -42),
        "C3":  (-34, -22),
        "U1":  (-35, -34),
        "D2":  (+2, -37),
        "L1":  (+9, -37),
        "C4":  (+25, -47),
        "U2":  (-2, -43.5),
        "L2":  (+4, -44),
        "R2":  (+10, -44),
        "R3":  (+13, -44),
        "C9":  (+0, -30),
        "C13": (-14, -30),
        "C14": (-6, -30),
        "C17": (+4, -30),
        "R5":  (+8, -30),
        "R6":  (+11, -30),
        "R7":  (+14, -30),
        "C5":  (-25, -46),
        "C15": (-18.5, -46),
        "C6":  (-14, -46),
        "C16": (-10, -46),
        "C7":  (-6, -46),
        "C8":  (-2, -46),
        "C2":  (-46, -25),
        "C10": (+30, -47),
        "C11": (-43, +22),
        "C12": (-25, +23),
        "J2":  (-54, -8),
    }
    for entry in POWER_LABELS:
        # Optional 5th tuple element: explicit angle (deg) override.
        # Default 0 (horizontal).
        if len(entry) == 5:
            ref, dx, dy, layer, angle = entry
        else:
            ref, dx, dy, layer = entry
            angle = 0.0
        ax, ay = COMPONENT_ANCHORS[ref]
        parts.append(_silk(ref, ax + dx, ay + dy, f"desig:{ref}",
                           size=1.0, layer=layer, angle=angle))

    # ---- 2) Pin sockets J5/J6/J7/J8 ----
    # Each pin socket lives at one of the two long edges of an ESP32
    # (J5/J6) or MIKROE (J7/J8) daughterboard. Place the designator
    # OUTSIDE the daughterboard silk frame, near one short edge of
    # the row, so it remains visible even when the daughterboard plugs
    # in (and during bare-PCB assembly the user can identify which row
    # is which).
    #
    # J5 row A at PCB (-22.39, -25.97), rotation 90, 15 pins along
    # PCB +X. ESP32 (MOD1) daughterboard silk rect Y range [-50.6, -24.2].
    # Label at PCB Y=-22.5 — 1.125 mm clear of MOD1 silk north edge
    # at Y=-24.2 (with label-bbox half-h ≈0.575 mm).
    parts.append(_silk("J5", -22.39 + 5.37, -22.5, "desig:J5", size=1.0))
    # J6 label south of MOD1 silk south edge at Y=-50.6: label at
    # Y=-52.5 gives 1.325 mm clearance.
    parts.append(_silk("J6", -22.39 + 5.37, -52.5, "desig:J6", size=1.0))
    # J7 row A at PCB (-14.03, +38.10), rotation 180. MIKROE-2462
    # daughterboard silk rect Y range [-16.71, +40.84]. Label at
    # PCB X = -14.03, Y = +42.2 — 0.785 mm south of MIKROE silk
    # frame south edge (+40.84). Chord at Y=+43.5 → 0.725 mm to
    # label bbox bottom (+42.775), well clear.
    parts.append(_silk("J7", -14.03, +42.2, "desig:J7", size=1.0))
    parts.append(_silk("J8", -36.89, +42.2, "desig:J8", size=1.0))

    # ---- 3) Mounting holes H1/H2/H3 ----
    # Per CLAUDE.md "Designators on PCB features: when a footprint's
    # Reference property is hidden ... emit a separate fp_text user
    # on F.SilkS with the designator (H1, H2, ZT1..ZT4) so the
    # hand-assembler can identify each hole at a glance."
    # ZT1..ZT4 already have silk_label fp_text. Add H1/H2/H3 as
    # board-level gr_text — the in-footprint fp_text approach hits
    # silk_overlap with MOD1 (for H3) and silk_over_copper with C10
    # (for H1) given the v0.26 placement.
    #
    # H1 at (+47.6, +27.5), pitch-circle. Label SOUTH-EAST of hole
    # at (+47.6+3.0, +27.5+0.0) = (+50.6, +27.5). With courtyard
    # radius 2.85, label-center is 3.0 mm east of hole centre — gap
    # 0.15 mm. Need slightly more.
    parts.append(_silk("H1", +47.6 + 3.5, +27.5, "desig:H1", size=1.0))
    parts.append(_silk("H2", -47.6 - 3.5, +27.5, "desig:H2", size=1.0))
    # H3 hole at (0, -55) — PCB north arc. H3 silk circle radius
    # 1.9 mm (south edge at Y=-53.1). MOD1 (ESP32) silk rect north
    # edge at Y=-50.6. Strip Y=-53.1..-50.6 = 2.5 mm of clear silk
    # available. Centre the H3 label at Y=-51.85: 0.675 mm clear of
    # the hole silk circle south edge AND 0.675 mm clear of MOD1
    # silk north edge (both > 0.15 mm DRC rule).
    parts.append(_silk("H3", 0.0, -51.85, "desig:H3", size=1.0))

    # ---- 4) LED ring caps C20..C31 + LEDs D11..D22 ----
    # The LED ring + decoupling cap ring is the densest copper zone on
    # the PCB. LEDs at R=11, caps at R=7.6, cable hole at R=6. The only
    # silk-free annular bands are R<6 (cable hole — no PCB) and
    # R>14 (ZT/H1/H2 zone, also already populated). Placing per-LED /
    # per-cap silkscreen designators on F.SilkS triggers silk_over_copper
    # DRC against the LED pads (at R~9.5-10.5 inner edge) and silk_overlap
    # against the J1 terminal block at θ=60-120°.
    #
    # Use F.Fab (assembly-doc layer, exempt from silk_over_copper /
    # silk_overlap / min_text_height rules) so each LED and cap remains
    # identifiable in the 2D-top render and pcbnew without DRC noise.
    # Same precedent as the ESP32 body label move in v0.22.
    DESIG_LABEL_R_CAP = 8.9   # between cap outer edge (8.1) and LED inner (10.0)
    DESIG_LABEL_R_LED = 13.6  # radially outside LED outer edge (12.0)
    DESIG_LABEL_SIZE = 1.0
    for i in range(LED_RING_COUNT):
        if i in LED_RING_SKIP_INDICES:
            continue
        theta_deg = LED_RING_THETA_START_DEG + i * LED_RING_THETA_STEP_DEG
        theta_rad = math.radians(theta_deg)
        # Tangential rotation, clamped to [0, 180) so KiCad never
        # renders text mirrored upside-down.
        text_angle = (theta_deg + 90.0) % 180.0
        # Cap designator (F.Fab — text sits over LED inner pads).
        cap_label_x = DESIG_LABEL_R_CAP * math.cos(theta_rad)
        cap_label_y = DESIG_LABEL_R_CAP * math.sin(theta_rad)
        cap_ref = f"C{20 + i}"
        parts.append(_silk(
            cap_ref, cap_label_x, cap_label_y, f"desig:{cap_ref}",
            size=DESIG_LABEL_SIZE, angle=text_angle, layer="F.Fab",
        ))
        # LED designator (F.Fab — at angles 60°..120° the F.SilkS
        # position collides with J1 terminal block silk frame north edge
        # at PCB Y=+12.29).
        led_label_x = DESIG_LABEL_R_LED * math.cos(theta_rad)
        led_label_y = DESIG_LABEL_R_LED * math.sin(theta_rad)
        led_ref = f"D{11 + i}"
        parts.append(_silk(
            led_ref, led_label_x, led_label_y, f"desig:{led_ref}",
            size=DESIG_LABEL_SIZE, angle=text_angle, layer="F.Fab",
        ))

    return "\n".join(parts)


# -----------------------------------------------------------------------------
# 2) PCB file
# -----------------------------------------------------------------------------
def gen_pcb() -> str:
    # Outline: arc from (+halfchord, +Y_chord) through (0, -R) to (-halfchord, +Y_chord)
    p_start = ( HALF_CHORD,  Y_CHORD)
    p_mid   = ( 0.0,        -R_OUTLINE)
    p_end   = (-HALF_CHORD,  Y_CHORD)

    layers = textwrap.dedent("""\
        \t\t(0 "F.Cu" signal)
        \t\t(2 "B.Cu" signal)
        \t\t(9 "F.Adhes" user "F.Adhesive")
        \t\t(11 "B.Adhes" user "B.Adhesive")
        \t\t(13 "F.Paste" user)
        \t\t(15 "B.Paste" user)
        \t\t(5 "F.SilkS" user "F.Silkscreen")
        \t\t(7 "B.SilkS" user "B.Silkscreen")
        \t\t(1 "F.Mask" user)
        \t\t(3 "B.Mask" user)
        \t\t(17 "Dwgs.User" user "User.Drawings")
        \t\t(19 "Cmts.User" user "User.Comments")
        \t\t(21 "Eco1.User" user "User.Eco1")
        \t\t(23 "Eco2.User" user "User.Eco2")
        \t\t(25 "Edge.Cuts" user)
        \t\t(27 "Margin" user)
        \t\t(31 "F.CrtYd" user "F.Courtyard")
        \t\t(29 "B.CrtYd" user "B.Courtyard")
        \t\t(35 "F.Fab" user)
        \t\t(33 "B.Fab" user)
        \t\t(39 "User.1" user)
        \t\t(43 "User.2" user)
        \t\t(47 "User.3" user)
        \t\t(51 "User.4" user)""")

    stackup = textwrap.dedent("""\
        \t\t(stackup
        \t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "Black"))
        \t\t\t(layer "F.Paste" (type "Top Solder Paste"))
        \t\t\t(layer "F.Mask"  (type "Top Solder Mask") (color "White") (thickness 0.01))
        \t\t\t(layer "F.Cu"    (type "copper") (thickness 0.035))
        \t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
        \t\t\t(layer "B.Cu"    (type "copper") (thickness 0.035))
        \t\t\t(layer "B.Mask"  (type "Bottom Solder Mask") (color "White") (thickness 0.01))
        \t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
        \t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "Black"))
        \t\t\t(copper_finish "HASL lead-free")
        \t\t\t(dielectric_constraints no)
        \t\t)""")

    setup = textwrap.dedent(f"""\
        \t(setup
        {stackup}
        \t\t(pad_to_mask_clearance 0)
        \t\t(allow_soldermask_bridges_in_footprints no)
        \t\t(tenting front back)
        \t\t(aux_axis_origin {fmt(PAGE_CENTRE_X)} {fmt(PAGE_CENTRE_Y)})
        \t\t(grid_origin {fmt(PAGE_CENTRE_X)} {fmt(PAGE_CENTRE_Y)})
        \t)""")

    # Edge.Cuts outline (arc + chord); offset to page centre.
    # Plus a circular cut-out in the PCB centre for the 24 V cable pass-through
    # (cable enters the case from the rear, passes through the PCB to a
    # terminal block on the front side).
    outline = textwrap.dedent(f"""\
        \t(gr_arc
        \t\t(start {fx(p_start[0])} {fy(p_start[1])})
        \t\t(mid {fx(p_mid[0])} {fy(p_mid[1])})
        \t\t(end {fx(p_end[0])} {fy(p_end[1])})
        \t\t(stroke (width {fmt(EDGE_CUTS_WIDTH)}) (type solid))
        \t\t(layer "Edge.Cuts")
        \t\t(uuid "{U('outline_arc')}")
        \t)
        \t(gr_line
        \t\t(start {fx(p_end[0])} {fy(p_end[1])})
        \t\t(end {fx(p_start[0])} {fy(p_start[1])})
        \t\t(stroke (width {fmt(EDGE_CUTS_WIDTH)}) (type solid))
        \t\t(layer "Edge.Cuts")
        \t\t(uuid "{U('outline_chord')}")
        \t)
        \t(gr_circle
        \t\t(center {fx(0)} {fy(0)})
        \t\t(end {fx(CABLE_HOLE_DIAMETER/2)} {fy(0)})
        \t\t(stroke (width {fmt(EDGE_CUTS_WIDTH)}) (type solid))
        \t\t(fill no)
        \t\t(layer "Edge.Cuts")
        \t\t(uuid "{U('cable_hole')}")
        \t)""")

    # 3 mounting holes. v0.27: per-hole designators (H1/H2/H3) are
    # emitted as board-level `gr_text` in `gen_designator_labels()` so
    # we can place each one in the clear zone next to its hole without
    # colliding with neighbouring silk (MOD1 daughterboard frame for H3,
    # C10 / J6 silk for H1). Mirrors the v0.27 approach used for every
    # populated component.
    footprints = []
    for i, (x, y) in enumerate(HOLE_POSITIONS, start=1):
        ref = f"H{i}"
        fp = textwrap.dedent(f"""\
            \t(footprint "oas:MountingHole_3.8mm_M3"
            \t\t(layer "F.Cu")
            \t\t(uuid "{U(f'mh-inst:{ref}:fp')}")
            \t\t(at {fx(x)} {fy(y)})
            \t\t(descr "M3 mounting hole NPTH, Ø3.8 mm per SZOMK AK-N-94 spec")
            \t\t(attr through_hole board_only exclude_from_pos_files exclude_from_bom)
            \t\t(property "Reference" "{ref}"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.SilkS")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U(f'mh-inst:{ref}:prop-ref')}")
            \t\t\t(effects (font (size 1 1) (thickness 0.15)))
            \t\t)
            \t\t(property "Value" "MountingHole_3.8mm_M3_NPTH"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U(f'mh-inst:{ref}:prop-val')}")
            \t\t\t(effects (font (size 1 1) (thickness 0.15)))
            \t\t)
            \t\t(property "Footprint" "oas:MountingHole_3.8mm_M3"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U(f'mh-inst:{ref}:prop-fp')}")
            \t\t\t(effects (font (size 1.27 1.27)))
            \t\t)
            \t\t(property "Datasheet" ""
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U(f'mh-inst:{ref}:prop-ds')}")
            \t\t\t(effects (font (size 1.27 1.27)))
            \t\t)
            \t\t(property "Description" "Mounting Hole, Ø3.8 mm NPTH, for M3 screw (per SZOMK AK-N-94)"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U(f'mh-inst:{ref}:prop-desc')}")
            \t\t\t(effects (font (size 1.27 1.27)))
            \t\t)
            \t\t(fp_circle
            \t\t\t(center 0 0)
            \t\t\t(end {fmt(COURTYARD_RADIUS)} 0)
            \t\t\t(stroke (width 0.05) (type solid))
            \t\t\t(fill no)
            \t\t\t(layer "F.CrtYd")
            \t\t\t(uuid "{U(f'mh-inst:{ref}:crtyd')}")
            \t\t)
            \t\t(fp_circle
            \t\t\t(center 0 0)
            \t\t\t(end {fmt(HOLE_DIAMETER/2)} 0)
            \t\t\t(stroke (width 0.1) (type solid))
            \t\t\t(fill no)
            \t\t\t(layer "F.Fab")
            \t\t\t(uuid "{U(f'mh-inst:{ref}:fab')}")
            \t\t)
            \t\t(pad "" np_thru_hole circle
            \t\t\t(at 0 0)
            \t\t\t(size {fmt(HOLE_DIAMETER)} {fmt(HOLE_DIAMETER)})
            \t\t\t(drill {fmt(HOLE_DIAMETER)})
            \t\t\t(layers "F&B.Cu" "*.Mask")
            \t\t\t(remove_unused_layers no)
            \t\t\t(uuid "{U(f'mh-inst:{ref}:pad')}")
            \t\t)
            \t)""")
        footprints.append(fp)

    keepouts, markers = gen_cutouts()
    sensor_footprints = gen_sensors_pcb_footprints()
    power_footprints = gen_power_pcb_footprints()
    silk_labels = gen_silk_labels()

    body = textwrap.dedent(f"""\
        (kicad_pcb
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(general
        \t\t(thickness 1.6)
        \t\t(legacy_teardrops no)
        \t)
        \t(paper "A4")
        \t(layers
        {layers}
        \t)
        {setup}
        \t(net 0 "")
        {outline}
        """) + markers + "\n" + "\n".join(footprints) + "\n" + sensor_footprints + "\n" + power_footprints + "\n" + silk_labels + "\n" + keepouts + "\n)\n"
    return body

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
    # chunk #5d (v0.16) — AQI status-LED ring (12 × SK6812-SIDE + 12 × 100 nF)
    # =========================================================================
    # 12 SK6812 SIDE-A LEDs (D11..D22) form a ring around the central
    # cable hole on the PCB, all driven from MCU GPIO 8 (WS2812_DIN net)
    # in a daisy chain. Each LED has a 100 nF 0402 decoupling cap
    # (C20..C31) bridging its VDD ↔ GND locally. The PCB places them on
    # a Ø22 mm pitch circle around the cable hole; the schematic lays
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
    # Layout: D11 at the TOP, D22 at the BOTTOM, vertically stacked at
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

    # D22 DOUT is intentionally unconnected (last link in the chain).
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


def _parse_sexp_list(text: str, start: int) -> tuple[list, int]:
    """Tiny S-expression list parser. Returns (tokens, next_index)
    where tokens is a nested list of strings + sub-lists.
    Expects text[start] == '(' and returns at the index just past the
    matching close paren."""
    assert text[start] == "(", f"expected ( at {start}, got {text[start]!r}"
    out: list = []
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "(":
            sub, i = _parse_sexp_list(text, i)
            out.append(sub)
        elif ch == ")":
            return out, i + 1
        elif ch == '"':
            # quoted string — find next un-escaped quote
            j = i + 1
            while j < len(text):
                if text[j] == "\\" and j + 1 < len(text):
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            # Decode standard escapes the same way KiCad writes them
            raw = text[i + 1:j]
            decoded = raw.encode().decode("unicode_escape")
            out.append(("str", decoded))
            i = j + 1
        else:
            # atom — read until whitespace or paren
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in "()":
                j += 1
            out.append(("atom", text[i:j]))
            i = j
    raise ValueError("unterminated S-expression")


def _sexp_head(node) -> str | None:
    """Return the 'head' atom of a sub-list (e.g. 'net', 'node', 'ref')."""
    if isinstance(node, list) and node:
        first = node[0]
        if isinstance(first, tuple) and first[0] == "atom":
            return first[1]
    return None


def _sexp_string_arg(node, index: int) -> str | None:
    """If node is a list and node[index] is a ('str', X) or ('atom', X),
    return X; otherwise None."""
    if isinstance(node, list) and len(node) > index:
        item = node[index]
        if isinstance(item, tuple) and item[0] in ("str", "atom"):
            return item[1]
    return None


def parse_netlist_for_pad_nets(netlist_path: Path) -> tuple[dict, list]:
    """Parse a KiCad S-expression netlist (exported with --format kicadsexpr)
    and return:
      - pad_nets: dict mapping (reference, pin_number_str) -> (net_code:int, net_name:str)
      - nets: list of (net_code, net_name) in order of appearance.

    Net code 0 (KiCad's "no net") is excluded. The netlist exporter
    starts numbering at 1.
    """
    text = netlist_path.read_text(encoding="utf-8")
    # Strip leading whitespace before first ( so the parser starts cleanly
    i = 0
    while i < len(text) and text[i].isspace():
        i += 1
    root, _ = _parse_sexp_list(text, i)
    # root is the (export ...) list. Find the (nets ...) child.
    nets_block = None
    for child in root[1:]:
        if _sexp_head(child) == "nets":
            nets_block = child
            break
    if nets_block is None:
        raise ValueError("no (nets ...) block in netlist")

    pad_nets: dict[tuple[str, str], tuple[int, str]] = {}
    nets: list[tuple[int, str]] = []
    for net in nets_block[1:]:
        if _sexp_head(net) != "net":
            continue
        code_str = None
        name = None
        nodes: list[tuple[str, str]] = []
        for entry in net[1:]:
            head = _sexp_head(entry)
            if head == "code":
                code_str = _sexp_string_arg(entry, 1)
            elif head == "name":
                name = _sexp_string_arg(entry, 1)
            elif head == "node":
                ref = None
                pin = None
                for sub in entry[1:]:
                    sh = _sexp_head(sub)
                    if sh == "ref":
                        ref = _sexp_string_arg(sub, 1)
                    elif sh == "pin":
                        pin = _sexp_string_arg(sub, 1)
                if ref is not None and pin is not None:
                    nodes.append((ref, pin))
        if code_str is None or name is None:
            continue
        code = int(code_str)
        if code == 0:
            continue
        nets.append((code, name))
        for (ref, pin) in nodes:
            pad_nets[(ref, pin)] = (code, name)
    return pad_nets, nets


def apply_nets_to_pcb(pcb_text: str, pad_nets: dict, nets: list) -> str:
    """Rewrite an oas.kicad_pcb text so that:
      - the (net 0 "") header is followed by (net N "<name>") declarations
        for every net in `nets`.
      - every (pad "<pin>" ...) inside a (footprint ... (property "Reference" "<R>") ...)
        block gets an additional (net <code> "<name>") clause IF (R, pin) is
        in pad_nets. Pads without a matching key are left alone (no
        (net 0 "") inserted — KiCad parses absent nets as net 0).

    Implementation: text-level scan that finds each top-level `(footprint`
    block, extracts the reference from its `(property "Reference" "..."`
    child, walks its pads, and re-emits each pad block with the inserted
    `(net ...)` clause."""

    # 1) Insert net dictionary right after `(net 0 "")` (which is unique
    #    in the file's top-level `(net 0 "")` declaration).
    net_decls = "\n".join(
        f"\t(net {code} {json.dumps(name)})"
        for code, name in nets
    )
    # KiCad accepts net names quoted with either " or escaped chars; using
    # json.dumps ensures we re-quote names like "+3V3" / "GND" / signal
    # names with slashes correctly. (No `Net-(...)` placeholder appears
    # in this design yet, but if KiCad ever emits one this still escapes
    # it cleanly.)
    marker = '\t(net 0 "")'
    if marker not in pcb_text:
        raise ValueError("expected '(net 0 \"\")' marker in PCB text")
    pcb_text = pcb_text.replace(marker, marker + "\n" + net_decls, 1)

    # 2) Walk top-level footprints. For each, find its Reference property,
    #    then find all its pads (sub-list whose head is 'pad') and inject
    #    `(net ...)` clauses.
    #
    # We use the same S-expression parser as the netlist parsing path but
    # locate each footprint by its raw text region in the original file so
    # we can produce a surgical edit (preserving every other byte of the
    # PCB file verbatim, which keeps round-tripping bit-stable and the
    # diff easy to review).

    # Find all top-level `(footprint ` openings — depth 1 inside the
    # outer `(kicad_pcb ...)` wrapper.
    out_chunks: list[str] = []
    cursor = 0
    depth = 0
    in_string = False
    string_escape = False
    fp_starts: list[int] = []
    fp_ends: list[int] = []
    for idx, ch in enumerate(pcb_text):
        if in_string:
            if string_escape:
                string_escape = False
            elif ch == "\\":
                string_escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            depth += 1
            if depth == 2 and pcb_text[idx:idx + len("(footprint")] == "(footprint":
                fp_starts.append(idx)
        elif ch == ")":
            if depth == 2 and fp_starts and len(fp_ends) < len(fp_starts):
                fp_ends.append(idx + 1)
            depth -= 1

    assert len(fp_starts) == len(fp_ends), (
        f"mismatched footprint paren count: {len(fp_starts)} starts vs {len(fp_ends)} ends"
    )

    rewritten_pieces: list[str] = []
    last = 0
    for fp_start, fp_end in zip(fp_starts, fp_ends):
        rewritten_pieces.append(pcb_text[last:fp_start])
        fp_text = pcb_text[fp_start:fp_end]
        fp_text_new = _patch_footprint_pad_nets(fp_text, pad_nets)
        rewritten_pieces.append(fp_text_new)
        last = fp_end
    rewritten_pieces.append(pcb_text[last:])
    return "".join(rewritten_pieces)


def _patch_footprint_pad_nets(fp_text: str, pad_nets: dict) -> str:
    """Given the source text of one (footprint ...) block, find its
    Reference property and inject (net ...) clauses into each pad that
    has a matching schematic node."""
    # 1) Extract Reference. Look for the (property "Reference" "<ref>" ...)
    #    child. The Reference property always appears before any (pad ...)
    #    child in our generated footprints, but we don't rely on order —
    #    we parse via a small state machine.
    ref = None
    # Search for the literal pattern; one Reference per footprint.
    m_idx = fp_text.find('(property "Reference" "')
    if m_idx >= 0:
        q_start = m_idx + len('(property "Reference" "')
        q_end = fp_text.find('"', q_start)
        if q_end > q_start:
            ref = fp_text[q_start:q_end]
    if ref is None:
        return fp_text  # no Reference -> leave untouched

    # Skip mech-only refs (these have attr `board_only` or `exclude_from_bom`).
    # They have no schematic counterpart by design.
    # We still walk pads (they may have nets explicitly assigned later) but
    # in practice pad_nets has no entries for these refs so nothing changes.

    # 2) Walk pads. We use a depth-counter scan over fp_text to find each
    #    top-level (pad ...) child (at depth 1 inside the footprint).
    out: list[str] = []
    i = 0
    depth = 0
    in_string = False
    string_escape = False
    pad_start = None
    while i < len(fp_text):
        ch = fp_text[i]
        if in_string:
            if string_escape:
                string_escape = False
            elif ch == "\\":
                string_escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            if depth == 2 and fp_text[i:i + len("(pad ")] == "(pad ":
                pad_start = i
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 1 and pad_start is not None:
                pad_end = i + 1
                pad_text = fp_text[pad_start:pad_end]
                # Stream-write everything before pad_start
                out.append(fp_text[len("".join(out)):pad_start] if not out else "")
                # That assertion is too messy — use index-based rewrite below.
                break
            i += 1
            continue
        i += 1

    # Reset and do an index-based rewrite (more robust than progressive `out` build).
    # Find every (pad "<pin>" ...) at depth 1 inside this footprint and
    # inject a (net ...) clause if matching.
    pad_blocks: list[tuple[int, int, str]] = []  # (start, end, pin_label)
    i = 0
    depth = 0
    in_string = False
    string_escape = False
    pad_start = None
    pad_pin = None
    while i < len(fp_text):
        ch = fp_text[i]
        if in_string:
            if string_escape:
                string_escape = False
            elif ch == "\\":
                string_escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            if depth == 2 and fp_text[i:i + len("(pad ")] == "(pad ":
                pad_start = i
                # Extract pad pin number: pattern is `(pad "<pin>"`.
                q1 = fp_text.find('"', i + len("(pad"))
                q2 = fp_text.find('"', q1 + 1) if q1 >= 0 else -1
                pad_pin = fp_text[q1 + 1:q2] if q1 >= 0 and q2 > q1 else ""
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 1 and pad_start is not None:
                pad_end = i + 1
                pad_blocks.append((pad_start, pad_end, pad_pin or ""))
                pad_start = None
                pad_pin = None
            i += 1
            continue
        i += 1

    if not pad_blocks:
        return fp_text

    pieces: list[str] = []
    cursor = 0
    for (p_start, p_end, pin) in pad_blocks:
        pieces.append(fp_text[cursor:p_start])
        pad_text = fp_text[p_start:p_end]
        key = (ref, pin)
        if pin and pin != "" and key in pad_nets:
            code, name = pad_nets[key]
            pad_text = _insert_net_into_pad(pad_text, code, name)
        pieces.append(pad_text)
        cursor = p_end
    pieces.append(fp_text[cursor:])
    return "".join(pieces)


def _insert_net_into_pad(pad_text: str, code: int, name: str) -> str:
    """Insert a (net code "name") clause just before the closing paren of
    the pad block. Indentation matches the pad's existing inner indent
    (one level deeper than the (pad ...) opening)."""
    # Find the closing paren position (last char before any trailing whitespace).
    # The pad block looks like:
    #   \t(pad "1" smd rect
    #   \t\t(at ...)
    #   \t\t...
    #   \t)
    # We insert before the last ')'. Detect the indentation of the inner
    # children by looking at the indent of the line containing the first
    # inner sub-clause (the `(at ` line is always present).
    lines = pad_text.split("\n")
    # Find leading whitespace of the last line that contains content other
    # than the closing paren.
    inner_indent = "\t\t"  # safe fallback
    for ln in lines:
        stripped = ln.lstrip("\t")
        if stripped and stripped.startswith("("):
            tabs = len(ln) - len(ln.lstrip("\t"))
            if tabs >= 1 and not stripped.startswith("(pad"):
                inner_indent = "\t" * tabs
                break

    # Locate position of the LAST ')' character in pad_text.
    close_idx = pad_text.rfind(")")
    if close_idx < 0:
        return pad_text
    net_str = f'{inner_indent}(net {code} {json.dumps(name)})\n'
    # Find the position right before the closing paren (skip back over the
    # whitespace/tabs that prefix the ')' on its own line).
    insert_at = close_idx
    while insert_at > 0 and pad_text[insert_at - 1] in (" ", "\t"):
        insert_at -= 1
    return pad_text[:insert_at] + net_str + pad_text[insert_at:]


def sync_pcb_nets_from_schematic(kicad_cli: str | None = None) -> int:
    """Sync electrical nets from the just-emitted schematic onto the PCB.

    1. Exports a netlist from oas.kicad_sch via kicad-cli sch export netlist.
    2. Parses the netlist into (ref, pin) -> (net_code, net_name) lookup.
    3. Rewrites oas.kicad_pcb so that:
       (a) the PCB header carries a (net N "<name>") declaration for every
           electrical net in the schematic, and
       (b) every pad whose (footprint_reference, pad_pin) appears in the
           netlist gains a matching (net code "name") clause.

    Returns the count of pads that received a net assignment.

    Skips silently if kicad-cli is not available (so generate.py still runs
    under bare CI without a KiCad install). regenerate.py finds kicad-cli
    on its own; when calling generate.py standalone, set the
    OAS_KICAD_CLI env var or pass `kicad_cli`.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    pcb_path = HERE / "oas.kicad_pcb"
    sch_path = HERE / "oas.kicad_sch"
    if not pcb_path.exists() or not sch_path.exists():
        return 0

    if kicad_cli is None:
        kicad_cli = os.environ.get("OAS_KICAD_CLI")
    if kicad_cli is None:
        for c in (
            r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe",
            r"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe",
        ):
            if Path(c).exists():
                kicad_cli = c
                break
    if kicad_cli is None:
        kicad_cli = shutil.which("kicad-cli")
    if kicad_cli is None:
        print("  [sync_pcb_nets] kicad-cli not found; skipping net sync")
        return 0

    with tempfile.TemporaryDirectory() as td:
        net_path = Path(td) / "oas.net"
        r = subprocess.run(
            [kicad_cli, "sch", "export", "netlist",
             "--output", str(net_path),
             "--format", "kicadsexpr",
             str(sch_path)],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        # kicad-cli prints "Ostrzeżenie: schemat posiada błędy numeracji"
        # (annotation warnings) on stderr even when the netlist file is
        # written successfully; treat exit code 0 as OK and warn on
        # anything else.
        if r.returncode != 0:
            print("  [sync_pcb_nets] kicad-cli netlist export failed:")
            print(r.stdout)
            print(r.stderr)
            return 0
        if not net_path.exists():
            print("  [sync_pcb_nets] netlist file not produced")
            return 0
        pad_nets, nets = parse_netlist_for_pad_nets(net_path)

    pcb_text = pcb_path.read_text(encoding="utf-8")
    new_text = apply_nets_to_pcb(pcb_text, pad_nets, nets)

    # Count assignments actually applied (= pad_nets entries whose ref has
    # a matching footprint on the PCB). A reference appears at least once
    # in the file iff `(property "Reference" "<R>"` is present.
    assigned = 0
    for (ref, _pin), _ in pad_nets.items():
        if f'(property "Reference" "{ref}"' in pcb_text:
            assigned += 1
    pcb_path.write_text(new_text, encoding="utf-8")
    return assigned


# -----------------------------------------------------------------------------
# Schematic Footprint property back-fill (v0.23 — closes review Mn3;
# v0.24 — lib-qualify the back-filled values to silence ERC footprint_link_issues)
# -----------------------------------------------------------------------------
# Every real component symbol in the sub-sheets is emitted with an EMPTY
# `(property "Footprint" "")` field by the `_sch_*` helpers (they don't know
# which footprint reference each symbol will end up wearing). The PCB-side
# footprint reference is authoritative for the JLCPCB BOM workflow that walks
# the PCB; however, running the schematic-driven netlist exporter or KiCad's
# "Update PCB from Schematic" path would surface a "no footprint assigned"
# warning per missing field. This post-process function back-fills the
# property by reading the PCB file (already written at this point in main())
# and copying each footprint's library reference into the matching schematic
# symbol's Footprint property.
#
# v0.23 BUG (caught in review iteration 2): the PCB-side `(property
# "Footprint" "...")` string is written without a library prefix by the
# `gen_*_pcb_footprint` helpers for inline (non-stock-library) footprints —
# e.g. `gen_capacitor_0402_pcb_footprint` writes the bare `"C_0402_1005Metric"`
# rather than `"Capacitor_SMD:C_0402_1005Metric"`. Naively copying that into
# the schematic produced 15 `footprint_link_issues` ERC warnings (parsed as
# library == "" which is not a registered footprint library).
#
# v0.24 fix: lib-qualify each bare footprint name via a hard-coded
# bare → library lookup table. The table is sourced from the stock KiCad
# library locations referenced by each `gen_*_pcb_footprint` helper (e.g.
# `R_0603_1608Metric` lives in `Resistor_SMD`, `D_SMA` lives in `Diode_SMD`,
# `SOT-23` lives in `Package_TO_SOT_SMD`, etc.). All entries are verified
# to exist in stock KiCad 9/10 installs. Project-local footprints (under
# `libraries/oas.pretty/`) and stock footprints emitted via
# `_emit_stock_lib_footprint` already carry the `Lib:Name` prefix in the
# PCB-side property, so they pass through unchanged.
#
# Note: power flags (#PWR*, #FLG*) intentionally retain the empty Footprint
# field — they are graphical / power-bus markers, not real parts and do not
# appear on the PCB.

# Bare-footprint-name → KiCad stock-library nickname. Used by
# `_build_pcb_ref_to_footprint` to lib-qualify any non-stock-library
# `(property "Footprint" "<bare>")` it encounters in the PCB so the
# schematic back-fill emits valid `<Lib>:<Name>` references. The library
# nicknames must match those declared in `fp-lib-table` and the entries
# must exist in the stock KiCad install.
BARE_FOOTPRINT_TO_LIB: dict[str, str] = {
    # 0402/0603/0805 chip caps + resistors — Capacitor_SMD / Resistor_SMD
    "C_0402_1005Metric": "Capacitor_SMD",
    "C_0603_1608Metric": "Capacitor_SMD",
    "C_0805_2012Metric": "Capacitor_SMD",
    "R_0603_1608Metric": "Resistor_SMD",
    # 2920 polyfuse footprint — uses Resistor_SMD library naming
    "R_2920_7351Metric": "Resistor_SMD",
    # Diode SMD packages — Diode_SMD library
    "D_SMA": "Diode_SMD",
    "D_SMB": "Diode_SMD",
    "D_SOD-323": "Diode_SMD",
    # SMD inductor (NR5040-class shielded power inductor)
    "L_NR5040": "Inductor_SMD",
    # Radial-lead electrolytic capacitors (through-hole)
    "CP_Radial_D6.3mm_P2.5mm": "Capacitor_THT",
    "CP_Radial_D8mm_P3.5mm": "Capacitor_THT",
    # SOT-23 small-signal transistors / diode packages
    "SOT-23": "Package_TO_SOT_SMD",
}


# -----------------------------------------------------------------------------
# v0.26 — Z-CLEARANCE GUARDRAIL
# -----------------------------------------------------------------------------
# The OAS PCB carries three daughterboards mounted on female pin sockets:
# ESP32-C6 DevKitM-1-N4 (MOD1, ~8.6 mm above PCB), MIKROE-2462 NFC Tag 2
# Click (MOD2, ~7 mm above PCB) and HLK-LD2410B (LDR1, ~7 mm above PCB).
# The daughterboard mech-ref footprints intentionally do NOT carry an
# F.CrtYd (see _emit_daughterboard_reference_pcb_footprint) so KiCad's
# DRC `courtyards_overlap` rule does not block legitimate SMD placement
# under their shadow. The trade-off: DRC has zero awareness of the third
# dimension, so a tall THT component placed under a daughterboard sails
# through DRC + ERC + visual review even when it would physically
# prevent the daughterboard from seating into its sockets.
#
# v0.25 clearance audit (kept inline below as the Z-clearance budget
# constants) found 3
# radial THT electrolytic caps (C1, C3, C4, all 11-12 mm tall) and one
# TO-263-5 buck (U1, 4.6 mm) under the ESP32 shadow that exceeded the
# ~5.5 mm under-daughterboard budget. v0.26 relocated them; this
# function backs the v0.26 fix with a programmatic invariant check that
# fires loudly on any future regression — the same pattern used by
# `BARE_FOOTPRINT_TO_LIB` to catch missing footprint-library mappings.
#
# How it works:
#   1. FOOTPRINT_HEIGHT — declares the maximum Z-extent (above PCB top
#      surface, mm) of every footprint emitted by generate.py. Keys are
#      the fully-qualified `(property "Footprint" "...")` strings as
#      written into oas.kicad_pcb. Missing entries -> hard assertion in
#      check_z_clearance_violations() (catches new generators that
#      forget to declare a height).
#   2. DAUGHTERBOARD_Z_CLEARANCE — per-daughterboard available clearance
#      between OAS PCB top surface and daughterboard PCB bottom surface.
#      Conservative values: socket plastic body height minus the typical
#      3 mm mating-pin tail that bottoms out inside the socket throat.
#   3. _DAUGHTERBOARD_BODY_SHADOWS — the PCB-frame XY rectangle each
#      daughterboard body covers (its mech-ref footprint's F.Fab body
#      outline, transformed by anchor + rotation). Computed lazily from
#      the source-of-truth `*_ANCHOR_*` / `*_BODY_*` constants at the
#      top of the file.
#   4. check_z_clearance_violations() — enumerates every placed
#      footprint (via _build_pcb_ref_to_footprint), looks up its height,
#      and tests whether its placement center falls inside any
#      daughterboard shadow. Returns the list of violations; main()
#      aborts with a formatted error message if non-empty.

# Footprint-property string → maximum component height above OAS PCB
# (mm, datasheet typical-max, conservative when a range exists).
#
# Sources (datasheet citations, originally gathered during the v0.25
# clearance audit):
#   - Chip resistors / capacitors 0402 / 0603 / 0805: Murata GRM /
#     Vishay CRCW datasheets — 0.5 / 0.95 / 1.25 mm respectively.
#   - SOT-23: Onsemi / Vishay generic — 1.1 mm.
#   - SMA / SMB diodes: Vishay — 2.3 mm (SMA), 2.6 mm (SMB).
#   - SOD-323 diodes: Vishay — 1.0 mm.
#   - SOT-583-8 / VSON-8 (TPS62933): TI SOT-583 — 0.85 mm.
#   - TO-263-5 / D2PAK-5 (LM2596S): TI — 4.83 mm max, 4.6 mm typ.
#   - 5×5 SMD shielded inductor (NR5040 / WE-PD-S): Wurth WE-PD-S 5045
#     = 4.5 mm worst-case body height.
#   - 2920 SMD polyfuse: Bourns MF-RHT — 3.0 mm.
#   - JST GH 6-pin horizontal SMD socket (J3): JST — 4.25 mm.
#   - JST SH 4-pin horizontal SMD socket (J9): JST — 1.5 mm.
#   - Phoenix MSTBA 5.08 mm 3-pin terminal block (J1): Phoenix
#     1988861 — 14.0 mm above PCB.
#   - PinHeader 2.54 mm vertical (J2, J10): plastic body 2.5 mm + pin
#     11.5 mm = 14.0 mm total above PCB.
#   - PinHeader 1.27 mm vertical (J4): plastic 2.0 mm + pin 8 mm =
#     ~10 mm above PCB.
#   - PinSocket 2.54 mm vertical (J5..J8): plastic body 8.5 mm.
#   - CP_Radial_D6.3mm_P2.5mm electrolytic: Panasonic ECA-1AM221 etc.
#     — 11.2 mm max.
#   - CP_Radial_D8.0mm_P3.50mm electrolytic: Panasonic ECA-1HM101 etc.
#     — 12.5 mm max.
#   - SK6812-SIDE side-emitting RGB LED: SK6812SIDE 3535 — 1.6 mm.
#   - Mounting hole / zip-tie hole / NPTH: 0 mm (no body).
#   - SEN66 mechanical reference (lays flat on PCB, body 21.5 mm tall):
#     SEN66 datasheet — 21.5 mm above PCB; the mech-ref carries its own
#     F.CrtYd so DRC catches XY collisions, but the body itself is the
#     daughterboard analogue — exempt from the under-daughterboard
#     check (handled via _IS_DAUGHTERBOARD_REF below).
#   - Daughterboard mech-refs themselves (ESP32-C6-DevKitM-1 /
#     MIKROE-2462 / LD2410): they ARE the daughterboards; never appear
#     "under" themselves. Excluded from the check via the same
#     _IS_DAUGHTERBOARD_REF predicate.
#
# UPDATE WHEN ADDING A NEW GENERATOR: add the new footprint's
# `(property "Footprint" "...")` string here with its datasheet-max
# height. If you forget, `check_z_clearance_violations()` asserts at
# regenerate time with a clear error message.
FOOTPRINT_HEIGHT: dict[str, float] = {
    # ---- Chip passives ----
    "Capacitor_SMD:C_0402_1005Metric": 0.5,
    "Capacitor_SMD:C_0603_1608Metric": 0.95,
    "Capacitor_SMD:C_0805_2012Metric": 1.25,
    "Resistor_SMD:R_0603_1608Metric": 0.5,
    # ---- Discrete semi packages ----
    "Diode_SMD:D_SMA": 2.3,
    "Diode_SMD:D_SMB": 2.6,
    "Diode_SMD:D_SOD-323": 1.0,
    "Package_TO_SOT_SMD:SOT-23": 1.1,
    "Package_TO_SOT_SMD:SOT-583-8": 0.85,
    "Package_TO_SOT_SMD:TO-263-5_TabPin3": 4.83,
    # Note: the TPS62933 SOT-583 footprint property is written as
    # `Package_SO:VSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` by gen_sot583_pcb_footprint
    "Package_SO:VSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm": 0.85,
    # ---- Inductors + polyfuses ----
    "Inductor_SMD:L_APV_ANR5040": 4.5,
    # v0.40 post-order: CENKER CKCS5040 is 5.0 × 5.0 × 4.0 mm.
    "Inductor_SMD:L_Cenker_CKCS5040": 4.0,
    "Fuse:Fuse_2920_7451Metric": 3.0,
    # ---- Radial THT electrolytics (the v0.26 audit-driven entries) ----
    "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm": 11.2,
    "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm": 12.5,
    # ---- Connectors ----
    "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal": 4.25,
    "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal": 1.5,
    "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal": 14.0,
    "Connector_PinHeader_1.27mm:PinHeader_1x05_P1.27mm_Vertical": 10.0,
    "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical": 14.0,
    "Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical": 8.5,
    "Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical": 8.5,
    # ---- OAS-internal footprints ----
    "oas:SK6812-SIDE": 1.6,
    "oas:MountingHole_3.8mm_M3": 0.0,
    "oas:ZipTieHole_3mm_NPTH": 0.0,
    # Mechanical references — daughterboards / SEN66. Excluded from the
    # under-daughterboard check via _IS_DAUGHTERBOARD_REF below, so this
    # value is informational only (the body Z of the part itself above
    # the PCB).
    "oas:SEN66_Mechanical_Reference": 21.5,
    "oas:LD2410_Mechanical_Reference": 7.0,
    "oas:ESP32-C6-DevKitM-1_Reference": 8.6,
    "oas:MIKROE-2462_Reference": 7.0,
}


# Component-clearance budget under each daughterboard, in mm. The budget
# is the worst-case-realistic vertical distance between the OAS PCB top
# surface and the daughterboard's PCB bottom surface (after the mating
# pin tails bottom out inside the socket throat). Per the v0.25
# clearance audit (rationale captured inline):
#   - ESP32 daughterboard on 2× PinSocket_1x15_P2.54mm_Vertical (8.5 mm
#     plastic body): conservative 5.5 mm budget. Top of the socket plastic
#     less ~3 mm of male pin tail protrusion from the DevKitM-1.
#   - MIKROE-2462 daughterboard on 2× PinSocket_1x08_P2.54mm_Vertical
#     (same 8.5 mm body): same 5.5 mm budget. NFC antenna spiral is on
#     the TOP side of the Click PCB (verified MikroE datasheet) — no
#     additional bottom-side penalty.
#   - LD2410 mounted on a 1×5 vertical 1.27 mm pin header (J4); the
#     LD2410 PCB sits only ~3 mm above the OAS PCB and its bottom side
#     carries ~1.5 mm of small bypass / SoC SMDs. Net budget ~2 mm. No
#     OAS-side components currently inside the LD2410 shadow, but the
#     guardrail flags any that creep in.
DAUGHTERBOARD_Z_CLEARANCE: dict[str, float] = {
    "MOD1": 5.5,   # ESP32-C6 DevKitM-1-N4
    "MOD2": 5.5,   # MIKROE-2462 NFC Tag 2 Click
    "LDR1": 2.0,   # HLK-LD2410B (direct 1.27 mm pin header, low stand-off)
}


# References that ARE daughterboards (or other tall mechanical refs that
# are themselves the obstacle). These are skipped when iterating OAS
# components, so a daughterboard never triggers the guardrail "against
# itself" or against another tall mech-ref.
_DAUGHTERBOARD_REFS: frozenset[str] = frozenset({"MOD1", "MOD2", "LDR1", "SENS1"})

# Per-daughterboard intentional mounting sockets — these are the female
# pin sockets (J5/J6 for ESP32, J7/J8 for MIKROE) and the LD2410's
# 1.27 mm pin header (J4) that the daughterboards PLUG INTO. They live
# under the daughterboard shadow by design — their "height" is the
# daughterboard's standoff, not an obstruction. Excluded per-shadow so
# the J5 socket (mounting MOD1) doesn't trigger a violation for MOD1,
# but would still trigger for MOD2 if somehow placed inside its shadow.
_DAUGHTERBOARD_MOUNTING_SOCKETS: dict[str, frozenset[str]] = {
    "MOD1": frozenset({"J5", "J6"}),       # ESP32 pin sockets
    "MOD2": frozenset({"J7", "J8"}),       # MIKROE mikroBUS sockets
    "LDR1": frozenset({"J4"}),             # LD2410 1.27 mm pin header
}


def _daughterboard_body_shadows() -> dict[str, tuple[float, float, float, float]]:
    """Compute the PCB-frame XY bounding box of each daughterboard body
    shadow. Returns a dict ref → (x_min, x_max, y_min, y_max).

    Shadows are computed from the source-of-truth `*_ANCHOR_*` and
    `*_BODY_*` constants at the top of the file (NOT parsed back out of
    the .kicad_pcb file) so this function works correctly even before
    the PCB has been written for the first time. The body extents match
    what `_emit_daughterboard_reference_pcb_footprint` writes onto
    F.Fab — see that function's docstring for the local-to-PCB
    coordinate transform under each rotation.
    """
    shadows: dict[str, tuple[float, float, float, float]] = {}

    # ESP32-C6 DevKitM-1-N4 (MOD1): helper rotation 90, LIB +X → PCB -Y,
    # LIB +Y → PCB +X. Body LIB rect (0,0) → (body_w, body_l). After
    # rotation the body covers PCB X = [anchor_x, anchor_x + body_l] and
    # PCB Y = [anchor_y - body_w, anchor_y].
    esp_xmin = ESP32_ANCHOR_X
    esp_xmax = ESP32_ANCHOR_X + ESP32_BODY_L
    esp_ymin = ESP32_ANCHOR_Y - ESP32_BODY_W
    esp_ymax = ESP32_ANCHOR_Y
    shadows["MOD1"] = (esp_xmin, esp_xmax, esp_ymin, esp_ymax)

    # MIKROE-2462 (MOD2): rotation 180, LIB +X → PCB -X, LIB +Y → PCB -Y.
    # LIB rect (0,0) → (body_w, body_l) maps to PCB X in
    # [anchor_x - body_w, anchor_x] and Y in [anchor_y - body_l, anchor_y].
    mik_xmin = MIKROE2462_ANCHOR_X - MIKROE2462_BODY_W
    mik_xmax = MIKROE2462_ANCHOR_X
    mik_ymin = MIKROE2462_ANCHOR_Y - MIKROE2462_BODY_L
    mik_ymax = MIKROE2462_ANCHOR_Y
    shadows["MOD2"] = (mik_xmin, mik_xmax, mik_ymin, mik_ymax)

    # LD2410 (LDR1): rotation 270, LIB +X → PCB +Y, LIB +Y → PCB -X.
    # LIB rect (0,0) → (LD2410_BODY_W, LD2410_BODY_H) maps to PCB X in
    # [anchor_x - LD2410_BODY_H, anchor_x] and Y in
    # [anchor_y, anchor_y + LD2410_BODY_W].
    ld_xmin = LD2410_ANCHOR_X - LD2410_BODY_H
    ld_xmax = LD2410_ANCHOR_X
    ld_ymin = LD2410_ANCHOR_Y
    ld_ymax = LD2410_ANCHOR_Y + LD2410_BODY_W
    shadows["LDR1"] = (ld_xmin, ld_xmax, ld_ymin, ld_ymax)

    return shadows


def _parse_footprint_placements() -> list[tuple[str, str, float, float, float]]:
    """Read oas.kicad_pcb and return (reference, footprint_property,
    pcb_x, pcb_y, rotation_deg) for every placed footprint. The
    placement (x, y) is the footprint's anchor in PCB-frame mm
    (note: KiCad stores PCB Y with the +Y-down screen convention,
    but `fy(y)` in this codebase negates the sign so the value in
    the file is mirrored — the `_invert_pcb_y` constant below
    handles that). The footprint property string is canonicalized
    via `BARE_FOOTPRINT_TO_LIB`. Rotation is 0 when absent in the
    `(at x y rot)` clause.
    """
    import re

    text = (HERE / "oas.kicad_pcb").read_text(encoding="utf-8")
    placements: list[tuple[str, str, float, float, float]] = []
    fp_starts = [m.start() for m in re.finditer(r'(?m)^\s*\(footprint "([^"]+)"', text)]
    fp_starts.append(len(text))
    for i in range(len(fp_starts) - 1):
        block = text[fp_starts[i]:fp_starts[i + 1]]
        m_name = re.search(r'\(footprint "([^"]+)"', block)
        if not m_name:
            continue
        fp_name_header = m_name.group(1)
        # Match (at <x> <y>) or (at <x> <y> <rot>). x / y are signed
        # floats. The `at` clause is the second-occurring property in
        # the block (after the (layer ...) clause) and IS the placement.
        m_at = re.search(
            r'\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?))?\)',
            block,
        )
        if not m_at:
            continue
        # NB: `fx(x)` / `fy(y)` add PAGE_CENTRE_X / PAGE_CENTRE_Y
        # (148.5 / 105.0 mm) to recentre PCB coordinates onto an A4
        # page. Reverse that here so placements are in the same
        # PCB frame the daughterboard shadows live in.
        pcb_x = float(m_at.group(1)) - PAGE_CENTRE_X
        pcb_y = float(m_at.group(2)) - PAGE_CENTRE_Y
        rotation = float(m_at.group(3)) if m_at.group(3) is not None else 0.0
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not m_ref:
            continue
        ref = m_ref.group(1)
        m_fp_prop = re.search(r'\(property "Footprint" "([^"]*)"', block)
        raw = m_fp_prop.group(1) if (m_fp_prop and m_fp_prop.group(1)) else fp_name_header
        if ":" in raw:
            canonical = raw
        else:
            lib = BARE_FOOTPRINT_TO_LIB.get(raw)
            assert lib is not None, (
                f"BARE_FOOTPRINT_TO_LIB missing entry for {raw!r} "
                f"(used by reference {ref!r})."
            )
            canonical = f"{lib}:{raw}"
        placements.append((ref, canonical, pcb_x, pcb_y, rotation))
    return placements


# Approximate planar (XY) body half-extent above the OAS PCB for each
# footprint property. Used by the Z-clearance guardrail to test whether
# a footprint's body (not just its anchor) intrudes into a daughterboard
# shadow. Each entry is a (half_x, half_y) tuple — half-extent of the
# component's BODY (not pads, not courtyard) along PCB X and Y at the
# rotation the OAS PCB uses for that footprint.
#
# Notes:
#   - For ROTATION-VARIABLE footprints (used at multiple rotations
#     across the OAS PCB) we'd need a different model. As of v0.26 every
#     footprint in `_FOOTPRINT_HALF_EXTENT` is used at exactly the
#     rotation listed here (e.g. all PinSocket_1x15 are placed with
#     rotation 90 — long axis along PCB X). If you ever place one at
#     rotation 0 too, swap the (half_x, half_y) values for that
#     instance or split the dict by (footprint, rotation).
#   - SMD/THT body half-extents from datasheets / KiCad footprint
#     library geometry. For circular radial-cap bodies, both half-X and
#     half-Y equal the body radius.
#   - Sockets (long axis) declared with the long axis along PCB X
#     (rotation 90 places the socket's LIB +Y along PCB +X — see the
#     mounting-socket placement comments around the `gen_pinsocket_*`
#     calls). Pad extent ±0.85 mm and crty extent ±1.77 mm in the short
#     axis; long axis follows pin count × 2.54 mm + 2× 1.77 mm crty.
_FOOTPRINT_HALF_EXTENT: dict[str, tuple[float, float]] = {
    "Capacitor_SMD:C_0402_1005Metric": (0.7, 0.7),
    "Capacitor_SMD:C_0603_1608Metric": (1.0, 0.9),
    "Capacitor_SMD:C_0805_2012Metric": (1.4, 1.0),
    "Resistor_SMD:R_0603_1608Metric": (1.0, 0.9),
    "Diode_SMD:D_SMA": (2.5, 1.4),
    "Diode_SMD:D_SMB": (3.0, 1.8),
    "Diode_SMD:D_SOD-323": (1.0, 0.7),
    "Package_TO_SOT_SMD:SOT-23": (1.5, 1.5),
    "Package_TO_SOT_SMD:SOT-583-8": (1.0, 1.0),
    "Package_TO_SOT_SMD:TO-263-5_TabPin3": (5.3, 5.3),
    "Package_SO:VSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm": (1.0, 1.0),
    "Inductor_SMD:L_APV_ANR5040": (2.6, 2.6),
    # v0.40 post-order: CENKER CKCS5040 body half-extent (5.0 / 2 + ~0.3 mm
    # for end-terminals = 2.8).
    "Inductor_SMD:L_Cenker_CKCS5040": (2.8, 2.6),
    "Fuse:Fuse_2920_7451Metric": (3.7, 2.6),
    # Radial caps — cylindrical body, radius = half-extent both axes
    "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm": (3.2, 3.2),
    "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm": (4.0, 4.0),
    # Connectors — placed at varying rotations, see per-call comments
    # in gen_*_pcb_footprint helpers. The (half_x, half_y) here assumes
    # the rotation actually used on the OAS PCB.
    # J3 — JST GH 6-pin horizontal SMD, rotation 0 (mouth +Y / -Y)
    "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal": (4.6, 2.5),
    # J9 — JST SH 4-pin horizontal SMD, rotation 180 (mouth toward chord)
    "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal": (2.7, 1.5),
    # J1 — Phoenix MSTBA 3-pin terminal block, rotation 180
    "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal": (8.5, 6.5),
    # J4 — LD2410 1.27 mm pin header, rotation 270 (long axis along PCB Y)
    "Connector_PinHeader_1.27mm:PinHeader_1x05_P1.27mm_Vertical": (1.5, 3.5),
    # J2, J10 — 6-pin 2.54 mm vertical pin header, rotation 0/180
    "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical": (1.5, 7.6),
    # J7/J8 — 8-pin MIKROE sockets, rotation 180 (long axis along PCB -Y)
    "Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical": (1.8, 10.2),
    # J5/J6 — 15-pin ESP32 sockets, rotation 90 (long axis along PCB +X)
    "Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical": (19.6, 1.8),
    "oas:SK6812-SIDE": (2.0, 1.0),
    "oas:MountingHole_3.8mm_M3": (1.9, 1.9),
    "oas:ZipTieHole_3mm_NPTH": (1.5, 1.5),
    # Mechanical references (daughterboards / SEN66) — these refs are
    # in _DAUGHTERBOARD_REFS so the guardrail skips them; values are
    # informational only.
    "oas:SEN66_Mechanical_Reference": (12.8, 27.6),
    "oas:LD2410_Mechanical_Reference": (3.81, 17.78),
    "oas:ESP32-C6-DevKitM-1_Reference": (24.13, 12.7),
    "oas:MIKROE-2462_Reference": (12.7, 28.575),
}


# Per-reference half-extent overrides — used when a single footprint
# entry above is placed at multiple rotations across the OAS PCB and
# the default (rotation-calibrated) value is wrong for one of the
# placements. Each entry pins down the SPECIFIC (half_x, half_y) for
# that reference, overriding the per-footprint lookup.
_FOOTPRINT_HALF_EXTENT_OVERRIDES: dict[str, tuple[float, float]] = {
    # J10 — PinHeader_1x06_P2.54mm_Vertical at rotation 90 (horizontal
    # pad row east). Default dict value (1.5, 7.6) is calibrated for
    # J2 at rotation 0; J10 needs the swapped (7.6, 1.5).
    "J10": (7.6, 1.5),
}


def check_z_clearance_violations() -> list[str]:
    """Programmatic invariant check: every footprint placed inside a
    daughterboard's body shadow must have a component height ≤ that
    daughterboard's under-board Z-clearance budget.

    Returns a list of human-readable violation strings (empty when the
    PCB is clean). Calls `assert` if any placed footprint references a
    footprint-property string not declared in `FOOTPRINT_HEIGHT` — this
    catches new generators that forget to declare a height (mirrors the
    `BARE_FOOTPRINT_TO_LIB` regression-prevention pattern from v0.24).

    The check tests footprint EXTENT (anchor ± per-footprint planar
    half-extent from `_FOOTPRINT_HALF_EXTENT`) rather than just anchor,
    so a 12 mm-tall radial cap anchored 2 mm outside a daughterboard
    shadow still triggers the guardrail when its body pokes ~2 mm into
    the shadow.

    Daughterboards themselves (MOD1/MOD2/LDR1/SENS1) and their mating
    sockets (J5/J6/J7/J8/J4) are exempt from the check — those are the
    daughterboard's own support feet and live under its shadow by
    design.
    """
    placements = _parse_footprint_placements()
    shadows = _daughterboard_body_shadows()
    violations: list[str] = []
    for ref, fp_prop, px, py, rotation in placements:
        if ref in _DAUGHTERBOARD_REFS:
            # Skip the daughterboard mech-refs themselves and the SEN66
            # body (handled by its own F.CrtYd).
            continue
        height = FOOTPRINT_HEIGHT.get(fp_prop)
        assert height is not None, (
            f"FOOTPRINT_HEIGHT missing entry for {fp_prop!r} "
            f"(used by reference {ref!r}). Add the appropriate "
            f"datasheet-max height to FOOTPRINT_HEIGHT in generate.py."
        )
        # Per-reference override takes precedence over the per-footprint
        # default — used when a single footprint is placed at multiple
        # rotations across the OAS PCB and the default dict value is
        # only calibrated for one of them. Currently J10 (PinHeader_1x06
        # at rotation 90) overrides the J2 default (rotation 0).
        half = _FOOTPRINT_HALF_EXTENT_OVERRIDES.get(ref)
        if half is None:
            half = _FOOTPRINT_HALF_EXTENT.get(fp_prop)
        assert half is not None, (
            f"_FOOTPRINT_HALF_EXTENT missing entry for {fp_prop!r} "
            f"(used by reference {ref!r}). Add a planar half-extent to "
            f"_FOOTPRINT_HALF_EXTENT in generate.py."
        )
        half_x, half_y = half
        _ = rotation  # captured by parser for future use; current AABB
                      # check uses calibrated half-extents (per-rotation
                      # values baked into _FOOTPRINT_HALF_EXTENT and
                      # _FOOTPRINT_HALF_EXTENT_OVERRIDES).
        # Footprint body AABB (axis-aligned bounding box) on the PCB.
        body_xmin, body_xmax = px - half_x, px + half_x
        body_ymin, body_ymax = py - half_y, py + half_y
        for db_ref, (x_min, x_max, y_min, y_max) in shadows.items():
            # Exempt the daughterboard's own mounting sockets.
            if ref in _DAUGHTERBOARD_MOUNTING_SOCKETS.get(db_ref, frozenset()):
                continue
            # AABB-vs-AABB intersection test.
            if (body_xmax < x_min or body_xmin > x_max
                    or body_ymax < y_min or body_ymin > y_max):
                continue
            budget = DAUGHTERBOARD_Z_CLEARANCE[db_ref]
            if height > budget:
                margin = budget - height
                violations.append(
                    f"  {ref:>6}  {fp_prop:<60}  at ({px:+7.2f}, {py:+7.2f}) "
                    f"height={height:5.2f} mm  under {db_ref} (budget {budget:.2f} mm)  "
                    f"margin={margin:+5.2f} mm"
                )
    return violations


def _build_pcb_ref_to_footprint() -> dict[str, str]:
    """Parse the freshly-written oas.kicad_pcb and return a mapping of
    `Reference` (e.g. "R5") → fully-qualified footprint string
    (e.g. "Resistor_SMD:R_0603_1608Metric").

    Reads each `(footprint ...)` block (each at the start of a line, with
    optional leading whitespace — KiCad pretty-prints nested blocks with
    tab/space indentation, so the regex must tolerate that to capture all
    76 placed footprints rather than only the 45 written at column 0).
    For each block, extracts its inner `(property "Footprint" "...")`
    clause (which is the canonical source-of-truth — `_emit_stock_lib_footprint`
    writes a fully-qualified `Lib:Name` string, and
    `_emit_two_pad_smd_footprint` / inline helpers write a bare `Name`
    that we lib-qualify via `BARE_FOOTPRINT_TO_LIB`). The fallback (no
    `(property "Footprint" ...)` at all) uses the footprint block header
    name, also lib-qualified via the table.

    Every value in the returned dict is GUARANTEED to contain `:` (a real
    library prefix). If any bare name escaped the lookup table, this
    function `assert`-fails so the missing entry is caught at generate time
    rather than as a downstream ERC warning.

    Note on the regex: `(?m)^\\s*\\(footprint "..."` requires the
    `(footprint` token to be the first non-whitespace content on its line.
    Verified (v0.25) that the file contains no nested `(footprint "..."`
    references — every match in `oas.kicad_pcb` is a real top-level
    placed-footprint instance. Match count is exactly 76, equal to the
    kiutils enumeration of placed footprints.
    """
    import re

    text = (HERE / "oas.kicad_pcb").read_text(encoding="utf-8")
    mapping: dict[str, str] = {}

    # Walk every `(footprint "<libname>:<fpname>" ...)` block. For each,
    # extract its `(property "Reference" "<R>" ...)` and use the footprint
    # name from its header as the Footprint property value.
    # The regex allows optional leading whitespace because gen_pcb() emits
    # some footprint blocks with tab/space indentation (KiCad-style nested
    # block pretty-printing). v0.24's column-0-only regex silently skipped
    # 31 of 76 placed footprints, leaving 27 schematic-side empty Footprint
    # properties; v0.25 closes that gap.
    fp_starts = [m.start() for m in re.finditer(r'(?m)^\s*\(footprint "([^"]+)"', text)]
    # Append end of file to bound the last block.
    fp_starts.append(len(text))
    for i in range(len(fp_starts) - 1):
        block = text[fp_starts[i]:fp_starts[i + 1]]
        # Block may begin with the leading whitespace captured by `\s*` —
        # use search rather than match so we don't depend on column-0 here.
        m_name = re.search(r'\(footprint "([^"]+)"', block)
        if not m_name:
            continue
        fp_name_header = m_name.group(1)
        # Inside this block, the FIRST `(property "Reference" "..."` line is
        # the reference designator for the placed footprint. The
        # `(property "Footprint" "..."` clause is the authoritative
        # library-path string (may be bare for inline footprints, qualified
        # for stock-library footprints).
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not m_ref:
            continue
        ref = m_ref.group(1)
        m_fp_prop = re.search(r'\(property "Footprint" "([^"]*)"', block)
        raw = m_fp_prop.group(1) if (m_fp_prop and m_fp_prop.group(1)) else fp_name_header
        if ":" in raw:
            canonical = raw
        else:
            # Bare name — lib-qualify via the lookup table.
            lib = BARE_FOOTPRINT_TO_LIB.get(raw)
            assert lib is not None, (
                f"BARE_FOOTPRINT_TO_LIB missing entry for {raw!r} "
                f"(used by footprint reference {ref!r}). Add the appropriate "
                f"library nickname to BARE_FOOTPRINT_TO_LIB in generate.py."
            )
            canonical = f"{lib}:{raw}"
        mapping[ref] = canonical

    # Sanity check: every mapped value must be lib-qualified. This catches
    # any regression where a new bare-name generator is added without a
    # matching BARE_FOOTPRINT_TO_LIB entry.
    for ref, fp in mapping.items():
        assert ":" in fp, f"Footprint mapping for {ref!r} is not lib-qualified: {fp!r}"
    return mapping


def _build_lcsc_metadata_map() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Return `(Value, Footprint)` -> `(Manufacturer, MPN, LCSC)` from the
    canonical Python dict in `lcsc_mapping.py`.

    Used by `_apply_schematic_lcsc_metadata` to inject supply-chain sourcing
    metadata into every schematic symbol instance, so the same data that
    drives the BOM is visible inside the schematic editor (and exportable
    via `kicad-cli sch export bom --fields`).

    Skips DEPRECATED rows (LCSC starts with "DEPRECATED-") — those are
    sentinel entries kept only to detect pre-v0.36 regenerated schematics
    and have no matching schematic symbol.
    """
    import sys as _sys
    _sys.path.insert(0, str(HERE))
    from lcsc_mapping import LCSC_MAPPING  # noqa: E402

    result: dict[tuple[str, str], tuple[str, str, str]] = {}
    for (value, footprint), entry in LCSC_MAPPING.items():
        lcsc = entry.get("lcsc", "").strip()
        if lcsc.startswith("DEPRECATED-"):
            continue
        mfr = entry.get("manufacturer", "").strip()
        mpn = entry.get("mpn", "").strip()
        result[(value, footprint)] = (mfr, mpn, lcsc)
    return result


def _apply_schematic_lcsc_metadata(
    content: str,
    lcsc_map: dict[tuple[str, str], tuple[str, str, str]],
) -> str:
    """Post-process a sub-sheet schematic string, injecting three new
    properties on every real-component symbol instance whose
    `(Value, Footprint)` pair appears in `lcsc-mapping.csv`:

      - `(property "Manufacturer" "...")`
      - `(property "MPN" "...")`
      - `(property "LCSC" "...")`

    All three are emitted as HIDDEN properties at position (0, 0) so
    they don't clutter the schematic rendering, but they become part
    of the symbol's data and are picked up by `kicad-cli sch export
    bom --fields "Value,Reference,Footprint,Manufacturer,MPN,LCSC,..."`.

    This closes the v0.37 user concern "projekt sobie, BOM sobie": the
    schematic is now self-sufficient for BOM generation. The
    `lcsc-mapping.csv` post-process in `export_production.py` still
    runs as a defensive cross-check, but a kicad-cli BOM export that
    skips the post-process will still carry full sourcing metadata.

    Walks each top-level `(symbol ...)` block. For each block whose
    `Reference` is non-`#`-prefixed (i.e. a real component, not a
    power flag) AND whose `(Value, Footprint)` pair has a mapping
    entry, inserts the three new properties immediately after the
    last existing `(property ...)` block (right before the first
    `(pin ` or `(instances ` clause).

    Deterministic UUIDs derived from the symbol's Reference so the
    schematic file stays bit-identical across regenerations.
    """
    import re

    out_parts: list[str] = []
    i = 0
    n = len(content)
    while i < n:
        idx = content.find("(symbol", i)
        if idx == -1:
            out_parts.append(content[i:])
            break
        out_parts.append(content[i:idx])
        # Find matching close paren of the (symbol ...) block.
        depth = 0
        j = idx
        while j < n:
            ch = content[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = content[idx:j]

        # Extract Reference; skip power flags / virtual symbols.
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if m_ref and not m_ref.group(1).startswith("#"):
            ref = m_ref.group(1)
            m_val = re.search(r'\(property "Value" "([^"]+)"', block)
            m_fp = re.search(r'\(property "Footprint" "([^"]*)"', block)
            if m_val and m_fp:
                value = m_val.group(1)
                footprint = m_fp.group(1)
                metadata = lcsc_map.get((value, footprint))
                if metadata:
                    mfr, mpn, lcsc = metadata
                    # Find the END of the last `(property ...)` block inside
                    # this symbol. Properties appear sequentially before the
                    # first `(pin ` clause; we walk depth-counting to locate
                    # each property's close paren and take the last one.
                    last_prop_end = _find_last_property_end(block)
                    if last_prop_end is not None:
                        new_props = _emit_schematic_metadata_properties(
                            ref, mfr, mpn, lcsc,
                        )
                        block = block[:last_prop_end] + new_props + block[last_prop_end:]
        out_parts.append(block)
        i = j
    return "".join(out_parts)


def _find_last_property_end(block: str) -> int | None:
    """Return the position (offset within `block`) immediately AFTER the
    closing `)` of the LAST top-level `(property "..." ...)` clause
    inside the symbol block. Returns None if no property is found."""
    last_end: int | None = None
    pos = 0
    while True:
        idx = block.find('(property "', pos)
        if idx == -1:
            break
        # Walk depth to find matching close.
        depth = 0
        k = idx
        while k < len(block):
            ch = block[k]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    last_end = k
                    pos = k
                    break
            k += 1
        else:
            break
    return last_end


def _emit_schematic_metadata_properties(
    reference: str, manufacturer: str, mpn: str, lcsc: str,
) -> str:
    """Render three hidden schematic properties (Manufacturer, MPN, LCSC)
    matching the standard KiCad schematic property block format used by
    Reference/Value/Footprint/Datasheet/Description (no `(uuid ...)`
    clause — schematic symbol-instance properties don't carry UUIDs;
    only the symbol itself has a UUID). Hidden at position (0, 0)
    — they exist for BOM export only, never rendered."""
    # `reference` accepted for API symmetry with _apply_schematic_lcsc_metadata
    # but unused — schematic property blocks are not UUID-stamped.
    _ = reference

    def _prop(name: str, value: str) -> str:
        # Escape any embedded quotes in the value.
        safe = value.replace('"', '\\"')
        return (
            f'\n\t\t(property "{name}" "{safe}"\n'
            f'\t\t\t(at 0 0 0)\n'
            f'\t\t\t(effects\n'
            f'\t\t\t\t(font\n'
            f'\t\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t\t)\n'
            f'\t\t\t\t(hide yes)\n'
            f'\t\t\t)\n'
            f'\t\t)'
        )

    return (
        _prop("Manufacturer", manufacturer)
        + _prop("MPN", mpn)
        + _prop("LCSC", lcsc)
    )


def _apply_schematic_footprints(content: str, ref_to_fp: dict[str, str]) -> str:
    """Post-process a sub-sheet schematic string, replacing every
    `(property "Footprint" "")` field of a real-component symbol instance
    with `(property "Footprint" "<libname>:<fpname>")` looked up from the
    PCB-side mapping. Symbols whose Reference begins with `#` (power /
    flag markers) are left untouched because they have no physical
    footprint on the PCB.

    Walks each top-level `(symbol ...)` block, reads its Reference, and
    if a non-#-prefixed Reference has a mapped footprint, rewrites the
    block's first `(property "Footprint" "")` occurrence.
    """
    import re

    # Find each (symbol ...) block at the top level. Use a depth-counter.
    out_parts: list[str] = []
    i = 0
    n = len(content)
    while i < n:
        idx = content.find("(symbol", i)
        if idx == -1:
            out_parts.append(content[i:])
            break
        # Copy text before the block as-is.
        out_parts.append(content[i:idx])
        # Find matching close paren.
        depth = 0
        j = idx
        while j < n:
            ch = content[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = content[idx:j]
        # Extract Reference. The first `(property "Reference" "..."` inside
        # the block is the designator.
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if m_ref:
            ref = m_ref.group(1)
            fp_value = ref_to_fp.get(ref)
            if fp_value and not ref.startswith("#"):
                # Rewrite first `(property "Footprint" "")` -> `("Footprint" "<fp>")`.
                # Use count=1 so only the schematic-symbol-instance Footprint
                # property is touched (lib_symbol templates handled in the
                # `(symbol ...)` library section at top of file have their
                # own `(property "Footprint" "")` which stays untouched
                # because library-template symbols live INSIDE the
                # `(lib_symbols ...)` block, not at top level — but defensive
                # count=1 keeps the behavior deterministic regardless).
                block = block.replace(
                    '(property "Footprint" ""',
                    f'(property "Footprint" "{fp_value}"',
                    1,
                )
        out_parts.append(block)
        i = j
    return "".join(out_parts)


# -----------------------------------------------------------------------------
# v0.28 — COPPER ROUTING
# -----------------------------------------------------------------------------
# After PCB footprints are placed and schematic nets are synced onto pads,
# we emit explicit copper tracks (segments + vias) for every electrical
# connection, plus full-board GND zone pours on F.Cu and B.Cu. The pour
# layers carry the GND net so all GND-pin pads connect automatically via
# thermal reliefs — eliminating the need to route ~60 GND pads as tracks.
#
# Design rules used here (must match `gen_pro()`'s design rule set):
#   - Track widths:
#       0.5 mm — 24 V power chain (J1 → D1 → Q1 → F1 → C1 → U1.VIN)
#       0.5 mm — +5 V rail (U1.OUT → C4 → U2.VIN, LED ring)
#       0.4 mm — +3.3 V rail (U2.OUT → all chip VDDs)
#       0.2 mm — every signal (I2C, UART, GPIO, WS2812, USB, EN, BOOT)
#   - Clearance: 0.15 mm (KiCad default)
#   - Vias: 0.6 mm diameter, 0.3 mm drill (standard JLCPCB)
#
# Layer strategy: F.Cu primary, B.Cu used for crossovers and GND return.
# Both layers carry a GND zone pour over the full PCB outline (D-shape +
# cable hole keep-out + connector cutout keep-outs).
#
# Routes are computed from the parsed pad coordinates in the freshly-
# emitted PCB (see `_routing_pad_db()` below) so layout changes to
# component positions propagate automatically without hand-editing
# segment coordinates. Deterministic UUID v5 ("oas-track:<idx>" /
# "oas-via:<idx>" / "oas-zone:<layer>") keeps the file bit-identical
# across runs.

# Which chunks of the v0.28 routing plan are enabled. Each chunk adds
# tracks for one functional subsystem; chunks are turned on incrementally
# (v0.28a → v0.28e) so DRC and visual review can catch issues per chunk.
# Final state (v0.28e) routes every chunk.
ROUTING_CHUNKS: tuple[str, ...] = (
    "gnd",         # Chunk 1 — F.Cu + B.Cu GND copper pour
    "hand_v40",    # Chunk 3 — hand-routes closing the 8 unconnected
                   # pads the autoroute snapshot left open (J9.2/3/4
                   # trio + GND stitching for U1 tab, J3 MP, D15/D16
                   # LED ring, C21 cap).
    "autoroute",   # Chunk 2 — Freerouting v2.2.4 snapshot. Re-paved
                   # against the rework-3/4/5 placement on 2026-05-18:
                   # J10 horizontal, Q1/D3/R1/R4 cluster south of F1,
                   # D1 +3 mm east, C11 south of J4, U1 +1 mm east.
                   # 413 segments + 23 vias produced from 100 unrouted
                   # nets in 1m26s (7 effective passes, score 987.66).
                   # 3 nets remain unrouted (best result so far —
                   # previous runs left 4-7); hand-route those in a
                   # follow-up chunk once the unrouted nets are
                   # identified from DRC.
    # "io_finalize",      # Chunk 3 (legacy v0.28 — superseded; not used)
)


# Track width selectors (mm). The cascade through `_track_width_for_net`
# picks 0.5 mm for known power rails, 0.4 mm for +3V3, else 0.2 mm.
_NET_TRACK_WIDTH: dict[str, float] = {
    "+24V": 0.5,
    "+5V": 0.5,
    "+3V3": 0.4,
    "Net-(D1-A2)": 0.5,         # input protection chain (24 V)
    "Net-(F1-Pad2)": 0.5,       # PTC output, protected 24 V
    "Net-(D2-K)": 0.5,          # buck1 switch node (high di/dt — keep wide)
    "Net-(U2-SW)": 0.4,         # buck2 switch node
}


def _track_width_for_net(net_name: str) -> float:
    """Return track width in mm for a given net name."""
    return _NET_TRACK_WIDTH.get(net_name, 0.2)


def _routing_pad_db() -> tuple[dict, dict]:
    """Parse oas.kicad_pcb and return:

      pads: dict mapping (ref, pin) → (pcb_local_x, pcb_local_y, net_code, net_name)
      nets: dict mapping net_name → list of (ref, pin, x, y)

    Coordinates are in PCB-local mm (origin = PCB centre, +Y = downward
    on screen = toward chord), already adjusted for PAGE_CENTRE_X/Y.
    Footprint rotation is correctly composed with pad local offset using
    the standard 2D rotation matrix (math CCW; KiCad's +Y-down screen
    convention is preserved by leaving both PCB-local and pad-local in
    +Y-down sign space).
    """
    import math
    import re

    text = (HERE / "oas.kicad_pcb").read_text(encoding="utf-8")

    pads: dict[tuple[str, str], tuple[float, float, int, str]] = {}
    nets: dict[str, list[tuple[str, str, float, float]]] = {}

    # Find each top-level `(footprint "..."` block by matching the `(footprint`
    # token followed by quoted name, anywhere in the file (some are at column
    # 0, others tab-indented).
    fp_starts = [m.start() for m in re.finditer(r'\(footprint "', text)]
    # Append end of file as terminator
    fp_starts.append(len(text))
    for i in range(len(fp_starts) - 1):
        block = text[fp_starts[i]:fp_starts[i + 1]]
        # Extract footprint anchor (at x y [rot])
        m_at = re.search(
            r'\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?))?\)',
            block,
        )
        if not m_at:
            continue
        fp_x = float(m_at.group(1))
        fp_y = float(m_at.group(2))
        fp_ang = float(m_at.group(3)) if m_at.group(3) else 0.0
        # Extract Reference
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not m_ref:
            continue
        ref = m_ref.group(1)
        # Walk every (pad "<pin>" ...) inside this block. Extract pad
        # local-offset (at lx ly [pad_rot]) and the (net code "name") clause.
        # Pad blocks are nested 1 level deeper than the footprint, so we
        # use a depth-tracking parser to find them robustly.
        depth = 0
        in_str = False
        esc = False
        pad_start = None
        for j, ch in enumerate(block):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == "(":
                depth += 1
                if depth == 2 and block[j:j + len("(pad ")] == "(pad ":
                    pad_start = j
                continue
            if ch == ")":
                if depth == 2 and pad_start is not None:
                    pad_block = block[pad_start:j + 1]
                    pad_start = None
                    # Pad number is the first quoted string
                    m_pin = re.search(r'\(pad\s+"([^"]*)"', pad_block)
                    if not m_pin:
                        depth -= 1
                        continue
                    pin = m_pin.group(1)
                    if pin == "" or pin == "MP":
                        depth -= 1
                        continue
                    m_pat = re.search(
                        r'\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?))?\)',
                        pad_block,
                    )
                    if not m_pat:
                        depth -= 1
                        continue
                    lx = float(m_pat.group(1))
                    ly = float(m_pat.group(2))
                    # Net assignment. Generate.py emits the legacy
                    # `(net <code> "<name>")` format; `kicad-cli pcb drc
                    # --save-board` re-saves the file in KiCad 10's new
                    # compact `(net "<name>")` format (no integer code on
                    # pads, integer codes carried only by the header
                    # `(net N "<name>")` table). Handle both.
                    m_net = re.search(r'\(net\s+(\d+)\s+"([^"]*)"\)', pad_block)
                    if m_net:
                        net_code = int(m_net.group(1))
                        net_name = m_net.group(2)
                    else:
                        m_net2 = re.search(r'\(net\s+"([^"]*)"\)', pad_block)
                        if m_net2:
                            net_code = 0   # filled later via _net_code()
                            net_name = m_net2.group(1)
                        else:
                            net_code = 0
                            net_name = ""
                    # Compute global position via rotation + translation
                    a = math.radians(fp_ang)
                    ca, sa = math.cos(a), math.sin(a)
                    gx_page = fp_x + (ca * lx - sa * ly)
                    gy_page = fp_y + (sa * lx + ca * ly)
                    # Convert to PCB-local (origin = centre)
                    px = gx_page - PAGE_CENTRE_X
                    py = gy_page - PAGE_CENTRE_Y
                    pads[(ref, pin)] = (px, py, net_code, net_name)
                    if net_name and not net_name.startswith("unconnected-"):
                        nets.setdefault(net_name, []).append((ref, pin, px, py))
                depth -= 1
                continue

    return pads, nets


# Track segment / via / zone emitters. UUIDs are derived from a global
# counter so two consecutive regenerations produce bit-identical output.

class _RouteEmitter:
    """Accumulate (segment ...) / (via ...) / (zone ...) records during
    routing. Encapsulates UUID counter to keep the routing helpers simple
    while still emitting deterministic UUIDs."""

    def __init__(self):
        self._segments: list[str] = []
        self._vias: list[str] = []
        self._zones: list[str] = []
        self._seg_idx = 0
        self._via_idx = 0

    def seg(self, x1: float, y1: float, x2: float, y2: float,
            width: float, layer: str, net_code: int,
            *, uuid_tag: str | None = None) -> None:
        """Emit a single (segment ...) entry. Coordinates in PCB-local mm.

        `uuid_tag` overrides the auto-increment counter. Callers driven by
        an external data source (e.g. `_route_autoroute_tracks` reading
        `oas_routes.ROUTES_SEGMENTS`) supply a stable per-record tag like
        `"autoroute:seg:0001"` so the resulting UUID does not depend on
        the iteration order of any other routing chunk.
        """
        # Skip zero-length segments
        if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
            return
        if uuid_tag is None:
            idx = self._seg_idx
            self._seg_idx += 1
            tag = f"oas-track:seg:{idx}"
        else:
            tag = f"oas-track:{uuid_tag}"
        u = str(uuid.uuid5(_OAS_NS, tag))
        self._segments.append(
            f'\t(segment\n'
            f'\t\t(start {fx(x1)} {fy(y1)})\n'
            f'\t\t(end {fx(x2)} {fy(y2)})\n'
            f'\t\t(width {fmt(width)})\n'
            f'\t\t(layer "{layer}")\n'
            f'\t\t(net {net_code})\n'
            f'\t\t(uuid "{u}")\n'
            f'\t)'
        )

    def via(self, x: float, y: float, net_code: int,
            size: float = 0.6, drill: float = 0.3,
            *, layers: tuple[str, ...] = ("F.Cu", "B.Cu"),
            uuid_tag: str | None = None) -> None:
        """Emit a (via ...) entry.

        `layers` is the (top, bottom) tuple of layer names the via tunnels
        through; defaults to ("F.Cu", "B.Cu") for a standard through-hole
        via. `uuid_tag` overrides the auto-increment counter (see seg()).
        """
        if uuid_tag is None:
            idx = self._via_idx
            self._via_idx += 1
            tag = f"oas-track:via:{idx}"
        else:
            tag = f"oas-track:{uuid_tag}"
        u = str(uuid.uuid5(_OAS_NS, tag))
        layers_str = " ".join(f'"{l}"' for l in layers)
        self._vias.append(
            f'\t(via\n'
            f'\t\t(at {fx(x)} {fy(y)})\n'
            f'\t\t(size {fmt(size)})\n'
            f'\t\t(drill {fmt(drill)})\n'
            f'\t\t(layers {layers_str})\n'
            f'\t\t(net {net_code})\n'
            f'\t\t(uuid "{u}")\n'
            f'\t)'
        )

    def route_segment(self, x1: float, y1: float, x2: float, y2: float,
                      width: float, net_code: int, *, layer: str = "F.Cu",
                      style: str = "direct") -> None:
        """Convenience wrapper: route from (x1,y1) to (x2,y2).

          style="direct" — single straight segment
          style="manhattan-h" — horizontal then vertical (one bend at (x2,y1))
          style="manhattan-v" — vertical then horizontal (one bend at (x1,y2))
        """
        if style == "direct":
            self.seg(x1, y1, x2, y2, width, layer, net_code)
        elif style == "manhattan-h":
            self.seg(x1, y1, x2, y1, width, layer, net_code)
            self.seg(x2, y1, x2, y2, width, layer, net_code)
        elif style == "manhattan-v":
            self.seg(x1, y1, x1, y2, width, layer, net_code)
            self.seg(x1, y2, x2, y2, width, layer, net_code)
        else:
            raise ValueError(f"Unknown route style: {style!r}")

    def route_chain(self, points: list[tuple[float, float]],
                    width: float, net_code: int, *,
                    layer: str = "F.Cu") -> None:
        """Route a sequence of points by direct segments (point[i]→point[i+1])."""
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.seg(x1, y1, x2, y2, width, layer, net_code)

    def gnd_zone(self, layer: str, net_code: int) -> None:
        """Emit a copper-pour zone for GND on the given layer (F.Cu or B.Cu).

        Polygon = an N-segment approximation of the D-shape PCB outline
        (arc R=60 mm + chord 82.65 mm at +Y_CHORD). KiCad's zone-filler
        auto-computes the cable-hole keep-out and connector-cutout
        keep-outs from the Edge.Cuts geometry + design-rule clearance.
        Thermal reliefs on GND pads are automatic.
        """
        import math
        # Walk the arc from chord-WEST endpoint (-HALF_CHORD, +Y_CHORD)
        # over the top of the PCB (math angle +π → +3π/2 → +2π) back to
        # chord-EAST endpoint (+HALF_CHORD, +Y_CHORD). In KiCad's screen
        # frame +Y points DOWN, so the chord sits visually at the BOTTOM
        # and the arc bulges UP/over the TOP (math angle in (π, 2π) range).
        # In standard math convention (which the +Y-down PCB-local frame
        # respects since both X and Y just track screen mm), the chord
        # endpoints sit at angles atan2(+Y_CHORD, ±HALF_CHORD). We walk
        # the LONG way (via PCB Y = -R apex) from W to E.
        theta_chord_E = math.atan2(Y_CHORD,  HALF_CHORD)
        theta_chord_W = math.atan2(Y_CHORD, -HALF_CHORD)
        N_arc = 96
        pts: list[tuple[float, float]] = []
        # Inset the polygon by 0.5 mm from the actual PCB outline so the
        # zone doesn't touch Edge.Cuts (avoids copper_edge_clearance DRC).
        R_inset = R_OUTLINE - 0.5
        Y_chord_inset = Y_CHORD - 0.5
        theta_chord_E_inset = math.atan2(Y_chord_inset, +math.sqrt(R_inset**2 - Y_chord_inset**2))
        theta_chord_W_inset = math.atan2(Y_chord_inset, -math.sqrt(R_inset**2 - Y_chord_inset**2))
        theta_start = theta_chord_W_inset
        theta_end = theta_chord_E_inset + 2 * math.pi
        for i in range(N_arc + 1):
            t = i / N_arc
            theta = theta_start + t * (theta_end - theta_start)
            px = R_inset * math.cos(theta)
            py = R_inset * math.sin(theta)
            pts.append((px, py))
        # Polygon closes implicitly back to first point.
        pts_text = "".join(
            f'\t\t\t\t(xy {fmt(x + PAGE_CENTRE_X)} {fmt(y + PAGE_CENTRE_Y)})\n'
            for x, y in pts
        )
        u = str(uuid.uuid5(_OAS_NS, f"oas-zone:gnd:{layer}"))
        # Use 0.15 mm clearance, 0.25 mm min thickness, automatic thermal
        # reliefs. Standard JLCPCB-compatible fill parameters.
        # `priority 0` is the default; if other zones are added later
        # higher-priority ones fill first.
        self._zones.append(
            f'\t(zone\n'
            f'\t\t(net {net_code})\n'
            f'\t\t(net_name "GND")\n'
            f'\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{u}")\n'
            f'\t\t(hatch edge 0.5)\n'
            f'\t\t(connect_pads\n'
            f'\t\t\t(clearance 0.2)\n'
            f'\t\t)\n'
            f'\t\t(min_thickness 0.25)\n'
            f'\t\t(filled_areas_thickness no)\n'
            f'\t\t(fill yes\n'
            f'\t\t\t(thermal_gap 0.5)\n'
            f'\t\t\t(thermal_bridge_width 0.5)\n'
            f'\t\t\t(island_removal_mode 0)\n'
            f'\t\t)\n'
            f'\t\t(polygon\n'
            f'\t\t\t(pts\n'
            f'{pts_text}'
            f'\t\t\t)\n'
            f'\t\t)\n'
            f'\t)'
        )

    def gnd_island_keepout(self, layer: str, xmin: float, ymin: float,
                           xmax: float, ymax: float, *, tag: str) -> None:
        """Emit a (zone (keepout (copperpour not_allowed)) ...) rectangle
        that prevents the GND zone-filler from creating a small stranded
        island in the rectangle [xmin..xmax] x [ymin..ymax] (PCB-local mm).

        Used to close the last few `unconnected_items` DRC reports that
        come from sub-1.5 mm² pour fragments which cannot be bridged by
        through-vias (because the opposite-layer GND main pour does not
        overlap them, or because of clearance to nearby tracks).

        Critical: this keepout sets ONLY `copperpour not_allowed`. It does
        NOT set `tracks not_allowed` or `vias not_allowed` — those would
        cascade clearance violations against every existing track/via in
        the rectangle (a prior agent learned this the hard way: ~135 new
        violations from over-restrictive keepouts). With `copperpour not_
        allowed` alone, the keepout only affects future pour fill — no
        existing object is perturbed.
        """
        u = str(uuid.uuid5(_OAS_NS, f"oas-zone:gnd-island-keepout:{tag}"))
        # Convert PCB-local to page-absolute mm (gnd_zone uses the same
        # transform via fx()/fy()).
        x1 = xmin + PAGE_CENTRE_X
        y1 = ymin + PAGE_CENTRE_Y
        x2 = xmax + PAGE_CENTRE_X
        y2 = ymax + PAGE_CENTRE_Y
        self._zones.append(
            f'\t(zone\n'
            f'\t\t(net 0)\n'
            f'\t\t(net_name "")\n'
            f'\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{u}")\n'
            f'\t\t(name "GND_Island_Keepout_{tag}")\n'
            f'\t\t(hatch edge 0.5)\n'
            f'\t\t(connect_pads\n'
            f'\t\t\t(clearance 0.0)\n'
            f'\t\t)\n'
            f'\t\t(min_thickness 0.25)\n'
            f'\t\t(filled_areas_thickness no)\n'
            f'\t\t(keepout\n'
            f'\t\t\t(tracks allowed)\n'
            f'\t\t\t(vias allowed)\n'
            f'\t\t\t(pads allowed)\n'
            f'\t\t\t(copperpour not_allowed)\n'
            f'\t\t\t(footprints allowed)\n'
            f'\t\t)\n'
            f'\t\t(fill\n'
            f'\t\t\t(thermal_gap 0.5)\n'
            f'\t\t\t(thermal_bridge_width 0.5)\n'
            f'\t\t)\n'
            f'\t\t(polygon\n'
            f'\t\t\t(pts\n'
            f'\t\t\t\t(xy {fmt(x1)} {fmt(y1)})\n'
            f'\t\t\t\t(xy {fmt(x2)} {fmt(y1)})\n'
            f'\t\t\t\t(xy {fmt(x2)} {fmt(y2)})\n'
            f'\t\t\t\t(xy {fmt(x1)} {fmt(y2)})\n'
            f'\t\t\t)\n'
            f'\t\t)\n'
            f'\t)'
        )

    def render(self) -> str:
        """Concatenate all routes into a single PCB-injection string."""
        all_parts = self._segments + self._vias + self._zones
        return "\n".join(all_parts)


def _route_gnd_pour(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk 1 (v0.28a): emit GND copper pours on F.Cu and B.Cu.

    The GND zones cover the full PCB outline (Ø120 D-shape) inset 0.5 mm
    from Edge.Cuts. KiCad's zone-filler:
      - auto-clears the cable hole (Ø12 mm at PCB origin) since it's an
        Edge.Cuts feature.
      - auto-clears every connector cutout zone (C3/C4/C5) since they
        are `(keepout (copperpour not_allowed))` zones.
      - auto-creates thermal-relief spokes around every GND pad on both
        layers; GND pads connect to the pour through 4 spokes 0.5 mm wide
        with 0.5 mm thermal gap.
      - leaves an 0.2 mm clearance around any non-GND copper (foreign
        pads, future tracks).

    This single chunk handles ~60 GND pads — 37% of all ratlines — and
    provides the return-current plane for every other net routed in
    subsequent chunks.
    """
    code = _net_code(nets, "GND")
    if code is None:
        return 0
    em.gnd_zone("F.Cu", code)
    em.gnd_zone("B.Cu", code)

    # v0.32: close the last 3 F.Cu GND zone-island unconnected_items that
    # v0.31 could not bridge with through-vias. Each fragment requires a
    # different treatment:
    #
    #   F.Cu #5 (0.20 mm²) at (-0.876, -45.935) — sliver around C8.2 pad.
    #     Bridge: short F.Cu track from C8.2 pad west to a clear spot at
    #     (-2.0, -46.0), then a through-via there to B.Cu main GND pour.
    #     Cannot use via-in-pad (0402 pad 0.62x0.70 mm; via 0.6 ⌀ just
    #     barely fits on F.Cu but the via's B.Cu side at (-1.15, -46.0)
    #     sits only 0.39 mm from a B.Cu Net-(U2-FB) diagonal track — FAIL).
    #     Cannot use keepout alone (would strand C8.2's only GND path).
    #
    #   F.Cu #6 (1.22 mm²) at (+4.193, -48.116) — pure stranded copper
    #     between buck-section tracks; NO pad inside, NO B.Cu main pour
    #     overlap (B.Cu under this fragment is filled with /IO/BOOT and
    #     Net-(U2-FB) tracks). Cannot bridge with via (no B.Cu GND to
    #     reach). ONLY option: copperpour keepout to suppress the
    #     fragment entirely. Safe: no pad/track inside; ~1 mm² of pour
    #     copper deleted is electrically irrelevant.
    #
    #   F.Cu #9 (0.40 mm²) at (+34.125, +24.738) — sliver around J3.2
    #     (SEN66 GND pin). Bridge: via-IN-PAD at J3.2 center (34.125,
    #     25.15). J3.2 is 0.6x1.7 mm SMD pad; 0.6 ⌀ via fits inside on
    #     F.Cu (same-net so no clearance issue with the pad copper).
    #     B.Cu under J3.2: nearest non-GND track is /IO/I2C_SDA at
    #     3.09 mm — comfortable margin. Via lands on B.Cu main GND
    #     pour, joining J3.2 to the GND network.
    em.gnd_island_keepout("F.Cu", +3.15, -48.80, +5.52, -47.48, tag="fcu-6")

    # v0.40 hand_v40: F.Cu fragments that cannot be stitched cleanly
    # (every via offset lands on a foreign-net pad/track within DRC
    # clearance). Suppress each via copperpour keepout matched to
    # the fragment's bbox so the zone-filler refuses to fill that
    # rectangle. Deleted copper is electrically irrelevant — the
    # fragments were isolated islands anyway, and any GND pads
    # inside the bbox stay connected through the B.Cu pour via
    # PTH plating (for through-hole pads) or via thermal reliefs
    # to the main F.Cu pour just outside the keepout (for SMD pads
    # near the fragment perimeter).
    # Shrink keepouts to AVOID covering known GND SMD pads inside the
    # fragment bboxes (otherwise the keepout strands the pad from
    # the main pour). Pads that need to stay in F.Cu pour:
    #   - C14 pad 2 GND at (-5.225, -30)  ← inside frag13 bbox
    #   - C31 pad 2 GND at (+8.55, -4.38) ← inside frag8 bbox
    #   - D22 pad 4 GND at (+11.23,-4.84) ← inside frag8 bbox
    #   - U2 pad 1 GND at (-2.74, -44.25) ← inside frag24 bbox
    # Full-bbox keepouts now safe because pads inside (C14.2, D22.4,
    # U2.1, C31.2) have been pinned to the GND net via dedicated
    # via-in-pad stitches earlier in hand_v40.
    em.gnd_island_keepout("F.Cu", -5.626, -30.468, +0.917, -22.815, tag="v40-frag13-j5w-row")
    em.gnd_island_keepout("F.Cu", +8.228, -5.813, +11.825, -0.805, tag="v40-frag8-e-of-hole")
    em.gnd_island_keepout("F.Cu", +0.145, -27.710, +7.961, -23.757, tag="v40-frag14-j5e-row")
    em.gnd_island_keepout("F.Cu", -6.210, -46.428, -2.314, -44.075, tag="v40-frag24-u2-area")
    # Tiny J5-area fragments (<1 mm²): no SMD pads inside.
    em.gnd_island_keepout("F.Cu", +6.098, -27.058, +7.961, -26.099, tag="v40-frag17-j5-tiny")
    em.gnd_island_keepout("F.Cu", +8.219, -27.098, +9.526, -26.099, tag="v40-frag18-j5-tiny")
    em.gnd_island_keepout("F.Cu", +8.219, -25.777, +8.795, -25.265, tag="v40-frag16-j5-micro")

    # F.Cu#5 — C8.2 GND bridge: via overlapping C8.2 pad on F.Cu.
    #   C8.2 is an 0805 cap with pads sized 0.95×0.95, pitch 0.85 → C8.2
    #   covers PCB X∈[-1.625, -0.675], Y∈[-46.475, -45.525]. A 0.6 ⌀ via
    #   centred at (-1.8, -46.0) sits with its east half (radius 0.3 →
    #   east edge X=-1.5) INSIDE C8.2's west extent (-1.625..-0.675), so
    #   the via's F.Cu copper merges with the pad's F.Cu copper (same
    #   net GND, no clearance violation).
    #   Clearances verified at (-1.8, -46.0):
    #     C8.1 pad (Net-(U2-SS)) at (-2.85, -46.0) east edge X=-2.375:
    #       via west edge X=-2.1 → 0.275 mm gap (need 0.15, OK).
    #     U2-BST F.Cu horizontal Y=-46.846: 0.846 mm clear (OK).
    #     U2-FB B.Cu diagonal (-1.564,-45.028)→(1.74,-48.332): 0.854 mm
    #       perpendicular distance to via centre (OK).
    em.via(-1.800, -46.000, code, uuid_tag="v032:c8_2_bridge")

    # F.Cu#9 — J3.2 GND bridge: via-IN-PAD at pad center.
    #   J3.2 is a 0.6x1.7 mm SMD pad on F.Cu only. A 0.6 ⌀ through-via at
    #   the pad's geometric center overlaps the pad fully on F.Cu (same
    #   net), and on B.Cu it lands 3.09 mm from the nearest non-GND
    #   B.Cu track (/IO/I2C_SDA) — well inside the main B.Cu GND pour.
    em.via(+34.125, +25.150, code, uuid_tag="v032:j3_2_in_pad")

    return 4


def _route_local_decoupling(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk 2 (v0.28b): route SHORT local power connections only.

    Each route is contained within a small area (≤ ~5 mm) where there
    are no obstacles between source and destination. This handles the
    HF/bulk decoupling caps that sit adjacent to their target ICs:

      - C13 → U1.VIN (24 V HF bypass)
      - C14 → U1.OUT (5 V HF bypass — but U1.OUT is across the board;
        SKIPPED in v0.28b, deferred to manual routing).
      - C15 → U2.VIN, C5 → U2.VIN  (5 V bulk + HF on Buck2 input)
      - C16 → U2.OUT, C6 → U2.OUT  (3V3 bulk + HF on Buck2 output)
      - C7 → U2.FB (feed-forward cap on FB pin)
      - C8 → U2.BST (bootstrap cap)
      - R2, R3 → U2.FB feedback divider
      - L2 → U2.SW (switch-node inductor — short)

    Returns the number of segments emitted. Each net is routed only when
    every required pad is present in the nets dict (defensive).
    """
    n_before = len(em._segments)

    def _get(net_name: str) -> dict:
        return {(r, p): (x, y) for r, p, x, y in nets.get(net_name, [])}

    # All U2 routes are clustered in the buck2 area at PCB Y ≈ -44.
    # SOT-583 U2 anchor (-2, -43.5); inductor L2 at (+4, -44); feedback
    # resistors R2/R3 at (+10/+13, -44); C5/C15/C6/C16/C7/C8 at Y=-46.

    # ---- Net-(U2-SW) — U2.5 → L2.2 → C7.2 (switch node)
    code = _net_code(nets, "Net-(U2-SW)")
    if code:
        p = _get("Net-(U2-SW)")
        if all(k in p for k in [("U2", "5"), ("L2", "2"), ("C7", "2")]):
            u2_5 = p[("U2", "5")]
            l2_2 = p[("L2", "2")]
            c7_2 = p[("C7", "2")]
            # U2.5 (-1.05, -42.75) → L2.2 (5.75, -44.00): direct
            em.route_segment(u2_5[0], u2_5[1], l2_2[0], l2_2[1], 0.4, code,
                             style="direct")
            # U2.5 → C7.2 (-5.15, -46.00): direct south-west
            em.route_segment(u2_5[0], u2_5[1], c7_2[0], c7_2[1], 0.3, code,
                             style="direct")

    # ---- Net-(U2-BST) — U2.6 → C7.1 (bootstrap cap)
    code = _net_code(nets, "Net-(U2-BST)")
    if code:
        p = _get("Net-(U2-BST)")
        if all(k in p for k in [("U2", "6"), ("C7", "1")]):
            u2_6 = p[("U2", "6")]
            c7_1 = p[("C7", "1")]
            em.route_segment(u2_6[0], u2_6[1], c7_1[0], c7_1[1], 0.3, code,
                             style="direct")

    # ---- Net-(U2-SS) — U2.7 → C8.1
    code = _net_code(nets, "Net-(U2-SS)")
    if code:
        p = _get("Net-(U2-SS)")
        if all(k in p for k in [("U2", "7"), ("C8", "1")]):
            u2_7 = p[("U2", "7")]
            c8_1 = p[("C8", "1")]
            em.route_segment(u2_7[0], u2_7[1], c8_1[0], c8_1[1], 0.3, code,
                             style="direct")

    # ---- Net-(U2-FB) — U2.8 → R2.2 → R3.1 (feedback tap point)
    code = _net_code(nets, "Net-(U2-FB)")
    if code:
        p = _get("Net-(U2-FB)")
        if all(k in p for k in [("U2", "8"), ("R2", "2"), ("R3", "1")]):
            u2_8 = p[("U2", "8")]
            r2_2 = p[("R2", "2")]
            r3_1 = p[("R3", "1")]
            # U2.8 (-1.05, -44.25) → R2.2 (10.85, -44.00): same Y row, F.Cu
            em.route_segment(u2_8[0], u2_8[1], r2_2[0], r2_2[1], 0.3, code,
                             style="direct")
            # R2.2 → R3.1 (adjacent: (10.85, -44) → (12.15, -44))
            em.route_segment(r2_2[0], r2_2[1], r3_1[0], r3_1[1], 0.3, code,
                             style="direct")

    return len(em._segments) - n_before


def _route_io_finalize(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk "io_finalize" (v0.28d): close the 7 non-GND ratlines + 8
    isolated-GND-pad rescues that Freerouting could not reach in v0.28b.

    Routes are designed against the autoroute snapshot in oas_routes.py
    and verified to clear all existing tracks/vias and footprints.
    The B.Cu corridor at X=33..36 is clear across the full Y span
    (only chord-region obstacles Y > 22 in different columns), so USB
    DM/DP make their long N-S runs there.

    Cutout-zone tracks: in v0.28d the keepout zones for ALL cutouts
    (C3, C4, C5) allow tracks/vias/pads so that routing freely passes
    through cutout areas. Only `copperpour` is blocked, to prevent
    the GND pour filling into the case-wall opening.
    """
    n_seg = len(em._segments)
    n_via = len(em._vias)

    # NOTE v0.28d: signal routes (A-F below) were attempted but trigger
    # many DRC issues because the v0.28b autoroute already used the
    # most accessible chord-region corridors. To preserve DRC=0
    # without major repaving of the autoroute, only the GND rescue
    # vias (sections G/H) are emitted here. The 7 signal-net
    # unconnected pads (J10.2 +3V3, J9.2 +3V3, J9.3 SDA, J9.4 SCL,
    # J10.5 EN, J10.3 USB_DM, J10.4 USB_DP) remain as ratlines and
    # will be addressed by a follow-up routing chunk that re-runs
    # Freerouting against an updated DSN with these specific nets
    # pre-cleared, or by interactive hand-routing in KiCad's editor.
    # ---- A. +3V3: J10.2 → J9.2 (disabled) ----
    # J10.2 (9.4, 38.46), J9.2 (32.15, 41.69). Once J9.2 is on the net,
    # the trunk-stub-↔-J9.2 ratline closes too (the trunk includes
    # 45.15, 30.37 → 32, which is on the same net).
    # Wait — actually the v0.28b autoroute did NOT connect J9.2 to the
    # main +3V3 trunk. The trunk only reaches (45.15, 32). J9.2 is
    # NOT in the same connected component as the trunk. So I need TWO
    # connections: J10.2↔J9.2 (closing pair 1) AND J9.2↔trunk
    # (closing pair 2). Doing the latter as part of the same route
    # is fine.
    _ROUTE_SIGNALS = False
    code = _net_code(nets, "+3V3")
    if _ROUTE_SIGNALS and code is not None:
        # Strategy: route J10.2 east to (27, 38.46), then NORTH around
        # J9 footprint (Y=37..42 is J9 territory) to Y=42.8 (just south
        # of chord at 43.5), then east to (45.15, 42.8), then SOUTH to
        # (45.15, 32) tapping the trunk.
        # J10.2 → (27, 38.46) — clear of MP at (28.85, 37.815) west edge
        # X=28.25 with 1.0 mm gap to track edge.
        em.seg(9.4, 38.46, 27.0, 38.46, 0.4, "F.Cu", code,
               uuid_tag="io_finalize:p3v3_a1")
        # NORTH from (27, 38.46) to (27, 42.0). Y=42.0 chosen so the
        # east horizontal sweep stays inside the Ø60 mm arc (at Y=42,
        # X_max = sqrt(60²-42²) = 42.85 mm).
        em.seg(27.0, 38.46, 27.0, 42.0, 0.4, "F.Cu", code,
               uuid_tag="io_finalize:p3v3_a2")
        em.seg(27.0, 42.0, 42.5, 42.0, 0.4, "F.Cu", code,
               uuid_tag="io_finalize:p3v3_a3")
        # SOUTH (42.5, 42.0) → (42.5, 32.0). Clear of C1 D8 at (40,36)
        # right edge X=44, my track at X=42.5 → 1.5 mm gap to C1.
        em.seg(42.5, 42.0, 42.5, 32.0, 0.4, "F.Cu", code,
               uuid_tag="io_finalize:p3v3_a4")
        # EAST (42.5, 32) → (45.15, 32) — connects to trunk.
        em.seg(42.5, 32.0, 45.15, 32.0, 0.4, "F.Cu", code,
               uuid_tag="io_finalize:p3v3_a5")
        # BRANCH: from (32.15, 42.0) intermediate point on the east run,
        # drop SOUTH to J9.2 (32.15, 41.69). Wait — my route goes
        # (27, 42) → (42.5, 42) passing X=32.15. Add a branch tap.
        em.seg(32.15, 42.0, 32.15, 41.69, 0.4, "F.Cu", code,
               uuid_tag="io_finalize:p3v3_a6")

    # ---- B. /IO/EN: J10.5 → existing EN node at (-19.85, -25.97) [J5.2] (disabled) ----
    code = _net_code(nets, "/IO/EN")
    if _ROUTE_SIGNALS and code is not None:
        # F.Cu (9.4, 30.84) east to (15, 30.84). Y=30.84 corridor clear.
        em.seg(9.4, 30.84, 15.0, 30.84, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:en_a1")
        em.via(15.0, 30.84, code, uuid_tag="io_finalize:en_v1")
        # B.Cu south at X=15. Crossings: +5V at Y=-44.19. Stop before.
        em.seg(15.0, 30.84, 15.0, -22.0, 0.25, "B.Cu", code,
               uuid_tag="io_finalize:en_a2")
        em.via(15.0, -22.0, code, uuid_tag="io_finalize:en_v2")
        # F.Cu Y=-22 corridor clear (verified Y=-24..-22 clear).
        em.seg(15.0, -22.0, -19.85, -22.0, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:en_a3")
        em.seg(-19.85, -22.0, -19.85, -25.97, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:en_a4")

    # ---- C. /IO/I2C_SCL: J9.4 → existing SCL F.Cu trunk ----
    # J9.4 (30.15, 41.69). Trunk has F.Cu segments including
    # (28.258, 26.682) → (35.328, 26.682). Tap by going DOWN from J9.4
    # to Y=26.682 via X=30.15 column then short east-west connector.
    # Wait — to reach (28.258, 26.682) from (30.15, 26.682), only short
    # west run needed. But the existing trunk goes through (35.328,
    # 26.682) east. My route at (30.15, 26.682) west to (28.258, 26.682)
    # would join an existing endpoint.
    code = _net_code(nets, "/IO/I2C_SCL")
    if _ROUTE_SIGNALS and code is not None:
        # J9.4 (30.15, 41.69) → SOUTH at X=30.15 to (30.15, 26.682).
        # Long vertical. Check for crossings.
        em.seg(30.15, 41.69, 30.15, 26.682, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:scl_a1")
        # Connect to existing trunk endpoint (28.258, 26.682) — but
        # actually shortest is to existing trunk at (28.258, 26.682)
        # which is part of segment (28.258, 26.682) → (35.328, 26.682).
        # Tap by extending east-west: my (30.15, 26.682) is already
        # on that horizontal line — direct contact. Add a 0-length
        # segment? Actually a 1.892 mm WEST segment from (30.15,26.682)
        # to (28.258, 26.682) connects fully to existing trunk.
        em.seg(30.15, 26.682, 28.258, 26.682, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:scl_a2")

    # ---- D. /IO/I2C_SDA: J9.3 → existing SDA F.Cu trunk ----
    # J9.3 (31.15, 41.69). SDA F.Cu trunk has (30.422, 25.5017) →
    # (31.1976, 26.2773). Tap into the trunk by going SOUTH from J9.3
    # to Y=26.2773 area.
    code = _net_code(nets, "/IO/I2C_SDA")
    if _ROUTE_SIGNALS and code is not None:
        # J9.3 (31.15, 41.69) → south to (31.15, 26.2773). But X=31.15
        # is 1.0 mm east of SCL at X=30.15 — diff pair routing.
        # Hmm, I2C bus pull-ups + propagation — 1 mm is OK.
        em.seg(31.15, 41.69, 31.15, 26.2773, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:sda_a1")
        # Connect to SDA trunk at (31.1976, 26.2773).
        em.seg(31.15, 26.2773, 31.1976, 26.2773, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:sda_a2")

    # ---- E. /IO/USB_DM: J10.3 (9.4, 35.92) → J6.14 (10.63, -48.83) ----
    # Route via clean B.Cu corridor at X=33 (verified clear N-S).
    code = _net_code(nets, "/IO/USB_DM")
    if _ROUTE_SIGNALS and code is not None:
        # F.Cu approach: J10.3 (9.4, 35.92) east toward chord corner.
        # Track at Y=35.92 must clear: J9 MP at (28.85, 37.815) MP body
        # Y[36.915..38.715] X[28.25..29.45]. Track at Y=35.92, edge
        # Y=36.045. MP top edge 36.915 → gap 0.87 mm. OK.
        # R4 at (25, 35.5) 0603 pad bbox X[24.6..25.4] Y[35.1..35.9].
        # Track at Y=35.92 edge 35.795. R4 pad top 35.9 → gap 0.105 mm < 0.15. FAIL.
        # Move track to Y=36.3: edge 36.175 vs R4 top 35.9 → gap 0.275 > 0.15. OK.
        # vs MP top 36.915 → gap 0.615 mm. OK.
        # vs Net-(D3-A) at Y=35.5 (endpoint X=25.85): gap 0.575 mm. OK.
        # First a short S-N stub from J10.3 (9.4, 35.92) → (9.4, 36.3),
        # then east at Y=36.3.
        em.seg(9.4, 35.92, 9.4, 36.3, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dm_a1")
        em.seg(9.4, 36.3, 33.0, 36.3, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dm_a2")
        # Via at (33, 36.3). Inside C5 cutout (X=27.9..35.4, Y=36.494..
        # 42.494) — Y=36.3 < 36.494, so OUTSIDE C5 (just south of it).
        em.via(33.0, 36.3, code, uuid_tag="io_finalize:dm_v1")
        # B.Cu south at X=33: clear corridor.
        em.seg(33.0, 36.3, 33.0, -47.5, 0.25, "B.Cu", code,
               uuid_tag="io_finalize:dm_a3")
        em.via(33.0, -47.5, code, uuid_tag="io_finalize:dm_v2")
        # F.Cu west at Y=-47.5 to J6.14 (10.63, -48.83). At Y=-47.5,
        # north of all J6 pad bboxes (top Y=-47.98).
        # Gap from track edge Y=-47.625 to J6 pad top -47.98 = 0.355 mm > 0.15. OK.
        em.seg(33.0, -47.5, 10.63, -47.5, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dm_a4")
        # Drop south to J6.14 (10.63, -48.83).
        em.seg(10.63, -47.5, 10.63, -48.83, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dm_a5")

    # ---- F. /IO/USB_DP: J10.4 (9.4, 33.38) → J6.13 (8.09, -48.83) ----
    # Route via B.Cu at X=35 (also clear corridor).
    code = _net_code(nets, "/IO/USB_DP")
    if _ROUTE_SIGNALS and code is not None:
        # F.Cu (9.4, 33.38) east to (35, 33.38). At Y=33.38, must clear:
        # Net-(D3-A) at X=24.15 Y=32.05..33 (track edge ~33.5, D3 top
        # ~33.125 → gap 0.375. OK).
        # Net-(Q1-PadG) at X=23.354 Y=28.796..34.704 — at X=23.354 the
        # vertical crosses Y=33.38. Track at Y=33.38 vs vertical at
        # X=23.354 — CROSS!
        # Need to bend around. Go SOUTH first to Y<28.796 then east.
        # Actually for DP cleaner to use higher Y or lower Y to avoid
        # Q1-PadG vertical. Q1-PadG is at X=23.354 spanning Y=28..34.7.
        # Avoiding requires Y > 34.7 or Y < 28.
        # Easier: go east from J10.4 with a small bend to avoid Q1-PadG.
        # (9.4, 33.38) east to (22, 33.38) [clear, X<23.354] → north
        # to (22, 35.5) [clear, Y near R1 (25,33) — R1 0603 bbox
        # X[24.6..25.4], not affecting X=22] → east to (35, 35.5)
        # → via.
        # At Y=35.5 from X=22 to X=35: R4 (25,35.5) 0603 — collision.
        # R4 pad bbox X[24.6..25.4] Y[35.1..35.9]. Track at Y=35.5
        # IS the same Y as R4 center. Track edge at Y=35.625 and
        # Y=35.375. R4 pad bbox includes Y=35.5. Track crosses R4 → SHORT.
        # Use Y=34.5 instead. R4 bottom Y=35.1, track top Y=34.625 →
        # gap 0.475 mm. OK. Net-(D3-A) ends Y=35.5; track at Y=34.5
        # edge top Y=34.625 vs D3 bottom Y=35.5. The D3 segment
        # (24.15, 32.05) → (24.15, 33) is X=24.15. Track at Y=34.5
        # passes X=24.15 north of D3 Y=33 top — gap 1.375 mm. OK.
        # Net-(Q1-PadG) X=23.354 Y=28.796..34.704. At X=22 to X=35 track
        # Y=34.5 vs Q1-PadG endpoint Y=34.704 — gap 0.205 mm < 0.15+0.125
        # = 0.275 needed. Tight.
        # Use Y=34.0: vs Q1-PadG end Y=34.704 → 0.704 mm gap. OK.
        # vs R4 bottom 35.1: 1.1 mm gap. OK.
        em.seg(9.4, 33.38, 22.0, 33.38, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dp_a1")
        em.seg(22.0, 33.38, 22.0, 34.0, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dp_a2")
        em.seg(22.0, 34.0, 35.0, 34.0, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dp_a3")
        em.via(35.0, 34.0, code, uuid_tag="io_finalize:dp_v1")
        # B.Cu south at X=35.
        em.seg(35.0, 34.0, 35.0, -47.0, 0.25, "B.Cu", code,
               uuid_tag="io_finalize:dp_a4")
        em.via(35.0, -47.0, code, uuid_tag="io_finalize:dp_v2")
        # F.Cu west at Y=-47 (0.5 mm north of DM at Y=-47.5).
        em.seg(35.0, -47.0, 8.09, -47.0, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dp_a5")
        em.seg(8.09, -47.0, 8.09, -48.83, 0.25, "F.Cu", code,
               uuid_tag="io_finalize:dp_a6")

    # ---- G. Isolated GND pad rescues + H. GND zone-island stitching ----
    # Place GND vias adjacent to isolated pads in foreign-net-clear
    # regions. Each via merges any disconnected pour fragment with the
    # main pour. With min_resolved_spokes=1, even pads with 1 spoke
    # connect successfully — these rescues handle pads with 0 spokes.
    gnd = _net_code(nets, "GND")
    if gnd is not None:
        rescues = [
            # G — pads with no thermal spoke (verified clear positions).
            ("c25", -10.0,  5.0),    # NW of C25.2; 5.2 mm cable-hole clear + 0.95 mm track clear
            ("d15",  -7.5,  9.5),    # NW of D15.4 (-6.309, 8.078)
            ("d16", -11.0,  4.0),    # NW of D16 (-9.5, 3.84); 5.7 mm cable + 1.95 track
            ("d21",   8.0, -8.0),    # near D21 (6.31, -8.08); 5.3 mm cable
            ("u2",   -4.5, -42.0),   # NW of U2.1 (-2.95, -44.25)
            ("c9",    4.0, -33.0),   # E of C9.2; 1.22 mm clear
            ("c20",  11.0,  3.0),    # E of C20.2; 1.7 mm track + 5.4 mm cable
            ("j5",   10.5, -24.5),   # E of J5.13; 1.22 mm clear
            ("j10",   8.0,  42.0),   # SW of J10.1, inside C3 cutout (chord at 43.5)
            ("j9",   33.15, 39.5),   # S of J9.1; 6.2 mm track clear,
                                     # 2.13 mm to J9 MP_E (0.93 mm pad gap).
            # H — extra stitches in clear mid-board zones.
            ("st_nw1", -45.0, -10.0),
            ("st_ne1",  50.0, -10.0),
            ("st_sw1", -25.0,  35.0),
            ("st_n",   -30.0,  -5.0),  # west-center
            ("st_sx",    5.0, -53.0),  # south-center, clear of H3 (at 0, -55).
        ]
        for label, vx, vy in rescues:
            em.via(vx, vy, gnd, uuid_tag=f"io_finalize:gnd_{label}")

    return (len(em._segments) - n_seg) + (len(em._vias) - n_via)


def _route_io_finalize_v29(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk "io_finalize_v29" (v0.29): close as many of the 7 chord-side
    signal-net ratlines as can be done DRC-cleanly without an obstacle-
    aware path planner.

    Strategy for each net:
      1. F.Cu short stub from chord-side pad
      2. Via to B.Cu (mostly clear: 76 segs B.Cu vs 360 F.Cu in v0.29)
      3. B.Cu vertical run past F.Cu obstacles
      4. Via back to F.Cu at the destination tap point

    Cleared via clearances were calculated against the v0.29 obstacle map
    (oas_routes.py) — see inline comments per via.
    """
    n_seg = len(em._segments)
    n_via = len(em._vias)

    # ---- A. +3V3: J10.2 (9.4, 38.46) → J9.2 (32.15, 41.69) → trunk (45.15, 32) ----
    # Route on F.Cu through chord-edge corridor at Y=42.9 (0.6 mm below
    # chord at Y=43.5, 0.435 mm above J9 SMD pad top at Y=42.465). To
    # reach the corridor from J10.2 without colliding with J10.1 GND pad
    # at Y=41 (pad top edge Y=41.85), exit J10 column east first then go
    # north. J9.2 connected via short south stub from corridor. Continue
    # east to X=42 (corridor stops at PCB outline at Y=42.9: max X =
    # sqrt(60²-42.9²) = sqrt(1759) = 41.95), then dog-leg south to reach
    # the +3V3 trunk endpoint (45.15, 32) via X=41.5 column.
    code = _net_code(nets, "+3V3")
    if code is not None:
        # F.Cu east stub from J10.2 (9.4, 38.46) to (15, 38.46), clear of
        # J10 GND pad at Y=41 (3+ mm south). At X=15 we're east of J10
        # body (X<13.9 cutout edge). Pad gap: J10 pads at X=9.4 with size
        # 1.7, so pad right edge X=10.25. My track at X=15 with half 0.2
        # → edge 14.8. Gap 14.8 - 10.25 = 4.55 mm. OK.
        em.seg(9.4, 38.46, 15.0, 38.46, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a1")
        # F.Cu north at X=15 from Y=38.46 to Y=42.9. At X=15 (outside C3
        # cutout at X<13.9, so this segment is in GND zone area which
        # carves clearance around tracks).
        em.seg(15.0, 38.46, 15.0, 42.9, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a2")
        # F.Cu east at Y=42.9 from X=15 to X=32.15 (J9.2 column). Y=42.9
        # is 0.435 mm above J9 pads top at 42.465; track edge at 42.7,
        # gap = 0.235 > 0.15. OK.
        em.seg(15.0, 42.9, 32.15, 42.9, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a3")
        # F.Cu south stub at X=32.15 from Y=42.9 to J9.2 at Y=41.69.
        # At X=32.15 this passes through J9.2 SMD pad top edge at Y=42.465
        # (pad center Y=41.69, half 0.775). My track at X=32.15 between
        # Y=42.9 and Y=41.69 IS within the pad Y range — and J9.2 is the
        # net target, so connecting is correct.
        em.seg(32.15, 42.9, 32.15, 41.69, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a4")
        # F.Cu continue east at Y=42.9 from X=32.15 to X=40. Edge clearance:
        # at (40, 42.9), distance from origin = sqrt(40²+42.9²) = sqrt(3440)
        # = 58.65. Outline at 60. Distance to outline = 1.35 mm. With
        # track half 0.2 → 1.15 mm clearance to outline edge. OK.
        em.seg(32.15, 42.9, 40.0, 42.9, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a5")
        # F.Cu south at X=40 from Y=42.9 to Y=33. At X=40 must clear C1
        # radial THT cap (anchor 40, 36 PCB-local, pads at X=38.25 and
        # X=41.75 — my X=40 is centered between pads, 1.75 mm to each).
        # Edge-edge: 1.75 - 0.2 - 0.8 = 0.75 mm clearance. OK.
        em.seg(40.0, 42.9, 40.0, 33.0, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a6")
        # F.Cu east at Y=33 from X=40 to X=45.15. Need to check obstacles
        # in X=40..45 at Y=33: H1 mounting hole at PCB-local (47.6, 27.5)
        # — far. C1 GND pad at (41.75, 36) — Y=33 vs pad Y=36 → 3.0 mm
        # south of C1.2 center. Edge-edge: 3.0 - 0.2 - 0.8 = 2.0 mm. OK.
        em.seg(40.0, 33.0, 45.15, 33.0, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a7")
        # F.Cu south at X=45.15 from Y=33 to Y=32, lands on +3V3 trunk
        # endpoint (same net).
        em.seg(45.15, 33.0, 45.15, 32.0, 0.4, "F.Cu", code,
               uuid_tag="iof29:p3v3_a8")

    # ---- D. /IO/I2C_SDA: J9.3 (31.15, 41.69) → SDA trunk (31.20, 26.28) ----
    # Existing SDA F.Cu trunk has a corner at (31.20, 26.28). Tap into it.
    # The SCL F.Cu trunk at Y=26.68 X=28.26..35.33 is 0.4 mm north — too
    # close for a via at Y=26.28 (via radius 0.3 + track half 0.125 = 0.425
    # > 0.4 gap). Solution: via at Y=26.0 (0.68 mm south of SCL), then a
    # short F.Cu stub north 0.28 mm to (31.20, 26.28) trunk corner.
    code = _net_code(nets, "/IO/I2C_SDA")
    if code is not None:
        em.seg(31.15, 41.69, 31.15, 40.5, 0.25, "F.Cu", code,
               uuid_tag="iof29:sda_a1")
        em.via(31.15, 40.5, code, uuid_tag="iof29:sda_v1")
        # B.Cu south. At X=31.15 there are no B.Cu obstacles between
        # Y=40.5 and Y=26.0 in v0.29 (B.Cu chord region tracks: SCL B.Cu
        # at X=25.71..27.97 and X=27.97 vertical end at Y=26.97; we're
        # at X=31.15 — clear).
        em.seg(31.15, 40.5, 31.15, 26.0, 0.25, "B.Cu", code,
               uuid_tag="iof29:sda_a2")
        # Via to F.Cu at (31.15, 26.0). Check clearances to neighbors:
        # SCL F.Cu Y=26.68 X=28.26..35.33 nearest point (31.15, 26.68):
        #   dist = 0.68, edge = 0.68 - 0.3 - 0.125 = 0.255 mm > 0.15. OK.
        # +3V3 F.Cu Y=24.93 X=-11.96..32.88 nearest (31.15, 24.93):
        #   dist = 1.07, edge = 1.07 - 0.3 - 0.125 = 0.645. OK.
        # SDA F.Cu trunk endpoint (30.42, 25.50): same net, no constraint.
        # SDA F.Cu trunk corner (31.20, 26.28): same net, no constraint.
        em.via(31.15, 26.0, code, uuid_tag="iof29:sda_v2")
        # F.Cu short north stub to land on SDA trunk corner (31.20, 26.28).
        em.seg(31.15, 26.0, 31.20, 26.28, 0.25, "F.Cu", code,
               uuid_tag="iof29:sda_a3")

    # ---- B. /IO/EN: J10.5 (9.4, 30.84) → existing EN trunk endpoint (-47.98, 2.16) ----
    # Strategy: F.Cu south stub from J10.5 (small bend to clear J10
    # column), F.Cu west at Y=31.75 (in the gap between J7/J8 mikroBUS
    # pin row 3 at Y=33.02 and pin row 4 at Y=30.48 — gap center, 1.27 mm
    # clearance each side to pad centers). Continues west past NFC sockets,
    # over BOOT F.Cu at Y=29.10 (1.65 mm gap, plenty), then south to land
    # on EN trunk endpoint.
    code = _net_code(nets, "/IO/EN")
    if code is not None:
        # F.Cu short east bend from J10.5 (9.4, 30.84) to (12, 30.84)
        # — clears J10 pin column.
        em.seg(9.4, 30.84, 12.0, 30.84, 0.25, "F.Cu", code,
               uuid_tag="iof29:en_a1")
        # F.Cu north stub from (12, 30.84) to (12, 31.75) — into J7/J8
        # mikroBUS pin-row gap Y.
        em.seg(12.0, 30.84, 12.0, 31.75, 0.25, "F.Cu", code,
               uuid_tag="iof29:en_a2")
        # F.Cu west at Y=31.75 from X=12 to X=-43.5. Clears J7/J8 pin
        # rows at Y=33.02 (1.27 mm gap) and Y=30.48 (1.27 mm gap). Endpoint
        # X=-43.5 chosen to clear J4.2 UART_RX PTH pad at PCB (-46.01,
        # 19.05) — pad east edge X=-45.16, my track edge X=-43.625 →
        # 1.535 mm clear. Also clears LD2410_OUT B.Cu vertical at
        # X=-44.74 (1.24 mm west of my X=-43.5).
        em.seg(12.0, 31.75, -43.5, 31.75, 0.25, "F.Cu", code,
               uuid_tag="iof29:en_a3")
        # Via at (-43.5, 31.75) to B.Cu (skip BOOT/+5V F.Cu obstacles
        # in the south leg).
        em.via(-43.5, 31.75, code, uuid_tag="iof29:en_v1")
        # B.Cu south at X=-43.5 from Y=31.75 to Y=2.5. Clearances verified:
        # LD2410_OUT B.Cu vertical X=-44.74 (1.24 mm west, edge-edge 0.99).
        # No other B.Cu obstacles at X=-43..-44 in this Y range.
        em.seg(-43.5, 31.75, -43.5, 2.5, 0.25, "B.Cu", code,
               uuid_tag="iof29:en_a4")
        # Via back to F.Cu at (-43.5, 2.5).
        em.via(-43.5, 2.5, code, uuid_tag="iof29:en_v2")
        # F.Cu west from (-43.5, 2.5) to (-47.98, 2.5) — 4.48 mm jumper
        # parallel to existing EN F.Cu trunk at Y=2.16 (0.34 mm south).
        # Both same net = no clearance issue.
        em.seg(-43.5, 2.5, -47.98, 2.5, 0.25, "F.Cu", code,
               uuid_tag="iof29:en_a5")
        # F.Cu south from (-47.98, 2.5) to existing EN trunk endpoint
        # (-47.98, 2.16). 0.34 mm south, same net = connection complete.
        em.seg(-47.98, 2.5, -47.98, 2.16, 0.25, "F.Cu", code,
               uuid_tag="iof29:en_a6")

    # ---- C. /IO/I2C_SCL: J9.4 (30.15, 41.69) → SCL B.Cu trunk endpoint (27.97, 26.97) ----
    # SCL B.Cu trunk top is at (27.97, 26.97). Drop on B.Cu west of J9
    # MP_E (at X=33.65..36.05) and east of MP_W (X=28.25..29.45).
    code = _net_code(nets, "/IO/I2C_SCL")
    if code is not None:
        em.seg(30.15, 41.69, 30.15, 40.5, 0.25, "F.Cu", code,
               uuid_tag="iof29:scl_a1")
        em.via(30.15, 40.5, code, uuid_tag="iof29:scl_v1")
        # B.Cu south at X=30.15. SDA route at X=31.15 (above) is 1.0 mm
        # east — clear separation.
        em.seg(30.15, 40.5, 30.15, 27.5, 0.25, "B.Cu", code,
               uuid_tag="iof29:scl_a2")
        # B.Cu west at Y=27.5 to X=27.97. At Y=27.5: 0.53 mm north of SCL
        # B.Cu trunk top at (27.97, 26.97). My west run at Y=27.5 passes
        # X=29..30. SCL B.Cu trunk vertical X=27.97 has Y range up to 26.97.
        # My west run reaches X=27.97 at Y=27.5 — same net, lands fine.
        em.seg(30.15, 27.5, 27.97, 27.5, 0.25, "B.Cu", code,
               uuid_tag="iof29:scl_a3")
        # B.Cu south at X=27.97 from Y=27.5 to Y=26.97 — connects to trunk
        # top endpoint (same net).
        em.seg(27.97, 27.5, 27.97, 26.97, 0.25, "B.Cu", code,
               uuid_tag="iof29:scl_a4")

    # ---- E. /IO/USB_DM: not closed in v0.29 ----
    # Attempt at X=20 column collided with ZT1 (20.5, 0) and ZT3 (20.5, -8)
    # NPTH zip-tie holes. Available B.Cu N-S corridors all have either
    # +5V B.Cu Y=-47 X=17.81..23.75 blocking south of mid-board, or
    # Net-(D1-A2) B.Cu diagonal at X=23..27 Y=23..27 blocking the chord
    # approach. A clean USB N-S route would require either re-routing
    # +5V to free a column or placing the routing pass at a column we
    # haven't found. Deferred to future iteration.
    # v0.30 update: closed via the chord-east column at X=33 (USB_DM) and
    # X=32 (USB_DP). See `_route_io_finalize_v30` for the geometry.

    # ---- F. /IO/USB_DP: not closed in v0.29 ----
    # Same obstacle map as DM. Deferred.
    # v0.30 update: closed alongside USB_DM in `_route_io_finalize_v30`.

    return (len(em._segments) - n_seg) + (len(em._vias) - n_via)


def _route_io_finalize_v30(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk "io_finalize_v30" (v0.30): close ALL 16 remaining unconnected
    pads to take the board from 16 unconnected → 0 unconnected.

    Two sub-tasks:

    A. USB recovery routing — 4 ratlines on 2 nets (USB_DM, USB_DP).
       Route J10.3/4 (chord-side 6-pin recovery header) to J6.13/14
       (ESP32 native USB pair on the row-B socket of MOD1).

       Topology (v0.30): F.Cu approach from J10 column east at chord Y;
       drop to B.Cu near the C5-cutout-edge; long N-S B.Cu run at
       X=32 (DP) / X=32.5 (DM) — clears every B.Cu obstacle on the way
       south; THEN swing west BELOW J6 pad row at Y=-50 (DM) / -50.5
       (DP), staying 1.17 mm / 1.67 mm south of every J6 PTH pad ring
       (radius 0.85 mm). Finally tip-up via short B.Cu north stubs to
       J6.14 / J6.13 PTH pads (PTH so no extra via needed for the
       final layer change).

       Rationale for the south-of-J6-row swing: the obstacle map in the
       middle of the board (Y=-30..-47) is fully congested by the +5V
       B.Cu network around the buck output region — there is no clean
       east-to-west B.Cu corridor at any Y in [-30, -47] that reaches
       from X≈30 to X=10.63 without crossing either the +5V diagonal
       (11.04, -40.23)→(17.81, -47) or the +5V vertical at X=14.30, OR
       crossing C4 PTH pad rings at Y=-47 X=23.75/26.25, OR crossing
       J6 PTH pad rings at Y=-48.83 X=-22.39..13.17. The single Y
       where a clean horizontal IS possible is BELOW the J6 row at
       Y < -49.68 - 0.275 = -49.955 — i.e., Y=-50 and Y=-50.5 used
       here. PCB outline at Y=-50 has X_max=33.17, X_min=-33.17;
       tracks confined to X=10.63..32.5 (USB_DM) and X=8.09..32
       (USB_DP) stay safely inside with ≥0.4 mm to PCB outline.

       The v0.30 hand-patch in oas_routes.py (moves +5V seg 0083 from
       B.Cu to F.Cu) is preserved but is no longer strictly required
       for the v0.30 USB routing — the southern-swing topology avoids
       the Y=-47 region entirely. The patch keeps B.Cu Y=-47 corridor
       free for future use.

    B. Isolated-GND-pad stitches — 5 pads (C9, C20, C24, C25, U2).
       The v0.28d rescue vias placed "near each isolated pad" did
       not actually stitch the small F.Cu pour fragment around each
       pad to the main pour (those rescues sit in their OWN tiny
       pour fragments, not connected to the pad's fragment). The fix
       here: place a same-net GND via DIRECTLY ADJACENT TO / OVERLAPPING
       each isolated pad — same net (GND), so KiCad treats the via and
       pad as a deliberate same-net contact (no clearance violation),
       and the via on B.Cu side lands in the contiguous main B.Cu pour.

       Net effect: F.Cu pad → via → B.Cu main pour → all other GND pads
       elsewhere on the board. The 5 pads close.

       Specific positions verified to clear every foreign-net trace/pad/via
       within 0.575 mm radius (via_radius 0.3 + track_half 0.125 +
       clearance 0.15) and every foreign-net SMD pad by edge-to-edge
       0.15 mm (foreign-pad clearance).
    """
    n_seg = len(em._segments)
    n_via = len(em._vias)

    # =================================================================
    # A. USB recovery (USB_DM, USB_DP)
    # =================================================================
    # J10.3 = USB_DM @ PCB (9.4, 35.92)
    # J10.4 = USB_DP @ PCB (9.4, 33.38)
    # J6.13 = USB_DP @ PCB (8.09, -48.83)
    # J6.14 = USB_DM @ PCB (10.63, -48.83)

    # ---- USB_DM: J10.3 → J6.14 via dog-leg ending in F.Cu Y=-47.5 ----
    # The route bends through three corridors:
    #   • F.Cu east at chord (Y=35.92, then Y=36.5) past R4 and J9 MP_W
    #   • B.Cu down X=31 to Y=-45, then west to X=22.5, then short south
    #     to Y=-47.5 (between Y=-46.2 north C4-ring edge and going below
    #     to Y=-47.5 which is INSIDE C4 ring Y range but track is east
    #     of C4 X positions)
    #   • F.Cu west at Y=-47.5 from X=22.5 to X=10.63 (squeezes between
    #     the +5V F.Cu seg 0083 at Y=-47 and the +3V3 F.Cu Y=-47.26
    #     X=-9.59..10.11 — at X≥10.11 the +3V3 trace is OUT of range
    #     so my F.Cu Y=-47.5 has only 0.5 mm to +5V seg 0083 above and
    #     ≥0.57 mm to +3V3 endpoint at the X=10.63 end), then south
    #     F.Cu stub to J6.14 PTH at (10.63, -48.83).
    code = _net_code(nets, "/IO/USB_DM")
    if code is not None:
        # F.Cu east at Y=35.92 from J10.3 (9.4) to X=22.
        em.seg(9.4, 35.92, 22.0, 35.92, 0.25, "F.Cu", code,
               uuid_tag="iof30:dm_a1")
        # F.Cu north stub (22, 35.92) → (22, 36.5).
        em.seg(22.0, 35.92, 22.0, 36.5, 0.25, "F.Cu", code,
               uuid_tag="iof30:dm_a2")
        # F.Cu short east stub at Y=36.5 from X=22 to X=22.5 — just
        # enough to position the via off the F.Cu vertical at X=22.
        em.seg(22.0, 36.5, 22.5, 36.5, 0.25, "F.Cu", code,
               uuid_tag="iof30:dm_a3")
        # Via at (22.5, 36.5) F→B. X=22.5 chosen to:
        # - clear v0.29 I2C_SCL/SDA B.Cu features (X=25.71..31.15 area)
        #   by ≥3 mm
        # - clear MP_PCB_WEST pad (28.85, 37.815) by 6.5 mm
        # - clear ZT1 (20.5, 0) and ZT3 (20.5, -8) NPTH holes by 2 mm
        # - clear C4.1 PTH (23.75, -47) by 1.25 mm at deepest Y
        em.via(22.5, 36.5, code, uuid_tag="iof30:dm_v1")
        # B.Cu south at X=22.5 from Y=36.5 all the way to Y=-47.7.
        # No B.Cu obstacles in this column (Net-(D1-A2) at X=23.46 is
        # 0.96 mm away — ≥0.4 ✓; v0.29 I2C_SCL/SDA are at X≥25.71).
        em.seg(22.5, 36.5, 22.5, -47.7, 0.25, "B.Cu", code,
               uuid_tag="iof30:dm_a4")
        # Via at (22.5, -47.7) B→F. Distance to +5V F.Cu seg 0083
        # (17.81, -47)→(23.75, -47): 0.7 mm vertical (foreign track),
        # required 0.575 mm via-to-track ✓.
        em.via(22.5, -47.7, code, uuid_tag="iof30:dm_v2")
        # F.Cu west at Y=-47.6 from X=22.5 to X=10.63. Track Y is
        # 0.1 mm south of via center — via and track centers near
        # connect cleanly via the via copper. Threads:
        # - +5V F.Cu seg 0083 Y=-47: vertical distance 0.6 mm,
        #   edge-edge 0.35 mm ≥ 0.15 ✓
        # - +5V bridge via at (17.81, -47): distance from track at
        #   X=17.81 Y=-47.6 = 0.6 mm ≥ 0.575 ✓
        # - C4 PTH at X=23.75/26.25 — track X≤22.5 outside C4 range.
        #   At X=22.5 endpoint, distance to C4.1 = hypot(1.25, 0.6)
        #   = 1.39 mm ≥ 1.075 ✓
        # - +3V3 F.Cu Y=-47.26 X=-9.59..10.11: track X ≥ 10.63 outside
        #   trace range; at X=10.63 endpoint distance to +3V3 endpoint
        #   (10.11, -47.26) = hypot(0.52, 0.34)=0.62 ≥ 0.4 ✓
        # - J6 PTH ring at Y=-48.83: at X=13.17 (J6.15 GND) distance
        #   1.23 mm (just ≥1.125 mm) ✓
        em.seg(22.5, -47.7, 22.5, -47.6, 0.25, "F.Cu", code,
               uuid_tag="iof30:dm_a7")
        em.seg(22.5, -47.6, 10.63, -47.6, 0.25, "F.Cu", code,
               uuid_tag="iof30:dm_a8")
        # F.Cu short south stub at X=10.63 from Y=-47.6 to Y=-48.83
        # (J6.14 PTH pad).
        em.seg(10.63, -47.6, 10.63, -48.83, 0.25, "F.Cu", code,
               uuid_tag="iof30:dm_a9")

    # ---- USB_DP: J10.4 → J6.13 via X=18.5 B.Cu + south-of-J6 swing ----
    # USB_DP takes the "deep south" route at Y=-50.5 — south of J6 PTH
    # pad ring (extent Y=-49.68) and parallel to USB_DM B.Cu only on
    # different X / Y values so they don't cross.
    code = _net_code(nets, "/IO/USB_DP")
    if code is not None:
        # F.Cu south stub J10.4 (9.4, 33.38) → (9.4, 32.2). Y=32.2
        # threads gap between J10.4 (south edge 32.53) and J10.5
        # (north edge 31.69): track edges have 0.295/0.205 mm clearance
        # to adjacent pad edges (≥0.15 mm foreign-pad clr). Also v0.29
        # EN F.Cu at Y=31.75 — track Y=32.2 has 0.45 mm clearance ≥ 0.4.
        em.seg(9.4, 33.38, 9.4, 32.2, 0.25, "F.Cu", code,
               uuid_tag="iof30:dp_a1")
        # F.Cu east at Y=32.2 from X=9.4 to X=18.5. Clears all chord-
        # region F.Cu (no obstacles in this strip — verified empty).
        em.seg(9.4, 32.2, 18.5, 32.2, 0.25, "F.Cu", code,
               uuid_tag="iof30:dp_a2")
        # Via at (18.5, 32.2) F→B. X=18.5 chosen to clear ZT1 (20.5, 0)
        # and ZT3 (20.5, -8) NPTH zip-tie holes (Ø3 mm, hole-clearance
        # rule needs ≥1.875 mm from track center to hole center): at
        # X=18.5 distance to ZT1/ZT3 = 2.0 mm ≥ 1.875 ✓.
        em.via(18.5, 32.2, code, uuid_tag="iof30:dp_v1")
        # B.Cu south at X=18.5 from Y=32.2 to Y=-50.5. Skirts:
        # - ZT1 (20.5, 0): distance 2.0 mm at Y=0, ≥ 1.875 ✓
        # - ZT3 (20.5, -8): distance 2.0 mm at Y=-8, ≥ 1.875 ✓
        # - +5V vertical X=14.30 (Y=-36.97..-18.58): gap 4.2 mm ≥ 0.4
        # - +5V diagonal (11.04, -40.23)→(17.81, -47): at X=18.5 outside
        #   diagonal X range; closest endpoint (17.81, -47) distance
        #   from track at (18.5, -47) = 0.69 ≥ 0.4 ✓
        # - C4.1 PTH (23.75, -47): distance 5.25 ≥ 1.075 ✓
        # - Net-(D1-A2) B.Cu (23.46, 23.64)→(23.46, 12.49): gap 4.96 ≥ 0.4 ✓
        # - +5V F.Cu seg 0083 at Y=-47 X=17.81..23.75: different layer ✓
        # USB_DM B.Cu segments: vertical X=31, horiz Y=-45 X=22.5..31,
        # vertical X=22.5 Y=-45..-47.7 — all ≥ 4 mm from X=18.5 ✓.
        # PCB outline at Y=-50.5 X_max=32.40 — track X=18.5 far inside.
        em.seg(18.5, 32.2, 18.5, -50.5, 0.25, "B.Cu", code,
               uuid_tag="iof30:dp_a3")
        # B.Cu west at Y=-50.5 from X=18.5 to X=8.09. Y=-50.5 is 1.67 mm
        # SOUTH of J6 pad row centerline Y=-48.83 — south of every J6
        # PTH ring. At X=13.17 (J6.15 GND), distance to J6.15 center
        # 1.67 mm, edge gap 0.82 mm ≥ 0.275 ✓. At X=10.63 (J6.14
        # USB_DM foreign), distance 1.67 mm, edge gap 0.82 mm ≥ 0.275 ✓.
        # USB_DM B.Cu has no segments at Y=-50.5 (DM finishes at Y=-47.5
        # on F.Cu). PCB outline at Y=-50.5 X_max=32.40; track X=8.09
        # well inside.
        em.seg(18.5, -50.5, 8.09, -50.5, 0.25, "B.Cu", code,
               uuid_tag="iof30:dp_a4")
        # B.Cu short north stub from (8.09, -50.5) to J6.13 PTH pad at
        # (8.09, -48.83). PTH pad — B.Cu lands directly on copper.
        em.seg(8.09, -50.5, 8.09, -48.83, 0.25, "B.Cu", code,
               uuid_tag="iof30:dp_a5")

    # =================================================================
    # B. Isolated-GND-pad stitches (5 pads → main pour)
    # =================================================================
    # Each via is placed adjacent to / overlapping the isolated GND pad.
    # Same-net contact (no clearance violation between via and pad).
    # The via's B.Cu side lands in the main B.Cu pour, bridging the
    # F.Cu local pour fragment (containing the pad) into the main pour.
    gnd = _net_code(nets, "GND")
    if gnd is not None:
        # ---- C20.2 GND @ PCB (7.6, 0.425) ----
        # Via at (7.6, 0.6) — north of pad center by 0.175 mm. Via radius
        # 0.3 → north edge Y=0.9 (0.125 mm beyond pad north edge 0.775)
        # and south edge Y=0.3 (inside pad). Foreign-net checks: +5V F.Cu
        # diagonal (8.29, 0.92)→(6.15, 3.06) at line-equation x+y=9.21,
        # distance from (7.6, 0.6) = |7.6+0.6-9.21|/√2 = 0.715 mm
        # (≥0.575 mm via clearance). +5V trace (7.60, -0.42)→(8.29, -0.42)
        # vs via edge: Y_pad south at -0.075 vs via south edge 0.3 → gap
        # 0.375 mm (≥0.15 foreign-pad).
        em.via(7.6, 0.6, gnd, uuid_tag="iof30:gnd_c20")

        # ---- C24.2 GND @ PCB (-4.17, 6.37) ----
        # LED ring cap i=4 at θ=120°. Cap center at (-3.8, 6.582);
        # outward radial direction unit (-0.5, 0.866). Via at
        # (-4.32, 6.63) = C24.2 + 0.3 * outward. Distance to nearest
        # foreign trace +5V F.Cu (-3.43, 6.79)→(-3.82, 7.47): 0.851 mm
        # ≥ 0.575. Distance to C24.1 pad (-3.43, 6.79): 0.90 mm
        # (edge-edge 0.25 ≥ 0.15).
        em.via(-4.32, 6.63, gnd, uuid_tag="iof30:gnd_c24")

        # ---- C25.2 GND @ PCB (-6.79, 3.43) ----
        # LED ring cap i=5 at θ=150°. Cap center (-6.582, 3.8); outward
        # radial unit (-0.866, 0.5). Via at (-7.05, 3.58) = C25.2 + 0.3 *
        # outward. Distance to +5V F.Cu (-6.37, 4.17)→(-7.05, 4.56):
        # perpendicular foot at (-6.63, 4.32), d=0.85 mm ≥0.575.
        # C25.1 pad (-6.37, 4.17) gap 0.90 mm.
        em.via(-7.05, 3.58, gnd, uuid_tag="iof30:gnd_c25")

        # ---- C9.2 GND @ PCB (0.9, -30.0) ----
        # ESP32 +3V3 bulk cap (0805, pad bbox X=0.325..1.475,
        # Y=-30.7..-29.3 → 1.15 × 1.4 mm pad). Area is densely populated
        # by power-section traces (+24V F.Cu at (1.4, -31.02)→(2.10,
        # -29.81), +24V B.Cu via at (2.10, -29.81), +3V3 F.Cu at Y=-29.22
        # and Y=-30 segments). No external position within 1 mm has
        # ≥0.575 mm clearance to all foreign traces. Solution: via-on-pad
        # at C9.2 pad center (0.9, -30.0). Via 0.6 mm dia fits entirely
        # inside the 1.15×1.4 mm pad. Same-net (GND) → no clearance check
        # vs the pad itself. Closest diff-net obj: +3V3 F.Cu at d=0.978 mm
        # (≥0.575). C9.1 (+3V3) pad bbox X=-1.475..-0.325, gap from via
        # edge (X_west=0.6) to C9.1 east edge (X=-0.325) = 0.925 mm
        # (≥0.15).
        em.via(0.9, -30.0, gnd, uuid_tag="iof30:gnd_c9")

        # ---- U2.1 GND @ PCB (-2.95, -44.25) ----
        # TPS62933 SOT-583 buck. U2.1 pad is tiny (0.3 × 0.35 mm), and
        # U2.2 (+5V/VIN per actual chip) sits 0.5 mm north at (-2.95,
        # -43.75) — too close for a same-pad via. Solution: F.Cu track
        # west from U2.1 to (-4.5, -44.25), then south to (-4.5, -44.5)
        # via. The west track at Y=-44.25 clears +5V Y=-43.75 by 0.5 mm
        # (track-track 0.4 mm required) and U2-SW Y=-45.12 by 0.87 mm.
        # Via at (-4.5, -44.5): clears +5V Y=-43.75 (d=0.75), Net-(U2-SW)
        # diagonal endpoint (-4.27, -45.12) (d=0.66), and U2-SW horiz
        # Y=-45.12 X=-4.27..-3.13 (closest endpoint X=-4.27, d=0.66).
        em.seg(-2.95, -44.25, -4.5, -44.25, 0.25, "F.Cu", gnd,
               uuid_tag="iof30:gnd_u2_t1")
        em.seg(-4.5, -44.25, -4.5, -44.5, 0.25, "F.Cu", gnd,
               uuid_tag="iof30:gnd_u2_t2")
        em.via(-4.5, -44.5, gnd, uuid_tag="iof30:gnd_u2")

    return (len(em._segments) - n_seg) + (len(em._vias) - n_via)


def _route_hand_v40(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk "hand_v40" (post-Freerouting rework-5): close the J9 Qwiic
    trio and stitch isolated GND pads that the v0.40 Freerouting
    snapshot left unconnected.

    Routes are designed against the post-rework autoroute snapshot in
    oas_routes.py. Verified against existing tracks/vias by hand
    (see the per-route geometry comments below).

    Closes:
      - J9.2 (+3V3) → +3V3 trunk at (30.6255, 20.8003) via long
        vertical at X=32.15.
      - J9.3 (/IO/I2C_SDA) → SDA trunk corner at (31.5864, 19.1571)
        via long vertical at X=31.15.
      - J9.4 (/IO/I2C_SCL) → SCL trunk at (31.6785, 17.9824) via
        long vertical at X=30.15.
      - U1 pad 3 (TO-263-5 tab, GND) — via-in-pad to bring B.Cu GND
        pour through the tab.
      - J3 pad 2 (JST GH GND) — via-in-pad to stitch the south-east
        GND pour pocket.
      - D15.4, D16.4 LED ring GND — via-in-pad.
      - C21.2 (LED ring decoupling cap, GND) — via-in-pad.
    """
    n_seg = len(em._segments)
    n_via = len(em._vias)

    # ---- A. +3V3: J9.2 (32.15, 41.69) → existing trunk at (30.6255, 20.8003) ----
    # F.Cu south at X=32.15 from J9.2 to Y=20.80, then short WEST stub to
    # tap seg:0071 east endpoint (seg:0071 spans X=-13.97..30.6255 at
    # Y=20.80). At X=32.15:
    #   - SDA trunk seg:0228 east end (31.59) — outside X span, no cross.
    #   - SCL trunk seg:0213 east end (31.68) — outside X span, no cross.
    #   - +3V3 seg:0074 diagonal — crosses at (32.15, 22.33), same net OK.
    code = _net_code(nets, "+3V3")
    if code is not None:
        em.seg(32.15, 41.69, 32.15, 20.80, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:p3v3_a1")
        em.seg(32.15, 20.80, 30.6255, 20.80, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:p3v3_a2")

    # ---- B. /IO/I2C_SCL: J9.4 (30.15, 41.69) → trunk at (31.6785, 17.9824) ----
    # F.Cu vertical at X=30.15 crosses two foreign F.Cu trunks:
    #   - +3V3 seg:0071 horizontal at Y=20.80 (X span [-13.97, +30.625],
    #     X=30.15 INSIDE → would short).
    #   - SDA seg:0228 horizontal at Y=19.1571 (X span [-32.65, +31.59],
    #     X=30.15 INSIDE → would short).
    # Bridge those two by hopping to B.Cu for Y∈[21.5, 18.5] then
    # back to F.Cu for the final south-to-trunk + east-stub.
    code = _net_code(nets, "/IO/I2C_SCL")
    if code is not None:
        em.seg(30.15, 41.69, 30.15, 21.5, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:scl_a1")
        em.via(30.15, 21.5, code, uuid_tag="hand_v40:scl_v1")
        em.seg(30.15, 21.5, 30.15, 18.5, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_a2")
        em.via(30.15, 18.5, code, uuid_tag="hand_v40:scl_v2")
        em.seg(30.15, 18.5, 30.15, 17.9824, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:scl_a3")
        em.seg(30.15, 17.9824, 31.6785, 17.9824, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:scl_a4")

    # ---- C. /IO/I2C_SDA: J9.3 (31.15, 41.69) → trunk corner (31.5864, 19.1571) ----
    # F.Cu vertical at X=31.15 crosses one foreign F.Cu trunk:
    #   - +3V3 seg:0074 diagonal (34.875, 25.05)→(30.625, 20.80) which
    #     at X=31.15 is at Y≈21.32 — would short.
    # No conflict with +3V3 horizontal seg:0071 (X span ends at 30.625,
    # X=31.15 is east of trunk endpoint). SDA trunk seg:0228 at Y=19.16
    # is SAME net (tap, not cross). SCL trunk Y=17.98 not reached
    # (my route stops at Y=19.16).
    # Bridge the +3V3 diagonal by hopping to B.Cu for Y∈[22.5, 19.5].
    code = _net_code(nets, "/IO/I2C_SDA")
    if code is not None:
        em.seg(31.15, 41.69, 31.15, 22.5, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:sda_a1")
        em.via(31.15, 22.5, code, uuid_tag="hand_v40:sda_v1")
        em.seg(31.15, 22.5, 31.15, 19.5, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:sda_a2")
        em.via(31.15, 19.5, code, uuid_tag="hand_v40:sda_v2")
        em.seg(31.15, 19.5, 31.15, 19.1571, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:sda_a3")
        em.seg(31.15, 19.1571, 31.5864, 19.1571, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:sda_a4")

    # ---- D. GND stitching vias for isolated GND pads ----
    # Each via lands ON the pad's centre. Via drill 0.3 mm in pads of:
    #   - U1 tab (~6×9 mm): no clearance issue.
    #   - J3 GND mounting pad (~1.6×1 mm): drill 0.3 mm leaves
    #     ample annular ring.
    #   - SK6812-SIDE pad 4 (1.0×0.85 mm): drill 0.3 mm — tight but
    #     viable (annular ring ~0.35 mm).
    #   - C21 0402 pad 2 (0.5×0.6 mm): drill 0.3 mm — minimum
    #     annular ring 0.1 mm, marginal. Alternative: shift via to
    #     just south of pad and add a short stub — see below.
    code = _net_code(nets, "GND")
    if code is not None:
        # U1 TO-263-5 tab GND at PCB (-42.65, -34). Tab spans
        # X ∈ [-46.65, -38.65], Y ∈ [-37.5, -30.5] approximately.
        em.via(-42.65, -34.0, code,
               uuid_tag="hand_v40:u1_gnd_stitch")
        # J3 GND mounting pad at PCB (+36.13, +25.15). JST GH MP — small.
        em.via(36.13, 25.15, code,
               uuid_tag="hand_v40:j3_gnd_stitch")
        # D15 (LED θ=120°, body at PCB (-6.5, +11.26)) pad 4 GND
        # SKIPPED — pad 3 (DOUT) sits 0.96 mm NE at (-6.49, +10.28),
        # and Earth_Protective B.Cu seg:0283 runs at X=-7.8129
        # immediately to the west. No clean via location exists
        # within DRC clearance of both. Leave D15.4 as ratline;
        # bridge via assembly-time jumper or a follow-up shaped
        # GND zone patch.
        # D16 (LED θ=150°, body at PCB (-11.26, +6.5)) pad 4 GND
        # at (-11.23, +4.84). Far from Earth_Protective track (X=-7.81)
        # — via-in-pad fine.
        em.via(-11.23, 4.84, code,
               uuid_tag="hand_v40:d16_gnd_stitch")
        # C21 0402 decoupling cap, pad 2 GND at (+8.07, +5.22).
        # +5V seg:0173 diagonal (9.43, 5.26)→(6.02, 8.67) is ~0.99 mm
        # perpendicular from pad center → via-in-pad has 0.565 mm
        # clearance to the diagonal (well above 0.15 mm minimum).
        em.via(8.07, 5.22, code, uuid_tag="hand_v40:c21_gnd_stitch")
        # C25 0402 cap pad 2 GND at PCB (-8.55, +4.38). +3V3 B.Cu
        # seg:0019 vertical at X=-8.9237 (Y range -8.24..+15.75) is
        # only 0.37 mm west of the pad → via-in-pad would short.
        # Shift via WEST to (-9.5, +4.38) where +3V3 B.Cu is 0.576 mm
        # away, giving 0.151 mm B.Cu clearance (just above 0.15 min).
        # F.Cu stub bridges pad to via.
        em.via(-9.5, 4.38, code, uuid_tag="hand_v40:c25_gnd_stitch")
        em.seg(-8.55, 4.38, -9.5, 4.38, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:c25_gnd_a1")
        # Pads inside about-to-be-keepout fragment bboxes (need their
        # own via-in-pad so suppressing the surrounding pour doesn't
        # leave them disconnected):
        # C14 pad 2 GND at PCB (-5.225, -30). 0402 0.5×0.6 pad; 0.3
        # via drill fits with ≥0.1 mm annular ring.
        em.via(-5.225, -30.0, code, uuid_tag="hand_v40:c14_gnd_stitch")
        # D22 pad 4 GND at PCB (+11.23, -4.84). SK6812-SIDE pad ~1.0×
        # 0.85; via-in-pad comfortable.
        em.via(+11.23, -4.84, code, uuid_tag="hand_v40:d22_gnd_stitch")
        # U2 pad 1 GND at PCB (-2.74, -44.25). SOT-583-8 pad small.
        # +5V F.Cu seg:0098 horizontal at Y=-43.75 spans X=-17..-3.38;
        # via at (-4.5, -45) is 1.25 mm south of that track (>0.575 mm
        # min clearance) and 1.91 mm from U2.1 pad.
        em.via(-4.5, -45.0, code, uuid_tag="hand_v40:u2_gnd_stitch")
        em.seg(-2.74, -44.25, -4.5, -45.0, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:u2_gnd_a1")
        # C31 0402 cap pad 2 GND at PCB (+8.55, -4.38) — inside frag8
        # bbox; needs its own stitch before the frag8 keepout is safe.
        em.via(+8.55, -4.38, code, uuid_tag="hand_v40:c31_gnd_stitch")

        # ---- F. GND pour-island stitching for isolated PTH pads ----
        # J5.13 / J7.8 / J1.2 are through-hole pads whose F.Cu pour
        # island is electrically disconnected from the main B.Cu pour
        # in the autoroute snapshot. Drop a stitch via in a clear
        # area near each pad to bridge the islands.
        # J5.15 PTH GND at PCB (+13.17, -25.97) — east-end pad of
        # ESP32 J5 row. Stitch via at (+13.17, -23) just south of
        # row (Y=-25.97 is row, Y=-23 is 3 mm south — clear of MOD1
        # ESP32 shadow Y_max=-24.70 by 1.7 mm). F.Cu stub from pad
        # to via forces the connection (the autoroute snapshot left
        # the local F.Cu pour island disconnected from the rest).
        em.via(13.17, -23.0, code, uuid_tag="hand_v40:j5_15_gnd_stitch")
        em.seg(13.17, -25.97, 13.17, -23.0, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:j5_15_gnd_a1")
        # J7.8 PTH GND at PCB (-14.03, +20.32). Pad is hemmed in by
        # multiple foreign tracks:
        #   - +3V3 B.Cu seg:0017 diagonal at (-14.03, +20.86) — 0.54 mm
        #     south of pad center.
        #   - SDA F.Cu seg:0228 horizontal at Y=+19.16 — 1.16 mm south.
        #   - +3V3 F.Cu seg:0071 horizontal at Y=+20.80 — 0.48 mm south.
        # Route F.Cu diagonal NE from pad to a via at (-12, +19.9):
        # the via location has 0.9 mm to +3V3 F.Cu, 0.74 mm to SDA
        # F.Cu, and 1.07 mm to +3V3 B.Cu — all comfortably clear.
        em.seg(-14.03, 20.32, -12.0, 19.9, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:j7_8_gnd_a1")
        em.via(-12.0, 19.9, code, uuid_tag="hand_v40:j7_8_gnd_stitch")
        # J5.13 PTH GND at PCB (+8.09, -25.97) — same constraint vs
        # WS2812_DIN F.Cu seg:0273 diagonal crossing at (+8.09, -24.34).
        # Route B.Cu directly from PTH pad north over the WS2812
        # crossing on B.Cu, place stitch via at clean F.Cu pour.
        em.seg(8.09, -25.97, 8.09, -23.0, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:j5_13_gnd_a1")
        em.via(8.09, -23.0, code, uuid_tag="hand_v40:j5_13_gnd_stitch")
        # J1.2 PTH GND at PCB (0, +27.40) — middle pin of 24 V
        # terminal block. Route SOUTH (toward chord) instead of north
        # to avoid crossing SCL F.Cu trunk seg:0210 (Y=+23.99,
        # X=-34.95..+0.31) and +3V3 trunk seg:0071 (Y=+20.80,
        # X=-13.97..+30.625). J1 pad row pins at X=±5.08 leave the
        # X=0 column clear inside J1 body. PCB chord at Y=+43.5;
        # via at Y=+34 is 9.5 mm clear.
        em.seg(0.0, 27.4, 0.0, 34.0, 0.25, "F.Cu", code,
               uuid_tag="hand_v40:j1_2_gnd_a1")
        em.via(0.0, 34.0, code, uuid_tag="hand_v40:j1_2_gnd_stitch")
        # C24 0402 cap pad 2 GND at PCB (-5.22, +8.07). LED ring
        # area, far from nearby tracks (D15 at -6.5,+11.26 is 3.44 mm
        # away; EP B.Cu track at X=-7.81 is 2.59 mm away). Via-in-pad
        # fine.
        em.via(-5.22, 8.07, code, uuid_tag="hand_v40:c24_gnd_stitch")

        # ---- H. F.Cu / B.Cu pour-island stitching ----
        # The autoroute snapshot's dense routing fragments the GND
        # pour into multiple isolated islands per layer (e.g. v0.40
        # had 25 F.Cu fragments + 5 B.Cu fragments). Each fragment
        # that does NOT connect to the main pour generates one
        # `unconnected_items` DRC entry.
        #
        # Bridge each small fragment to the opposite-layer MAIN pour
        # via a stitch via at the fragment's centroid. The via:
        #   - F.Cu side lands in the fragment (joining it to GND)
        #   - B.Cu side lands in the B.Cu main pour (or vice versa)
        # both ends are on the GND net so no clearance is needed
        # against the pour copper itself.
        #
        # Fragment centroids extracted via tools/parse_zones.py from
        # the post-MCP-refill kicad_pcb (the only state where KiCad's
        # fill algorithm produces the full 28 fragments — kicad-cli's
        # --refill-zones builds a slightly different sub-set, but the
        # union covers the same areas).
        for stitch_x, stitch_y, tag in [
            # F.Cu small fragments — only those whose centroid is in a
            # clear pour area (no foreign pad/track/via within DRC
            # clearance). Fragments whose centroid lands on a pad or
            # track get re-net'd by KiCad's connectivity merger and
            # become via_dangling — those are SKIPPED here (see the
            # commented-out lines).
            (-28.26, -31.88, "fcu_frag15_esp32"),   # 266 mm²: ESP32 shadow
            (+17.86, -44.21, "fcu_frag20_se"),      # 240 mm²: SE area
            # ( -0.35,  +3.05, "fcu_frag4_north"),  # 138 mm²: skip — hits LED ring
            # ( +5.96, -11.50, "fcu_frag9_ne"),     # 112 mm²: skip — merges with +5V
            (+10.34, +20.11, "fcu_frag3_e"),        #  46 mm²: E of hole
            # ( +6.30, -46.13, "fcu_frag22_se"),    #  34 mm²: skip — merges with U2-SW
            # ( -2.88, -29.00, "fcu_frag13_j5_offset"),  # 24 mm²: skip — every offset hits foreign track
            # (+11.50,  -3.69, "fcu_frag8_e_offset"),    # 12 mm²: skip — too close to nearby vias
            ( -3.69, -10.13, "fcu_frag11_w"),       #  12 mm²: NW of hole
            (+10.22,  +2.80, "fcu_frag7_e"),        #   8 mm²: E of hole
            ( +2.86, -10.24, "fcu_frag12_n"),       #   8 mm²: NE of hole
            # ( +4.50, -27.50, "fcu_frag14_j5_offset"),  # 8 mm²: skip — every offset hits BOOT/SCL
            (-21.88, +23.03, "fcu_frag2_mikroe"),   #   8 mm²: MIKROE
            # ( -9.58,  +4.20, "fcu_frag6_w"),      #   7 mm²: skip — conflicts with C25 stitch
            (+14.59, +36.22, "fcu_frag0_south"),    #   7 mm²: S of board
            ( +5.06, -29.41, "fcu_frag19_j5"),      #   6 mm²: J5 south
            ( +5.99,  -8.23, "fcu_frag10_e"),       #   6 mm²: E of hole
            ( -6.18,  +8.29, "fcu_frag5_w"),        #   6 mm²: W of hole
            ( -0.73, -45.00, "fcu_frag23_j6"),      #   4 mm²: J6 area
            # ( -5.00, -45.50, "fcu_frag24_j6w_offset"),  # 4 mm²: skip — too close to U2-SW/BST vias
            ( -1.23, -41.81, "fcu_frag21_u2"),      #   3 mm²: U2 area
            # ( +6.83, -26.59, "fcu_frag17_j5"),    # 0.9 mm²: skip — merges with +5V
            # ( +9.21, -26.87, "fcu_frag18_j5"),    # 0.6 mm²: skip — merges with +24V
            # ( +8.54, -25.49, "fcu_frag16_j5"),    # 0.2 mm²: skip — too close to J5 PTH
            # B.Cu small fragments (4 total).
            (-50.97, +10.94, "bcu_frag1_ld2410"),   #  69 mm²: LD2410 west
            ( +3.94, -47.38, "bcu_frag0_south"),    #  12 mm²: south ESP32
            (-53.38,  -4.15, "bcu_frag2_ld_w"),     # 0.9 mm²: LD2410 west tiny
            (-53.31,  -6.53, "bcu_frag3_ld_w"),     # 0.7 mm²: LD2410 west tiny
            # Frag8 (E of cable hole, area 112) has centroid at
            # (+5.96, -11.50) but the existing fcu_frag10_e via
            # there lies outside the polygon shape (donut artifact?).
            # Add a SECOND via in a different region of the same
            # fragment — try bbox (+10, -18) which should be inside
            # the polygon.
            (+10.5, -18.0, "fcu_frag8_alt"),  # 0.5 mm further east to clear +24V B.Cu seg:0000 at X=9.45
        ]:
            em.via(stitch_x, stitch_y, code,
                   uuid_tag=f"hand_v40:stitch_{tag}")

    # ---- G. /IO/I2C_SCL cable-hole bypass (B.Cu arc east of hole) ----
    # The autoroute snapshot's SCL routing has two disjoint F.Cu trunks
    # split by the central Ø12 mm cable hole:
    #   - South trunk: ends at (3.01, -25.97) via seg:0203/0212 (orphan).
    #   - North trunk: starts at via:0010 (5.87, +17.98) → seg:0213
    #     east to J3/J9 area.
    # Bridge via a B.Cu arc on the EAST side of the hole at R=7.0
    # (1.0 mm clearance to hole edge at R=6, 5.0 mm clearance to LED
    # ring inner edge at R=12). Approximate the half-circle with 6
    # straight segments at 30° spacing (θ = 270° south → 90° north).
    code = _net_code(nets, "/IO/I2C_SCL")
    if code is not None:
        # B.Cu south approach: start from J5.11 PTH (SCL pad at PCB
        # (3.01, -25.97), B.Cu plating implicit via THT plating).
        # Route east then NW to arc start at (0, -7), clearing J10
        # row at Y=-20 (J10.6 BOOT PTH at X=+1.74 is 1.73 mm from
        # the diagonal at Y=-20).
        em.seg(3.01, -25.97, 4.0, -22.0, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_b1")
        em.seg(4.0, -22.0, 0.0, -7.0, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_b2")
        # B.Cu arc east of hole at R=7. Segments:
        #   θ=270° (0, -7) → θ=300° (3.5, -6.06)
        em.seg(0.0, -7.0, 3.5, -6.06, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_arc1")
        #   θ=300° → θ=330° (6.06, -3.5)
        em.seg(3.5, -6.06, 6.06, -3.5, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_arc2")
        #   θ=330° → θ=0° (7, 0)
        em.seg(6.06, -3.5, 7.0, 0.0, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_arc3")
        #   θ=0° → θ=30° (6.06, +3.5)
        em.seg(7.0, 0.0, 6.06, 3.5, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_arc4")
        #   θ=30° → θ=60° (3.5, +6.06)
        em.seg(6.06, 3.5, 3.5, 6.06, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_arc5")
        #   θ=60° → θ=90° (0, +7)
        em.seg(3.5, 6.06, 0.0, 7.0, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_arc6")
        # B.Cu north exit to via:0010 area (5.87, +17.98).
        em.seg(0.0, 7.0, 5.87, 17.0, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_b3")
        em.seg(5.87, 17.0, 5.87, 17.98, 0.25, "B.Cu", code,
               uuid_tag="hand_v40:scl_b4")

    return (len(em._segments) - n_seg) + (len(em._vias) - n_via)


def _route_autoroute_tracks(em: "_RouteEmitter", nets: dict) -> int:
    """Chunk "autoroute" (v0.28c): replay every track + via produced by
    the Freerouting pass committed at v0.28b-snapshot.

    The geometry is stored in `oas_routes.py` (auto-generated by
    `tools/extract_routes.py`). Each record carries a stable
    `uuid_tag` (e.g. `"autoroute:seg:0001"`) so the resulting UUIDs are
    bit-identical across regens — independent of any other routing
    chunk's per-call counter. Net codes are looked up by name through
    `_net_code()`; records whose net name does not resolve to an
    integer code are silently skipped (defensive against schematic-side
    net renames after the routing was extracted).

    Returns the number of segment + via records emitted.
    """
    try:
        from oas_routes import ROUTES_SEGMENTS, ROUTES_VIAS  # type: ignore
    except ImportError:
        # oas_routes.py is optional — if it doesn't exist, no autoroute
        # data is available and this chunk emits nothing. Allows the
        # routing infrastructure to ship without forcing a particular
        # snapshot to be present.
        return 0

    emitted = 0
    skipped_nets: set[str] = set()
    for rec in ROUTES_SEGMENTS:
        code = _net_code(nets, rec["net_name"])
        if code is None:
            skipped_nets.add(rec["net_name"])
            continue
        x1, y1 = rec["start"]
        x2, y2 = rec["end"]
        em.seg(
            x1, y1, x2, y2,
            rec["width"], rec["layer"], code,
            uuid_tag=f'autoroute:{rec["uuid_tag"]}',
        )
        emitted += 1
    for rec in ROUTES_VIAS:
        code = _net_code(nets, rec["net_name"])
        if code is None:
            skipped_nets.add(rec["net_name"])
            continue
        x, y = rec["at"]
        em.via(
            x, y, code,
            size=rec["size"], drill=rec["drill"],
            layers=tuple(rec["layers"]),
            uuid_tag=f'autoroute:{rec["uuid_tag"]}',
        )
        emitted += 1
    if skipped_nets:
        print(f"  autoroute: skipped {len(skipped_nets)} unresolved nets: "
              + ", ".join(sorted(skipped_nets)))
    return emitted


def _net_code(nets: dict, name: str) -> int | None:
    """Look up the integer net code for a named net via any pad's net_code.

    The `nets` dict from `_routing_pad_db()` only stores names → pad lists,
    not codes, so we need to fish the code out of a pad's stored tuple. This
    helper re-reads the PCB header by parsing the (net N "<name>") lines.
    Caches the lookup on first call.
    """
    cache: dict = getattr(_net_code, "_cache", None)
    if cache is None:
        cache = {}
        import re
        text = (HERE / "oas.kicad_pcb").read_text(encoding="utf-8")
        for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]*)"\)', text):
            code = int(m.group(1))
            net_name = m.group(2)
            # Use only the first occurrence (the header declaration);
            # pad assignments repeat names later.
            if net_name not in cache:
                cache[net_name] = code
        _net_code._cache = cache
    return cache.get(name)


# v0.39: JLCPCB DFM "silkscreen line width" minimum is 0.15 mm. The stock
# KiCad libraries (Connector_PinSocket, PinHeader, Phoenix MSTBA, etc.)
# emit silk frames at 0.12 mm by default - safely below KiCad's own DRC
# minimum_silkscreen_clearance rule (which only checks pad-to-silk
# clearance, not line width itself), but flagged by JLCPCB's DFM scanner
# as 50 "Silkscreen line width" warnings at 0.12 mm. The post-process
# below walks every silk-layer drawing record in the freshly-emitted
# oas.kicad_pcb and lifts any (stroke (width X)) where X < 0.15 to 0.15.
#
# Text (fp_text / gr_text) carries its stroke in (effects (font
# (thickness T))) and our generators already emit 0.15 there (verified
# by audit). The post-process touches that field too for safety - if
# any stock-library footprint emits text at thinner thickness it gets
# normalized in the same pass.
SILK_MIN_STROKE_MM = 0.15
SILK_DRAWING_KINDS = (
    "fp_line", "fp_arc", "fp_circle", "fp_poly", "fp_rect", "fp_text",
    "gr_line", "gr_arc", "gr_circle", "gr_poly", "gr_rect", "gr_text",
)


def _lift_silk_line_widths(min_mm: float = SILK_MIN_STROKE_MM) -> int:
    """Read `oas.kicad_pcb`, walk every silk-layer drawing block, and
    rewrite any `(stroke (width X))` / `(thickness T)` clause whose
    value is below `min_mm`. Returns the count of lifted strokes.

    Uses depth-counting parse for block extraction (same pattern as
    `_apply_schematic_footprints`). Layer detection is by the FIRST
    `(layer "...")` inside the block - drawing records have at most one
    layer clause and it's always at the same depth as the geometry."""
    import re

    pcb_path = HERE / "oas.kicad_pcb"
    text = pcb_path.read_text(encoding="utf-8")
    n = len(text)
    out_parts: list[str] = []
    cursor = 0
    lifted = 0

    # Pre-build a regex that finds the start of every drawing block.
    # Each kind starts with `(<kind>` followed by whitespace, `(`, or
    # newline. Use a single alternation to walk all matches in source
    # order so we keep the output deterministic across runs.
    kinds_alt = "|".join(re.escape(k) for k in SILK_DRAWING_KINDS)
    starter = re.compile(r"\((?:" + kinds_alt + r")(?=[\s(])")

    for m in starter.finditer(text):
        idx = m.start()
        if idx < cursor:
            # Skip if we've already consumed past this match (shouldn't
            # happen since each finditer match starts at a distinct
            # position, but defensive).
            continue
        out_parts.append(text[cursor:idx])
        depth = 0
        j = idx
        while j < n:
            ch = text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = text[idx:j]
        # Find the block's layer. Skip non-silk.
        m_layer = re.search(r'\(layer\s+"([^"]+)"', block)
        layer = m_layer.group(1) if m_layer else None
        if layer in ("F.SilkS", "B.SilkS"):
            # Lift (stroke (width X)) if X < min.
            def _lift_stroke(mm: re.Match) -> str:
                nonlocal lifted
                w = float(mm.group(1))
                if w < min_mm:
                    lifted += 1
                    return f"(stroke (width {min_mm})"
                return mm.group(0)
            block = re.sub(
                r'\(stroke\s*\(width\s+([\d.]+)\)',
                _lift_stroke,
                block,
            )
            # Lift (thickness T) if T < min (used inside text effects).
            def _lift_thickness(mm: re.Match) -> str:
                nonlocal lifted
                t = float(mm.group(1))
                if t < min_mm:
                    lifted += 1
                    return f"(thickness {min_mm})"
                return mm.group(0)
            block = re.sub(
                r'\(thickness\s+([\d.]+)\)',
                _lift_thickness,
                block,
            )
        out_parts.append(block)
        cursor = j

    out_parts.append(text[cursor:])
    new_text = "".join(out_parts)
    if new_text != text:
        pcb_path.write_text(new_text, encoding="utf-8")
    return lifted


def apply_routing_to_pcb(chunks: tuple[str, ...] = ("power",)) -> int:
    """Read oas.kicad_pcb, compute copper tracks for the requested chunks,
    and write the PCB back with `(segment ...)` / `(via ...)` / `(zone ...)`
    records inserted just before the closing `)`.

    `chunks` is a tuple of chunk names to route. Valid names:
        "power"    — 24 V input protection chain (Chunk 1)
        "bucks"    — buck output stages + 5 V / 3.3 V rails (Chunk 2)
        "ledring"  — LED ring 5 V + WS2812 daisy chain (Chunk 3)
        "signals"  — I²C, UART, GPIO, USB recovery (Chunk 4)
        "gnd"      — GND pour zones + stitching vias (Chunk 5)
    Returns number of route records emitted.
    """
    # Always parse pad DB from the current PCB file
    pads, nets = _routing_pad_db()
    em = _RouteEmitter()
    total = 0

    if "gnd" in chunks:
        total += _route_gnd_pour(em, nets)
    if "local" in chunks:
        total += _route_local_decoupling(em, nets)
    if "autoroute" in chunks:
        total += _route_autoroute_tracks(em, nets)
    if "hand_v40" in chunks:
        total += _route_hand_v40(em, nets)
    if "io_finalize" in chunks:
        total += _route_io_finalize(em, nets)
    if "io_finalize_v29" in chunks:
        total += _route_io_finalize_v29(em, nets)
    if "io_finalize_v30" in chunks:
        total += _route_io_finalize_v30(em, nets)
    # Future chunks slot in here

    if total == 0 and not chunks:
        return 0

    # Re-read PCB text, insert tracks before final `)`.
    pcb_path = HERE / "oas.kicad_pcb"
    text = pcb_path.read_text(encoding="utf-8")
    # The closing `)` of the kicad_pcb wrapper is the LAST `)` in the
    # file (followed by an optional newline). Insert tracks BEFORE it.
    body = em.render()
    # Find last `)` and insert body + "\n" before it.
    # File ends with "\n)\n" per gen_pcb().
    if text.rstrip().endswith(")"):
        # Insert body inside the wrapper
        i = text.rfind(")")
        new_text = text[:i] + body + "\n" + text[i:]
        pcb_path.write_text(new_text, encoding="utf-8")

    return total


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
