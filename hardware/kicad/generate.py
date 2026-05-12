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
        ("UART_TX",     "output",        38.1, 1.27, 0),
        ("UART_RX",     "input",         38.1, 3.81, 0),
    ],
    "sensors": [],
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
    # SuperMini (via its 3V3 pin, bypassing the module's onboard LDO so we
    # don't dissipate ~250 mW close to the SEN66 air-quality sensor), plus
    # the SEN66 itself, VEML7700 ambient light sensor, and NT3H2211 NFC tag.
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
    #                  3.0-3.6 V supply requirements of SEN66, VEML7700,
    #                  NT3H2211. R3 = 10 kΩ gives a low-current divider
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
# 3c) MCU sub-sheet — ESP32-C6 SuperMini (U3) + local decoupling + recovery header
# -----------------------------------------------------------------------------
# Embedded lib_symbols for the MCU sub-sheet. Self-contained: each sub-sheet
# carries its own copy of the symbols it uses (the +3V3 / GND and Device:C /
# Device:C_Polarized blocks are intentionally duplicated with POWER_LIB_SYMBOLS
# so the .kicad_sch file opens identically on any machine).
#
# Symbol sources:
#   - "OAS:ESP32-C6_SuperMini" : own work, defined inline below. Models a 2×8
#     SIP header (16-pin) ESP32-C6 SuperMini module — the most common
#     small-form-factor variant. Reference pinout cross-checked against the
#     community pinout at https://www.espboards.dev/esp32/esp32-c6-super-mini/.
#     Only the GPIOs actually used by OAS plus a few representative unused
#     GPIOs are exposed; this is sufficient for the schematic because the
#     module is hand-soldered onto the PCB as a daughter-board (the underlying
#     ESP32-C6 chip itself is encapsulated by the SuperMini's onboard hardware).
#   - "Connector_Generic:Conn_01x06" : copied verbatim from KiCad 10's stock
#     Connector_Generic.kicad_sym (GPL).
#   - "Device:C", "Device:C_Polarized", "power:+3V3", "power:GND" : copied
#     verbatim from KiCad 10's stock libraries (GPL).
MCU_LIB_SYMBOLS = """\
\t\t(symbol "OAS:ESP32-C6_SuperMini"
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 12.7 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "ESP32-C6_SuperMini"
\t\t\t\t(at 0 -12.7 0)
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
\t\t\t(property "Datasheet" "https://www.espboards.dev/esp32/esp32-c6-super-mini/"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "ESP32-C6 SuperMini module (2x8 SIP, ~22mm spacing). WiFi 6, BLE 5.3, Zigbee/Thread, onboard USB-C, onboard WS2812 on GPIO 8."
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "ki_keywords" "esp32-c6 supermini wifi ble"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "ESP32-C6_SuperMini_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -10.16 -10.16)
\t\t\t\t\t(end 10.16 10.16)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type background)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "ESP32-C6_SuperMini_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at -12.7 8.89 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "5V"
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
\t\t\t\t\t(at -12.7 6.35 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GND"
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
\t\t\t\t\t(at -12.7 3.81 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "3V3"
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
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at -12.7 1.27 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO6"
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
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at -12.7 -1.27 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO7"
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
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at -12.7 -3.81 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO8"
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
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at -12.7 -6.35 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO10"
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
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at -12.7 -8.89 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO11"
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
\t\t\t\t(pin input line
\t\t\t\t\t(at 12.7 8.89 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "EN"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "9"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 6.35 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO9"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "10"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 3.81 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO16"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "11"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 1.27 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO17"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "12"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 -1.27 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO18"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "13"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 -3.81 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO19"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "14"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 -6.35 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO20"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "15"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin bidirectional line
\t\t\t\t\t(at 12.7 -8.89 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GPIO21"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "16"
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


def _sch_esp32c6_supermini(
    x: float, y: float, reference: str, value: str, uuid_tag: str,
) -> str:
    """Emit an ESP32-C6 SuperMini (OAS:ESP32-C6_SuperMini) symbol instance.

    16 pins total in a 2×8 SIP layout. With angle=0 (no rotation), lib pin
    positions map to schematic as:
      Left side (pins 1-8, X = anchor_x - 12.7):
        Pin 1 (5V):    (X-12.7, Y-8.89)
        Pin 2 (GND):   (X-12.7, Y-6.35)
        Pin 3 (3V3):   (X-12.7, Y-3.81)
        Pin 4 (GPIO6): (X-12.7, Y-1.27)
        Pin 5 (GPIO7): (X-12.7, Y+1.27)
        Pin 6 (GPIO8): (X-12.7, Y+3.81)
        Pin 7 (GPIO10):(X-12.7, Y+6.35)
        Pin 8 (GPIO11):(X-12.7, Y+8.89)
      Right side (pins 9-16, X = anchor_x + 12.7):
        Pin 9  (EN):    (X+12.7, Y-8.89)
        Pin 10 (GPIO9): (X+12.7, Y-6.35)
        Pin 11 (GPIO16):(X+12.7, Y-3.81)
        Pin 12 (GPIO17):(X+12.7, Y-1.27)
        Pin 13 (GPIO18):(X+12.7, Y+1.27)
        Pin 14 (GPIO19):(X+12.7, Y+3.81)
        Pin 15 (GPIO20):(X+12.7, Y+6.35)
        Pin 16 (GPIO21):(X+12.7, Y+8.89)
    Body rectangle in schem: (X-10.16, Y-10.16) to (X+10.16, Y+10.16).
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 17)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['mcu']}"
    pin_blocks = "\n".join(
        f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{pin_uuids[n-1]}\")\n\t\t)"
        for n in range(1, 17)
    )
    return textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "OAS:ESP32-C6_SuperMini")
        \t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{sym_uuid}")
        \t\t(property "Reference" "{reference}"
        \t\t\t(at {fmt(x + 13.97)} {fmt(y - 12.7)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify left)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "{value}"
        \t\t\t(at {fmt(x + 13.97)} {fmt(y - 15.24)} 0)
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
        \t\t(property "Datasheet" "https://www.espboards.dev/esp32/esp32-c6-super-mini/"
        \t\t\t(at {fmt(x)} {fmt(y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" "ESP32-C6 SuperMini module (manual-mount daughter board)"
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


def _sch_conn_01x06(
    x: float, y: float, angle: int, reference: str, value: str, uuid_tag: str,
    dnp: bool = False,
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
    """
    sym_uuid = U("sym:" + uuid_tag)
    pin_uuids = [U(f"sym-pin:{uuid_tag}-{n}") for n in range(1, 7)]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['mcu']}"
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


def gen_mcu_sch() -> str:
    """MCU sub-sheet — ESP32-C6 SuperMini (U3) + C9/C9b decoupling + J2 recovery header.

    Layout (schematic page-absolute mm, KiCad +Y is down on screen):

      +3V3 rail (Y=76.20) ------------------------ +3V3 PWR -----
                |                |              |
                C9 (10uF/+)      C9b (100nF)    | (drop right and down)
                |  pin 2 (bot)   |  pin 2 (bot) |
                GND              GND            |
                                                |
                                                |     U3.3 (3V3)
                                                +-- L-route ------- pin 3 left

      Top-right of the U3 body (at 152.4, 110), the J2 header sits at
      (200, 101.11) just to its right, with pins exiting LEFT toward U3.
      The four signal pins (J2.3-6) align Y-row-by-row with U3.9-12 so
      every recovery-header wire is a clean horizontal hop.

      Left-edge hierarchical labels (X=120) carry the sensor-bound nets:
      I2C_SDA, I2C_SCL, LD2410_OUT, NFC_FD.  Right-side hierarchical
      labels (X=222) carry UART_TX / UART_RX (T-tapped on the wires that
      already run from U3 right pins to J2).

    Pinout (per v0.3 ARCHITECTURE.md, post strap-pin validation):
      U3.1  5V          (NO-CONNECT — VBUS not used outside the SuperMini)
      U3.2  GND
      U3.3  3V3
      U3.4  GPIO 6     → I2C_SDA      (shared bus: SEN66, VEML7700, NT3H2211)
      U3.5  GPIO 7     → I2C_SCL
      U3.6  GPIO 8     (NO-CONNECT — onboard WS2812 on SuperMini, no ext. LED)
      U3.7  GPIO 10    → LD2410_OUT   (presence interrupt; was GPIO 4 = MTMS strap)
      U3.8  GPIO 11    → NFC_FD       (NT3H2211 FD; was GPIO 5 = MTDI strap)
      U3.9  EN         → J2.3         (reset / recovery)
      U3.10 GPIO 9     → J2.4         (boot-mode strap; recovery header only)
      U3.11 GPIO 16    → UART_TX (→J2.5)  (256000 baud to LD2410 RX)
      U3.12 GPIO 17    → UART_RX (←J2.6)  (256000 baud from LD2410 TX)
      U3.13-16 GPIO 18-21   (NO-CONNECT — reserved for future expansion)

    Inter-sheet nets exported via hierarchical_label (matching sheet ports
    are added to oas.kicad_sch's MCU sheet block):
      I2C_SDA, I2C_SCL    → sensors sub-sheet (chunk #5)
      UART_TX, UART_RX    → sensors sub-sheet (LD2410)
      LD2410_OUT          → sensors sub-sheet
      NFC_FD              → sensors sub-sheet

    +3V3 and GND are NOT exported as hierarchical labels: the power
    section already declared them via global power symbols, which is
    KiCad's canonical mechanism for spanning power nets across hierarchy.
    Adding hier labels for them would produce "multiple net names on the
    same net" ERC noise without any electrical benefit.
    """
    file_uuid = SHEET_FILE_UUIDS["mcu"]

    # ===== U3: ESP32-C6 SuperMini module =====
    # All coordinates on the 1.27 mm (50 mil) KiCad connection grid:
    # X-values are multiples of 1.27 (column index in the comment), Y-values
    # likewise (row index). U3 anchor (152.4, 110.49) = column 120, row 87.
    U3_X = 152.40           # column 120 (= 120 * 1.27)
    U3_Y = 110.49           # row 87
    # Pin tip schem positions, derived from the symbol's lib pin coords.
    # Left side: lib X=-12.7, pins at lib Y in {+8.89, +6.35, ..., -8.89}.
    # At angle=0, lib (Xl, Yl) maps to schem (X+Xl, Y-Yl).
    U3_X_LEFT  = U3_X - 12.7    # 139.70 — column 110
    U3_X_RIGHT = U3_X + 12.7    # 165.10 — column 130
    # Pin Y rows (8 rows, 2.54 mm pitch, 5.08 mm offset for top pin)
    PIN_Y = [
        U3_Y - 8.89,   # row 0 — 101.60 — pin 1 / 9
        U3_Y - 6.35,   # row 1 — 104.14 — pin 2 / 10
        U3_Y - 3.81,   # row 2 — 106.68 — pin 3 / 11
        U3_Y - 1.27,   # row 3 — 109.22 — pin 4 / 12
        U3_Y + 1.27,   # row 4 — 111.76 — pin 5 / 13
        U3_Y + 3.81,   # row 5 — 114.30 — pin 6 / 14
        U3_Y + 6.35,   # row 6 — 116.84 — pin 7 / 15
        U3_Y + 8.89,   # row 7 — 119.38 — pin 8 / 16
    ]
    # Aliases for the rows we care about (matches the comment table above).
    U3_5V_Y    = PIN_Y[0]   # 101.60 — pin 1
    U3_GND_Y   = PIN_Y[1]   # 104.14 — pin 2
    U3_3V3_Y   = PIN_Y[2]   # 106.68 — pin 3
    U3_SDA_Y   = PIN_Y[3]   # 109.22 — pin 4 (GPIO6)
    U3_SCL_Y   = PIN_Y[4]   # 111.76 — pin 5 (GPIO7)
    U3_LED_Y   = PIN_Y[5]   # 114.30 — pin 6 (GPIO8, onboard WS2812)
    U3_LDR_Y   = PIN_Y[6]   # 116.84 — pin 7 (GPIO10 LD2410_OUT)
    U3_NFC_Y   = PIN_Y[7]   # 119.38 — pin 8 (GPIO11 NFC_FD)
    U3_EN_Y    = PIN_Y[0]   # 101.60 — pin 9 (EN)
    U3_BOOT_Y  = PIN_Y[1]   # 104.14 — pin 10 (GPIO9)
    U3_TX_Y    = PIN_Y[2]   # 106.68 — pin 11 (GPIO16)
    U3_RX_Y    = PIN_Y[3]   # 109.22 — pin 12 (GPIO17)
    # Pins 13-16 (GPIO18-21) all no-connect; addressed via PIN_Y[4..7]
    # at X=U3_X_RIGHT.

    # ===== C9: bulk decoupling, 10uF polarized =====
    C9_X = 129.54            # column 102
    C9_Y = 80.01             # row 63
    C9_TOP_Y = C9_Y - 3.81   # 76.20 — pin 1 (anode +) on the +3V3 bus
    C9_BOT_Y = C9_Y + 3.81   # 83.82 — pin 2 (cathode -) drops to GND
    C9_GND_Y = 87.63         # row 69 — local GND symbol anchor

    # ===== C9b: HF decoupling, 100nF ceramic =====
    C9b_X = 138.43           # column 109 (just left of U3 body left edge X=142.24)
    C9b_Y = 80.01
    C9b_TOP_Y = C9b_Y - 3.81 # 76.20 — pin 1 on the +3V3 bus
    C9b_BOT_Y = C9b_Y + 3.81 # 83.82
    C9b_GND_Y = 87.63

    # ===== +3V3 bus =====
    # Horizontal at Y=76.20 from C9.pin1 (X=129.54) through C9b.pin1
    # (X=138.43) east to an L-corner at X=140.97 (one grid step right of
    # C9b, still 1.27 mm left of U3 body left edge X=142.24). The bus
    # then drops south to U3.3 row (Y=106.68) and runs east into U3.3.
    BUS_3V3_Y       = C9_TOP_Y     # 76.20
    BUS_3V3_X_LEFT  = C9_X         # 129.54
    BUS_3V3_X_RIGHT = 140.97       # column 111 — L-corner
    PWR_3V3_X       = 134.62       # column 106 — between C9 and C9b
    PWR_3V3_Y       = BUS_3V3_Y    # power symbol anchor sits on the bus

    # ===== J2: SWD/UART recovery header, 6-pin, DNP =====
    # Anchor Y chosen so J2.3 (= U3.9 row, EN) aligns with U3.9 at Y=101.60.
    # Conn_01x06 pin 3 lib Y=0 maps to schem Y=anchor_y. So anchor_y = 101.60.
    # J2 placed to the right of U3 so its left-facing pins connect via
    # short horizontal wires to U3's right pins. The four signal pins
    # (J2.3-J2.6) align row-by-row with U3.9-U3.12.
    J2_X = 199.39            # column 157
    J2_Y = U3_EN_Y           # 101.60
    J2_PIN_X = J2_X - 5.08   # 194.31 — pin tip column (all 6 pins)
    J2_P1_Y = J2_Y - 5.08    # 96.52  — 3V3
    J2_P2_Y = J2_Y - 2.54    # 99.06  — GND
    J2_P3_Y = J2_Y           # 101.60 — EN (← U3.9)
    J2_P4_Y = J2_Y + 2.54    # 104.14 — GPIO 9 BOOT (← U3.10)
    J2_P5_Y = J2_Y + 5.08    # 106.68 — UART_TX (← U3.11)
    J2_P6_Y = J2_Y + 7.62    # 109.22 — UART_RX (← U3.12)

    # ===== Hier-label columns =====
    # All hier labels for sensor-bound nets on LEFT side at X=119.38 (signals
    # flow OUT of MCU to the LEFT, since the sensors sheet is bottom-LEFT
    # in the root sheet layout).
    HLABEL_LEFT_X = 119.38   # column 94
    # UART hier labels on the RIGHT, between J2 body and the right margin,
    # T-tapping the existing U3→J2 wires.
    HLABEL_RIGHT_X = 222.25  # column 175

    # ===== Wires =====
    parts: list[str] = []

    # ---- +3V3 wiring ----
    # +3V3 bus: horizontal from C9.pin1 at X=129.54 east to the L-corner at
    # X=140.97, then south to U3.3 row at Y=106.68, then east to U3.3 pin
    # tip at (139.70, 106.68). The downward leg sits in the 1.27 mm gap
    # between C9b (X=138.43) and the U3 body left edge (X=142.24).
    parts.append(_sch_wire(BUS_3V3_X_LEFT, BUS_3V3_Y, BUS_3V3_X_RIGHT, BUS_3V3_Y, "3v3-bus"))
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, BUS_3V3_Y, BUS_3V3_X_RIGHT, U3_3V3_Y, "3v3-bus-down"))
    parts.append(_sch_wire(BUS_3V3_X_RIGHT, U3_3V3_Y, U3_X_LEFT, U3_3V3_Y, "3v3-to-u3"))
    # Junction dots at the two mid-wire taps on the +3V3 bus:
    #   - (PWR_3V3_X, BUS_3V3_Y) where the +3V3 power-symbol pin lands.
    #   - (C9b_X, BUS_3V3_Y) where C9b pin 1 lands.
    parts.append(_sch_junction(PWR_3V3_X, BUS_3V3_Y, "3v3-bus-tap-pwr"))
    parts.append(_sch_junction(C9b_X, BUS_3V3_Y, "3v3-bus-tap-c9b"))
    # C9.pin2 → local GND symbol
    parts.append(_sch_wire(C9_X, C9_BOT_Y, C9_X, C9_GND_Y, "c9-to-gnd"))
    # C9b.pin2 → local GND symbol
    parts.append(_sch_wire(C9b_X, C9b_BOT_Y, C9b_X, C9b_GND_Y, "c9b-to-gnd"))

    # ---- U3.2 (GND) → local GND symbol on the LEFT ----
    # Short horizontal hop out of U3.2 to a GND power symbol just to the
    # left of the pin tip. The U3_GND symbol is placed inside the same
    # 2.54mm grid as the pin so the GND value-text doesn't overlap U3.
    U3_GND_X = U3_X_LEFT - 3.81   # 135.89 (column 107) — GND symbol anchor
    parts.append(_sch_wire(U3_X_LEFT, U3_GND_Y, U3_GND_X, U3_GND_Y, "u3gnd-hop"))

    # ---- I2C / interrupt signal wires (U3 left pins → left hier labels) ----
    # GPIO 6 (SDA), GPIO 7 (SCL), GPIO 10 (LD2410_OUT), GPIO 11 (NFC_FD)
    parts.append(_sch_wire(U3_X_LEFT, U3_SDA_Y, HLABEL_LEFT_X, U3_SDA_Y, "sda-wire"))
    parts.append(_sch_wire(U3_X_LEFT, U3_SCL_Y, HLABEL_LEFT_X, U3_SCL_Y, "scl-wire"))
    parts.append(_sch_wire(U3_X_LEFT, U3_LDR_Y, HLABEL_LEFT_X, U3_LDR_Y, "ldr-wire"))
    parts.append(_sch_wire(U3_X_LEFT, U3_NFC_Y, HLABEL_LEFT_X, U3_NFC_Y, "nfc-wire"))

    # ---- U3 right pins → J2 / UART hier labels (4 horizontal hops) ----
    # EN and BOOT_MODE: 2-pin nets ending at J2.3 / J2.4.
    parts.append(_sch_wire(U3_X_RIGHT, U3_EN_Y,   J2_PIN_X, J2_P3_Y, "en-to-j2"))
    parts.append(_sch_wire(U3_X_RIGHT, U3_BOOT_Y, J2_PIN_X, J2_P4_Y, "boot-to-j2"))
    # UART_TX / UART_RX wires run east from U3 right pins all the way to
    # the right-edge UART hier labels at X=HLABEL_RIGHT_X=222.25. J2.5 and
    # J2.6 sit mid-wire at X=J2_PIN_X=194.31 — each needs a junction dot
    # to mark the T-tap.
    parts.append(_sch_wire(U3_X_RIGHT, U3_TX_Y,   HLABEL_RIGHT_X, U3_TX_Y, "tx-bus"))
    parts.append(_sch_wire(U3_X_RIGHT, U3_RX_Y,   HLABEL_RIGHT_X, U3_RX_Y, "rx-bus"))
    parts.append(_sch_junction(J2_PIN_X, U3_TX_Y, "uart-tx-j2-tap"))
    parts.append(_sch_junction(J2_PIN_X, U3_RX_Y, "uart-rx-j2-tap"))

    # ---- J2.1 (3V3) and J2.2 (GND) local power flags ----
    # +3V3 symbol just above J2.1; wire down from symbol to pin tip.
    PWR_J2_3V3_Y = J2_P1_Y - 3.81      # 92.71 (row 73) — symbol 3.81 mm above pin
    parts.append(_sch_wire(J2_PIN_X, PWR_J2_3V3_Y, J2_PIN_X, J2_P1_Y, "j2-3v3-drop"))
    # GND symbol just left of J2.2; wire from pin tip leftward to symbol.
    PWR_J2_GND_X = J2_PIN_X - 5.08      # 189.23 (column 149)
    parts.append(_sch_wire(J2_PIN_X, J2_P2_Y, PWR_J2_GND_X, J2_P2_Y, "j2-gnd-hop"))

    # ===== Junctions =====
    # Already emitted UART tap junctions above. No others needed: every
    # other wire endpoint coincides exactly with a pin tip (KiCad
    # auto-joins pin tips to wires of the same coordinate).

    # ===== Hierarchical labels =====
    # Left-edge labels: angle=180 (arrow points left, text reads R→L),
    # justify=right (text extends to the LEFT of the anchor).
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
    # Right-edge labels: angle=0 (arrow points right), justify=left.
    parts.append(_sch_hierarchical_label(
        name="UART_TX", shape="output",
        x=HLABEL_RIGHT_X, y=U3_TX_Y, angle=0, justify="left",
        uuid_tag="uart-tx",
    ))
    parts.append(_sch_hierarchical_label(
        name="UART_RX", shape="input",
        x=HLABEL_RIGHT_X, y=U3_RX_Y, angle=0, justify="left",
        uuid_tag="uart-rx",
    ))

    # ===== No-connect markers =====
    # U3.1 (5V), U3.6 (GPIO 8 = onboard WS2812), U3.13-16 (GPIO 18-21)
    parts.append(_sch_no_connect(U3_X_LEFT,  U3_5V_Y, "u3-5v"))
    parts.append(_sch_no_connect(U3_X_LEFT,  U3_LED_Y, "u3-gpio8"))
    parts.append(_sch_no_connect(U3_X_RIGHT, PIN_Y[4], "u3-gpio18"))
    parts.append(_sch_no_connect(U3_X_RIGHT, PIN_Y[5], "u3-gpio19"))
    parts.append(_sch_no_connect(U3_X_RIGHT, PIN_Y[6], "u3-gpio20"))
    parts.append(_sch_no_connect(U3_X_RIGHT, PIN_Y[7], "u3-gpio21"))

    # ===== U3 symbol (ESP32-C6 SuperMini) =====
    parts.append(_sch_esp32c6_supermini(
        x=U3_X, y=U3_Y,
        reference="U3", value="ESP32-C6 SuperMini",
        uuid_tag="u3",
    ))

    # ===== J2 symbol (SWD/UART recovery header, DNP) =====
    parts.append(_sch_conn_01x06(
        x=J2_X, y=J2_Y, angle=0,
        reference="J2", value="SWD/UART Recovery (DNP)",
        uuid_tag="j2", dnp=True,
    ))

    # ===== Capacitors (C9 bulk, C9b HF) =====
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C9_X, y=C9_Y, angle=0,
        reference="C9", value="10uF 10V",
        uuid_tag="c9", sheet_key="mcu",
    ))
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C9b_X, y=C9b_Y, angle=0,
        reference="C9b", value="100nF",
        uuid_tag="c9b", sheet_key="mcu",
    ))

    # ===== Power flags =====
    # +3V3 on the bus between C9 and C9b (angle=0, triangle points UP).
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=PWR_3V3_X, y=PWR_3V3_Y, angle=0,
        reference="#PWR25",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr25-3v3-bus",
        sheet_key="mcu",
    ))
    # +3V3 above J2.1 (angle=0, triangle UP).
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=J2_PIN_X, y=PWR_J2_3V3_Y, angle=0,
        reference="#PWR26",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr26-3v3-j2",
        sheet_key="mcu",
    ))
    # GND below C9 (angle=0 — triangle hangs DOWN by default).
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
    # GND on U3.2 (angle=270 so the triangle points RIGHT toward the
    # symbol; pin tip lands on the GND symbol's connection point).
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U3_GND_X, y=U3_GND_Y, angle=270,
        reference="#PWR29",
        value_offset_x=-3.81, value_offset_y=0.0,
        uuid_tag="pwr29-gnd-u3",
        sheet_key="mcu",
    ))
    # GND on J2.2 (angle=270).
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=PWR_J2_GND_X, y=J2_P2_Y, angle=270,
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
        {MCU_LIB_SYMBOLS}
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
        elif name == "mcu":
            content = gen_mcu_sch()
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
