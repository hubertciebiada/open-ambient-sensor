"""boardgen/_footprints_custom.py — project-local `oas:*` footprints.

Custom mechanical-reference footprints with no KiCad stock equivalent:
mounting hole, SEN66 / LD2410 / SK6812 body shadows, zip-tie holes, and
the ESP32-C6-DevKitM-1 daughterboard reference. Each is
hand-written S-expression tied to project-specific measurements from
`boardgen/_project.py`.

Split from `_footprints.py` at v0.40-post-audit-16 to keep each module
within typical LLM context window.
"""
from __future__ import annotations

import textwrap

from boardgen._common import (  # noqa: F401
    U, fmt,
    PCB_VERSION, GEN_VERSION,
)
from boardgen._project import (  # noqa: F401
    fx, fy,
    HOLE_DIAMETER, COURTYARD_RADIUS, CUTOUTS,
    SEN66_ANCHOR_X, SEN66_ANCHOR_Y, SEN66_ROTATION,
    SEN66_ZIPTIE_LOCAL, _sen66_local_to_pcb,
    J3_X, J3_Y, J3_ROTATION,
    LD2410_BODY_W, LD2410_BODY_H,
    LD2410_SILK_INSET, LD2410_SILK_INSET_CONN, LD2410_EMIT_SILK_OUTLINE,
    LD2410_ANTENNA_X_END, LD2410_CONNECTOR_X, LD2410_CONNECTOR_Y,
    LD2410_ANCHOR_X, LD2410_ANCHOR_Y, LD2410_ROTATION,
    _ld2410_local_to_pcb,
    J4_PCB_X, J4_PCB_Y, J4_PCB_ROTATION,
    ESP32_BODY_W, ESP32_BODY_L,
    ESP32_PIN_ROW_INSET, ESP32_PIN_PITCH, ESP32_PIN_COUNT_PER_ROW,
    ESP32_PIN_START_OFFSET,
    ESP32_ANCHOR_X, ESP32_ANCHOR_Y, ESP32_ROTATION,
    J1_PCB_X, J1_PCB_Y, J1_PCB_ROTATION,
    J9_PCB_X, J9_PCB_Y, J9_PCB_ROTATION,
    J10_PCB_X, J10_PCB_Y, J10_PCB_ROTATION,
    LED_RING_COUNT, LED_RING_THETA_START_DEG, LED_RING_THETA_STEP_DEG,
    LED_RING_SKIP_INDICES,
    SK6812SIDE_BODY_W, SK6812SIDE_BODY_H,
    SK6812SIDE_PAD_HEIGHT, SK6812SIDE_PAD_Y,
    SK6812SIDE_PADS,
    FUSE1812L_BODY_W, FUSE1812L_BODY_H,
    FUSE1812L_PAD_W, FUSE1812L_PAD_H, FUSE1812L_PAD_X,
    _led_ring_position, _led_cap_position,
)


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
#     the PCB so the LD2410 daughterboard stays clear,
#     and so the J3 socket aligns with the SEN66's on-body JST GH
#     connector for a short cable run.
#   - No pads, no drilled holes (the 4× zip-tie retention holes are a
#     separate footprint: `ZipTieHole_3mm_NPTH`).
SEN66_BODY_X = 55.2
SEN66_BODY_Y = 25.6
SEN66_BODY_Z = 21.5                # body height (CLAUDE.md hard constraint)
# (v0.53: SEN66_SILK_INSET removed — the F.SilkS body outline it inset was
# dropped when the module started recessing through a real cutout, issue #2.)

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
    zip-tie holes, and ensuring that future components (LD2410
    and any new daughterboard) avoid the SEN66 zone.

    Rendered on `F.Fab` only (full body outline + air openings + connector
    marker + foam-divider hint). v0.53 (issue #2): the module now recesses
    THROUGH a real board cutout, so every F.SilkS element of this footprint
    fell inside the opening — the F.SilkS body outline and the
    "JST GH cable ->" text were removed (silk over an internal cutout drops
    at fab). The F.CrtYd body-shadow guardrail is KEPT (a placement over the
    hole is impossible anyway, and the courtyard still documents the shadow);
    module identification silk is carried by board-level gr_text in
    gen_silk_labels(), relocated onto the remaining rim.
    """
    # Footprint-local coordinates with the rectangle's corner at (0, 0)
    # are awkward for KiCad — the footprint anchor sits at (0, 0) and
    # all features sit in +X, +Y. That's fine; pcbnew accepts it.
    x_min, y_min = 0.0, 0.0
    x_max, y_max = SEN66_BODY_X, SEN66_BODY_Y

    # F.Fab body outline (un-inset rectangle). v0.53 (issue #2): F.Fab art
    # is KEPT verbatim even though it now sits over the recess cutout — F.Fab
    # is the assembly-drawing layer (never silkscreened), so it is not a
    # fab/DFM concern, and it accurately documents the recessed module body +
    # inlets + outlet + connector. The F.SilkS body outline and the
    # "JST GH cable ->" F.SilkS text were REMOVED (they fell entirely inside
    # the cutout — silk over an internal opening drops at fab / trips JLCDFM).
    # Module identification silk is carried by the board-level gr_text labels
    # in gen_silk_labels(), relocated onto the remaining rim.
    fab_outline = textwrap.dedent(f"""\
        \t(fp_rect
        \t\t(start {fmt(x_min)} {fmt(y_min)})
        \t\t(end {fmt(x_max)} {fmt(y_max)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('sen66:fp:fab-outline')}")
        \t)""")

    # (v0.53: F.SilkS body outline removed — see the note above; it fell
    # inside the recess cutout.)

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
    # (v0.53: the "JST GH cable ->" F.SilkS text was removed — it fell inside
    # the recess cutout. The connector marker stays on F.Fab only.)

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
    # sockets (MOD1 ESP32) are DIFFERENT — they sit on
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
            fab_outline,
            inlet1_top, inlet1_bot, inlet1_left_arc, inlet1_right_arc,
            inlet2, outlet, divider, conn_marker,
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
    zone for other components (Qwiic, decoupling caps, etc.).

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
# Pad rectangles: ASYMMETRIC land pattern from EasyEDA C5378721 — four
# rect pads 1.2 mm tall, widths 1.00/0.70/0.45/1.00 mm, centres at
# body-local X = -1.80/-0.45/+0.575/+1.80. Pad-row centreline at
# body-local +Y = SK6812SIDE_PAD_Y (0.15 mm) — re-centred on where
# JLCPCB lands the part pins; see the SK6812SIDE_PAD_Y comment in
# _project.py. The emission face is on the opposite long edge (-Y).
#
# Layers:
#   F.Cu      — 4 SMD pads
#   F.Fab     — body outline (4.0 × 1.6 mm), pin-1 dot, emission-edge arrow
#   F.SilkS   — pin-1 dot near pad 1 + small emission-direction arrow on
#                the body's -Y edge. No body silk RECT is emitted
#                (historically it tripped silk_overlap DRC against the
#                since-removed (issue #7) MIKROE-2462 silk at the
#                angle-180° LED position; the body outline lives
#                on F.Fab instead).
#   F.CrtYd   — small courtyard slightly larger than the body
#
# Property layout:
#   Reference (hidden, on F.SilkS at body-local (0, -1.5))
#   Value     (hidden, on F.Fab     at body-local (0, +2.5))


def gen_sk6812_side_footprint() -> str:
    """Custom SK6812-SIDE footprint definition (library file)."""
    body_hw = SK6812SIDE_BODY_W / 2.0    # = 2.0 (half-extent along +X)
    body_hh = SK6812SIDE_BODY_H / 2.0    # = 0.8 (half-extent along +Y)
    # Courtyard: encloses the body AND the asymmetric land. The outer
    # pads run past the body ends on +/-X and the pad row runs past the
    # body on +Y; 0.20 mm margin on every side.
    pad_x_min = min(lx - pw / 2.0 for lx, pw in SK6812SIDE_PADS)
    pad_x_max = max(lx + pw / 2.0 for lx, pw in SK6812SIDE_PADS)
    crty_x_min = min(-body_hw, pad_x_min) - 0.20
    crty_x_max = max(+body_hw, pad_x_max) + 0.20
    crty_y_min = -body_hh - 0.20         # emission side
    crty_y_max = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT/2 + 0.20
    # Pad rectangles -- asymmetric land pattern (see SK6812SIDE_PADS).
    pad_blocks = []
    for pin_num, (lx, pw) in enumerate(SK6812SIDE_PADS, start=1):
        pad_blocks.append(textwrap.dedent(f"""\
            \t(pad "{pin_num}" smd rect
            \t\t(at {fmt(lx)} {fmt(SK6812SIDE_PAD_Y)})
            \t\t(size {fmt(pw)} {fmt(SK6812SIDE_PAD_HEIGHT)})
            \t\t(layers "F.Cu" "F.Paste" "F.Mask")
            \t\t(uuid "{U(f'sk6812-side:fp:pad-{pin_num}')}")
            \t)"""))
    pads = "\n".join(pad_blocks)
    # Pin-1 dot on F.SilkS above pad 1, at pad 1's INNER edge (not its
    # centre): the asymmetric land puts pad 1 centre at -1.80, and a dot
    # that far out collided with the since-removed (issue #7) MIKROE-2462
    # (MOD2) silk at the theta=135 deg LED (D14). The inner edge keeps the
    # dot next to pad 1 and clear of any neighbouring silk on every slot.
    pin1_dot_x = SK6812SIDE_PADS[0][0] + SK6812SIDE_PADS[0][1] / 2.0
    # v0.44: dot centre 0.50 mm above pad 1's top edge (was 0.35 mm).
    # With the silk stroke lifted to the 0.15 mm JLCPCB floor the filled
    # dot's outer edge reaches 0.225 mm past its centre, so 0.50 mm of
    # centre clearance leaves silk-edge to pad-edge at ~0.275 mm — clear
    # of JLCPCB DFM "Silkscreen to pad" (0.35 mm gave only ~0.125 mm).
    pin1_dot_y = SK6812SIDE_PAD_Y + SK6812SIDE_PAD_HEIGHT / 2 + 0.50
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
        \t(model "${KIPRJMOD}/libraries/oas.3dshapes/SK6812-SIDE-A.step"
        \t\t(offset (xyz 0 0 0))
        \t\t(scale (xyz 1 1 1))
        \t\t(rotate (xyz 0 0 0))
        \t)
        )
        """)


# -----------------------------------------------------------------------------
# 1ac) Fuse_1812L_4532Metric — Littelfuse 1812L-series PTC fuse footprint
# -----------------------------------------------------------------------------
# Custom land pattern for F1, the 24 V input PTC fuse (Littelfuse
# 1812L075/33DR, LCSC C151170). KiCad stock `Fuse:Fuse_1812_4532Metric`
# is a generic IPC-7351 1812 chip-fuse land (pad gap 3.15 mm); the
# Littelfuse 1812L series has wide termination bands and a tighter
# recommended land (gap 2.30 mm). On the generic stock land the part's
# pin inner edge sits 0.43 mm past the copper -> JLCPCB DFM DANGER
# "pin inner edge".
#
# Pad geometry is the verbatim EasyEDA F1812 footprint of C151170 — the
# exact data JLCPCB's DFM resolves against (1 EasyEDA unit = 0.254 mm):
# two rect pads 1.4067 × 3.4992 mm at body-local X = ±1.8534 mm.
#
# Layers:
#   F.Cu     — 2 SMD pads
#   F.Fab    — body outline (4.55 × 3.24 mm) + ${REFERENCE} text
#   F.SilkS  — 2 short body-edge lines in the inter-pad gap (stock-fuse
#               style; a full body RECT would run under the pads)
#   F.CrtYd  — courtyard, 0.20 mm past the pads / body
# 3D model: KiCad stock `Resistor_SMD.3dshapes/R_1812_4532Metric.step` —
# the 1812 PTC body is dimensionally a 1812 chip, so the resistor STEP is
# a 1:1 visual surrogate (bundled with KiCad, CC-BY-SA + Design Exception).


def gen_fuse_1812l_footprint() -> str:
    """Custom Littelfuse-1812L PTC fuse footprint definition (library file)."""
    body_hw = FUSE1812L_BODY_W / 2.0        # 2.275
    body_hh = FUSE1812L_BODY_H / 2.0        # 1.62
    pad_hw = FUSE1812L_PAD_W / 2.0          # 0.70335
    pad_hh = FUSE1812L_PAD_H / 2.0          # 1.7496
    pad_outer_x = FUSE1812L_PAD_X + pad_hw  # 2.55675
    crty_x = max(body_hw, pad_outer_x) + 0.20
    crty_y = max(body_hh, pad_hh) + 0.20
    # F.SilkS: two short body-edge lines, confined to the inter-pad gap
    # (pad inner edge at X = ±1.150) so they never run over copper.
    silk_x = 0.8
    silk_y = body_hh + 0.09     # 1.71 — snug above / below the body
    pad_blocks = []
    for pin_num, sign in ((1, -1.0), (2, +1.0)):
        pad_blocks.append(textwrap.dedent(f"""\
            \t(pad "{pin_num}" smd rect
            \t\t(at {fmt(sign * FUSE1812L_PAD_X)} 0)
            \t\t(size {fmt(FUSE1812L_PAD_W)} {fmt(FUSE1812L_PAD_H)})
            \t\t(layers "F.Cu" "F.Mask" "F.Paste")
            \t\t(uuid "{U(f'fuse-1812l:fp:pad-{pin_num}')}")
            \t)"""))
    pads = "\n".join(pad_blocks)
    return textwrap.dedent(f"""\
        (footprint "Fuse_1812L_4532Metric"
        \t(version {PCB_VERSION})
        \t(generator "pcbnew")
        \t(generator_version "{GEN_VERSION}")
        \t(layer "F.Cu")
        \t(descr "PTC resettable fuse, 1812 (4532 Metric) SMD. Land matched to the Littelfuse 1812L-series termination geometry (EasyEDA F1812 / LCSC C151170) — pad gap 2.30 mm, tighter than the generic IPC Fuse_1812_4532Metric land (3.15 mm).")
        \t(tags "fuse ptc resettable polyfuse 1812 littelfuse")
        \t(attr smd)
        \t(property "Reference" "REF**"
        \t\t(at 0 {fmt(-(body_hh + 1.0))} 0)
        \t\t(unlocked yes)
        \t\t(layer "F.SilkS")
        \t\t(hide yes)
        \t\t(uuid "{U('fuse-1812l:fp:prop-ref')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Value" "Fuse_1812L_4532Metric"
        \t\t(at 0 {fmt(body_hh + 1.0)} 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fuse-1812l:fp:prop-val')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(property "Footprint" ""
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fuse-1812l:fp:prop-fp')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Datasheet" "https://www.lcsc.com/datasheet/C151170.pdf"
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fuse-1812l:fp:prop-ds')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(property "Description" "Littelfuse 1812L075/33DR PTC resettable fuse — 33 V, 750 mA hold / 1.5 A trip, 1812 SMD."
        \t\t(at 0 0 0)
        \t\t(unlocked yes)
        \t\t(layer "F.Fab")
        \t\t(hide yes)
        \t\t(uuid "{U('fuse-1812l:fp:prop-desc')}")
        \t\t(effects (font (size 1.27 1.27)))
        \t)
        \t(fp_rect
        \t\t(start {fmt(-body_hw)} {fmt(-body_hh)})
        \t\t(end {fmt(body_hw)} {fmt(body_hh)})
        \t\t(stroke (width 0.1) (type solid))
        \t\t(fill no)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('fuse-1812l:fp:fab-body')}")
        \t)
        \t(fp_text user "${{REFERENCE}}"
        \t\t(at 0 0 0)
        \t\t(layer "F.Fab")
        \t\t(uuid "{U('fuse-1812l:fp:fab-ref')}")
        \t\t(effects (font (size 1 1) (thickness 0.15)))
        \t)
        \t(fp_rect
        \t\t(start {fmt(-crty_x)} {fmt(-crty_y)})
        \t\t(end {fmt(crty_x)} {fmt(crty_y)})
        \t\t(stroke (width 0.05) (type solid))
        \t\t(fill no)
        \t\t(layer "F.CrtYd")
        \t\t(uuid "{U('fuse-1812l:fp:crtyd')}")
        \t)
        \t(fp_line
        \t\t(start {fmt(-silk_x)} {fmt(-silk_y)})
        \t\t(end {fmt(silk_x)} {fmt(-silk_y)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('fuse-1812l:fp:silk-top')}")
        \t)
        \t(fp_line
        \t\t(start {fmt(-silk_x)} {fmt(silk_y)})
        \t\t(end {fmt(silk_x)} {fmt(silk_y)})
        \t\t(stroke (width 0.12) (type solid))
        \t\t(layer "F.SilkS")
        \t\t(uuid "{U('fuse-1812l:fp:silk-bot')}")
        \t)
        """) + pads + textwrap.dedent("""
        \t(model "${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_1812_4532Metric.step"
        \t\t(offset (xyz 0 0 0))
        \t\t(scale (xyz 1 1 1))
        \t\t(rotate (xyz 0 0 0))
        \t)
        )
        """)


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


def _daughterboard_body_content(
    body_w: float, body_l: float,
    pin_row_inset: float, pin_pitch: float, pin_count_per_row: int,
    body_label: str,
    antenna_label: str | None,
    usb_label: str | None,
    uuid_tag: str,
    pin_start_offset: float | None = None,
    antenna_tab_w: float | None = None,
    antenna_tab_protrusion: float | None = None,
    emit_silk_outline: bool = True,
) -> str:
    """Inner body content (body outline on F.Fab + pin-row dots on F.Fab +
    optional F.SilkS outline) shared by the library footprint definition and
    the in-PCB placement instance for a daughterboard mech-ref. Returns the
    block ready to embed inside a (footprint ...) wrapper.

    `pin_start_offset` is the distance (in LIB +Y direction) from the
    body's pin-1-side short edge to pin 1's centerline. If None, the
    pin block is centred along the long axis. Asymmetric daughterboards
    (e.g. ESP32-C6 DevKitM-1 with pins offset toward the antenna)
    pass an explicit value.

    `antenna_tab_w` / `antenna_tab_protrusion` (both given, or both None):
    draw the F.Fab body outline as the TRUE outline of a module whose PCB
    antenna overhangs the pin-1-side short edge (LIB Y=0) — a rectangular
    tab of width `antenna_tab_w` (centred on `body_w`) protruding
    `antenna_tab_protrusion` in the LIB -Y direction. Used for the
    ESP32-C6-DevKitM-1 (the ESP32-C6-MINI-1 antenna section). F.Fab may cross
    Edge.Cuts, so the tab can hang off-board.

    `emit_silk_outline`: when False, NO F.SilkS body outline is drawn. Set
    False for the ESP32 (issue #3): after the -7.5 mm move its body outline
    would fall off the board at the NW corner AND cross the buck-section pads
    (R6/C9) on the east edge and the U1 pads under the antenna tab — every
    F.SilkS position in the module footprint is a silk_edge or
    silk_over_copper violation. The J5/J6 socket silk frames + the
    board-level "ESP32-C6 DevKitM-1" F.Fab label document the module instead;
    the full true shape (incl. tab) lives on F.Fab.
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

    # Body F.Fab outline (fabrication documentation layer). With an antenna
    # tab, emit the full true outline (body rect + protruding tab) as a
    # closed polygon; otherwise a plain body rectangle.
    if antenna_tab_w is not None and antenna_tab_protrusion is not None:
        tab_x1 = (body_w - antenna_tab_w) / 2.0
        tab_x2 = (body_w + antenna_tab_w) / 2.0
        tab_y = -antenna_tab_protrusion
        _poly_pts = [
            (0.0, 0.0), (0.0, body_l), (body_w, body_l), (body_w, 0.0),
            (tab_x2, 0.0), (tab_x2, tab_y), (tab_x1, tab_y), (tab_x1, 0.0),
        ]
        _pts_txt = "\n".join(f"\t\t\t(xy {fmt(px)} {fmt(py)})" for px, py in _poly_pts)
        parts.append(textwrap.dedent(f"""\
            \t(fp_poly
            \t\t(pts
            {_pts_txt}
            \t\t)
            \t\t(stroke (width 0.1) (type solid))
            \t\t(fill no)
            \t\t(layer "F.Fab")
            \t\t(uuid "{U('fp-fab-outline:' + uuid_tag)}")
            \t)"""))
    else:
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
    # the female pin sockets along the long edges. Omitted when
    # emit_silk_outline is False (see docstring — ESP32 issue #3).
    if emit_silk_outline:
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
    # daughterboard rotation. Pass None for boards without such hints.
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
    antenna_tab_w: float | None = None,
    antenna_tab_protrusion: float | None = None,
    emit_silk_outline: bool = True,
) -> str:
    """Return the .kicad_mod library-file content for a daughterboard
    mechanical-reference footprint.

    Mirrors the embedded body that `_emit_daughterboard_reference_pcb_footprint`
    writes into the placed-instance footprint inside `oas.kicad_pcb`,
    but with library-file metadata (no `(at x y rotation)` anchor, no
    embedded `(uuid ...)` for the footprint itself — KiCad pcbnew
    generates those when the lib footprint is dropped onto a board).
    Adding the matching lib file silences KiCad's `lib_footprint_issues`
    DRC warning — so the `antenna_tab_*` / `emit_silk_outline` args MUST be
    passed identically here and at the placement call site.
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
        antenna_tab_w=antenna_tab_w,
        antenna_tab_protrusion=antenna_tab_protrusion,
        emit_silk_outline=emit_silk_outline,
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
    antenna_tab_w: float | None = None,
    antenna_tab_protrusion: float | None = None,
    emit_silk_outline: bool = True,
) -> str:
    """Emit a daughterboard mechanical-reference footprint placed at
    (anchor_x, anchor_y) on the OAS PCB. The footprint is purely visual
    (F.Fab outline + optional F.SilkS outline + pin-row hints); the actual
    electrical female pin sockets are placed separately in chunk #7.
    `antenna_tab_*` / `emit_silk_outline` pass through to
    `_daughterboard_body_content` — see its docstring.

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
    MOD1 / LDR1 without rethinking the standoff budget (v0.22
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
        antenna_tab_w=antenna_tab_w,
        antenna_tab_protrusion=antenna_tab_protrusion,
        emit_silk_outline=emit_silk_outline,
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
