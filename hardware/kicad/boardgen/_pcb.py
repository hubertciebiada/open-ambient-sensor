"""boardgen/_pcb.py - gen_pcb() — assemble oas.kicad_pcb body.

Calls into `boardgen/_footprints.py` for the actual footprint sexp text
and stitches it together with the Edge.Cuts outline (D-shape arc + flat
chord), mounting holes (3 x NPTH M3), central cable hole, layer stackup,
setup block, and a placeholder net 0. The placement orchestrators
emit their own component-shadow keepouts and silk labels.

The output is consumed by `boardgen/02_pcb_board.py` (stage 02) which
writes it to `oas.kicad_pcb`.
"""
from __future__ import annotations

import math
import textwrap

from boardgen._common import (
    U, fmt,
    PCB_VERSION, GEN_VERSION,
)
from boardgen._project import (
    fx, fy,
    PAGE_CENTRE_X, PAGE_CENTRE_Y,
    HALF_CHORD, Y_CHORD, R_OUTLINE,
    HOLE_POSITIONS, EDGE_CUTS_WIDTH, HOLE_DIAMETER, COURTYARD_RADIUS,
    CABLE_HOLE_DIAMETER,
    SEN66_CUTOUT_X_MIN, SEN66_CUTOUT_X_MAX,
    SEN66_CUTOUT_Y_MIN, SEN66_CUTOUT_Y_MAX, SEN66_CUTOUT_CORNER_R,
)
from boardgen._footprints import (
    gen_cutouts,
    gen_sensors_pcb_footprints,
    gen_power_pcb_footprints,
    gen_silk_labels,
)


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

    # SEN66 recess cutout (v0.53, GitHub issue #2): a rounded rectangle
    # milled through the board so the SEN66 module recesses into the
    # enclosure rear space — the flat-mount body height broke the AK-N-94
    # lid close. Emitted as 4 straight gr_line edges + 4 quarter-circle
    # gr_arc corners on Edge.Cuts, derived from SEN66_CUTOUT_* in
    # _project.py so the opening tracks any future SEN66 anchor move.
    cx0, cx1 = SEN66_CUTOUT_X_MIN, SEN66_CUTOUT_X_MAX
    cy0, cy1 = SEN66_CUTOUT_Y_MIN, SEN66_CUTOUT_Y_MAX
    cr = SEN66_CUTOUT_CORNER_R
    cs = cr * math.sqrt(0.5)   # corner-arc midpoint offset (r·cos45°)
    _cut_lines = [
        # (start_x, start_y, end_x, end_y, tag) — edges shortened by cr at
        # each end so they meet the quarter-arc corners.
        (cx0 + cr, cy0, cx1 - cr, cy0, "n"),   # north edge (min Y)
        (cx1, cy0 + cr, cx1, cy1 - cr, "e"),   # east edge (max X)
        (cx1 - cr, cy1, cx0 + cr, cy1, "s"),   # south edge (max Y)
        (cx0, cy1 - cr, cx0, cy0 + cr, "w"),   # west edge (min X)
    ]
    _cut_arcs = [
        # (start_x, start_y, mid_x, mid_y, end_x, end_y, tag) — quarter arcs
        # bulging toward each rectangle corner (mid on the outward diagonal).
        (cx1 - cr, cy0, cx1 - cr + cs, cy0 + cr - cs, cx1, cy0 + cr, "ne"),
        (cx1, cy1 - cr, cx1 - cr + cs, cy1 - cr + cs, cx1 - cr, cy1, "se"),
        (cx0 + cr, cy1, cx0 + cr - cs, cy1 - cr + cs, cx0, cy1 - cr, "sw"),
        (cx0, cy0 + cr, cx0 + cr - cs, cy0 + cr - cs, cx0 + cr, cy0, "nw"),
    ]
    cutout_parts = []
    for sx, sy, ex, ey, tag in _cut_lines:
        cutout_parts.append(textwrap.dedent(f"""\
            \t(gr_line
            \t\t(start {fx(sx)} {fy(sy)})
            \t\t(end {fx(ex)} {fy(ey)})
            \t\t(stroke (width {fmt(EDGE_CUTS_WIDTH)}) (type solid))
            \t\t(layer "Edge.Cuts")
            \t\t(uuid "{U('sen66_cutout_edge_' + tag)}")
            \t)"""))
    for sx, sy, mx, my, ex, ey, tag in _cut_arcs:
        cutout_parts.append(textwrap.dedent(f"""\
            \t(gr_arc
            \t\t(start {fx(sx)} {fy(sy)})
            \t\t(mid {fx(mx)} {fy(my)})
            \t\t(end {fx(ex)} {fy(ey)})
            \t\t(stroke (width {fmt(EDGE_CUTS_WIDTH)}) (type solid))
            \t\t(layer "Edge.Cuts")
            \t\t(uuid "{U('sen66_cutout_corner_' + tag)}")
            \t)"""))
    outline = outline + "\n" + "\n".join(cutout_parts)

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
