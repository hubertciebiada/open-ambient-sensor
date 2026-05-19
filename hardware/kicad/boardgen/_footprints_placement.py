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
from pathlib import Path

from boardgen._common import (  # noqa: F401
    U, fmt,
    PCB_VERSION, GEN_VERSION,
    OAS_NAME_SHORT, OAS_VERSION_LINE, OAS_REPO_URL,
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
    MIKROE2462_BODY_W, MIKROE2462_BODY_L,
    MIKROE2462_PIN_ROW_INSET, MIKROE2462_PIN_PITCH,
    MIKROE2462_PIN_COUNT_PER_ROW, MIKROE2462_PIN_START_OFFSET,
    MIKROE2462_ANCHOR_X, MIKROE2462_ANCHOR_Y, MIKROE2462_ROTATION,
    J1_PCB_X, J1_PCB_Y, J1_PCB_ROTATION,
    J9_PCB_X, J9_PCB_Y, J9_PCB_ROTATION,
    J10_PCB_X, J10_PCB_Y, J10_PCB_ROTATION,
    LED_RING_COUNT, LED_RING_THETA_START_DEG, LED_RING_THETA_STEP_DEG,
    LED_RING_SKIP_INDICES,
    SK6812SIDE_BODY_W, SK6812SIDE_BODY_H,
    SK6812SIDE_PAD_WIDTH, SK6812SIDE_PAD_HEIGHT, SK6812SIDE_PAD_Y,
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
    gen_polyfuse_smd_pcb_footprint,
    gen_capacitor_polarized_radial_pcb_footprint,
    gen_sot23_3pin_pcb_footprint,
    gen_to263_5_pcb_footprint,
    gen_sot583_pcb_footprint,
    gen_pinheader_6_recovery_pcb_footprint,
)


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
    # F1 — polyfuse. v0.41 downsized 2920 -> 1812 (Littelfuse 1812L075THDR)
    # so the 3D model can be sourced from KiCad stock under permissive
    # CC-BY-SA + Design Exception (see gen_polyfuse_smd_pcb_footprint
    # docstring). 1812 body 4.5 x 3.2 mm with pad pitch 4.40 mm vs old
    # 2920 body 7.4 x 5.1 mm with pad pitch 6.775 mm — new courtyard
    # ~6.0 x 4.0 mm centered at (+15, +25) leaves comfortable clearance
    # vs both J1 east edge (+9.12) and SEN66 west courtyard (+23.50).
    parts.append(gen_polyfuse_smd_pcb_footprint(
        x=+15, y=+25, rotation=0,
        reference="F1", value="1812L075THDR",
        uuid_tag="f1-ptc",
        descr="PTC polyfuse 750 mA hold / 1.5 A trip / 75 V (Littelfuse 1812L075THDR, 1812 SMD).",
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
    # v0.41 2026-05-19: silk Y offset increased 4.5 → 7.5 mm because LED
    # ring radius bumped from 13 to 14.7 (LED emission outward fix) — D17
    # body now spans Y=[-15.7..-13.7], its pads Y=[-16.05..-15.05]. Old
    # silk Y=-15.5 collided with D17 pads. New silk Y = J10_PCB_Y + 7.5
    # = -12.5, in the gap between D17 (south edge -13.7) and D18 body
    # (north edge -11.4).
    parts.append(_silk(
        "J10 flash", J10_PCB_X + 6.35, J10_PCB_Y + 7.5, "j10-body-id",
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
