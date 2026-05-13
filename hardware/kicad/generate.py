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
import textwrap
import uuid
from pathlib import Path

HERE = Path(__file__).parent

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
CUTOUTS = [
    # name, x_min, x_max, y_min, y_max  (PCB-local mm, +Y = toward chord)
    ("C3",  +4.900, +13.900, +28.998, +Y_CHORD),  # 9 × 15.5 mm,   clipped at chord (would extend +1 mm beyond)
    ("C4", +18.900, +22.900, +34.998, +Y_CHORD),  # 4 × 9 mm,      clipped at chord (would extend +0.5 mm; has language tab Ø3 mm in case wall)
    ("C5", +27.900, +35.400, +36.494, +42.494),   # 7.5 × 6 mm,    fully inside PCB
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
J3_X = 36.0   # v0.9: located below SEN66 body shadow. Centred horizontally
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
MIKROE2462_ANCHOR_X = -12.76       # v0.15.7: rotated 180° around body
                                    # center. Anchor now at body BOTTOM-RIGHT
                                    # corner in PCB (was top-left in v0.15.6).
                                    # Body PCB range unchanged: X=-38.16..-12.76.
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
J1_PCB_Y = +22.4             # PCB Y of pin row (footprint-local Y = 0).
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
# AQI status LED ring (v0.16) — 12 × SK6812-SIDE side-emit addressable RGB
# -----------------------------------------------------------------------------
# Twelve side-emit RGB LEDs on a Ø22 mm pitch circle around the central
# Ø12 mm cable hole. Each LED radiates LIGHT RADIALLY OUTWARD into the
# AK-N-94 perforated cover where it scatters and reads as a soft glowing
# halo (no per-perforation hot-spot dotting). Side-emit geometry chosen
# over top-emit per `hardware/components/_research-led-diffuse-ring.md`.
#
# LED chip: SK6812 SIDE-A (Shenzhen Normand / OPSCO Optoelectronics).
# Package 4.0 × 2.0 × 1.6 mm. Pinout 1=DIN, 2=VDD, 3=DOUT, 4=GND
# (verified against Normand 2018 rev 01 datasheet and OPSCO 2021 rev A/1).
# See `hardware/components/sk6812-side.md` for the verified part spec.
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
# LED_RING_RADIUS = 11.0 mm puts LED centres on a Ø22 mm pitch circle.
# Inner-most LED body edge at R = 11 - 1 = 10 mm (body half-width 1 mm
# radially); 4 mm radial clearance to the Ø12 mm cable hole edge at R=6.
# Outer-most LED body edge at R = 12 mm. Outer edge nearest pre-existing
# component is the MIKROE-2462 silk rect at PCB X = -12.26 mm at angle
# 180° (LED D17 body at X ≤ -12 mm) — 0.26 mm of silk-to-silk separation
# on paper, but we *suppress* the LED body's F.SilkS rectangle so the
# DRC silk_overlap rule (0.15 mm) is not stressed. F.Fab still carries
# the body outline for assembly documentation.
LED_RING_RADIUS = 11.0
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
SUBSHEET_SIZE = (38.1, 12.7)

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

    # Courtyard — match the body outline exactly (no inflate). The SEN66
    # lives directly on the PCB (face-up, v0.6+). The body's "footprint
    # courtyard" matches the body outline so neighbouring components
    # know to keep clear of the SEN66 body shadow on the PCB surface.
    courtyard = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U('sen66:fp:crtyd')}")
        \t)""")

    body_blocks = "\n".join([
        ref_block, value_block, footprint_block, datasheet_block, desc_block,
        fab_outline, silk_outline,
        inlet1_top, inlet1_bot, inlet1_left_arc, inlet1_right_arc,
        inlet2, outlet, divider, conn_marker, conn_label,
        courtyard,
    ])

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
        \t(property "Description" "HiLink HLK-LD2410B 24 GHz mmWave presence radar daughterboard mechanical-reference. ~33x16x7 mm. Mounts via 5-pin 1.27 mm pin header (J4) above the OAS PCB; antenna patches on the LD2410 top face point toward the AK-N-94 cover."
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
        \t(descr "HiLink HLK-LD2410B mechanical-reference (no pads). 24 GHz mmWave presence radar daughterboard. Body ~33x16x7 mm above OAS PCB on 1.27 mm pin header (J4). Antenna patches on the top face point through the enclosure cover.")
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
        \t\t(layer "F.Fab")
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
    for name, x1, x2, y1, y2 in CUTOUTS:
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
            \t\t\t(tracks not_allowed)
            \t\t\t(vias not_allowed)
            \t\t\t(pads not_allowed)
            \t\t\t(copperpour not_allowed)
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
    return textwrap.dedent(f"""\
        \t(footprint "{lib_id}"
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
        \t\t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-crtyd:' + uuid_tag)}")
        \t\t)
        \t)""")


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
        \t\t(descr "HiLink HLK-LD2410B mechanical-reference (no pads). 24 GHz mmWave presence radar daughterboard. Body ~33x16x7 mm above OAS PCB on 1.27 mm pin header (J4). Antenna patches on the LD2410 top face point through the enclosure cover.")
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
        \t\t(property "Description" "HiLink HLK-LD2410B 24 GHz mmWave presence radar daughterboard mechanical-reference. Body ~33x16x7 mm. Mounts via 5-pin 1.27 mm pin header (J4) above the OAS PCB; antenna patches on the LD2410 top face point toward the AK-N-94 cover."
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
) -> str:
    """Emit a placed SK6812-SIDE footprint instance at PCB (x, y).

    Embeds the same body content as `gen_sk6812_side_footprint()` (the
    library file body) directly into the PCB file so opening pcbnew
    without the project-local library still renders the placement.
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
    return textwrap.dedent(f"""\
        \t(footprint "oas:SK6812-SIDE"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "SK6812 SIDE-A addressable RGB LED. 4020 side-emit, integrated WS281x controller. Pinout 1=DIN 2=VDD 3=DOUT 4=GND.")
        \t\t(attr smd)
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 -1.5 {rotation})
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
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
        \t\t\t(layer "F.Fab")
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
) -> str:
    """Emit a placed Capacitor_SMD:C_0402_1005Metric footprint instance.

    Uses a self-contained 0402 pad pattern (pad pitch 0.85 mm, pad size
    0.62 × 0.70 mm) so the .kicad_pcb file remains stand-alone (no
    library lookup needed). Pad 1 sits at footprint-local +X, pad 2 at -X.
    """
    pad_x = 0.425                 # half of 0.85 mm pad pitch
    pad_w = 0.62
    pad_h = 0.70
    body_hw = 1.0 / 2.0           # body 1.0 × 0.5 mm
    body_hh = 0.5 / 2.0
    crty_x = pad_x + pad_w / 2.0 + 0.10
    crty_y = max(pad_h, 0.5) / 2.0 + 0.10
    rot_clause = f" {rotation}" if rotation != 0 else ""
    return textwrap.dedent(f"""\
        \t(footprint "C_0402_1005Metric"
        \t\t(layer "F.Cu")
        \t\t(uuid "{U('fp-inst:' + uuid_tag)}")
        \t\t(at {fx(x)} {fy(y)} {rotation})
        \t\t(descr "{descr}")
        \t\t(attr smd)
        \t\t(property "Reference" "{reference}"
        \t\t\t(at 0 -1.0 {rotation})
        \t\t\t(layer "F.SilkS")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-ref:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at 0 1.0 {rotation})
        \t\t\t(layer "F.Fab")
        \t\t\t(hide yes)
        \t\t\t(uuid "{U('fp-prop-val:' + uuid_tag)}")
        \t\t\t(effects (font (size 1.0 1.0) (thickness 0.15)))
        \t\t)
        \t\t(property "Footprint" "C_0402_1005Metric"
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
        \t\t\t(start {fmt(-body_hw)} {fmt(-body_hh)})
        \t\t\t(end {fmt(body_hw)} {fmt(body_hh)})
        \t\t\t(stroke (width 0.1) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.Fab")
        \t\t\t(uuid "{U('fp-fab-body:' + uuid_tag)}")
        \t\t)
        \t\t(fp_rect
        \t\t\t(start {fmt(-crty_x)} {fmt(-crty_y)})
        \t\t\t(end {fmt(crty_x)} {fmt(crty_y)})
        \t\t\t(stroke (width 0.05) (type solid))
        \t\t\t(fill no)
        \t\t\t(layer "F.CrtYd")
        \t\t\t(uuid "{U('fp-crtyd:' + uuid_tag)}")
        \t\t)
        \t\t(pad "1" smd rect
        \t\t\t(at {fmt(-pad_x)} 0{rot_clause})
        \t\t\t(size {fmt(pad_w)} {fmt(pad_h)})
        \t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
        \t\t\t(uuid "{U('fp-pad-1:' + uuid_tag)}")
        \t\t)
        \t\t(pad "2" smd rect
        \t\t\t(at {fmt(+pad_x)} 0{rot_clause})
        \t\t\t(size {fmt(pad_w)} {fmt(pad_h)})
        \t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
        \t\t\t(uuid "{U('fp-pad-2:' + uuid_tag)}")
        \t\t)
        \t)""")


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
    # v0.9: previous "-> J3" cable-direction arrow at the SEN66 connector
    # and the "to SEN66" label at J3 are dropped — with J3 now directly
    # below the SEN66 body shadow, the SEN66 ↔ J3 association is visually
    # obvious from the silk outlines alone.

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

    # ---- v0.15.8: ESP32 and MIKROE-2462 body-label boards (mirror Task
    # #8 for these daughterboards). The body labels live INSIDE the
    # respective body silk rects but rotate with the footprint, making
    # them upside-down or vertical depending on placement. Board-level
    # gr_text keeps them horizontal.
    # ESP32 body centre (rotation 90 -> LIB +Y → PCB +X, +X → PCB -Y).
    # Body LIB extent: 0..body_w × 0..body_l. Centre LIB = (body_w/2,
    # body_l/2). PCB = (anchor_x + body_l/2, anchor_y - body_w/2).
    esp32_body_cx = ESP32_ANCHOR_X + ESP32_BODY_L / 2.0
    esp32_body_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("ESP32-C6 DevKitM-1", esp32_body_cx, esp32_body_cy,
                       "esp32-body", size=1.0))
    # ESP32 antenna ("ant") and USB-C ("USB") short-edge hints. LIB
    # (body_w/2, 2.5) and (body_w/2, body_l - 6.0). After rotation 90.
    esp32_ant_cx = ESP32_ANCHOR_X + 2.5
    esp32_ant_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("ant", esp32_ant_cx, esp32_ant_cy,
                       "esp32-antenna", size=1.0))
    esp32_usb_cx = ESP32_ANCHOR_X + (ESP32_BODY_L - 6.0)
    esp32_usb_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("USB", esp32_usb_cx, esp32_usb_cy,
                       "esp32-usb", size=1.0))
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
    parts.append(_silk("J1 (24V)", +15.0, J1_PCB_Y, "j1-body-id", size=1.0))
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

    # ---- v0.7: cutout-zone reservation labels + outlines on F.SilkS ----
    # Each cutout C1..C5 along the chord is reserved for a future
    # connector that extends through the case wall (24V terminal, JST GH
    # to LD2410, USB-C debug, Qwiic, etc.). Draw both:
    #   - A thin F.SilkS rectangle outlining the cutout footprint, inset
    #     by SILK_EDGE_INSET on each side so it clears Edge.Cuts even
    #     when the cutout is clipped at the chord
    #   - A "C# AUX" text label centred in the rectangle. For narrow
    #     rects the text is rotated 90° so it still fits inside the
    #     outline without overlapping (DRC silk_overlap).
    SILK_EDGE_INSET = 0.3       # mm — keeps rect off the board edge.
                                # With 0.12 mm silk stroke, line outer edge
                                # sits 0.06 mm beyond the centerline; 0.3 mm
                                # inset leaves 0.24 mm clear to Edge.Cuts,
                                # comfortably above the 0.15 mm DRC limit.
    SILK_TEXT_MIN_HORIZONTAL_FIT = 5.0   # mm — width needed to keep "C# AUX"
                                          # at 1.0 mm horizontal inside the rect
    for name, x1, x2, y1, y2 in CUTOUTS:
        rx1, rx2 = x1 + SILK_EDGE_INSET, x2 - SILK_EDGE_INSET
        ry1, ry2 = y1 + SILK_EDGE_INSET, y2 - SILK_EDGE_INSET
        cx = (rx1 + rx2) / 2
        cy = (ry1 + ry2) / 2
        rect_w = rx2 - rx1
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
        parts.append(_silk(
            f"{name} AUX", cx, cy, f"cutout-silk-{name}",
            size=1.0, angle=text_angle,
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

    # 3 mounting holes
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
        """) + markers + "\n" + "\n".join(footprints) + "\n" + sensor_footprints + "\n" + silk_labels + "\n" + keepouts + "\n)\n"
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
    "io": [],
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
    # The east-going horizontal segments at Y=97.79 and Y=100.33 traverse
    # the io block area — which is empty for now, so visually fine.
    # Vertical legs at X=143.51 (UART_TX) and X=146.05 (UART_RX) keep the
    # two nets on distinct columns.
    inter_wires.append(_root_wire(88.9, 97.79, 143.51, 97.79, "uart-tx-east-from-sensors"))
    inter_wires.append(_root_wire(143.51, 97.79, 143.51, 52.07, "uart-tx-vertical"))
    inter_wires.append(_root_wire(143.51, 52.07, 139.7, 52.07, "uart-tx-west-into-mcu"))
    inter_wires.append(_root_wire(88.9, 100.33, 146.05, 100.33, "uart-rx-east-from-sensors"))
    inter_wires.append(_root_wire(146.05, 100.33, 146.05, 54.61, "uart-rx-vertical"))
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
\t\t(symbol "Device:Q_PMOS"
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
\t\t\t(symbol "Q_PMOS_0_1"
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
\t\t\t(symbol "Q_PMOS_1_1"
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
\t\t\t\t\t(number "D"
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
\t\t\t\t\t(number "G"
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
\t\t\t\t\t(number "S"
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
        \t\t(lib_id "Device:Q_PMOS")
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
        \t\t(pin "D"
        \t\t\t(uuid "{pin_d_uuid}")
        \t\t)
        \t\t(pin "G"
        \t\t\t(uuid "{pin_g_uuid}")
        \t\t)
        \t\t(pin "S"
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
    side). When the gate-source voltage tries to exceed -18 V (gate well
    below source), the Zener breaks down in reverse and clamps the gate-
    side junction to V_S - 18 V, keeping |Vgs| within the PMV65XP's
    +/-20 V absolute maximum.

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
                     │     │            D3 (18V Zener, cathode → S net,
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
    below Q1's absolute maximum (PMV65XP Vds_max = -50V).

    The Q1 gate-source clamp (R4 + D3) is mandatory because PMV65XP
    (like the previous DMP4015SK3) has Vgs_max = +/-20V, while the
    natural pull-down through R1 alone would set Vgs = -24V at the 24V
    supply, exceeding the absolute max. With D3 (18V Zener) shunting
    the gate-side junction to source whenever the gate tries to drop
    more than 18V below source, |Vgs| is clamped to <=18V. R4 (1k)
    provides series isolation in the gate path.

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
        - D3 (18V Zener, angle=270) placed LEFT of the R4/R1 column with
          its CATHODE wired UP to the VIN net (Q1.S side, via a T-tap on
          the existing vin-horiz wire) and its ANODE wired DOWN-and-RIGHT
          via an L-route to the R4/R1 junction. Clamp current at steady
          state flows S -> D3 (reverse breakdown at Vz=18V) -> junction
          -> R1 -> GND, drawing ~60 uA when active.
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

    # ----- D3: 18 V Zener gate-source clamp, angle=270 (body vertical) -----
    # PMV65XP (and the predecessor DMP4015SK3) both have Vgs_max = +/-20V
    # absolute maximum. With R1 alone pulling the gate toward GND, Vgs at
    # the 24V supply settles at -24V — overshooting the gate-oxide limit
    # by 20% and slowly destroying Q1. D3 (18V Zener) clamps |Vgs| to
    # <=18V by shunting current from Q1.S to the R4/R1 junction whenever
    # the junction voltage drops more than 18V below source. With the
    # clamp active, the junction sits at V_S - 18V = 6V; the gate sees the
    # same 6V through R4 (no DC gate current), so Vgs = 6 - 24 = -18V.
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
    parts.append(_sch_diode_tvs(
        x=D1_X, y=D1_Y, angle=90,
        reference="D1", value="SMBJ24A", uuid_tag="d1",
    ))

    # ----- D3: 18 V Zener gate-source clamp (PMV65XP Vgs protection) -----
    # See R4/D3 constants block above for the topology rationale. D3
    # cathode taps the J1.1 -> Q1.S VIN wire; anode lands on the R4/R1
    # junction so a clamp event sinks current from Q1.S through D3
    # (reverse breakdown at Vz=18V) into the junction and out through
    # R1 to GND. Candidate part: MMSZ4705 (18V Zener, 500mW, SOD-123,
    # JLCPCB Basic Parts Library). PCB-layout chunk picks the final
    # footprint based on the same-day JLCPCB stock check.
    parts.append(_sch_diode_zener(
        x=D3_X, y=D3_Y, angle=270,
        reference="D3", value="18V Zener 500mW", uuid_tag="d3",
    ))

    # ----- Q1: P-MOSFET reverse-polarity protection (PMV65XP) -----
    # Source = J1.1 (unprotected input), Drain = +24V protected rail.
    # When input polarity is correct, the body diode conducts initially,
    # then the gate is pulled negative through R4 + R1 to GND. The D3
    # Zener clamp limits |Vgs| to <=18V, so the channel turns fully on
    # at Vgs = -18V — shorting out the body diode for low conduction loss.
    # PMV65XP from Nexperia: Vds_max = -50V (margin over the 38.9V SMBJ24A
    # clamp, even better than the previous DMP4015SK3's -40V), Vgs_max =
    # +/-20V (same limit as DMP4015SK3 — that's why the D3 + R4 Zener
    # clamp from Fix #1 is still required), Id continuous = -1.95A
    # (plenty for our ~350 mA combined load), RDS(on) typ = 90 mOhm at
    # Vgs=-10V (slightly higher than DMP4015SK3's 70 mOhm but still
    # negligible at 350 mA = 11 mW dissipation), SOT-23-3 package.
    # JLCPCB Basic Parts Library — no setup fee, no intermittent-stock
    # concern that prompted the swap away from DMP4015SK3.
    parts.append(_sch_q_pmos(
        x=Q1_X, y=Q1_Y, angle=0,
        reference="Q1", value="PMV65XP", uuid_tag="q1",
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
        reference="R1", value="100k", uuid_tag="r1",
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
    # 24V -> 5V buck converter block (U1 LM2596S-5.0 + L1 + D2 + C3/C3b/C4/C4b)
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
    #   * C3 100uF/50V + C3b 100 nF : input bulk + HF bypass at U1.VIN.
    #                    50 V rating gives margin over the 24 V nominal AND
    #                    the 38.9 V SMBJ24A clamp voltage.
    #   * C4 220uF/10V + C4b 100 nF : output bulk + HF bypass at the +5V rail.
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
    #            FB ↑   +5V bus ─────── L1 ─── C4 ─── C4b ─┴── (to flag)
    #            |                |             |     |
    #     +24V bus extension      |             GND   GND
    #     ────────── C3 ── C3b ── U1.VIN     U1.OUT ── switch node
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
    # X chosen far enough right of C1, C3, C3b for cap value labels
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
    # 15.24 mm to C3b leaves clear gaps between adjacent caps' value-text
    # labels ("100uF 50V" renders ~11.4 mm wide at size 1.27).
    C3_X = 160.02 + PWR_X_SHIFT
    C3_Y = 76.20 + PWR_Y_SHIFT
    C3_TOP_Y = C3_Y - 3.81        # 72.39 — on +24V bus
    C3_BOT_Y = C3_Y + 3.81        # 80.01
    C3_GND_Y = 82.55 + PWR_Y_SHIFT  # GND symbol anchor, 2.54 below cap.bot

    # ----- C3b: input HF ceramic bypass, 100nF, angle=0 -----
    C3b_X = 175.26 + PWR_X_SHIFT
    C3b_Y = 76.20 + PWR_Y_SHIFT
    C3b_TOP_Y = C3b_Y - 3.81      # 72.39 — on +24V bus
    C3b_BOT_Y = C3b_Y + 3.81      # 80.01
    C3b_GND_Y = 82.55 + PWR_Y_SHIFT

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
    # C4 (polarized, 220uF/10V) and C4b (ceramic, 100nF) tap the +5V bus to
    # GND on the OUTPUT side of L1. Pin 1 (top, anode +) on +5V bus, pin 2
    # (bottom) to GND. Column spacing of 15.24 mm (C4↔L1, C4b↔C4) keeps the
    # "220uF 10V" / "100nF" value-text labels clear of neighbouring caps'
    # references.
    C4_X = 238.76 + PWR_X_SHIFT
    C4_Y = 71.12 + PWR_Y_SHIFT
    C4_TOP_Y = C4_Y - 3.81        # 67.31 — on +5V bus
    C4_BOT_Y = C4_Y + 3.81        # 74.93
    C4_GND_Y = 77.47 + PWR_Y_SHIFT

    C4b_X = 254.00 + PWR_X_SHIFT
    C4b_Y = 71.12 + PWR_Y_SHIFT
    C4b_TOP_Y = C4b_Y - 3.81      # 67.31 — on +5V bus
    C4b_BOT_Y = C4b_Y + 3.81      # 74.93
    C4b_GND_Y = 77.47 + PWR_Y_SHIFT

    # ----- +5V flag and PWR_FLAG sentinel -----
    # Column = C4b column (254.00). The flag stack lifts above the +5V bus
    # at Y=67.31: PWR_FLAG sentinel midway, +5V triangle at top-right Y=62.23
    # for visual alignment with the existing +24V flag (also at Y=62.23, far
    # to the left).
    COL_5V       = C4b_X          # 254.00
    Y_5V_BUS     = 67.31 + PWR_Y_SHIFT  # +5V bus row (above U1 body top edge Y=69.85)
    JUNC_5V_Y    = 64.77 + PWR_Y_SHIFT  # PWR_FLAG sentinel on the vertical to flag
    FLAG_5V_Y    = 62.23 + PWR_Y_SHIFT  # +5V triangle, same Y as +24V flag

    # ----- Buck-block wires -----
    # +24V bus extension from C1.top (142.24, 72.39) RIGHT to U1.VIN
    # (165.10, 72.39). Single wire segment; junctions added at C3.top and
    # C3b.top tap points, and at the (now 3-way) C1.top corner.
    parts.append(_sch_wire(C1_X, F1_TOP_Y, U1_VIN_X, U1_VIN_Y, "vin-c1-to-u1"))

    # C3.bot → C3-GND
    parts.append(_sch_wire(C3_X, C3_BOT_Y, C3_X, C3_GND_Y, "c3bot-to-gnd"))
    # C3b.bot → C3b-GND
    parts.append(_sch_wire(C3b_X, C3b_BOT_Y, C3b_X, C3b_GND_Y, "c3bbot-to-gnd"))

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
    # C4b.top — a single wire segment with junctions at the tap points.
    parts.append(_sch_wire(U1_FB_X, Y_5V_BUS, COL_5V, Y_5V_BUS, "5v-bus"))

    # C4.bot → C4-GND
    parts.append(_sch_wire(C4_X, C4_BOT_Y, C4_X, C4_GND_Y, "c4bot-to-gnd"))
    # C4b.bot → C4b-GND
    parts.append(_sch_wire(C4b_X, C4b_BOT_Y, C4b_X, C4b_GND_Y, "c4bbot-to-gnd"))

    # +5V bus terminus → PWR_FLAG sentinel column upward, then to +5V flag.
    parts.append(_sch_wire(COL_5V, Y_5V_BUS, COL_5V, JUNC_5V_Y, "5v-bus-to-junc"))
    parts.append(_sch_wire(COL_5V, JUNC_5V_Y, COL_5V, FLAG_5V_Y, "5v-junc-to-flag"))

    # ----- Buck-block junctions -----
    # C1.top is now a 3-way: existing f1-to-c1 enters from left, NEW
    # vin-c1-to-u1 exits right, C1's body pin drops down.
    parts.append(_sch_junction(C1_X, F1_TOP_Y, "vin-c1-extended"))
    # C3.top tap on +24V bus.
    parts.append(_sch_junction(C3_X, C3_TOP_Y, "24v-c3"))
    # C3b.top tap on +24V bus.
    parts.append(_sch_junction(C3b_X, C3b_TOP_Y, "24v-c3b"))
    # D2.K tap on switch node.
    parts.append(_sch_junction(D2_X, U1_OUT_Y, "switch-d2"))
    # L1.top tap on +5V bus.
    parts.append(_sch_junction(L1_X, Y_5V_BUS, "5v-l1"))
    # C4.top tap on +5V bus.
    parts.append(_sch_junction(C4_X, Y_5V_BUS, "5v-c4"))
    # C4b.top + bus terminus + vertical to PWR_FLAG: 3-way.
    parts.append(_sch_junction(COL_5V, Y_5V_BUS, "5v-c4b"))
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

    # ----- C3b: input HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C3b_X, y=C3b_Y, angle=0,
        reference="C3b", value="100nF", uuid_tag="c3b",
    ))

    # ----- C4: output bulk electrolytic, 220 uF / 10 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C4_X, y=C4_Y, angle=0,
        reference="C4", value="220uF 10V", uuid_tag="c4",
    ))

    # ----- C4b: output HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C4b_X, y=C4b_Y, angle=0,
        reference="C4b", value="100nF", uuid_tag="c4b",
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
        x=C3b_X, y=C3b_GND_Y, angle=0,
        reference="#PWR08",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr08-gnd-c3b",
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
        x=C4b_X, y=C4b_GND_Y, angle=0,
        reference="#PWR13",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr13-gnd-c4b",
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
    # 5V -> 3.3V buck converter block (U2 TPS62933 + L2 + R2/R3 FB div + C5/C5b/C6/C6b/C7)
    # =========================================================================
    # Cascaded second buck stage. Takes the +5V rail produced by U1 (above)
    # and steps it down to a regulated 3.3V rail that powers the ESP32-C6
    # DevKitM-1-N4 (via its 3V3 pin, bypassing the module's onboard LDO so
    # we don't dissipate ~250 mW close to the SEN66 air-quality sensor),
    # plus the SEN66 itself and the NT3H1101 NFC tag.
    #
    # Component selection rationale (see commit message and CLAUDE.md):
    #   * TPS62933   : 3.8-30 V Vin range (17 V abs-max for the typical-use
    #                  recommendation, well above our 5 V), 3 A, 500 kHz
    #                  default, SYNCHRONOUS topology (no external Schottky
    #                  catch diode needed — high-side and low-side both
    #                  internal). SOT-583-8 package, JLCPCB Basic library.
    #                  ~95% efficiency at ~300 mA load — much better than
    #                  LM2596's ~80% (LM2596 has external Schottky losses
    #                  and runs at 150 kHz so the inductor ripple is much
    #                  larger). The 17 V Vin_max ceiling that ruled it out
    #                  upstream of D1 is irrelevant here because we cascade
    #                  from the regulated +5V rail.
    #   * L2 2.2uH  : Per TPS62933 datasheet typical-application table for
    #                  3.3 V output at 500 kHz. Shielded SMD ferrite-core
    #                  inductor with ≥2 A saturation and ~50 mOhm DCR.
    #                  4×4 mm or 3×3 mm package — much smaller than LM2596's
    #                  33 uH because the higher fsw drops the inductor
    #                  requirement by ~15×.
    #   * R2 44.2k 1% / R3 10k 1% (FB divider): TPS62933 FB pin reference
    #                  voltage = 0.6 V. Vout = Vfb × (1 + R2/R3) =
    #                  0.6 × (1 + 4.42) = 3.252 V — well within the
    #                  ESP32-C6's 3.0-3.6 V supply window and the typical
    #                  3.0-3.6 V supply requirements of SEN66 and NT3H1101.
    #                  R3 = 10 kΩ gives a low-current divider
    #                  (~60 µA), and R2 = 44.2 kΩ is the nearest E96 value.
    #                  1% tolerance keeps the output voltage variation due
    #                  to divider tolerance below ±20 mV.
    #   * C5 10uF + C5b 100nF : input bulk + HF ceramic bypass at U2.VIN.
    #                  Per datasheet: ceramic X5R/X7R; 16 V rating gives
    #                  3× margin over the 5 V input.
    #   * C6 22uF + C6b 100nF : output bulk + HF ceramic bypass at the
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
    # selects the default ~500 kHz internal oscillator. SS pin (soft-start)
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
    # the +3.3V net exits to the right through C6/C6b decoupling and a
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
    U2_RT_Y     = U2_Y + 5.08     # 149.86 — tied to GND (default 500 kHz)
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
    # to GND. C5 sits 15.24 mm left of C5b — wide enough that the
    # value-text label "10uF 16V" (rendered ~10 mm at size 1.27) clears
    # C5b's value-text "100nF" without visual overlap.
    C5_X = 170.18 + PWR_X_SHIFT   # 134 × 1.27
    C5_Y = 140.97 + PWR_Y_SHIFT   # 111 × 1.27
    C5_TOP_Y = C5_Y - 3.81        # 137.16 — on +5V bus row
    C5_BOT_Y = C5_Y + 3.81        # 144.78
    C5_GND_Y = 147.32 + PWR_Y_SHIFT  # GND symbol, 2.54 below cap.bot

    # ----- C5b: input HF ceramic bypass, 100nF, angle=0 -----
    C5b_X = 185.42 + PWR_X_SHIFT  # 146 × 1.27 — 15.24 mm right of C5, 7.62 left of VIN
    C5b_Y = 140.97 + PWR_Y_SHIFT
    C5b_TOP_Y = C5b_Y - 3.81      # 137.16
    C5b_BOT_Y = C5b_Y + 3.81      # 144.78
    C5b_GND_Y = 147.32 + PWR_Y_SHIFT

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
    # TPS62933 FB pin reference voltage Vfb = 0.6 V.
    #   Vout = Vfb × (1 + R2/R3)  =>  R2/R3 = (Vout/Vfb - 1) = 4.5 for Vout=3.3V
    # With R3 = 10 kΩ (datasheet-recommended low-current divider):
    #   R2 = 45 kΩ ideal → nearest E96 = 44.2 kΩ
    #   → Vout = 0.6 × (1 + 4.42) = 3.252 V  (within ESP32-C6's 3.0-3.6 V window)
    #
    # Layout: R2 (top, 44.2 kΩ) and R3 (bottom, 10 kΩ) vertically stacked,
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
    # C6 (22uF) and C6b (100nF) tap the +3.3V bus to GND. Placed to the
    # right of the FB divider with 15-16 mm column spacing so the
    # value-text labels ("44.2k 1%" / "22uF 10V" / "100nF") never overlap.
    C6_X = 256.54 + PWR_X_SHIFT   # 202 × 1.27 (16.51 right of R2)
    C6_Y = 140.97 + PWR_Y_SHIFT
    C6_TOP_Y = C6_Y - 3.81        # 137.16 — on +3.3V bus
    C6_BOT_Y = C6_Y + 3.81        # 144.78
    C6_GND_Y = 147.32 + PWR_Y_SHIFT

    C6b_X = 271.78 + PWR_X_SHIFT  # 214 × 1.27 (15.24 right of C6)
    C6b_Y = 140.97 + PWR_Y_SHIFT
    C6b_TOP_Y = C6b_Y - 3.81      # 137.16
    C6b_BOT_Y = C6b_Y + 3.81      # 144.78
    C6b_GND_Y = 147.32 + PWR_Y_SHIFT

    # ----- +3.3V flag, PWR_FLAG sentinel -----
    # Column = C6b + 7.62 = 279.40. This sits ~25 mm right of the +5V flag
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
    # VIN bus horizontal: C5.top → C5b.top → U2.VIN pin
    parts.append(_sch_wire(C5_X, U2_VIN_Y, U2_VIN_X, U2_VIN_Y, "vin-bus-c5-c5b-u2"))
    # C5 and C5b drops to local GND symbols
    parts.append(_sch_wire(C5_X, C5_BOT_Y, C5_X, C5_GND_Y, "c5bot-to-gnd"))
    parts.append(_sch_wire(C5b_X, C5b_BOT_Y, C5b_X, C5b_GND_Y, "c5bbot-to-gnd"))

    # RT → GND: RT pin (programmable f_sw) tied to GND for default ~500 kHz.
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
    # C6 column, C6b column, to the flag column COL_3V3. Single wire
    # with junctions at the four tap points (R2 vertical end, C6 pin,
    # C6b pin, mid-bus T's).
    parts.append(_sch_wire(L2_X, Y_3V3_BUS, COL_3V3, Y_3V3_BUS, "3v3-bus"))

    # C6 and C6b drops to local GND symbols
    parts.append(_sch_wire(C6_X, C6_BOT_Y, C6_X, C6_GND_Y, "c6bot-to-gnd"))
    parts.append(_sch_wire(C6b_X, C6b_BOT_Y, C6b_X, C6b_GND_Y, "c6bbot-to-gnd"))

    # +3.3V bus terminus → PWR_FLAG sentinel column upward, then to +3V3 flag.
    parts.append(_sch_wire(COL_3V3, Y_3V3_BUS, COL_3V3, JUNC_3V3_Y, "3v3-bus-to-junc"))
    parts.append(_sch_wire(COL_3V3, JUNC_3V3_Y, COL_3V3, FLAG_3V3_Y, "3v3-junc-to-flag"))

    # ----- Buck-3.3V junctions -----
    # VIN 4-way tap: VIN bus horizontal ends, +5V drop wire passes through,
    # VIN-to-EN wire starts. Plus U2.VIN pin endpoint.
    parts.append(_sch_junction(U2_VIN_X, U2_VIN_Y, "vin-u2"))
    # C5b.top tap on VIN bus (mid-bus T with pin endpoint)
    parts.append(_sch_junction(C5b_X, U2_VIN_Y, "vin-c5b"))
    # SW wire passes through C7.bot tap column
    parts.append(_sch_junction(C7_X, U2_SW_Y, "sw-c7"))
    # FB tap: R2.bot pin + R3.top pin + FB wire end = 3 endpoints
    parts.append(_sch_junction(COL_FB_DIV, R2_BOT_Y, "fb-tap"))
    # +3.3V bus mid-bus T's: R2-vertical end, C6 pin, C6b pin
    parts.append(_sch_junction(COL_FB_DIV, Y_3V3_BUS, "3v3-r2"))
    parts.append(_sch_junction(C6_X, Y_3V3_BUS, "3v3-c6"))
    parts.append(_sch_junction(C6b_X, Y_3V3_BUS, "3v3-c6b"))
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

    # ----- C5b: input HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C5b_X, y=C5b_Y, angle=0,
        reference="C5b", value="100nF", uuid_tag="c5b",
    ))

    # ----- C6: output bulk ceramic, 22 uF / 10 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C6_X, y=C6_Y, angle=0,
        reference="C6", value="22uF 10V", uuid_tag="c6",
    ))

    # ----- C6b: output HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C6b_X, y=C6b_Y, angle=0,
        reference="C6b", value="100nF", uuid_tag="c6b",
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

    # ----- R2: feedback divider top, 44.2 kΩ 1% -----
    parts.append(_sch_resistor(
        x=R2_X, y=R2_Y, angle=0,
        reference="R2", value="44.2k 1%", uuid_tag="r2",
    ))

    # ----- R3: feedback divider bottom, 10 kΩ 1% -----
    parts.append(_sch_resistor(
        x=R3_X, y=R3_Y, angle=0,
        reference="R3", value="10k 1%", uuid_tag="r3",
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
        x=C5b_X, y=C5b_GND_Y, angle=0,
        reference="#PWR18",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr18-gnd-c5b",
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
        x=C6b_X, y=C6b_GND_Y, angle=0,
        reference="#PWR23",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr23-gnd-c6b",
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
    28,   # J3.13 = GPIO13   (USB D+, native USB-Serial-JTAG; onboard USB only)
    29,   # J3.14 = GPIO12   (USB D-, native USB-Serial-JTAG; onboard USB only)
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

    Combines the dynamically-built ESP32-C6-DevKitM-1 symbol (see
    ESP32C6_DEVKITM1_PINS for the single source of truth) with the
    stock Device:R block and the static tail (Conn_01x06, Device:C,
    Device:C_Polarized, power:+3V3, power:GND).
    """
    return "\n".join((
        _esp32c6_devkitm1_lib_symbol(),
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


def gen_mcu_sch() -> str:
    """MCU sub-sheet — ESP32-C6-DevKitM-1-N4 (U3) + C9/C9b decoupling
    + R5/R6 I²C pull-ups + J2 recovery header.

    Layout (schematic page-absolute mm, KiCad +Y is down on screen):

      +3V3 rail (Y=76.20) ===================================
        |       |        |       |        |       |
        C9      R5       R6      C9b      +3V3    |
       (10uF)  (10k)    (10k)   (100nF)   PWR     | (drop right and down)
        |       v         v       |               |
        GND   SDA tap   SCL tap   GND             |
                                                  |
                                                  v
                                          U3.1 (3V3 pin) at top of J1

      U3 anchored at (152.40, 110.49) with 30 pins (J1 left, J3 right;
      15 pins per header) modelled on the official Espressif user guide
      pin layout. R5 (SDA pull-up) drops south from the +3V3 bus and
      taps the SDA wire at U3.10 (GPIO 6). R6 (SCL pull-up) drops south
      and taps the SCL wire at U3.11 (GPIO 7); its vertical wire crosses
      the SDA horizontal wire mid-segment without a junction, so the two
      stay electrically distinct per KiCad's wire-crossing rule.

      J2 (SWD/UART recovery, DNP) sits to the right of U3, with TX/RX
      pins aligned to U3's J3.2 / J3.3 rows so the UART wires are short
      straight runs. BOOT and EN (RST) reach J2 via local labels (so we
      don't have to route a wire across the body of U3 from J1.2 (RST)
      to the right side).

    Pinout (v0.4 of CLAUDE.md / docs/ARCHITECTURE.md, post chip-pinout
    validation against the Espressif user guide). Pin numbers below are
    the symbol's own (1..30) numbers, mapping to the DevKitM-1 J1/J3
    header positions as recorded in ESP32C6_DEVKITM1_PINS:
      U3.1  (J1.1)  3V3      → +3V3 bus
      U3.2  (J1.2)  RST      → local label "RST" (joins to J2.5 EN)
      U3.3  (J1.3)  GPIO2    → LD2410_OUT (presence interrupt)
      U3.4  (J1.4)  GPIO3    → NFC_FD (NT3H1101 field detect)
      U3.5..9       GPIO4/5/0/1/8  no-connect (strap pins / unused / RGB LED)
      U3.10 (J1.10) GPIO6    → I2C_SDA
      U3.11 (J1.11) GPIO7    → I2C_SCL
      U3.12 (J1.12) GPIO14   no-connect
      U3.13 (J1.13) GND      → GND
      U3.14 (J1.14) 5V       no-connect
      U3.15 (J1.15) GND      → GND
      U3.16 (J3.1)  GND      → GND
      U3.17 (J3.2)  GPIO16   → UART_TX (256000 baud → LD2410 RX)
      U3.18 (J3.3)  GPIO17   → UART_RX (256000 baud ← LD2410 TX)
      U3.19..25     GPIO23/22/21/20/19/18/15  no-connect
      U3.26 (J3.11) GPIO9    → local label "BOOT" (joins to J2.6 BOOT)
      U3.27 (J3.12) GND      → GND
      U3.28..29     GPIO13/12 no-connect (USB D+/D-, onboard USB only)
      U3.30 (J3.15) GND      → GND

    Inter-sheet nets exported via hierarchical_label (matching sheet ports
    are added to oas.kicad_sch's MCU sheet block):
      I2C_SDA, I2C_SCL    → sensors sub-sheet
      UART_TX, UART_RX    → sensors sub-sheet (LD2410)
      LD2410_OUT          → sensors sub-sheet
      NFC_FD              → sensors sub-sheet

    +3V3 and GND are NOT exported as hierarchical labels: the power
    section already declared them via global power symbols, which is
    KiCad's canonical mechanism for spanning power nets across hierarchy.
    Adding hier labels for them would produce "multiple net names on the
    same net" ERC noise without any electrical benefit.

    J2 (SWD/UART Recovery, DNP) pinout — same as v0.3:
      J2.1 (top)    +3V3
      J2.2          GND
      J2.3          UART_TX
      J2.4          UART_RX
      J2.5          RST           (matches RST local label near U3.2)
      J2.6 (bottom) BOOT          (matches BOOT local label near U3.26)
    """
    file_uuid = SHEET_FILE_UUIDS["mcu"]

    # ===== U3: ESP32-C6-DevKitM-1-N4 module =====
    # All coordinates on the 1.27 mm (50 mil) KiCad connection grid.
    # U3 anchor (152.40, 110.49); the new 30-pin symbol has its top
    # row at anchor_y - 17.78 and bottom row at anchor_y + 17.78.
    U3_X = 152.40
    U3_Y = 110.49
    # Pin tip shorthands (X) — derived from the lib-symbol geometry.
    U3_X_LEFT  = U3_X + ESP32C6_DEVKITM1_LIB_X_LEFT   # 139.70
    U3_X_RIGHT = U3_X + ESP32C6_DEVKITM1_LIB_X_RIGHT  # 165.10

    # Resolve symbol-pin tip (x, y) by signal name (one source of truth).
    def pin_xy(signal: str) -> tuple[float, float]:
        pin_num = ESP32C6_DEVKITM1_SIGNAL_PIN[signal]
        return _mcu_pin_xy(pin_num, U3_X, U3_Y)
    # Pre-resolve the OAS-routed pin coordinates.
    U3_3V3_X,    U3_3V3_Y    = pin_xy("3V3")          # J1.1
    U3_RST_X,    U3_RST_Y    = pin_xy("RST")          # J1.2
    U3_LDR_X,    U3_LDR_Y    = pin_xy("LD2410_OUT")   # J1.3 GPIO2
    U3_NFC_X,    U3_NFC_Y    = pin_xy("NFC_FD")       # J1.4 GPIO3
    U3_WS_X,     U3_WS_Y     = pin_xy("WS2812_DIN")   # J1.9 GPIO8 (v0.16)
    U3_SDA_X,    U3_SDA_Y    = pin_xy("I2C_SDA")      # J1.10 GPIO6
    U3_SCL_X,    U3_SCL_Y    = pin_xy("I2C_SCL")      # J1.11 GPIO7
    U3_TX_X,     U3_TX_Y     = pin_xy("UART_TX")      # J3.2  GPIO16
    U3_RX_X,     U3_RX_Y     = pin_xy("UART_RX")      # J3.3  GPIO17
    U3_BOOT_X,   U3_BOOT_Y   = pin_xy("BOOT")         # J3.11 GPIO9

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

    # ===== C9b: HF decoupling, 100nF ceramic =====
    C9b_X = 138.43
    C9b_Y = 80.01
    C9b_TOP_Y = C9b_Y - 3.81
    C9b_BOT_Y = C9b_Y + 3.81
    C9b_GND_Y = 87.63

    # ===== R5 / R6: I²C bus pull-ups, 10 kΩ 1% 0402 =====
    # Sensirion SEN66 datasheet §3.1 specifies 10 kΩ pull-ups for the
    # shared I²C bus (SEN66 + NT3H1101 + Qwiic expansion). Standard
    # mode (100 kHz) compatible; trace length <50 mm fits well within
    # rise-time budget with 10 kΩ pull-ups.
    # R5 = SDA pull-up, R6 = SCL pull-up.
    #
    # Geometry: both resistor bodies are vertical (angle=0), with pin 1
    # (top, at body_y - 3.81) landing on the +3V3 bus at Y=76.20 and pin
    # 2 (bottom, at body_y + 3.81) feeding a vertical wire south to the
    # SDA / SCL horizontal rails. R5 sits at X=121.92 (just east of the
    # left-hier-label area which ends near X=119.38) and R6 at X=124.46.
    # The 2.54 mm spacing keeps the bodies tight together; their textual
    # labels do overlap slightly with C9 in the rendered SVG — a known
    # visual nit; the schematic is still electrically correct.
    #
    # The +3V3 bus is extended westward from C9 (X=129.54) to R5
    # (X=121.92) to cover both pull-up taps.
    R5_X = 121.92
    R6_X = 124.46
    R5_Y = 80.01                    # body center; pin1 = 76.20, pin2 = 83.82
    R6_Y = 80.01

    # ===== +3V3 bus =====
    # Horizontal at Y=76.20 from R5 (X=128.27) east through R6 (130.81),
    # C9 (129.54 — sits BETWEEN R5 and R6), C9b (138.43), then on to an
    # L-corner at X=140.97 from where the bus drops south to U3.1 (3V3
    # pin) row at Y=92.71 and runs east to the U3.1 pin tip.
    BUS_3V3_Y       = 76.20
    BUS_3V3_X_LEFT  = R5_X         # 128.27 (one grid step west of C9)
    BUS_3V3_X_RIGHT = 140.97       # L-corner west of U3 body left edge
    PWR_3V3_X       = 134.62       # power flag between R6 and C9b
    PWR_3V3_Y       = BUS_3V3_Y

    # ===== J2: SWD/UART recovery header, 6-pin, DNP =====
    # Place J2 such that its TX/RX pin rows line up with U3.J3.2/J3.3 so
    # UART takes a straight east-going wire from U3 to J2 (no detour).
    # J2 with angle=0 lib pin Y offsets {+5.08, +2.54, 0, -2.54, -5.08,
    # -7.62}. With pin 3 at anchor (J2_Y), the row of U3.J3.2 (= U3_TX_Y
    # = 95.25) must coincide with J2_PIN_Y[3] = J2_Y. So we set
    # J2_Y = U3_TX_Y.
    J2_X = 199.39
    J2_Y = U3_TX_Y               # 95.25 — TX wire is straight horizontal
    J2_PIN_X = J2_X - 5.08       # 194.31 — pin tip column (all 6 pins)
    J2_PIN_Y = {
        1: J2_Y - 5.08,          # 90.17  — TOP    (+3V3)
        2: J2_Y - 2.54,          # 92.71            (GND)
        3: J2_Y,                 # 95.25            (TX)  ← U3_TX_Y
        4: J2_Y + 2.54,          # 97.79            (RX)  ← U3_RX_Y
        5: J2_Y + 5.08,          # 100.33           (RST/EN)
        6: J2_Y + 7.62,          # 102.87 — BOTTOM  (BOOT)
    }

    # J2_PIN_MAP — recovery header pinout signal assignment. RST (=EN)
    # and BOOT come in via local labels rather than direct wires.
    J2_PIN_MAP: dict[int, str] = {
        1: "+3V3",
        2: "GND",
        3: "TX",        # ← U3.17 GPIO16 ; continues east to UART_TX hier label
        4: "RX",        # ← U3.18 GPIO17 ; continues east to UART_RX hier label
        5: "RST",       # ← U3.2  RST    (local label)
        6: "BOOT",      # ← U3.26 GPIO9  (local label)
    }
    assert set(J2_PIN_MAP.values()) == {"+3V3", "GND", "RST", "BOOT", "TX", "RX"}, \
        f"J2_PIN_MAP must cover all 6 required signals exactly once: {J2_PIN_MAP}"
    J2_PIN_OF: dict[str, int] = {sig: pin for pin, sig in J2_PIN_MAP.items()}

    # ===== Hierarchical-label columns =====
    # LEFT-edge labels (sensor-bound nets): X=119.38.
    HLABEL_LEFT_X = 119.38
    # RIGHT-edge labels: X=222.25 (UART_TX, UART_RX).
    HLABEL_RIGHT_X = 222.25
    HLABEL_TX_Y = J2_PIN_Y[J2_PIN_OF["TX"]]   # 95.25 (= U3_TX_Y)
    HLABEL_RX_Y = J2_PIN_Y[J2_PIN_OF["RX"]]   # 97.79 (= U3_RX_Y)

    # ===== Wires =====
    parts: list[str] = []

    # ---- +3V3 wiring ----
    # Horizontal bus from R5 (128.27) east to L-corner (140.97), drop
    # south to U3.1 row, run east to U3.1 (3V3) pin tip.
    parts.append(_sch_wire(BUS_3V3_X_LEFT,  BUS_3V3_Y, BUS_3V3_X_RIGHT, BUS_3V3_Y, "3v3-bus"))
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, BUS_3V3_Y, BUS_3V3_X_RIGHT, U3_3V3_Y,  "3v3-bus-down"))
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, U3_3V3_Y,  U3_X_LEFT,       U3_3V3_Y,  "3v3-to-u3"))
    # Junction dots for the four mid-bus taps where C9.pin1, R5.pin1,
    # R6.pin1, C9b.pin1, +3V3 power-flag, and the L-corner connection
    # share the horizontal bus. R5.pin1 sits at BUS_3V3_X_LEFT — it is
    # an endpoint of the bus, so no junction needed there. R6.pin1, C9.pin1,
    # C9b.pin1, and PWR_3V3_X are mid-wire taps that DO need junctions.
    parts.append(_sch_junction(R6_X,      BUS_3V3_Y, "3v3-bus-tap-r6"))
    parts.append(_sch_junction(C9_X,      BUS_3V3_Y, "3v3-bus-tap-c9"))
    parts.append(_sch_junction(PWR_3V3_X, BUS_3V3_Y, "3v3-bus-tap-pwr"))
    parts.append(_sch_junction(C9b_X,     BUS_3V3_Y, "3v3-bus-tap-c9b"))

    # ---- R5 SDA-pull-up wire: R5.pin2 (128.27, 83.82) south to SDA at (128.27, U3_SDA_Y)
    # The wire endpoint sits mid-wire on the horizontal SDA — junction needed.
    parts.append(_sch_wire(R5_X, R5_Y + 3.81, R5_X, U3_SDA_Y, "r5-pullup-to-sda"))
    parts.append(_sch_junction(R5_X, U3_SDA_Y, "r5-sda-tap"))
    # ---- R6 SCL-pull-up wire: R6.pin2 (130.81, 83.82) south to SCL at (130.81, U3_SCL_Y)
    # This vertical wire passes MID-SEGMENT through the horizontal SDA
    # wire at (130.81, U3_SDA_Y) WITHOUT a junction — per KiCad rules the
    # crossing wires stay electrically separate. The endpoint at SCL DOES
    # get a junction (T-tap on the SCL horizontal wire).
    parts.append(_sch_wire(R6_X, R6_Y + 3.81, R6_X, U3_SCL_Y, "r6-pullup-to-scl"))
    parts.append(_sch_junction(R6_X, U3_SCL_Y, "r6-scl-tap"))

    # ---- C9.pin2 / C9b.pin2 → local GND symbols ----
    parts.append(_sch_wire(C9_X,  C9_BOT_Y,  C9_X,  C9_GND_Y,  "c9-to-gnd"))
    parts.append(_sch_wire(C9b_X, C9b_BOT_Y, C9b_X, C9b_GND_Y, "c9b-to-gnd"))

    # ---- I2C / interrupt signal wires (U3 left pins → left hier labels) ----
    parts.append(_sch_wire(U3_X_LEFT, U3_SDA_Y, HLABEL_LEFT_X, U3_SDA_Y, "sda-wire"))
    parts.append(_sch_wire(U3_X_LEFT, U3_SCL_Y, HLABEL_LEFT_X, U3_SCL_Y, "scl-wire"))
    parts.append(_sch_wire(U3_X_LEFT, U3_LDR_Y, HLABEL_LEFT_X, U3_LDR_Y, "ldr-wire"))
    parts.append(_sch_wire(U3_X_LEFT, U3_NFC_Y, HLABEL_LEFT_X, U3_NFC_Y, "nfc-wire"))
    # v0.16: WS2812_DIN signal wire — U3 GPIO 8 (J1.9) → WS2812_DIN hier
    # label going to the sensors sub-sheet's SK6812-SIDE AQI ring chain.
    parts.append(_sch_wire(U3_X_LEFT, U3_WS_Y, HLABEL_LEFT_X, U3_WS_Y, "ws2812-wire"))

    # ---- RST: U3.2 (J1.2) → local label "RST" ----
    # U3.2 pin tip is on the LEFT side at (139.70, 95.25). We tag the
    # local label one grid step west of the pin so the label text doesn't
    # overlap U3's pin name.
    RST_LABEL_X = U3_X_LEFT - 2.54   # 137.16
    parts.append(_sch_wire(U3_X_LEFT, U3_RST_Y, RST_LABEL_X, U3_RST_Y, "rst-u3-stub"))
    parts.append(_sch_local_label(
        name="RST", x=RST_LABEL_X, y=U3_RST_Y, angle=180, justify="right",
        uuid_tag="rst-u3",
    ))

    # ---- BOOT: U3.26 (J3.11) → local label "BOOT" ----
    # U3.26 pin tip is on the RIGHT side at (165.10, 118.11). Tag one
    # grid step east of the pin.
    BOOT_LABEL_X = U3_X_RIGHT + 2.54  # 167.64
    parts.append(_sch_wire(U3_X_RIGHT, U3_BOOT_Y, BOOT_LABEL_X, U3_BOOT_Y, "boot-u3-stub"))
    parts.append(_sch_local_label(
        name="BOOT", x=BOOT_LABEL_X, y=U3_BOOT_Y, angle=0, justify="left",
        uuid_tag="boot-u3",
    ))

    # ---- UART: U3 right pins → J2 (TX/RX are straight wires) ----
    j2_tx_y   = J2_PIN_Y[J2_PIN_OF["TX"]]    # 95.25 = U3_TX_Y
    j2_rx_y   = J2_PIN_Y[J2_PIN_OF["RX"]]    # 97.79 = U3_RX_Y
    j2_rst_y  = J2_PIN_Y[J2_PIN_OF["RST"]]   # 100.33
    j2_boot_y = J2_PIN_Y[J2_PIN_OF["BOOT"]]  # 102.87

    # TX: straight east from U3.17 to UART_TX hier label, passing through J2.3.
    parts.append(_sch_wire(U3_X_RIGHT, U3_TX_Y, HLABEL_RIGHT_X, U3_TX_Y, "tx-bus"))
    parts.append(_sch_junction(J2_PIN_X, j2_tx_y, "tx-j2-tap"))
    # RX: straight east from U3.18 to UART_RX hier label, passing through J2.4.
    parts.append(_sch_wire(U3_X_RIGHT, U3_RX_Y, HLABEL_RIGHT_X, U3_RX_Y, "rx-bus"))
    parts.append(_sch_junction(J2_PIN_X, j2_rx_y, "rx-j2-tap"))

    # ---- J2.5 (RST) and J2.6 (BOOT) local labels ----
    # Stubs hop west from each J2 pin tip and end at a local label of
    # the matching name. KiCad joins them to the matching U3-side labels.
    J2_RST_LABEL_X = J2_PIN_X - 2.54
    parts.append(_sch_wire(J2_PIN_X, j2_rst_y, J2_RST_LABEL_X, j2_rst_y, "j2-rst-stub"))
    parts.append(_sch_local_label(
        name="RST", x=J2_RST_LABEL_X, y=j2_rst_y, angle=180, justify="right",
        uuid_tag="rst-j2",
    ))
    J2_BOOT_LABEL_X = J2_PIN_X - 2.54
    parts.append(_sch_wire(J2_PIN_X, j2_boot_y, J2_BOOT_LABEL_X, j2_boot_y, "j2-boot-stub"))
    parts.append(_sch_local_label(
        name="BOOT", x=J2_BOOT_LABEL_X, y=j2_boot_y, angle=180, justify="right",
        uuid_tag="boot-j2",
    ))

    # ---- J2.1 (+3V3) and J2.2 (GND) local power flags ----
    j2_3v3_y = J2_PIN_Y[J2_PIN_OF["+3V3"]]
    j2_gnd_y = J2_PIN_Y[J2_PIN_OF["GND"]]
    PWR_J2_3V3_Y = j2_3v3_y - 3.81
    parts.append(_sch_wire(J2_PIN_X, PWR_J2_3V3_Y, J2_PIN_X, j2_3v3_y, "j2-3v3-drop"))
    PWR_J2_GND_X = J2_PIN_X - 5.08
    parts.append(_sch_wire(J2_PIN_X, j2_gnd_y, PWR_J2_GND_X, j2_gnd_y, "j2-gnd-hop"))

    # ---- U3 GND pins → local GND symbols ----
    # Five GND pins on U3 (J1.13/15 and J3.1/12/15). Each gets a local
    # GND symbol hugging the pin so the GND text doesn't collide with
    # adjacent pin labels.
    for gnd_pin in ESP32C6_DEVKITM1_GND_PINS:
        gx, gy = _mcu_pin_xy(gnd_pin, U3_X, U3_Y)
        # Direction the GND symbol sits relative to the pin tip:
        # LEFT-side pins get the symbol to the west (angle=270 → triangle
        # points east, into the symbol); RIGHT-side pins to the east
        # (angle=90 → triangle points west, into the symbol).
        on_left = (gx < U3_X)
        if on_left:
            sym_x = gx - 3.81
            sym_angle = 270
            voff_x = -3.81
        else:
            sym_x = gx + 3.81
            sym_angle = 90
            voff_x = 3.81
        # Short horizontal hop from pin tip to symbol anchor.
        parts.append(_sch_wire(gx, gy, sym_x, gy, f"u3-gnd-hop-{gnd_pin}"))
        parts.append(_sch_power_flag(
            lib_id="power:GND", value="GND",
            x=sym_x, y=gy, angle=sym_angle,
            reference=f"#PWR_GND_U3_{gnd_pin}",
            value_offset_x=voff_x, value_offset_y=0.0,
            uuid_tag=f"pwr-gnd-u3-{gnd_pin}",
            sheet_key="mcu",
        ))

    # ===== Hierarchical labels =====
    parts.append(_sch_hierarchical_label(
        name="I2C_SDA", shape="bidirectional",
        x=HLABEL_LEFT_X, y=U3_SDA_Y, angle=180, justify="right",
        uuid_tag="i2c-sda",
    ))
    parts.append(_sch_hierarchical_label(
        name="I2C_SCL", shape="output",
        x=HLABEL_LEFT_X, y=U3_SCL_Y, angle=180, justify="right",
        uuid_tag="i2c-scl",
    ))
    parts.append(_sch_hierarchical_label(
        name="LD2410_OUT", shape="input",
        x=HLABEL_LEFT_X, y=U3_LDR_Y, angle=180, justify="right",
        uuid_tag="ld2410-out",
    ))
    parts.append(_sch_hierarchical_label(
        name="NFC_FD", shape="input",
        x=HLABEL_LEFT_X, y=U3_NFC_Y, angle=180, justify="right",
        uuid_tag="nfc-fd",
    ))
    # v0.16: WS2812_DIN — output to the sensors sub-sheet's SK6812-SIDE
    # AQI status-LED ring (D11 first LED, then daisy-chain through D22).
    parts.append(_sch_hierarchical_label(
        name="WS2812_DIN", shape="output",
        x=HLABEL_LEFT_X, y=U3_WS_Y, angle=180, justify="right",
        uuid_tag="ws2812-din",
    ))
    parts.append(_sch_hierarchical_label(
        name="UART_TX", shape="output",
        x=HLABEL_RIGHT_X, y=HLABEL_TX_Y, angle=0, justify="left",
        uuid_tag="uart-tx",
    ))
    parts.append(_sch_hierarchical_label(
        name="UART_RX", shape="input",
        x=HLABEL_RIGHT_X, y=HLABEL_RX_Y, angle=0, justify="left",
        uuid_tag="uart-rx",
    ))

    # ===== No-connect markers =====
    # Drive from ESP32C6_DEVKITM1_NC_PINS so the markers stay in lock-step
    # with the partition table at the top of the module.
    for nc_pin in ESP32C6_DEVKITM1_NC_PINS:
        nx, ny = _mcu_pin_xy(nc_pin, U3_X, U3_Y)
        parts.append(_sch_no_connect(nx, ny, f"u3-pin-{nc_pin}"))

    # ===== U3 symbol (ESP32-C6-DevKitM-1-N4) =====
    parts.append(_sch_esp32c6_devkitm1(
        x=U3_X, y=U3_Y,
        reference="U3", value="ESP32-C6-DevKitM-1-N4",
        uuid_tag="u3",
    ))

    # ===== J2 symbol (SWD/UART recovery header, DNP) =====
    parts.append(_sch_conn_01x06(
        x=J2_X, y=J2_Y, angle=0,
        reference="J2", value="SWD/UART Recovery (DNP)",
        uuid_tag="j2", dnp=True,
    ))

    # ===== Capacitors (C9 bulk, C9b HF) =====
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
        x=C9b_X, y=C9b_Y, angle=0,
        reference="C9b", value="100nF",
        uuid_tag="c9b", sheet_key="mcu",
    ))

    # ===== Resistors (R5 SDA pull-up, R6 SCL pull-up) =====
    parts.append(_sch_resistor(
        x=R5_X, y=R5_Y, angle=0,
        reference="R5", value="10k 1%",
        uuid_tag="r5", sheet_key="mcu",
    ))
    parts.append(_sch_resistor(
        x=R6_X, y=R6_Y, angle=0,
        reference="R6", value="10k 1%",
        uuid_tag="r6", sheet_key="mcu",
    ))

    # ===== Power flags =====
    # +3V3 on the bus between R6 and C9b (angle=0, triangle points UP).
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
    # GND below C9b.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C9b_X, y=C9b_GND_Y, angle=0,
        reference="#PWR28",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr28-gnd-c9b",
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
    numbering). Per `hardware/components/sk6812-side.md`.

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
    # variant has a DIFFERENT pin order — see hardware/components/hlk-ld2410b.md.)
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
    # chunk #5c — MIKROE-2462 NFC Tag 2 Click daughterboard (U4 + C12)
    # =========================================================================
    # NFC tag is hosted on a MikroElektronika "NFC Tag 2 Click"
    # (MIKROE-2462) daughterboard: NXP NT3H1101 (NTAG I²C plus) +
    # onboard PCB antenna + 16-pin mikroBUS male header (2×8, 2.54 mm
    # pitch). The board plugs into a 2×8 female pin socket on the OAS
    # PCB ("goldpiny żeńskie"). Pin-only mating means the daughterboard
    # is easy to swap or remove for service.
    #
    # WHY a daughterboard rather than a discrete NT3H2x11 SMD on the OAS
    # PCB: the alternative requires designing + tuning a PCB trace
    # antenna for 13.56 MHz (NXP AN11203) which is a non-trivial
    # sub-project. The MIKROE-2462 ships pre-tuned with its own antenna.
    # Cost ~€12; saves antenna design effort and reduces NFC firmware
    # risk by sticking to a well-documented community-supported chip.
    #
    # mikroBUS standard pinout (looking at the host socket with the
    # notch / chamfer facing UP, daughterboard above):
    #   LEFT column  (pins 1..8, top -> bottom):
    #     1=AN  2=RST 3=CS  4=SCK 5=MISO 6=MOSI 7=+3.3V 8=GND
    #   RIGHT column (pins 9..16, top -> bottom):
    #     9=PWM 10=INT 11=RX 12=TX 13=SCL  14=SDA  15=+5V  16=GND
    #
    # NFC Tag 2 Click uses ONLY these mikroBUS pins:
    #   pin 7  (+3.3V) — VCC supply for NT3H1101
    #   pin 8  (GND)   — ground (left side)
    #   pin 10 (INT)   — FD (field-detect) open-drain output. Asserts
    #                    LOW when an NFC field is present. Wired to
    #                    MCU GPIO 3 via the NFC_FD hier label so
    #                    ESPHome can wake on phone-tap without polling.
    #   pin 13 (SCL)   — I²C clock (NT3H1101 slave)
    #   pin 14 (SDA)   — I²C data (NT3H1101 slave, address 0x55)
    #   pin 16 (GND)   — ground (right side)
    #
    # All other mikroBUS pins (1, 2, 3, 4, 5, 6, 9, 11, 12, 15) are
    # unused by NFC Tag 2 Click; each gets a `(no_connect ...)` marker
    # so ERC stays quiet.

    # ===== U4: mikroBUS 2x8 socket (placeholder symbol) =====
    # Anchor far enough LEFT of J3/J4 to keep the wiring clean.
    # Conn_02x08_Top_Bottom body spans lib X = -5.08..+7.62, lib Y =
    # +7.62..-10.16. With anchor (120, 125) (no rotation), pin schem
    # positions are:
    #   left  col: X = 114.92,  Y = anchor_Y - lib_Y
    #   right col: X = 127.62,  Y = anchor_Y - lib_Y
    U4_X = 120.65
    U4_Y = 125.73
    U4_LEFT_X = U4_X - 5.08      # 115.57 — pin tip X for LEFT column
    U4_RIGHT_X = U4_X + 7.62     # 128.27 — pin tip X for RIGHT column
    # Pin Y positions (pin n is at lib Y from +7.62 to -10.16 in 2.54 steps;
    # mapped to schem Y = anchor_Y - lib_Y so the top pin sits ABOVE anchor).
    U4_PIN_Y = {
        1:  U4_Y - 7.62,    # 118.11 — LEFT  top    — AN  (NC)
        2:  U4_Y - 5.08,    # 120.65 — LEFT  row 2  — RST (NC)
        3:  U4_Y - 2.54,    # 123.19 — LEFT  row 3  — CS  (NC)
        4:  U4_Y,           # 125.73 — LEFT  row 4  — SCK (NC)
        5:  U4_Y + 2.54,    # 128.27 — LEFT  row 5  — MISO (NC)
        6:  U4_Y + 5.08,    # 130.81 — LEFT  row 6  — MOSI (NC)
        7:  U4_Y + 7.62,    # 133.35 — LEFT  row 7  — +3.3V
        8:  U4_Y + 10.16,   # 135.89 — LEFT  bottom — GND
        9:  U4_Y - 7.62,    # 118.11 — RIGHT top    — PWM (NC)
        10: U4_Y - 5.08,    # 120.65 — RIGHT row 2  — INT (= FD)
        11: U4_Y - 2.54,    # 123.19 — RIGHT row 3  — RX  (NC)
        12: U4_Y,           # 125.73 — RIGHT row 4  — TX  (NC)
        13: U4_Y + 2.54,    # 128.27 — RIGHT row 5  — SCL
        14: U4_Y + 5.08,    # 130.81 — RIGHT row 6  — SDA
        15: U4_Y + 7.62,    # 133.35 — RIGHT row 7  — +5V (NC)
        16: U4_Y + 10.16,   # 135.89 — RIGHT bottom — GND
    }

    # ----- mikroBUS pin 7 (+3.3V, LEFT col): wire WEST to +3V3 flag -----
    PWR_U4P7_3V3_X = U4_LEFT_X - 5.08     # 110.49 — flag anchor west of pin
    parts.append(_sch_wire(U4_LEFT_X, U4_PIN_Y[7], PWR_U4P7_3V3_X, U4_PIN_Y[7], "u4-p7-3v3-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=PWR_U4P7_3V3_X, y=U4_PIN_Y[7], angle=90,
        reference="#PWR50",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr50-3v3-u4-p7",
        sheet_key="sensors",
    ))

    # ----- mikroBUS pin 8 (GND, LEFT col): wire WEST to GND flag -----
    PWR_U4P8_GND_X = U4_LEFT_X - 5.08      # 110.49
    parts.append(_sch_wire(U4_LEFT_X, U4_PIN_Y[8], PWR_U4P8_GND_X, U4_PIN_Y[8], "u4-p8-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_U4P8_GND_X, y=U4_PIN_Y[8], angle=270,
        reference="#PWR51",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr51-gnd-u4-p8",
        sheet_key="sensors",
    ))

    # ----- mikroBUS pin 10 (INT/FD, RIGHT col): wire EAST to NFC_FD hier label -----
    U4_HLABEL_X = HLABEL_LEFT_X                # 160.02 — shared column with J3/J4
    parts.append(_sch_wire(U4_RIGHT_X, U4_PIN_Y[10], U4_HLABEL_X, U4_PIN_Y[10], "u4-p10-fd"))
    parts.append(_sch_hierarchical_label(
        name="NFC_FD", shape="output",
        x=U4_HLABEL_X, y=U4_PIN_Y[10], angle=0, justify="left",
        uuid_tag="nfc-fd-u4",
    ))

    # ----- mikroBUS pin 13 (SCL, RIGHT col): wire EAST to I2C_SCL hier label -----
    parts.append(_sch_wire(U4_RIGHT_X, U4_PIN_Y[13], U4_HLABEL_X, U4_PIN_Y[13], "u4-p13-scl"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SCL", shape="input",
        x=U4_HLABEL_X, y=U4_PIN_Y[13], angle=0, justify="left",
        uuid_tag="scl-u4",
    ))

    # ----- mikroBUS pin 14 (SDA, RIGHT col): wire EAST to I2C_SDA hier label -----
    parts.append(_sch_wire(U4_RIGHT_X, U4_PIN_Y[14], U4_HLABEL_X, U4_PIN_Y[14], "u4-p14-sda"))
    parts.append(_sch_hierarchical_label(
        name="I2C_SDA", shape="bidirectional",
        x=U4_HLABEL_X, y=U4_PIN_Y[14], angle=0, justify="left",
        uuid_tag="sda-u4",
    ))

    # ----- mikroBUS pin 16 (GND, RIGHT col): wire EAST to GND flag -----
    PWR_U4P16_GND_X = U4_RIGHT_X + 5.08    # 133.35
    parts.append(_sch_wire(U4_RIGHT_X, U4_PIN_Y[16], PWR_U4P16_GND_X, U4_PIN_Y[16], "u4-p16-gnd-hop"))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_U4P16_GND_X, y=U4_PIN_Y[16], angle=90,
        reference="#PWR52",
        value_offset_x=3.81, value_offset_y=0.0,
        uuid_tag="pwr52-gnd-u4-p16",
        sheet_key="sensors",
    ))

    # ----- No-connect markers on unused mikroBUS pins (1, 2, 3, 4, 5, 6 left;
    #       9, 11, 12, 15 right). ERC will warn `pin_not_connected` on every
    #       unwired pin unless we silence it with no_connect.
    for n in (1, 2, 3, 4, 5, 6):
        parts.append(_sch_no_connect(U4_LEFT_X, U4_PIN_Y[n], f"u4-nc-{n}"))
    for n in (9, 11, 12, 15):
        parts.append(_sch_no_connect(U4_RIGHT_X, U4_PIN_Y[n], f"u4-nc-{n}"))

    # ===== C12: 100 nF local decoupling on the U4 +3.3V supply =====
    # Sits WEST of U4 between +3V3 (top) and GND (bottom). Anchored
    # vertically so it lines up with the pin 7/8 power flags.
    C12_X = 105.41
    C12_Y = (U4_PIN_Y[7] + U4_PIN_Y[8]) / 2   # mid between pin 7 (+3V3) and pin 8 (GND)
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

    # ===== U4 + C12 symbols =====
    parts.append(_sch_conn_02x08_top_bottom(
        x=U4_X, y=U4_Y, angle=0,
        reference="U4",
        value="MIKROE-2462 NFC Tag 2 Click (NT3H1101 + onboard antenna, mikroBUS)",
        uuid_tag="u4-nfc-tag",
        sheet_key="sensors",
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
    # Pin layout per Normand SK6812 SIDE-A datasheet (verified in
    # hardware/components/sk6812-side.md): 1=DIN, 2=VDD, 3=DOUT, 4=GND.
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
                    "min_clearance": 0.15,
                    "min_connection": 0.0,
                    "min_copper_edge_clearance": 0.3,
                    "min_groove_width": 0.0,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.5,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2,
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
    bodies = [
        _esp32c6_devkitm1_lib_symbol(),
        _sk6812_side_lib_symbol(),
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
            else:
                content = gen_subsheet_sch(name)
        (HERE / f"{name}.kicad_sch").write_text(content, encoding="utf-8")
    (HERE / "oas.kicad_pro").write_text(gen_pro(), encoding="utf-8")
    (HERE / "fp-lib-table").write_text(gen_fp_lib_table(), encoding="utf-8")
    (HERE / "sym-lib-table").write_text(gen_sym_lib_table(), encoding="utf-8")
    (HERE / "libraries").mkdir(parents=True, exist_ok=True)
    (HERE / "libraries" / "OAS.kicad_sym").write_text(
        gen_oas_symbol_library(), encoding="utf-8",
    )

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
