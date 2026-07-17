"""boardgen/_footprints_placement.py — placement orchestrators.

The three public entry points (`gen_power_pcb_footprints`,
`gen_sensors_pcb_footprints`, `gen_silk_labels`) plus `gen_cutouts`
compose layer-1 (custom) and layer-2 (stock) generators at the
placement coordinates from `boardgen/_project.py` and return one big
string that `gen_pcb()` (in `boardgen/_pcb.py`) splices into the
assembled .kicad_pcb body.

Split from `_footprints.py` at v0.40-post-audit-16 to keep each module
within typical LLM context window.
"""
from __future__ import annotations

import math
import textwrap

from boardgen._common import (  # noqa: F401
    U, fmt,
    PCB_VERSION, GEN_VERSION,
    OAS_NAME_SHORT, OAS_VERSION_LINE, OAS_REPO_URL_SILK_LINES,
)
from boardgen._project import (  # noqa: F401
    fx, fy,
    HOLE_DIAMETER, COURTYARD_RADIUS, CUTOUTS,
    SEN66_ANCHOR_X, SEN66_ANCHOR_Y, SEN66_ROTATION,
    SEN66_ZIPTIE_LOCAL, _sen66_local_to_pcb,
    J3_X, J3_Y, J3_ROTATION,
    _J3_COURTYARD_HALF_X, J3_CABLE_SLOT_X_MIN,
    BOARD_ID_CENTER_X, BOARD_ID_CENTER_Y, BOARD_ID_ROW_PITCH,
    LD2410_BODY_W, LD2410_BODY_H,
    LD2410_SILK_INSET, LD2410_SILK_INSET_CONN, LD2410_EMIT_SILK_OUTLINE,
    LD2410_ANTENNA_X_END, LD2410_CONNECTOR_X, LD2410_CONNECTOR_Y,
    LD2410_ANCHOR_X, LD2410_ANCHOR_Y, LD2410_ROTATION,
    _ld2410_local_to_pcb,
    J4_PCB_X, J4_PCB_Y, J4_PCB_ROTATION,
    ESP32_BODY_W, ESP32_BODY_L,
    ESP32_PIN_ROW_INSET, ESP32_PIN_PITCH, ESP32_PIN_COUNT_PER_ROW,
    ESP32_PIN_START_OFFSET,
    ESP32_ANTENNA_TAB_W, ESP32_ANTENNA_TAB_PROTRUSION,
    ESP32_ANCHOR_X, ESP32_ANCHOR_Y, ESP32_ROTATION,
    J1_PCB_X, J1_PCB_Y, J1_PCB_ROTATION,
    J2_PCB_X, J2_PCB_Y, J2_PCB_ROTATION,
    J9_PCB_X, J9_PCB_Y, J9_PCB_ROTATION,
    J10_PCB_X, J10_PCB_Y, J10_PCB_ROTATION,
    J1_PIN_MAP, J2_PIN_MAP, J10_PIN_MAP,
    J4_END_SIGNALS, J5_END_SIGNALS, J6_END_SIGNALS,
    LED_RING_COUNT, LED_RING_THETA_START_DEG, LED_RING_THETA_STEP_DEG,
    LED_RING_SKIP_INDICES,
    SK6812SIDE_BODY_W, SK6812SIDE_BODY_H,
    SK6812SIDE_PAD_HEIGHT, SK6812SIDE_PAD_Y,
    SK6812SIDE_PAD_X_OFFSETS,
    _led_ring_position, _led_cap_position,
)

from boardgen._footprints_custom import (  # noqa: F401
    SEN66_BODY_X, SEN66_BODY_Y,
    ZIPTIE_HOLE_DIAMETER, ZIPTIE_HOLE_SILK_RING_DIAMETER,
    _emit_pcb_footprint_simple_npth,
    _emit_daughterboard_reference_pcb_footprint,
)
from boardgen._footprints_stock import (
    gen_sen66_reference_pcb_footprint,
    gen_ld2410_reference_pcb_footprint,
    gen_j3_jst_gh_pcb_footprint,
    gen_j4_pinheader_pcb_footprint,
    gen_j1_terminal_block_pcb_footprint,
    gen_j9_qwiic_pcb_footprint,
    gen_j10_recovery_pcb_footprint,
    gen_pinsocket_pcb_footprint,
    gen_sk6812_side_pcb_footprint,
    gen_capacitor_0402_pcb_footprint,
    gen_resistor_0603_pcb_footprint,
    gen_capacitor_0603_pcb_footprint,
    gen_capacitor_0805_pcb_footprint,
    gen_diode_sma_pcb_footprint,
    gen_diode_smb_pcb_footprint,
    gen_diode_sod323_pcb_footprint,
    gen_inductor_smd_5x5_pcb_footprint,
    gen_fuse_1812l_pcb_footprint,
    gen_capacitor_polarized_radial_pcb_footprint,
    gen_sot23_3pin_pcb_footprint,
    gen_to263_5_pcb_footprint,
    gen_sot583_pcb_footprint,
    gen_pinheader_6_recovery_pcb_footprint,
)


# -----------------------------------------------------------------------------
# 1a) Footprint-local → PCB coordinate transform
# -----------------------------------------------------------------------------
def _rotate_local(lx: float, ly: float, rotation: float) -> tuple[float, float]:
    """Rotate a footprint-local (lx, ly) delta by `rotation` degrees.

    Uses the SAME matrix KiCad applies to a footprint placed `(at x y rot)`
    — identical to the convention in `_sen66_local_to_pcb` /
    `_ld2410_local_to_pcb`. Returns the PCB-space delta to add to the
    footprint origin, so a pad / silk position can be DERIVED from the
    placement instead of being hand-typed per pin.
    """
    a = math.radians(rotation)
    cos_a, sin_a = math.cos(a), math.sin(a)
    return (cos_a * lx + sin_a * ly, -sin_a * lx + cos_a * ly)


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
        keepout_zone = textwrap.dedent(f"""\
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
            \t)""")

        # v0.50: emit the keepout zone ONLY for cutouts that truly block
        # copper (allow_pads=False). An allow_pads=True cutout has every
        # keepout flag set to "allowed" — the zone is inert inside KiCad,
        # but KiCad's Specctra DSN export STILL turns it into a HARD
        # keepout that walls Freerouting out of fully-routable case-wall-
        # opening space (e.g. the USB-C opening). Skipping the zone
        # keeps the Dwgs.User marker (documentation) without the phantom
        # autoroute obstacle.
        if not allow_pads:
            keepouts.append(keepout_zone)

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
#   Sensor decoupling: C10 (SEN66), C11 (LD2410) — near each
#     sensor's socket.
#   J2 — DNP recovery header, placed off in a free corner.
#
# All components use the stub footprint generators above. Pin numbering
# matches the corresponding KiCad symbol library so the v0.20 net-sync
# pass attaches schematic nets correctly.


def gen_power_pcb_footprints() -> str:
    """Emit PCB footprints for all power-section schematic components,
    plus sensor decoupling C10/C11 and the DNP J2 recovery header.

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
    # (Historical placement-iteration notes below reference the NFC /
    # MIKROE-2462 daughterboard, removed in issue #7; its former shadow
    # X=-40.16..-14.76 / Y=-16.51..+40.64 is free board area now.)
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
    # Routing rework (cluster spread): the J1 / Q1 reverse-polarity
    # protection cluster (D1 / F1 / Q1 / D3 / R1 / R4) was jammed
    # courtyard-to-courtyard in the corner east of J1, leaving no room
    # for traces to escape the pads — ~7 signal nets were unroutable
    # across three independent Freerouting attempts.
    #
    # The corridor east of J1 is bounded X +9.15..+23.22 (J1 east edge ..
    # SEN66 zone west edge), Y +8..+43.5 (chord). HOWEVER the C2 case-wall
    # cutout occupies X +1.1..+16.8, Y +27.2..+43.5 and is exported to
    # Freerouting as a HARD copper keepout (a keepout-type zone exports as
    # a Specctra DSN keepout regardless of its `tracks allowed` sub-rule).
    # Any component placed inside that box has UNROUTABLE pads — this is
    # the real reason Freerouting could never close the cluster nets.
    #
    # Fix: spread the six parts entirely within the ROUTABLE region:
    #   - north band  : X +9.15..+23.22, Y +12..+27.2 (clear; the AQI LED
    #     ring — D12 at (+11.67,+11.67) — eats the SW corner up to ~Y +14)
    #   - east strip  : X +16.8..+23.22, Y +27.2..+42 (east of the C2
    #     cutout, so the keepout does not apply)
    # D1 / F1 / Q1 go in the north band; the gate network D3 / R4 / R1
    # forms a vertical column in the east strip. Generous courtyard gaps
    # (>=1.7 mm) give every pad a clear escape lane.
    #
    # D1 (SMBJ24A TVS, SMB ~7.4 x 4.6 courtyard) — north band, top row at
    # (+14, +17). Courtyard X +10.3..+17.7, Y +14.7..+19.3 — north edge
    # +14.7 clears the D12 LED courtyard top (~+14.2). Rotation 180 keeps
    # pad 1 (cathode, KiCad D_SMB KLC) on the EAST physical side, facing
    # the Q1 source.
    parts.append(gen_diode_smb_pcb_footprint(
        x=+17, y=+22.5, rotation=90,
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
    # v0.50 placement rework: Q1 sits in the RIGHT protection-cluster
    # column, between F1 (north) and D1 (south). The cluster is two
    # side-by-side columns (right: F1/Q1/D1; left: gate network D3/R4/R1)
    # instead of one tall stack.
    # v0.53 (issue #2): both columns moved 3 mm WEST (right X=+20→+17, left
    # X=+15→+12) tracking the SEN66 recess cutout, whose west edge is at
    # X=+20.5. The widest right-column courtyard is D1's SMB (half-X 2.25 mm
    # at rotation 90) → east courtyard edge +19.25, i.e. 1.25 mm clear of the
    # cutout west edge. Left column west edge (R1/R4 0603, half-X ~0.8, +12)
    # clears the J1 terminal-block east edge (+9.15) by ~2.05 mm.
    parts.append(gen_sot23_3pin_pcb_footprint(
        x=+17, y=+15.5, rotation=90,
        reference="Q1", value="AO3401A",
        uuid_tag="q1-pmos",
        descr="P-MOSFET reverse-polarity protection. SOT-23. AO3401A: Vds=-30 V, Vgs=±12 V, RDS(on)=60 mΩ @ Vgs=-10 V.",
    ))
    # D3 — Q1 gate-source Zener clamp. v0.50 placement rework: NORTH end
    # of the LEFT protection-cluster column (gate network D3/R4/R1),
    # rotated 90; the right column carries F1/Q1/D1. v0.53: left column
    # X=+15→+12 (see the cluster note above D1). D3.2 (cathode,
    # gate-junction net D3-A) faces SOUTH toward R4/R1.
    parts.append(gen_diode_sod323_pcb_footprint(
        x=+12, y=+16.5, rotation=90,
        reference="D3", value="10V Zener 200mW",
        uuid_tag="d3-zener",
        descr="10 V Zener clamp on Q1 gate-source to keep |Vgs| ≤ 10 V (v0.37 — was 18V pre-fix; AO3401A Vgs_max=±12V).",
    ))
    # F1 — PTC polyfuse, Littelfuse 1812L075/33DR (LCSC C151170, 33 V /
    # 750 mA hold / 1.5 A trip, 1812 SMD). v0.42 land pattern moved off
    # KiCad stock `Fuse:Fuse_1812_4532Metric` to the project-local
    # `oas:Fuse_1812L_4532Metric` — the stock generic IPC land (pad gap
    # 3.15 mm) mismatched this part's terminal geometry (gap 2.30 mm),
    # tripping JLCPCB DFM "pin inner edge". See gen_fuse_1812l_pcb_footprint.
    # Body 4.55 x 3.24 mm, courtyard ~5.6 x 3.9 mm. v0.50 placement
    # rework: F1 is the NORTH end of the RIGHT protection-cluster column
    # (F1/Q1/D1); the gate network D3/R4/R1 forms the left column -- two
    # columns instead of one tall stack. v0.53: right column X=+20→+17
    # (see the cluster note above D1).
    parts.append(gen_fuse_1812l_pcb_footprint(
        x=+17, y=+9.5, rotation=90,
        reference="F1", value="1812L075/33DR",
        uuid_tag="f1-ptc",
        descr="PTC polyfuse 750 mA hold / 1.5 A trip / 33 V (Littelfuse 1812L075/33DR, LCSC C151170, 1812 SMD).",
    ))
    # R4 (gate series) and R1 (gate pulldown) continue the LEFT
    # protection-cluster column (X=+12 as of v0.53), below D3, both rotated
    # 90. The gate-junction net D3-A runs the column axis X=+12 (D3.2 --
    # R4.2 -- R1.1 align). R4.1 (north) carries Net-(Q1-G) across to the Q1
    # gate in the right column; R1.2 (south) is the GND pulldown leg (pour).
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+12, y=+21.5, rotation=90,
        reference="R4", value="1k",
        uuid_tag="r4-gate-series",
        descr="1 kΩ gate series resistor between Q1.G and Vgs clamp junction.",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+12, y=+26.5, rotation=90,
        reference="R1", value="100k 1%",
        uuid_tag="r1-gate-pulldown",
        descr="100 kΩ 1% gate-GND pulldown for Q1 (P-MOSFET reverse-polarity).",
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
    #   Row Y=-30.8 : north flank — small HF caps, I²C pullups, R7
    #   Row Y=-34.5 : Buck1 satellites — D2 (SMA), L1 (5x5 SMD inductor)
    #   Row Y=-40.5 : Buck2 main — U2 (SOT-583), L2 (5x5), R2, R3
    #   Row Y=-43.5 : south flank — small HF caps near J6 pad row
    #
    # v0.44: the four rows were respread toward the ESP32 centreline (was
    # -30 / -37 / -44 / -46). Pre-v0.44 the -46 and -44 rows sat only 2 mm
    # apart hard against the J6 pin-header THT pad row — JLCPCB DFM
    # ("tht to smd", jlcdfm.com) flagged 18 Danger (SMD pad edge 1.26-1.88 mm
    # from a J6 THT pad). New row pitch keeps every SMD pad clear of both
    # J5 / J6 THT pad rows; the 6.0x5.5 mm L1 / L2 inductor courtyards set
    # the inter-row spacing (-40.5 ↔ -34.5 = 6.0 mm).
    #
    # IMPORTANT: ESP32 pin socket pad rows (J5 at Y=-25.97 pads y∈[-27.74,
    # -24.20]; J6 at Y=-48.83 pads y∈[-50.60, -47.06]) block SMD placement
    # in those Y bands. Usable inside-ESP32 SMD strip: Y ∈ [-47, -28]
    # (with ~0.5 mm margin from pin pads).
    #
    # C2 (Y2 GND-Earth_Protective) sits OUTSIDE the daughterboard, at
    # (-32, -25) in the strip west of ESP32 west edge.

    # ---- v0.26: C1 placed south-east of SEN66, on the V_24V_PROT net ----
    # The audit's "west-of-ESP32 column at X=-34" zone (used by U1, C3) was
    # under the (since-removed, issue #7) MIKROE-2462 NFC daughterboard
    # shadow at Y > -16.51 — so C1 could not share that column.
    # C1 lives on the protected-rail net (downstream of Q1 reverse-polarity
    # FET, upstream of U1.VIN through C3). Position (+40, +36) sits south
    # of J3 (JST GH SEN66 socket at +36, +27 — its crty extends to PCB Y
    # +30.2 max; gap 1.55), east of C5 case-wall cutout (+27.9..+35.4;
    # gap 0.35 — tight but clear), west of C10 0603 (now relocated to
    # +46, +32) and mounting hole H1 at +47.631 / +27.5 (distance ~13.1 mm).
    # PCB outline corner (+44.25, +40.25): distance 59.82 — 0.18 mm inside.
    # v0.43: C1 nudged ~4 mm EAST (to +37) to open room in the NE radial
    # cluster for C3, which is relocated here from the LD2410-north pocket
    # (that pocket is taken over by J2). C1 and C3 are the same part
    # (100 µF / 50 V, 8 mm radial); they sit as a pair in the NE corner.
    parts.append(gen_capacitor_polarized_radial_pcb_footprint(
        x=+35.75, y=-39, rotation=0,
        reference="C1", value="100uF/50V",
        uuid_tag="c1-protected-bulk",
        diameter_mm=8.0, pitch_mm=3.5,
        descr="100 µF / 50 V radial electrolytic bulk on protected +24V rail. v0.43: hand-tuned into the NE radial cluster (body centre +35.75, -39), paired with C3.",
    ))
    # C3 (U1.VIN input bulk) — v0.43: relocated from the LD2410-north
    # pocket (now occupied by J2) to the NE corner next to C1, out of every
    # daughterboard shadow (C3 is a ~12 mm-tall radial — must stay clear of
    # the ESP32 / SEN66 shadows per the v0.26 relocation rule).
    parts.append(gen_capacitor_polarized_radial_pcb_footprint(
        x=+25.75, y=-39, rotation=0,
        reference="C3", value="100uF/50V",
        uuid_tag="c3-u1-vin-bulk",
        diameter_mm=8.0, pitch_mm=3.5,
        descr="100 µF / 50 V radial electrolytic input bulk for U1 buck. v0.43: relocated to the NE radial cluster next to C1 (body centre +25.75, -39) — the prior LD2410-north spot is now occupied by J2.",
    ))

    # ---- v0.26: U1 in west-of-ESP32 strip ----
    parts.append(gen_to263_5_pcb_footprint(
        x=-38.03, y=-34.014, rotation=180,
        reference="U1", value="LM2596S-5.0",
        uuid_tag="u1-lm2596",
        descr="LM2596S-5.0 5 V 3 A asynchronous step-down buck (TI), TO-263-5. v0.50-routing-rework: hand-placed in KiCad — rotated 180° and shifted ~3 mm west to (-38.03, -34.014) to relieve buck fan-out congestion. The 180° flip points the 5-lead row east toward the ESP32 fan-out zone; the compensating westward shift keeps the body clear of the LD2410 east edge.",
    ))
    # ---- v0.50 Task-3 re-spread: buck section under the ESP32 ----
    # The 20 SMD power-section parts are re-placed into a clean 2-row
    # grid inside the user rectangle (PCB-local X[-27.5,+20.5],
    # Y[-44.5,-30] -- the gap between the ESP32 J5 and J6 pin rows).
    # Row N at Y=-33.5, Row S at Y=-40.7 leave a ~5.7 mm horizontal
    # routing corridor; every courtyard clears the J5 row (north) and
    # the J6 row (south) by >=3.6 mm. West->east follows the power
    # flow: buck1 (D2/L1) west, buck2 (U2 cluster) centre, ESP32 +3V3
    # decoupling + I2C pull-ups east. U1/C1/C3/C4/C10 out of scope.
    #   Row S (Y=-40.7): L1 C14 C5 C15 U2 C7 L2 C6 C9 C2
    #   Row N (Y=-33.5): D2 C13 C8 R2 R3 C16 C17 R5 R6 R7
    # D2 -- buck1 freewheel diode (Row N west, above L1).
    parts.append(gen_diode_sma_pcb_footprint(
        x=-23.1, y=-33.5, rotation=0,
        reference="D2", value="SS14",
        uuid_tag="d2-schottky",
        descr="SS14 Schottky diode 40 V / 1 A, SMA, freewheeling for U1 buck.",
    ))
    parts.append(gen_inductor_smd_5x5_pcb_footprint(
        x=-23.1, y=-40.7, rotation=0,
        reference="L1", value="33uH",
        uuid_tag="l1-buck1",
        descr="33 µH ≥2 A SMD shielded power inductor (Wurth WE-PD-S or eq).",
    ))
    # ---- C4 in the NE radial cluster, east of ESP32 / north of SEN66 ----
    # v0.43: position hand-tuned in KiCad alongside C1/C3/C10 to pack the
    # 4-cap NE cluster, then transcribed back here (body-centre coords).
    parts.append(gen_capacitor_polarized_radial_pcb_footprint(
        x=+25.568, y=-48, rotation=0,
        reference="C4", value="220uF/10V",
        uuid_tag="c4-u1-vout-bulk",
        diameter_mm=6.3, pitch_mm=2.5,
        descr="220 µF / 10 V radial electrolytic output bulk on +5V rail. v0.43: hand-tuned into the NE radial cluster (body centre +25.568, -48).",
    ))

    # ---- Buck2 (TPS62933) cluster ----
    # U2 + the power chain on Row S; the BST/SS caps and the FB divider
    # (R2/R3) on Row N directly above. Row S order U2 -> C7(BST) ->
    # L2(SW) keeps the switch node compact.
    parts.append(gen_sot583_pcb_footprint(
        x=-5.8, y=-40.7, rotation=0,
        reference="U2", value="TPS62933",
        uuid_tag="u2-tps62933",
        descr="TPS62933 5 V→3.3 V synchronous buck (TI), SOT-583/VSON-8.",
    ))
    parts.append(gen_inductor_smd_5x5_pcb_footprint(
        x=+3.3, y=-40.7, rotation=0,
        reference="L2", value="2.2uH",
        uuid_tag="l2-buck2",
        descr="2.2 µH ≥2 A SMD shielded power inductor for U2 buck.",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=-8.05, y=-33.5, rotation=0,
        reference="R2", value="100k",
        uuid_tag="r2-fb-top",
        descr="FB top divider for TPS62933 (sets +3.3V).",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=-3.65, y=-33.5, rotation=0,
        reference="R3", value="30.9k",
        uuid_tag="r3-fb-bot",
        descr="FB bottom divider for TPS62933 (sets +3.3V).",
    ))

    # ---- HF bypass + bulk caps ----
    # C13 (U1 VIN HF) Row N; C14 (+5V HF) Row S; C9 (ESP32 +3V3 bulk)
    # Row S east; C17 (ESP32 +3V3 HF) Row N east by the I2C pull-ups.
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-16.85, y=-33.5, rotation=0,
        reference="C13", value="100nF",
        uuid_tag="c13-u1-vin-hf",
        descr="100 nF input HF ceramic bypass at U1.VIN (paired with C3).",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-17.7, y=-40.7, rotation=0,
        reference="C14", value="100nF",
        uuid_tag="c14-u1-vout-hf",
        descr="100 nF HF ceramic bypass on +5V rail (paired with C4).",
    ))
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=+13.5, y=-40.7, rotation=0,
        reference="C9", value="10uF",
        uuid_tag="c9-esp32-bulk",
        descr="10 µF 0805 ceramic bulk on ESP32 +3V3.",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=+5.15, y=-33.5, rotation=0,
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
        x=+9.55, y=-33.5, rotation=0,
        reference="R5", value="4.7k",
        uuid_tag="r5-i2c-sda-pullup",
        descr="I²C SDA 4.7 kΩ pull-up to +3V3 (v0.22 spec — sized for bus rise time at realized ~60-100 mm bus length, see CLAUDE.md M1).",
    ))
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+14.0, y=-33.5, rotation=0,
        reference="R6", value="4.7k",
        uuid_tag="r6-i2c-scl-pullup",
        descr="I²C SCL 4.7 kΩ pull-up to +3V3 (v0.22 spec — see R5).",
    ))
    # R7 — GPIO 8 boot-strap 10 kΩ pull-up to +3V3 (v0.22, Task #18 M2).
    # See R7 schematic block for rationale.
    parts.append(gen_resistor_0603_pcb_footprint(
        x=+18.4, y=-33.5, rotation=0,
        reference="R7", value="10k",
        uuid_tag="r7-gpio8-bootstrap-pullup",
        descr="GPIO 8 boot-strap 10 kΩ pull-up to +3V3 (v0.22, see CLAUDE.md M2). Replaces the DevKitM-1's onboard pull-up that doesn't work in OAS (VCC_5V unpowered).",
    ))

    # ---- Buck2 VIN/VOUT caps ----
    # C5/C15 (VIN, Row S west of U2), C6/C16 (VOUT, +3.3V rail),
    # C7 (BST, Row S between U2 and L2), C8 (SS, Row N above U2).
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=-13.6, y=-40.7, rotation=0,
        reference="C5", value="10uF",
        uuid_tag="c5-u2-vin-bulk",
        descr="10 µF 0805 ceramic input bulk for U2.VIN (+5V).",
    ))
    # C15 -- buck2 VIN HF bypass, Row S between C5 and U2.
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-9.5, y=-40.7, rotation=0,
        reference="C15", value="100nF",
        uuid_tag="c15-u2-vin-hf",
        descr="100 nF input HF ceramic bypass at U2.VIN.",
    ))
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=+9.05, y=-40.7, rotation=0,
        reference="C6", value="22uF",
        uuid_tag="c6-u2-vout-bulk",
        descr="22 µF 0805 ceramic output bulk on +3.3V rail.",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=+0.75, y=-33.5, rotation=0,
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
        x=-2.1, y=-40.7, rotation=0,
        reference="C7", value="100nF",
        uuid_tag="c7-u2-bst",
        descr="Bootstrap cap C(BST) between U2.SW and U2.BST. REQUIRED.",
    ))
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=-12.45, y=-33.5, rotation=0,
        reference="C8", value="47nF",
        uuid_tag="c8-u2-ss",
        descr="Soft-start cap C(SS) between U2.SS and GND. Sets ramp time.",
    ))

    # ---- C2 (Y2 safety cap) ----
    # v0.50 Task-3: re-placed at the east end of Row S (+18.0, -40.7),
    # under the ESP32 shadow. C2 bridges GND <-> Earth_Protective; its
    # Earth_Protective trace runs back to J1.3 (24 V terminal block).
    parts.append(gen_capacitor_0805_pcb_footprint(
        x=+18.0, y=-40.7, rotation=0,
        reference="C2", value="10nF Y2",
        uuid_tag="c2-y2",
        descr="10 nF Y2 safety class — GND ↔ Earth_Protective EMI bridge. v0.50 Task-3: re-placed at the east end of Row S (+18.0, -40.7).",
    ))

    # Sensor decoupling caps: C10 (SEN66 +3V3), C11 (LD2410 +5V).
    # v0.26: C10 shifted from (+42, +33) to (+46, +32) to clear C1
    # (relocated to (+40, +36) — 12 mm-tall D8 radial bulk for the
    # protected +24V rail). New C10 position sits east of C1 (gap 0.75
    # mm), south of J3 (gap to J3 east edge +41.98 = 2.02 mm), west of
    # mounting hole H1 at (+47.631, +27.5) (distance 5.21 mm, gap 1.36
    # mm after H1 2.85 + C10 1.0 keep-clear).
    parts.append(gen_capacitor_0603_pcb_footprint(
        x=+32, y=-47, rotation=0,
        reference="C10", value="100nF",
        uuid_tag="c10-sen66-decoupling",
        descr="100 nF local decoupling for SEN66 (J3 +3V3 pin 1/6). v0.43: hand-tuned to (+32, -47) in the NE radial cluster.",
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
        x=-52.5, y=+14.0, rotation=270,
        reference="C11", value="100nF",
        uuid_tag="c11-ld2410-decoupling-pcb",
        descr="100 nF local decoupling for LD2410 (J4 pin 5 / +5V). v0.45: vertical, placed at the 11-o'clock of J4's west end — west of the LD2410 body (LDR1, X>=97.4) in open copper. Nudged 0.5 mm north of the v0.44 spot (Y +14.5 -> +14.0) — the v0.44 position left C11.1 only 2.98 mm from the nearest J4 THT pad (JLCDFM 'tht to smd' warning); +0.5 mm lifts that to ~3.4 mm, clear of the >3.05 mm rule. North field is open (no neighbour within 4 mm).",
    ))
    # (C12 — the NFC +3V3 decoupling cap — was removed together with the
    # MIKROE-2462 daughterboard, issue #7.)

    # J2 — DNP recovery pin header. v0.43: relocated from the cramped NW
    # corner to the free pocket NORTH of the LD2410, placed HORIZONTAL
    # (rotation 90 → pad row along PCB +X). See the J2_PCB_* block in
    # _project.py for the placement rationale. The horizontal row lets the
    # per-pin signal labels go on real F.SilkS (gen_silk_labels).
    parts.append(gen_pinheader_6_recovery_pcb_footprint(
        x=J2_PCB_X, y=J2_PCB_Y, rotation=J2_PCB_ROTATION,
        reference="J2", value="UART/Boot Recovery (DNP)",
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
    # expansion socket. Lives in the C2 RJ45 / Ethernet cutout; mouth
    # faces PCB +Y (chord side, case wall) so the cable plugs in from
    # outside the case. See `J9_PCB_*` constants near the top of the file.
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
    # ~8 mm above OAS PCB. Antenna tab overhangs the WEST short edge
    # (Y=anchor_y side after rotation → PCB -X), USB-C at the other short
    # edge. v0.53 (issue #3): F.Fab carries the TRUE outline incl. the
    # ESP32-C6-MINI-1 antenna tab. F.SilkS carries CORNER TICKS since the
    # pin-offset fix (5.37 → 1.575, see _project.py HISTORY): the body is
    # fully on-board now (NW corner 1.364 mm inside R60), but a FULL silk
    # rect is still impossible — the west short edge would cross the U1
    # lead-pad ends (X −31.55..−28.05) and the J5/J6 socket-frame ends
    # (X −30.22), and the east short edge skirts the C2 pad column
    # (~X +17.6). The four L-ticks mark the corners and skip those
    # congested mid-spans.
    parts.append(_emit_daughterboard_reference_pcb_footprint(
        lib_id="oas:ESP32-C6-DevKitM-1_Reference",
        reference="MOD1",
        descr="ESP32-C6-DevKitM-1-N4 daughterboard shadow (EAN 5904422385651). Body 25.4×48.26 mm + 13.20×5.37 mm antenna tab; 8.6 mm tall; mounts on 2×1x15 P2.54 mm female pin sockets. Pin block offset 1.575 mm from the antenna edge (48.26 − 14×2.54 − 11.125) per Espressif dimensions PDF.",
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
        antenna_tab_w=ESP32_ANTENNA_TAB_W,
        antenna_tab_protrusion=ESP32_ANTENNA_TAB_PROTRUSION,
        emit_silk_outline="corners",
    ))

    # (MOD2 — the MIKROE-2462 NFC daughterboard shadow reservation — was
    # removed together with the NFC feature, issue #7.)

    # Female pin sockets for the ESP32 daughterboard.
    # The daughterboard mates with 2 parallel pin rows on OAS PCB.
    # Pad positions match the daughterboard's onboard pin headers (see the
    # respective body comments above for pin layout per datasheet).
    #
    # ESP32-C6 DevKitM-1 — 2×1×15, row spacing 22.86 mm, pitch 2.54 mm,
    # pin block offset 1.575 mm from antenna short edge (= LIB Y=0; see
    # the _project.py HISTORY note — was wrongly 5.37 until the issue-#3
    # review).
    # In PCB after helper rotation 90, LIB +Y → PCB +X, LIB +X → PCB -Y.
    # Row A (LIB X = 1.27): pin row along PCB X at PCB Y = anchor_y - 1.27.
    # Row B (LIB X = body_w - 1.27 = 24.13): PCB Y = anchor_y - 24.13.
    # Pin 1 of each row at PCB X = anchor_x + 1.575 = -28.89 — the
    # PHYSICAL datum: net 6.5 mm west of the v0.51 boards' -22.39 (the
    # user-measured 7.5 mm move, trimmed 1.0 mm back east after a live fit
    # check — see ESP32_ANCHOR_X in _project.py); the offset fix re-derived
    # the anchor, NOT the socket position.
    esp32_row_a_y = ESP32_ANCHOR_Y - ESP32_PIN_ROW_INSET                    # -25.97
    esp32_row_b_y = ESP32_ANCHOR_Y - (ESP32_BODY_W - ESP32_PIN_ROW_INSET)   # -48.83
    esp32_row_x_start = ESP32_ANCHOR_X + ESP32_PIN_START_OFFSET             # -28.89
    parts.append(gen_pinsocket_pcb_footprint(
        pin_count=ESP32_PIN_COUNT_PER_ROW,
        x=esp32_row_x_start, y=esp32_row_a_y, rotation=90,
        reference="J5",
        value="ESP32 row A (pins 1..15, antenna-side row)",
        descr="Stock 1x15 P2.54 mm female pin socket. ESP32-C6 DevKitM-1-N4 plugs into this row + J6 (other row). Pin block offset 1.575 mm from antenna short edge per Espressif dimensions PDF.",
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

    # (J7/J8 — the MIKROE-2462 mikroBUS socket pair — was removed together
    # with the NFC feature, issue #7.)

    # AQI status LED ring — 7 x SK6812-SIDE on a Ø26 mm pitch circle (8
    # slots at 45 deg pitch, one skipped at θ=90 deg for the J1 cable
    # area), each LED radiating outward into the AK-N-94 perforated
    # cover. Plus one 100 nF 0402 decoupling cap per LED, sited radially
    # inward from each LED so the cap pads are positioned near the
    # corresponding VDD pad.
    #
    # Skip at index 2 (D13, θ=90 deg, PCB (0, +13)) and its decoupling
    # cap (C22). The freed-up corridor lets the 24 V supply cable from
    # the central Ø12 mm hole reach the J1 terminal block which sits
    # SOUTH of the LED ring, between the ring and the chord-edge
    # cutouts. (Audit-19, 2026-05-19: was D14 skipped at i=3 in the
    # prior 12x30 deg ring; reduced to 8x45 deg for cheaper SMT
    # placement on standard-multiple angles.)
    for i in range(LED_RING_COUNT):
        if i in LED_RING_SKIP_INDICES:
            continue
        led_x, led_y, led_rot = _led_ring_position(i)
        led_ref = f"D{11 + i}"      # D11..D18 (D1..D5 used by power section)
        parts.append(gen_sk6812_side_pcb_footprint(
            x=led_x, y=led_y, rotation=led_rot,
            reference=led_ref,
            uuid_tag=f"led-ring-{led_ref}",
            show_pin_labels=(i == 0),  # D11 = visual reference for orientation verification
        ))
        cap_x, cap_y, cap_rot = _led_cap_position(i)
        cap_ref = f"C{20 + i}"      # C20..C27
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
      - "SEN66 air quality"  — names the SEN66 recess-cutout zone
      - "SEN66 SIN-T"        — SEN66 module MPN (east rim, vertical)
      - board name + version — SE pocket identification block
      - LD2410 body / antenna labels
    (No "-> J3" / "to SEN66" cable-direction arrows — dropped in v0.9;
    the J3 designator + F.Fab connector value carry that context.)

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

    def _pin_labels(*, origin_x: float, origin_y: float, rotation: float,
                    pin1_local: tuple[float, float],
                    step_local: tuple[float, float],
                    pin_map: dict[int, str],
                    label_offset: tuple[float, float],
                    layer: str, tag: str,
                    size: float = 0.8, angle: float = 0.0) -> list[str]:
        """Emit one `gr_text` per connector pin.

        Every pad's PCB position is DERIVED from the footprint placement
        (origin + rotation) via `_rotate_local`, so a per-pin label can
        never disagree with where the pad physically lands — no hand-typed
        coordinates. `pin1_local` is pad 1 in footprint-local mm,
        `step_local` the local delta to the next pad; `label_offset` is a
        PCB-space nudge applied to every label to clear the pad row.
        """
        out: list[str] = []
        for pin, text in sorted(pin_map.items()):
            lx = pin1_local[0] + (pin - 1) * step_local[0]
            ly = pin1_local[1] + (pin - 1) * step_local[1]
            rdx, rdy = _rotate_local(lx, ly, rotation)
            out.append(_silk(text,
                             origin_x + rdx + label_offset[0],
                             origin_y + rdy + label_offset[1],
                             f"{tag}-p{pin}", size=size, layer=layer,
                             angle=angle))
        return out

    parts = []
    # SEN66 body label. v0.53 (issue #2): the SEN66 body shadow is now a real
    # recess cutout, so this label can no longer sit inside the body. Moved to
    # the rim band just SOUTH of the cutout (south edge +23.0) and NORTH of
    # the J3 cable slot (north edge +28.0) — a ~3.4 mm clear strip.
    # Centred horizontally on the cutout mid-X = anchor_x + SEN66_BODY_Y/2.
    # v0.53-c (user change order): text switched from "SEN66 air quality"
    # to the module MPN "SEN66 SIN-T" — the MPN identifies the exact part
    # to a stranger holding the board, where "air quality" said little.
    # (The former dedicated MPN label on the east rim is gone — this label
    # now carries that duty; uuid tag "sen66-body" kept, no UUID churn.)
    body_mid_x = SEN66_ANCHOR_X + SEN66_BODY_Y / 2
    parts.append(_silk("SEN66 SIN-T", body_mid_x, +24.6, "sen66-body"))
    # ---- Board identification block (F.SilkS, west pocket) ----
    # v0.53-c (user change order): the name + version block moved from the
    # SE pocket (where the new J3 cable slot displaced the long name line)
    # into the west pocket freed by the NFC removal (issue #7), joined by
    # the public repo URL — a physical board now self-documents where its
    # sources live. (First iteration used a QR code here; replaced by
    # plain text per user decision — the QR needed a filled-poly
    # exemption in the stage-13 silk lifter plus scan-polarity care,
    # while text needs nothing.) Pocket clearance survey lives at
    # BOARD_ID_* in _project.py. Five rows centred on the block anchor:
    # name, version, then the URL split at its slashes (a single 53-char
    # line at the 1.0 mm min_text_height would be ~72 mm wide). Name /
    # version / URL strings come from _common.py — single source of
    # truth, bump OAS_VERSION_LINE on each release tag.
    _id_rows = (OAS_NAME_SHORT, OAS_VERSION_LINE) + OAS_REPO_URL_SILK_LINES
    _id_tags = ("board-id-name", "board-id-version",
                "board-id-url-1", "board-id-url-2", "board-id-url-3")
    _id_y0 = BOARD_ID_CENTER_Y - (len(_id_rows) - 1) * BOARD_ID_ROW_PITCH / 2
    for _id_i, (_id_text, _id_tag) in enumerate(zip(_id_rows, _id_tags)):
        parts.append(_silk(_id_text, BOARD_ID_CENTER_X,
                           _id_y0 + _id_i * BOARD_ID_ROW_PITCH,
                           _id_tag, size=1.0))
    # No separate "-> J3" / "to SEN66" cable-direction arrows are emitted
    # (dropped back in v0.9). The J3↔SEN66 relationship is documented by the
    # J3 "J3" designator + its F.Fab value "JST SM06B-GHS-TB (SEN66
    # connector)" and by the "SEN66 SIN-T" board label; the cable slot east
    # of J3 carries its own "SEN66 lead" hint (see below).

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

    # (v0.53-c: the former dedicated MPN label on the east rim — vertical
    # "SEN66 SIN-T" at (+52, -20), uuid tag "sen66-mpn" — was REMOVED per
    # user change order; the "sen66-body" label south of the cutout now
    # reads "SEN66 SIN-T" and carries the MPN duty alone.)

    # ---- J3 cable-slot hint (v0.53-c, issue #2 follow-up) ----
    # The pass-through slot east of J3 (J3_CABLE_SLOT_* in _project.py)
    # is a non-obvious feature — an unlabeled internal hole reads as a
    # mistake. A short vertical hint on the 5 mm FR4 web between J3 and
    # the slot names what passes through: the SEN66 module's lead, up
    # from the back side and west into J3's mouth. Centred on the web
    # (X = (J3 east courtyard 19.70 + slot west edge 24.70)/2 = 22.20)
    # at J3_Y. Size 1.0 (the board min_text_height — 0.8 trips the DRC
    # text_height check); 10 chars span ~Y 26.7..40.3, the text column
    # (X ±0.65) stays ~1.85 mm off both the courtyard and the slot edge,
    # and the north end clears D1's silk by >1 mm.
    parts.append(_silk("SEN66 lead",
                       (J3_X + _J3_COURTYARD_HALF_X + J3_CABLE_SLOT_X_MIN) / 2,
                       J3_Y, "j3-slot-hint", size=1.0, angle=90.0))

    # ---- v0.15.8: ESP32 body-label board (the MIKROE-2462 body label
    # left with the NFC removal, issue #7).
    # v0.22 moved this label to F.Fab (was F.SilkS): back then the body
    # center sat directly over power-section SMD pads, tripping
    # silk_over_copper DRC. v0.53-c restores it to F.SilkS (user change
    # order — the board had no printed ESP32 identification): after the
    # v0.50 buck re-spread the body center falls in the ~5.7 mm routing
    # corridor BETWEEN the two buck component rows (row A at Y=-33.5,
    # row B at Y=-40.7), and the v0.53 module move west shifted the text
    # with it. The exact body-centre Y (-37.4) grazed L2's silk frame
    # (north edge ≈-37.9, DRC silk_overlap), so the label is nudged
    # +1.3 mm south of dead-centre to the SILK corridor midpoint: L2/L1
    # silk north edges ≈-37.9, row-A 0603 silk south edges ≈-34.2 ->
    # centre -36.1, text band ≈-36.8..-35.4 clears both by >1 mm (and
    # every pad by >1.4 mm). The label sits under the socketed
    # daughterboard (~8.6 mm standoff), readable at an angle and during
    # assembly.
    esp32_body_cx = ESP32_ANCHOR_X + ESP32_BODY_L / 2.0
    esp32_body_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0 + 1.3
    parts.append(_silk("ESP32-C6 DevKitM-1", esp32_body_cx, esp32_body_cy,
                       "esp32-body", size=1.0))
    # ESP32 USB-C ("USB") short-edge hint on F.Fab. The "ant" antenna-
    # edge hint was removed in v0.50 Task-3 (not needed, and the buck
    # re-spread put L1 in that spot). LIB (body_w/2, body_l - 6.0)
    # after rotation 90.
    esp32_usb_cx = ESP32_ANCHOR_X + (ESP32_BODY_L - 6.0)
    esp32_usb_cy = ESP32_ANCHOR_Y - ESP32_BODY_W / 2.0
    parts.append(_silk("USB", esp32_usb_cx, esp32_usb_cy,
                       "esp32-usb", size=1.0, layer="F.Fab"))

    # v0.41 2026-05-19: "AQI ring" silk text removed. After LED rotation
    # fix (emission outward → pads moved inward radially), the pads of
    # D18 collided with this label's bbox @ R=15.5 mm theta=315°.
    # User confirmed the label is not essential ("nie jest potrzebny
    # totalnie") — the LED ring's visual function is self-evident.

    # ---- v0.41-followup-2 (2026-05-19): J1 mating-plug NO-GO zone silk ----
    # Visible silk rectangle marking the area between J1's mating face
    # (north edge of J1 body) and the central Ø12 cable hole's south
    # edge, bounded west/east by J1 body left/right edges. No LED body
    # or cap may sit inside — the cable-terminal plug needs this clear
    # space. The rectangle is inset 0.4 mm from the exact no-go bounds
    # so the silk lines meet DRC silk_clearance (0.15 mm min) vs J1
    # silk + edge.cuts.
    #   J1 silk geometry (Phoenix MSTBA 2,5/3-G-5,08): the silk body rectangle
    #   LIB X range is [-3.65, +13.81] (slightly wider than the F.Fab body
    #   outline [-3.54, +13.7] by 0.11 mm each side). After rotation 180°
    #   around pin-1 LIB origin: PCB X = J1_PCB_X - LIB_X = +5.08 - LIB_X.
    #   So LIB -3.65 → PCB +8.73, LIB +13.81 → PCB -8.73. Silk X range is
    #   thus the symmetric [-8.73, +8.73] — and this is exactly the visible
    #   J1 silk extent which the plug-clearance no-go zone should cover.
    #
    #   No-go silk rect: vertical edges aligned with J1 silk vertical edges
    #   (X = ±8.73). Y bounds: cable hole south edge (+6.0) + 0.4 mm
    #   silk_clearance offset → top at +6.40; J1 silk mating face north
    #   edge (+22.29 in PCB Y after rotation; the closest J1 silk line
    #   north of J1 body) - 0.4 mm offset → bottom at +21.50.
    nogo_x_w = -8.73
    nogo_x_e = +8.73
    nogo_y_n = +6.40
    nogo_y_s = +21.50
    nogo_stroke = 0.12
    nogo_edges = [
        # (start_x, start_y, end_x, end_y, tag)
        (nogo_x_w, nogo_y_n, nogo_x_e, nogo_y_n, "nogo-n"),  # top
        (nogo_x_w, nogo_y_s, nogo_x_e, nogo_y_s, "nogo-s"),  # bottom
        (nogo_x_w, nogo_y_n, nogo_x_w, nogo_y_s, "nogo-w"),  # left
        (nogo_x_e, nogo_y_n, nogo_x_e, nogo_y_s, "nogo-e"),  # right
    ]
    for (sx, sy, ex, ey, tag) in nogo_edges:
        parts.append(textwrap.dedent(f"""\
            \t(gr_line
            \t\t(start {fx(sx)} {fy(sy)})
            \t\t(end {fx(ex)} {fy(ey)})
            \t\t(stroke (width {fmt(nogo_stroke)}) (type solid))
            \t\t(layer "F.SilkS")
            \t\t(uuid "{U('silk-' + tag)}")
            \t)"""))
    # Centred label inside the rect: identifies the no-go zone as reserved
    # for the J1 mating plug (the female Phoenix MSTB terminal block plug
    # that mates with J1).
    parts.append(_silk(
        "J1 PLUG",
        (nogo_x_w + nogo_x_e) / 2.0,
        (nogo_y_n + nogo_y_s) / 2.0,
        "nogo-label",
        size=1.0,
    ))

    # ---- J1 / J2 / J9 / J10 per-pin silkscreen labels ----
    # Every per-pin label below is positioned by `_pin_labels`, which
    # derives each pad's PCB coordinate from the footprint placement
    # (origin + rotation). The label TEXT comes from the connector pin
    # maps in _project.py — the SAME dicts the schematic generators use —
    # so a silk label can never silently drift from the netlist.

    # J1 — Phoenix MSTBA 2,5/3 terminal block, 3-pin, 5.08 mm pitch,
    # rotation 180°. Pads run along footprint-local +X from pad 1 at the
    # origin; in PCB space pin 1 (24V) lands at +5.08, pin 2 (GND) at 0,
    # pin 3 (PE) at -5.08. The stock Phoenix footprint already prints a
    # pin-1 triangle on F.SilkS; the terminal body silk fills the strip
    # immediately south of the pads and the chord connector J9
    # crowds the rest, so the per-pin 24V/GND/PE labels go on F.Fab
    # (assembly layer — visible in the 2D render, exempt from
    # silk_overlap). The F.SilkS "J1 (24V)" body-id stays printed.
    parts.append(_silk("J1 (24V)", +15.0, J1_PCB_Y, "j1-body-id",
                       size=1.0, layer="F.Fab"))
    parts.extend(_pin_labels(
        origin_x=J1_PCB_X, origin_y=J1_PCB_Y, rotation=J1_PCB_ROTATION,
        pin1_local=(0.0, 0.0), step_local=(5.08, 0.0),
        pin_map=J1_PIN_MAP, label_offset=(0.0, -0.8),
        layer="F.Fab", tag="j1-pin", size=0.8,
    ))

    # J2 — UART/Boot recovery header, 1x06 P2.54 mm. v0.43: relocated
    # HORIZONTAL (rotation 90, pad row along PCB +X) north of the LD2410 —
    # see J2_PCB_* in _project.py. Per-pin signal labels go on real
    # F.SilkS, each rotated 90° (perpendicular to the horizontal pad row —
    # the whole name turned on its side, ~1 mm wide, so it clears the
    # 2.54 mm pitch), placed just NORTH of the row (away from the LD2410).
    parts.extend(_pin_labels(
        origin_x=J2_PCB_X, origin_y=J2_PCB_Y, rotation=J2_PCB_ROTATION,
        pin1_local=(0.0, 0.0), step_local=(0.0, 2.54),
        pin_map=J2_PIN_MAP, label_offset=(0.0, -4.5),
        layer="F.SilkS", tag="j2-pin", size=1.0, angle=90.0,
    ))

    # J9 — Qwiic JST SH 4-pin at 1.0 mm pitch: too fine for four separate
    # readable per-pin texts. The connector is mechanically keyed (the
    # Qwiic cable mates one way only) and follows the universal Qwiic
    # pinout, so a single pin-1 marker is sufficient. Routing rework: J9
    # relocated INTERNAL (east of J10) — the F.Fab pin-1 hint tracks the
    # new J9_PCB_* anchor automatically.
    parts.append(_silk("J9 GND", J9_PCB_X + 1.5, J9_PCB_Y, "j9-p1-gnd",
                       size=0.8, layer="F.Fab"))
    # v0.50-rework: J9 lost its F.SilkS identity when the C2 cutout (whose
    # silk label named it) was removed. Add a direct "J9" F.SilkS label
    # south of the connector body so the connector stays identified per
    # the silkscreen convention.
    parts.append(_silk("J9", J9_PCB_X, J9_PCB_Y + 5.0, "j9-id",
                       size=1.0, layer="F.SilkS"))

    # J10 — native-USB recovery header, 1x06 P2.54 mm, rotation 90° (pad
    # row along PCB +X, pad 1 at the origin). v0.43: per-pin signal labels
    # moved to real F.SilkS, each rotated 90° (perpendicular to the
    # horizontal row — the whole name turned on its side, ~1 mm wide, so
    # it clears the 2.54 mm pitch), placed just SOUTH of the pad row.
    parts.extend(_pin_labels(
        origin_x=J10_PCB_X, origin_y=J10_PCB_Y, rotation=J10_PCB_ROTATION,
        pin1_local=(0.0, 0.0), step_local=(0.0, 2.54),
        pin_map=J10_PIN_MAP, label_offset=(0.0, +3.8),
        layer="F.SilkS", tag="j10-pin", size=1.0, angle=90.0,
    ))
    # J10 connector ID — moved EAST of the pad row (user request: the old
    # placement, 7.5 mm SOUTH of the pads, had drifted far from the
    # connector). Pad 6 sits at PCB X = J10_PCB_X + 5·2.54 = +1.74; the
    # label is centred just east of it on the pad-row Y.
    parts.append(_silk(
        "J10 flash", J10_PCB_X + 5 * 2.54 + 5.2, J10_PCB_Y, "j10-body-id",
        size=1.0,
    ))

    # ---- v0.7: cutout-zone reservation labels + outlines on F.SilkS ----
    # Each cutout in CUTOUTS along the chord is a case-wall opening that
    # hosts a connector (24V terminal, JST GH, USB-C debug, Qwiic, etc.).
    # Draw both:
    #   - A thin F.SilkS rectangle outlining the cutout footprint, inset
    #     by SILK_EDGE_INSET on each side so it clears Edge.Cuts even
    #     when the cutout is clipped at the chord
    #   - A short text label centred in the rectangle identifying what
    #     the cutout hosts ("<name> AUX" default). For narrow rects the
    #     text is rotated 90° so it still fits inside the outline without
    #     overlapping (DRC silk_overlap).
    # CUTOUTS is currently empty (see boardgen/_project.py — the USBC
    # opening left with SW1 in v0.53, GitHub issue #5), so this loop
    # emits nothing today; the mechanism stays for any future opening
    # that hosts a connector again.
    SILK_EDGE_INSET = 0.3       # mm — keeps rect off the board edge.
                                # With 0.12 mm silk stroke, line outer edge
                                # sits 0.06 mm beyond the centerline; 0.3 mm
                                # inset leaves 0.24 mm clear to Edge.Cuts,
                                # comfortably above the 0.15 mm DRC limit.
    SILK_TEXT_MIN_HORIZONTAL_FIT = 5.0   # mm — width needed to keep label
                                          # at 1.0 mm horizontal inside the rect
    for name, x1, x2, y1, y2, allow_pads in CUTOUTS:
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
    # Layout reference (v0.44 — rows respread off the J5/J6 THT pad rows):
    #   Row Y=-30.8  small SMDs (HF caps + I²C pull-ups + R7) — sits in
    #              the strip between J5 silk (Y=-27.30..-24.64) and the
    #              Buck1-satellite row at Y=-34.5. INSIDE the ESP32
    #              daughterboard shadow.
    #   Row Y=-34.5  D2 (SMA), L1 (5x5) — INSIDE ESP32 shadow.
    #   Row Y=-40.5  U2, L2, R2, R3 — Buck2 main, INSIDE ESP32 shadow.
    #   Row Y=-43.5  south flank (C5..C8, C15, C16) — sits above the
    #              J6 silk frame. INSIDE ESP32 shadow.
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
    POWER_LABELS: list[
        tuple[str, float, float, str]
        | tuple[str, float, float, str, float]
    ] = [
        # input-protection cluster (NOT under any daughterboard shadow).
        # Routing rework (cluster spread): the six parts sit in the
        # routable region — D1 (+14,+17) / F1 (+13,+23.5) / Q1 (+19.5,+21)
        # in the north band, and the gate network D3 (+20,+28) / R4
        # (+20,+33) / R1 (+20,+38, all rotated 90 / vertical) as a column
        # in the east strip.
        #   - D1: F.SilkS label SOUTH of the body, in the D1<->F1 gap.
        #   - F1: F.Fab vertical text EAST of the body, in the F1<->Q1
        #     gap (J1 crowds the west side).
        #   - Q1: F.Fab text SOUTH of the body, in the Q1<->D3 gap.
        #   - D3 / R4 / R1: F.Fab text EAST of each body, in the strip
        #     between the east column and the SEN66 zone (+23.22).
        ("D1",  +3.5, 0.0, "F.Fab"),
        ("F1",  +3.7, 0.0, "F.Fab", 90.0),
        ("Q1",  0.0, +3.0, "F.Fab"),
        ("D3",  -2.5,  0.0, "F.Fab"),
        ("R4",  -2.5,  0.0, "F.Fab"),
        ("R1",  -2.5,  0.0, "F.Fab"),
        # Buck1 cluster — NE radial caps (C1, C3, C4, C10).
        # v0.43: printed F.SilkS designators so each cap is identifiable
        # on the assembled board (the cap body covers its own footprint).
        # C1 + C4 have a clear strip toward the board arc → label NORTH of
        # the body. C3 is boxed in on FOUR sides now (C4 N / C1 E / ESP32 W /
        # SEN66-recess-cutout S). v0.53 (issue #2): the recess cutout north
        # edge (Y=-33.95) sits 0.45 mm from the old SE-pocket F.SilkS 'C3'
        # text, and every clear direction runs into the C1/C3 body silk. So
        # 'C3' moves to F.Fab (exempt from silk DRC) — the same remedy already
        # used for the boxed-in C10/C11/C2 designators. The cap is still
        # identified by its body silk + the F.Fab designator (assembly
        # drawing); it stays in the readable 4:30 (SE) pocket.
        ("C1",  0.0, -6.5, "F.SilkS"),
        ("C3",  +4.28, +4.12, "F.Fab", 90.0),
        # U1 (TO-263-5): signal pads at X_local=-7.65 (= PCB X=-41.65),
        # tab pad east at X_local=+1.5 to +6.2 (= PCB X=-32.5..-27.8).
        # Label needs to clear the signal pad column (PCB X=-41.65 ±
        # half pad width 2.3 = -43.95..-39.35) AND clear the tab pad
        # east edge at -27.8. Body Y range ±5 from anchor (PCB Y=-29
        # to -39). Place label SOUTH of body (offset 0, +7) at PCB Y=-27
        # — north of the north-flank row at Y=-30.8 by 3.8 mm (gap to
        # C13 north). That row holds C13/C14/C9/C17/R5/R6/R7; their
        # courtyards extend ~1.5 mm, so Y=-27 leaves ~2.3 mm clear.
        ("U1",  0.0, +7.0,  "F.Fab"),
        # v0.50 Task-3 re-spread: the 20 buck-section designators sit
        # ON each body (dx=dy=0) on F.Fab. At ~3.5 mm part pitch an
        # offset label would collide with its neighbour in the 2D-top
        # render; an on-body F.Fab designator is unambiguous and
        # collision-free. All sit under the ESP32 shadow -> F.Fab
        # (exempt from silk DRC). C2 moves F.SilkS -> F.Fab as it is
        # now under the shadow too.
        ("D2",  0.0, 0.0, "F.Fab"),
        ("L1",  0.0, 0.0, "F.Fab"),
        # C4 — NE radial cluster. F.SilkS designator NORTH of the body,
        # in the open strip toward the board arc.
        ("C4",  0.0, -5.0, "F.SilkS"),
        ("U2",  0.0, 0.0, "F.Fab"),
        ("L2",  0.0, 0.0, "F.Fab"),
        ("R2",  0.0, 0.0, "F.Fab"),
        ("R3",  0.0, 0.0, "F.Fab"),
        ("C9",  0.0, 0.0, "F.Fab"),
        ("C13", 0.0, 0.0, "F.Fab"),
        ("C14", 0.0, 0.0, "F.Fab"),
        ("C17", 0.0, 0.0, "F.Fab"),
        ("R5",  0.0, 0.0, "F.Fab"),
        ("R6",  0.0, 0.0, "F.Fab"),
        ("R7",  0.0, 0.0, "F.Fab"),
        ("C5",  0.0, 0.0, "F.Fab"),
        ("C15", 0.0, 0.0, "F.Fab"),
        ("C6",  0.0, 0.0, "F.Fab"),
        ("C16", 0.0, 0.0, "F.Fab"),
        ("C7",  0.0, 0.0, "F.Fab"),
        ("C8",  0.0, 0.0, "F.Fab"),
        ("C2",  0.0, 0.0, "F.Fab"),
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
        # Historically moved to F.Fab to avoid silk_overlap with the
        # (since-removed, issue #7) MOD2 west silk at X=-40.16.
        ("C11", 0.0, -2.0, "F.Fab"),
        # J2 DNP recovery — v0.43: relocated horizontal north of the
        # LD2410. Designator sits just EAST of the pad row, in the pocket
        # vacated by C3, clear of the per-pin labels (which sit north of
        # the row).
        ("J2",  +15.5, 0.0, "F.SilkS"),
    ]
    # Component anchors mirror the placements in gen_power_pcb_footprints().
    # Keep this dict in lock-step with that function.
    COMPONENT_ANCHORS = {
        # v0.53 (issue #2): protection cluster moved 3 mm west with the
        # SEN66 recess cutout — keep these anchors in lock-step with
        # gen_power_pcb_footprints() (right column X=+17, left column X=+12).
        "D1":  (+17, +22.5),
        "F1":  (+17, +9.5),
        "Q1":  (+17, +15.5),
        "D3":  (+12, +16.5),
        "R4":  (+12, +21.5),
        "R1":  (+12, +26.5),
        "C1":  (+35.75, -39),
        "C3":  (+25.75, -39),
        "U1":  (-38.03, -34.014),
        "D2":  (-23.1, -33.5),
        "L1":  (-23.1, -40.7),
        "C4":  (+25.568, -48),
        "U2":  (-5.8, -40.7),
        "L2":  (+3.3, -40.7),
        "R2":  (-8.05, -33.5),
        "R3":  (-3.65, -33.5),
        "C9":  (+13.5, -40.7),
        "C13": (-16.85, -33.5),
        "C14": (-17.7, -40.7),
        "C17": (+5.15, -33.5),
        "R5":  (+9.55, -33.5),
        "R6":  (+14.0, -33.5),
        "R7":  (+18.4, -33.5),
        "C5":  (-13.6, -40.7),
        "C15": (-9.5, -40.7),
        "C6":  (+9.05, -40.7),
        "C16": (+0.75, -33.5),
        "C7":  (-2.1, -40.7),
        "C8":  (-12.45, -33.5),
        "C2":  (+18.0, -40.7),
        "C10": (+32, -47),
        "C11": (-52.5, +14.0),
        "J2":  (J2_PCB_X, J2_PCB_Y),
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

    # ---- 2) Pin sockets J5/J6 ----
    # Each pin socket lives at one of the two long edges of the ESP32
    # (J5/J6) daughterboard. Place the designator
    # OUTSIDE the daughterboard silk frame, near one short edge of
    # the row, so it remains visible even when the daughterboard plugs
    # in (and during bare-PCB assembly the user can identify which row
    # is which).
    #
    # J5/J6 designators. v0.53 (issue #3): the label X was hardcoded to the
    # old row-1 X (-22.39); it now DERIVES from the pin-row start
    # (ESP32_ANCHOR_X + ESP32_PIN_START_OFFSET) so it follows the -7.5 mm
    # DevKit move. Label sits a further 2 pitches east (≈ over pin 3). Y is
    # unchanged (ESP32_ANCHOR_Y did not move): J5 at Y=-22.5 (NORTH of the
    # J5 pin row at -25.97 and the MOD1 north edge -24.70); J6 at Y=-52.5
    # (SOUTH of the MOD1 south edge -50.10).
    _j5j6_label_x = ESP32_ANCHOR_X + ESP32_PIN_START_OFFSET + 2 * ESP32_PIN_PITCH
    parts.append(_silk("J5", _j5j6_label_x, -22.5, "desig:J5", size=1.0))
    parts.append(_silk("J6", _j5j6_label_x, -52.5, "desig:J6", size=1.0))
    # (J7/J8 designators — the MIKROE-2462 mikroBUS socket pair — were
    # removed together with the NFC feature, issue #7.)

    # ---- 2b) Module connector pin labels ----
    # ESP32 (J5/J6) and LD2410 (J4) plug onto
    # multi-pin rows. Pad positions are DERIVED from the same placement
    # constants the pin sockets are generated from (see
    # gen_sensors_pcb_footprints) via `_pin_labels`, so a label can never
    # disagree with where the pad physically lands.
    #   J5/J6/J4 — only the first + last pad carry a SIGNAL-NAME label
    #     (J*_END_SIGNALS), placed just OUTSIDE the daughterboard body so
    #     the module can be oriented during hand-assembly.
    esp32_row_a_y = ESP32_ANCHOR_Y - ESP32_PIN_ROW_INSET
    esp32_row_b_y = ESP32_ANCHOR_Y - (ESP32_BODY_W - ESP32_PIN_ROW_INSET)
    esp32_row_x_start = ESP32_ANCHOR_X + ESP32_PIN_START_OFFSET
    # ESP32 J5 (antenna-side row) — end labels pushed SOUTH, clear of the
    # MOD1 body south edge.
    parts.extend(_pin_labels(
        origin_x=esp32_row_x_start, origin_y=esp32_row_a_y, rotation=90,
        pin1_local=(0.0, 0.0), step_local=(0.0, ESP32_PIN_PITCH),
        pin_map=J5_END_SIGNALS, label_offset=(0.0, +2.9),
        layer="F.SilkS", tag="j5-end", size=1.0,
    ))
    # ESP32 J6 (USB-side row) — end label pushed SOUTH of the J6 socket
    # silk frame. v0.53 (issue #3): only the EAST end is labelled now
    # (J6_END_SIGNALS = {15: "GND"}). With the DevKit moved west, the west
    # end (pin-16, PCB X=-28.89) sits over the SW board arc — the narrow gap
    # between the J6 frame south edge (-50.16) and the arc is too small for
    # the label — and since BOTH J6 ends were "GND" (no orientation value;
    # J5's 3V3/GND end labels already orient the module), the west "GND" was
    # dropped rather than crammed. The east end has ample room at the -2.9
    # offset.
    parts.extend(_pin_labels(
        origin_x=esp32_row_x_start, origin_y=esp32_row_b_y, rotation=90,
        pin1_local=(0.0, 0.0), step_local=(0.0, ESP32_PIN_PITCH),
        pin_map=J6_END_SIGNALS, label_offset=(0.0, -2.9),
        layer="F.SilkS", tag="j6-end", size=1.0,
    ))
    # LD2410 J4 — 1x05 P1.27 mm header at the LD2410 body's south edge;
    # end labels (OUT / VCC signal names) rotated 90° (vertical) and
    # pushed well SOUTH so they clear both the body silk and the C11
    # decoupling cap pads that sit at the same Y as a smaller offset.
    parts.extend(_pin_labels(
        origin_x=J4_PCB_X, origin_y=J4_PCB_Y, rotation=J4_PCB_ROTATION,
        pin1_local=(0.0, 0.0), step_local=(0.0, 1.27),
        pin_map=J4_END_SIGNALS, label_offset=(0.0, +4.5),
        layer="F.SilkS", tag="j4-end", size=1.0, angle=90.0,
    ))

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

    # ---- 4) LED ring caps C20..C27 + LEDs D11..D18 ----
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
