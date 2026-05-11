"""
Generate the KiCad 10 base project for OAS (Open Ambient Sensor).

Produces:
  - oas.kicad_pro       (project; design rules tuned for JLCPCB)
  - oas.kicad_sch       (root schematic, references 4 sub-sheets)
  - power.kicad_sch     (POWER sector — input terminal J1 + power flags)
  - mcu.kicad_sch       (empty sub-sheet — MCU sector)
  - sensors.kicad_sch   (empty sub-sheet — SENSORS sector)
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
from itertools import count
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
# Clock-face sector layout
# -----------------------------------------------------------------------------
# Treat the PCB as a clock face:
#   09:00 → 12:00  (left-top quadrant)   = POWER
#   12:00 → 03:00  (right-top quadrant)  = MCU + logic
#   03:00 → 09:00  (bottom half, 180°)   = SENSORS
# Power flow runs clockwise so signal paths never need to cross sector lines.
# Drawn on Dwgs.User as 3 radial separators + 3 sector labels (not plotted).
SECTOR_LABEL_RADIUS = 28   # mm from centre — where labels sit
SECTOR_LABEL_HEIGHT = 4.0  # mm — text size

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
CUTOUTS = [
    # name, x_min, x_max, y_min, y_max  (PCB-local mm, +Y = toward chord)
    ("C1", -33.800, -21.800, +31.494, +42.498),   # 12 × 11 mm,    fully inside PCB
    ("C2", -16.800,  -1.100, +27.198, +Y_CHORD),  # 15.7 × 19.3 mm, clipped at chord (would extend +3 mm beyond)
    ("C3",  +4.900, +13.900, +28.998, +Y_CHORD),  # 9 × 15.5 mm,   clipped at chord (would extend +1 mm beyond)
    ("C4", +18.900, +22.900, +34.998, +Y_CHORD),  # 4 × 9 mm,      clipped at chord (would extend +0.5 mm; has language tab Ø3 mm in case wall)
    ("C5", +27.900, +35.400, +36.494, +42.494),   # 7.5 × 6 mm,    fully inside PCB
]

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
_uuid_counter = count()

def U(tag: str = "") -> str:
    """Deterministic UUID v5 namespaced under the OAS project.

    Each call increments a per-run counter; combined with the project
    namespace it produces stable UUIDs across regenerations, so
    `python generate.py` is idempotent and git diffs only show real
    geometry changes.
    """
    return str(uuid.uuid5(_OAS_NS, f"{tag}:{next(_uuid_counter)}"))

# Root project + sheet UUIDs (must match between .kicad_pro and .kicad_sch)
# Use a tagged seed so this UUID is stable independent of call order elsewhere.
ROOT_SHEET_UUID = str(uuid.uuid5(_OAS_NS, "sheet:root"))

# Hierarchical sub-sheets — one per PCB sector (see CLAUDE.md):
#   power   ↔ POWER sector   (09:00–12:00)
#   mcu     ↔ MCU sector     (12:00–03:00)
#   sensors ↔ SENSORS sector (03:00–09:00) — VEML7700, LD2410, WS2812, NFC
#   io      ↔ connector cluster along the chord (USB-C, SWD, Qwiic)
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
        \t\t(uuid "{U()}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Value" "MountingHole_3.8mm_M3_NPTH"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U()}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U()}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Datasheet" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U()}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Description" "Mounting Hole, Ø3.8 mm NPTH, for M3 screw (per SZOMK AK-N-94)"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U()}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(COURTYARD_RADIUS)} 0)
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U()}")
        \t)
        \t(fp_circle
        \t\t(center 0 0)
        \t\t(end {fmt(HOLE_DIAMETER/2)} 0)
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U()}")
        \t)
        \t(pad "" np_thru_hole circle
        \t\t(at 0 0)
        \t\t(size {fmt(HOLE_DIAMETER)} {fmt(HOLE_DIAMETER)})
        \t\t(drill {fmt(HOLE_DIAMETER)})
        \t\t(layers "F&B.Cu" "*.Mask")
        \t\t(remove_unused_layers no)
        \t\t(uuid "{U()}")
        \t)
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
            \t\t\t(footprints not_allowed)
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


def gen_sectors() -> str:
    """Return Dwgs.User entities outlining the three PCB sectors.

    The PCB is treated as a clock face:
      09→12  POWER (left-top quadrant)
      12→03  MCU   (right-top quadrant)
      03→09  SENSORS (bottom half, 180°)
    Three radial separators (at 12, 03, 09 o'clock) plus a label per sector.
    """
    def clock_xy(hour: float, radius: float) -> tuple[float, float]:
        """Map clock hour (0..12) and radius to PCB-local (x, y)."""
        angle = math.radians(hour / 12.0 * 360.0)
        return (radius * math.sin(angle), -radius * math.cos(angle))

    items = []
    # Three radial separator lines, each from the cable-hole edge to the PCB outline.
    for hour in (0.0, 3.0, 9.0):
        sx, sy = clock_xy(hour, CABLE_HOLE_DIAMETER / 2 + 0.5)
        ex, ey = clock_xy(hour, R_OUTLINE - 0.5)
        items.append(textwrap.dedent(f"""\
            \t(gr_line
            \t\t(start {fx(sx)} {fy(sy)})
            \t\t(end {fx(ex)} {fy(ey)})
            \t\t(stroke (width 0.15) (type dash))
            \t\t(layer "Dwgs.User")
            \t\t(uuid "{U('sector_line:'+str(hour))}")
            \t)"""))

    # Sector labels at the middle of each arc segment.
    for hour, name in [(10.5, "POWER"), (1.5, "MCU"), (6.0, "SENSORS")]:
        cx, cy = clock_xy(hour, SECTOR_LABEL_RADIUS)
        items.append(textwrap.dedent(f"""\
            \t(gr_text "{name}"
            \t\t(at {fx(cx)} {fy(cy)} 0)
            \t\t(layer "Dwgs.User")
            \t\t(uuid "{U('sector_label:'+name)}")
            \t\t(effects
            \t\t\t(font (size {fmt(SECTOR_LABEL_HEIGHT)} {fmt(SECTOR_LABEL_HEIGHT)}) (thickness 0.4))
            \t\t)
            \t)"""))

    return "\n".join(items)


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
            \t\t(uuid "{U()}")
            \t\t(at {fx(x)} {fy(y)})
            \t\t(descr "M3 mounting hole NPTH, Ø3.8 mm per SZOMK AK-N-94 spec")
            \t\t(attr through_hole board_only exclude_from_pos_files exclude_from_bom)
            \t\t(property "Reference" "{ref}"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.SilkS")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U()}")
            \t\t\t(effects (font (size 1 1) (thickness 0.15)))
            \t\t)
            \t\t(property "Value" "MountingHole_3.8mm_M3_NPTH"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U()}")
            \t\t\t(effects (font (size 1 1) (thickness 0.15)))
            \t\t)
            \t\t(property "Footprint" "oas:MountingHole_3.8mm_M3"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U()}")
            \t\t\t(effects (font (size 1.27 1.27)))
            \t\t)
            \t\t(property "Datasheet" ""
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U()}")
            \t\t\t(effects (font (size 1.27 1.27)))
            \t\t)
            \t\t(property "Description" "Mounting Hole, Ø3.8 mm NPTH, for M3 screw (per SZOMK AK-N-94)"
            \t\t\t(at 0 0 0)
            \t\t\t(layer "F.Fab")
            \t\t\t(hide yes)
            \t\t\t(uuid "{U()}")
            \t\t\t(effects (font (size 1.27 1.27)))
            \t\t)
            \t\t(fp_circle
            \t\t\t(center 0 0)
            \t\t\t(end {fmt(COURTYARD_RADIUS)} 0)
            \t\t\t(stroke (width 0.05) (type solid))
            \t\t\t(fill no)
            \t\t\t(layer "F.CrtYd")
            \t\t\t(uuid "{U()}")
            \t\t)
            \t\t(fp_circle
            \t\t\t(center 0 0)
            \t\t\t(end {fmt(HOLE_DIAMETER/2)} 0)
            \t\t\t(stroke (width 0.1) (type solid))
            \t\t\t(fill no)
            \t\t\t(layer "F.Fab")
            \t\t\t(uuid "{U()}")
            \t\t)
            \t\t(pad "" np_thru_hole circle
            \t\t\t(at 0 0)
            \t\t\t(size {fmt(HOLE_DIAMETER)} {fmt(HOLE_DIAMETER)})
            \t\t\t(drill {fmt(HOLE_DIAMETER)})
            \t\t\t(layers "F&B.Cu" "*.Mask")
            \t\t\t(remove_unused_layers no)
            \t\t\t(uuid "{U()}")
            \t\t)
            \t)""")
        footprints.append(fp)

    keepouts, markers = gen_cutouts()
    sectors = gen_sectors()

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
        """) + sectors + "\n" + markers + "\n" + "\n".join(footprints) + "\n" + keepouts + "\n)\n"
    return body

# -----------------------------------------------------------------------------
# 3) Hierarchical schematic — root + 4 empty per-sector sub-sheets
# -----------------------------------------------------------------------------
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
    return textwrap.dedent(f"""\
        \t(sheet
        \t\t(at {fmt(x)} {fmt(y)})
        \t\t(size {fmt(sx)} {fmt(sy)})
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(stroke
        \t\t\t(width 0.1524)
        \t\t\t(type solid)
        \t\t)
        \t\t(fill
        \t\t\t(color 0 0 0 0.0000)
        \t\t)
        \t\t(uuid "{block_uuid}")
        \t\t(property "Sheetname" "{display}"
        \t\t\t(at {fmt(x)} {fmt(name_y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left bottom)
        \t\t\t)
        \t\t)
        \t\t(property "Sheetfile" "{name}.kicad_sch"
        \t\t\t(at {fmt(x)} {fmt(file_y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left top)
        \t\t\t)
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "/{ROOT_SHEET_UUID}"
        \t\t\t\t\t(page "{page}")
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)""")


def gen_root_sch() -> str:
    """Root schematic referencing the 4 per-sector sub-sheets.

    Contains no symbols of its own — only (sheet ...) blocks that point
    to power.kicad_sch / mcu.kicad_sch / sensors.kicad_sch / io.kicad_sch.
    """
    sheet_blocks = "\n".join(
        _gen_sheet_block(name, page)
        for page, name in enumerate(SUBSHEETS, start=2)
    )
    return textwrap.dedent(f"""\
        (kicad_sch
        \t(version {SCH_VERSION})
        \t(generator "eeschema")
        \t(generator_version "{GEN_VERSION}")
        \t(uuid "{ROOT_SHEET_UUID}")
        \t(paper "A4")
        \t(lib_symbols
        \t)
        """) + sheet_blocks + textwrap.dedent("""
        \t(sheet_instances
        \t\t(path "/"
        \t\t\t(page "1")
        \t\t)
        \t)
        \t(embedded_fonts no)
        )
        """)


def gen_subsheet_sch(name: str) -> str:
    """Empty per-sector sub-sheet (just the file header + empty lib_symbols).

    Placeholder for upcoming per-sector content (chunks #1b onward).
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
) -> str:
    """Emit a power-symbol instance (+24V / GND / Earth_Protective / PWR_FLAG).

    `value_offset_x/y` give the Value-label position relative to (x, y) in
    schematic mm — chosen empirically per symbol so the visible label
    matches the symbol's default placement convention.
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuid = U("sym-pin:" + uuid_tag)
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
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
) -> str:
    """Emit a resistor (Device:R) symbol instance.

    With angle=0, lib pin positions map to schematic as:
      Pin 1 (top):    (x, y - 3.81)
      Pin 2 (bottom): (x, y + 3.81)
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin1_uuid = U("sym-pin:" + uuid_tag + "-1")
    pin2_uuid = U("sym-pin:" + uuid_tag + "-2")
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"
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


def gen_power_sch() -> str:
    """Power sub-sheet — J1 input terminal + reverse-polarity protection (Q1, R1).

    Layout (page-absolute mm, KiCad +Y is down on screen):

        +24V@(91.44, 76.2)               GND@(78.74, 104.14)   Earth_Protective@(83.82, 106.68)
            |                                  |                       |
        PWR_FLAG@(91.44, 81.28)             PWR_FLAG@               PWR_FLAG@
        (rot 0, flag graphic up)            (78.74, 99.06)          (83.82, 101.6)
            |                                  |                       |
            ─── Q1.D ─── Q1 PMOS ─── Q1.S ─── J1.1 (96.52, 93.98)
        Q1.G@(83.82, 88.9)                  J1.2 (96.52, 96.52)    J1.3 (96.52, 99.06)
            |
            └─ R1.top (73.66, 91.44)
               R1 100k pulldown
               R1.bot (73.66, 99.06)
                  |
               GND@(73.66, 101.6)

    The reverse-polarity P-MOSFET Q1 (AO3415A) sits between J1.1 and the
    protected +24V rail. Source = unprotected input (J1.1), Drain = +24V.
    R1 (100 kΩ) pulls Q1.gate to GND so Vgs ≈ -24 V turns the channel on
    when polarity is correct.

    J1 itself sits at (101.6, 96.52). For each pin (GND, PE) a horizontal
    wire goes LEFT to its own per-net column, then a vertical wire to the
    flag's anchor point; a junction marks the PWR_FLAG sentinel tap-off.
    +24V is on Q1.D instead of J1.1, so the +24V flag column is at Q1.D's
    x position (91.44).
    """
    file_uuid = SHEET_FILE_UUIDS["power"]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"

    # J1 placement and pin Y coordinates.
    J1_X = 101.6
    J1_Y = 96.52
    PIN1_Y = J1_Y - 2.54     # 93.98 — +24V (unprotected, local to J1.1 -> Q1.S)
    PIN2_Y = J1_Y            # 96.52 — GND
    PIN3_Y = J1_Y + 2.54     # 99.06 — PE
    PIN_X  = J1_X - 5.08     # 96.52 — pin tips on J1 symbol's left side

    # Q1 placement (P-MOSFET, body centred at this point, angle=0).
    # With angle=0 the lib +y axis maps to schematic -y, so pin schematic
    # positions are:  D = (Q1_X+2.54, Q1_Y-5.08), G = (Q1_X-5.08, Q1_Y),
    # S = (Q1_X+2.54, Q1_Y+5.08).
    Q1_X = 88.9
    Q1_Y = 88.9
    Q1_D_X = Q1_X + 2.54     # 91.44
    Q1_D_Y = Q1_Y - 5.08     # 83.82
    Q1_G_X = Q1_X - 5.08     # 83.82
    Q1_G_Y = Q1_Y            # 88.9
    Q1_S_X = Q1_X + 2.54     # 91.44
    Q1_S_Y = Q1_Y + 5.08     # 93.98  — matches PIN1_Y; same horizontal row as J1.1

    # R1 placement (100k pulldown, angle=0).
    # Pin 1 (top) = (R1_X, R1_Y-3.81), pin 2 (bottom) = (R1_X, R1_Y+3.81).
    R1_X = 73.66
    R1_Y = 95.25
    R1_TOP_Y = R1_Y - 3.81   # 91.44
    R1_BOT_Y = R1_Y + 3.81   # 99.06

    # Per-net column X for the flag stacks.
    COL_24V = Q1_D_X         # 91.44 — protected rail lives on Q1.D wire
    COL_GND = 78.74
    COL_PE  = 83.82
    COL_R1_GND = R1_X        # 73.66 — second GND symbol for R1.bottom

    # Y coordinates for each flag / PWR_FLAG sentinel pair.
    # Spacing FLAG-to-PWR_FLAG is 5.08 mm (Part A cosmetic fix — was 2.54,
    # which left the symbols' value-text labels overlapping in eeschema).
    JUNC_24V_Y = 81.28       # PWR_FLAG sentinel + junction on Q1.D wire
    FLAG_24V_Y = 76.2        # +24V triangle, 5.08 mm further from Q1.D
    JUNC_GND_Y = 99.06       # PWR_FLAG sentinel on GND column (below J1.2)
    FLAG_GND_Y = 104.14      # GND symbol, 5.08 mm below PWR_FLAG
    JUNC_PE_Y  = 101.6       # PWR_FLAG sentinel on PE column (below J1.3)
    FLAG_PE_Y  = 106.68      # PE symbol, 5.08 mm below PWR_FLAG

    parts: list[str] = []

    # ----- Wires -----
    # J1.1 (unprotected) -> Q1.S: short horizontal hop, no flag, local net.
    parts.append(_sch_wire(PIN_X, PIN1_Y, Q1_S_X, Q1_S_Y, "vin-horiz"))

    # Q1.D -> +24V flag column: vertical, with a junction at PWR_FLAG height
    # so the sentinel can tap off without an extra branch wire.
    parts.append(_sch_wire(Q1_D_X, Q1_D_Y, COL_24V, JUNC_24V_Y, "24v-vert-low"))
    parts.append(_sch_wire(COL_24V, JUNC_24V_Y, COL_24V, FLAG_24V_Y, "24v-vert-high"))

    # Q1.G -> R1.top: horizontal then vertical (simple L-bend, no junction).
    parts.append(_sch_wire(Q1_G_X, Q1_G_Y, R1_X, Q1_G_Y, "q1g-horiz"))
    parts.append(_sch_wire(R1_X, Q1_G_Y, R1_X, R1_TOP_Y, "q1g-vert"))

    # R1.bottom -> dedicated GND symbol (shares the GND global net).
    parts.append(_sch_wire(R1_X, R1_BOT_Y, COL_R1_GND, 101.6, "r1gnd-vert"))

    # GND row (J1.2 -> column 78.74 -> flag below)
    parts.append(_sch_wire(PIN_X, PIN2_Y, COL_GND, PIN2_Y, "gnd-horiz"))
    parts.append(_sch_wire(COL_GND, PIN2_Y, COL_GND, JUNC_GND_Y, "gnd-vert-high"))
    parts.append(_sch_wire(COL_GND, JUNC_GND_Y, COL_GND, FLAG_GND_Y, "gnd-vert-low"))

    # PE row (J1.3 -> column 83.82 -> flag below)
    parts.append(_sch_wire(PIN_X, PIN3_Y, COL_PE, PIN3_Y, "pe-horiz"))
    parts.append(_sch_wire(COL_PE, PIN3_Y, COL_PE, JUNC_PE_Y, "pe-vert-high"))
    parts.append(_sch_wire(COL_PE, JUNC_PE_Y, COL_PE, FLAG_PE_Y, "pe-vert-low"))

    # ----- Junctions (T-branch points where PWR_FLAG joins the column wire) -----
    parts.append(_sch_junction(COL_24V, JUNC_24V_Y, "24v"))
    parts.append(_sch_junction(COL_GND, JUNC_GND_Y, "gnd"))
    parts.append(_sch_junction(COL_PE,  JUNC_PE_Y,  "pe"))

    # ----- J1 symbol (Phoenix MSTBA 2,5/3-G-5,08, 5.08 mm pitch) -----
    j1_uuid = U("sym:j1")
    j1_pin1_uuid = U("sym-pin:j1-1")
    j1_pin2_uuid = U("sym-pin:j1-2")
    j1_pin3_uuid = U("sym-pin:j1-3")
    parts.append(textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector:Screw_Terminal_01x03")
        \t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{j1_uuid}")
        \t\t(property "Reference" "J1"
        \t\t\t(at {fmt(J1_X + 2.54)} {fmt(J1_Y - 7.62)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "Phoenix_MSTBA_2,5/3-G-5,08"
        \t\t\t(at {fmt(J1_X + 2.54)} {fmt(J1_Y - 5.08)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" ""
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" ""
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" ""
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

    # ----- Q1: P-MOSFET reverse-polarity protection (AO3415A) -----
    # Source = J1.1 (unprotected input), Drain = +24V (protected rail).
    # When input polarity is correct, the body diode conducts initially, then
    # R1 pulls the gate to GND -> Vgs ~ -24 V turns the channel fully on,
    # shorting out the body diode for low conduction loss.
    parts.append(_sch_q_pmos(
        x=Q1_X, y=Q1_Y, angle=0,
        reference="Q1", value="AO3415A", uuid_tag="q1",
    ))

    # ----- R1: 100 kΩ gate-GND pulldown -----
    parts.append(_sch_resistor(
        x=R1_X, y=R1_Y, angle=0,
        reference="R1", value="100k", uuid_tag="r1",
    ))

    # ----- Power flag symbols (+24V, GND, Earth_Protective, R1-side GND) -----
    parts.append(_sch_power_flag(
        lib_id="power:+24V", value="+24V",
        x=COL_24V, y=FLAG_24V_Y, angle=0,
        reference="#PWR01",
        value_offset_x=0.0, value_offset_y=-2.54,   # label above the triangle
        uuid_tag="pwr01-24v",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_GND, y=FLAG_GND_Y, angle=0,
        reference="#PWR02",
        value_offset_x=0.0, value_offset_y=3.81,    # label below the symbol
        uuid_tag="pwr02-gnd",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:Earth_Protective", value="Earth_Protective",
        x=COL_PE, y=FLAG_PE_Y, angle=0,
        reference="#PWR03",
        value_offset_x=0.0, value_offset_y=7.62,    # label below the Ø2.54 circle
        uuid_tag="pwr03-pe",
    ))
    # GND for R1.bottom — same net as #PWR02 via the global power label.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_R1_GND, y=101.6, angle=0,
        reference="#PWR04",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr04-gnd-r1",
    ))

    # ----- PWR_FLAG sentinels (one per power net: +24V, GND, PE) -----
    # On the +24V net the PWR_FLAG sentinel sits on Q1.D's vertical wire
    # at JUNC_24V_Y. With angle 0 the flag graphic extends UP (toward the
    # +24V triangle above it).
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_24V, y=JUNC_24V_Y, angle=0,
        reference="#FLG01",
        value_offset_x=0.0, value_offset_y=-3.81,
        uuid_tag="flg01-24v",
    ))
    # GND and PE: PWR_FLAG rotated 180° so its graphic extends DOWN toward
    # the flag symbol (which is below the pin row on screen).
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_GND, y=JUNC_GND_Y, angle=180,
        reference="#FLG02",
        value_offset_x=0.0, value_offset_y=-3.81,
        uuid_tag="flg02-gnd",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_PE, y=JUNC_PE_Y, angle=180,
        reference="#FLG03",
        value_offset_x=0.0, value_offset_y=-3.81,
        uuid_tag="flg03-pe",
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
    return textwrap.dedent("""\
        (sym_lib_table
        \t(version 7)
        )
        """)

# -----------------------------------------------------------------------------
# Write everything
# -----------------------------------------------------------------------------
def main():
    (HERE / "libraries" / "oas.pretty").mkdir(parents=True, exist_ok=True)

    (HERE / "libraries" / "oas.pretty" / "MountingHole_3.8mm_M3.kicad_mod").write_text(
        gen_mounting_hole_footprint(), encoding="utf-8"
    )
    (HERE / "oas.kicad_pcb").write_text(gen_pcb(), encoding="utf-8")
    (HERE / "oas.kicad_sch").write_text(gen_root_sch(), encoding="utf-8")
    for name in SUBSHEETS:
        if name == "power":
            content = gen_power_sch()
        else:
            content = gen_subsheet_sch(name)
        (HERE / f"{name}.kicad_sch").write_text(content, encoding="utf-8")
    (HERE / "oas.kicad_pro").write_text(gen_pro(), encoding="utf-8")
    (HERE / "fp-lib-table").write_text(gen_fp_lib_table(), encoding="utf-8")
    (HERE / "sym-lib-table").write_text(gen_sym_lib_table(), encoding="utf-8")

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
        "libraries/oas.pretty/MountingHole_3.8mm_M3.kicad_mod",
    ]:
        full = HERE / p
        print(f"  {p}  ({full.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
