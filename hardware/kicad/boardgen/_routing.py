"""boardgen/_routing.py — copper routing (segments, vias, GND pour zones).

Routes the freshly-placed-and-net-synced PCB:

  - Always: F.Cu + B.Cu GND copper pour ("gnd" chunk)
  - Optional (disabled in v0.40-audit-19 pending LED ring reroute):
    "hand_v40" hand-routed signal traces, "autoroute" Freerouting snapshot
    replay, "local" local decoupling, "io_finalize*" IO finishing passes

`ROUTING_CHUNKS` is the single source of truth for which chunks fire.
`apply_routing_to_pcb()` is the orchestrator called from main() AFTER
`sync_pcb_nets_from_schematic()` (so every pad already carries a net code
that the routing chunks can match against).

Deterministic UUID v5 ("oas-track:<idx>" / "oas-via:<idx>" /
"oas-zone:<layer>") keeps the file bit-identical across runs.
"""
from __future__ import annotations

import math
import re
import uuid
from typing import Any, cast

from boardgen._common import HERE, _OAS_NS, fmt
from boardgen._project import (
    fx, fy,
    R_OUTLINE, HALF_CHORD, Y_CHORD,
    PAGE_CENTRE_X, PAGE_CENTRE_Y,
)


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
    "gnd",         # Chunk 1 — F.Cu + B.Cu GND copper pour. ALWAYS on.
    # Audit-19 (2026-05-19): "hand_v40" and "autoroute" temporarily
    # DISABLED. The LED ring rework (12 LEDs at 30 deg -> 8 LEDs at
    # 45 deg with skip moved from i=3 to i=2) and the placement-formula
    # fix (LED rotation 270-theta -> 90-theta) collectively moved
    # every LED pad to a new PCB position. The previously-captured
    # autoroute snapshot in oas_routes.py references segment endpoints
    # at the OLD pad positions -- replaying it would emit traces in
    # mid-air. Same applies to "hand_v40" which stitches GND to the
    # old D15/D16/C21 pad coords.
    # TODO: after running Freerouting externally on the new layout and
    # re-running tools/extract_routes.py, restore the full tuple:
    #   ROUTING_CHUNKS = ("gnd", "hand_v40", "autoroute")
    # The GND copper pour reconnects every GND pad automatically;
    # non-GND signal nets show as WARN-level unconnected pads until
    # the reroute completes (DRC tolerates -- warning not error).
    # "hand_v40",
    # "autoroute",
    # "io_finalize",      # legacy v0.28 chunk — superseded; not used
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

    # v0.32: close the last 2 F.Cu GND zone-island unconnected_items that
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
    #   F.Cu #9 (0.40 mm²) at (+34.125, +24.738) — sliver around J3.2
    #     (SEN66 GND pin). Bridge: via-IN-PAD at J3.2 center (34.125,
    #     25.15). J3.2 is 0.6x1.7 mm SMD pad; 0.6 ⌀ via fits inside on
    #     F.Cu (same-net so no clearance issue with the pad copper).
    #     B.Cu under J3.2: nearest non-GND track is /IO/I2C_SDA at
    #     3.09 mm — comfortable margin. Via lands on B.Cu main GND
    #     pour, joining J3.2 to the GND network.

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
        from oas_routes import ROUTES_SEGMENTS, ROUTES_VIAS
    except ImportError:
        # oas_routes.py is optional — if it doesn't exist, no autoroute
        # data is available and this chunk emits nothing. Allows the
        # routing infrastructure to ship without forcing a particular
        # snapshot to be present.
        return 0

    emitted = 0
    skipped_nets: set[str] = set()
    for rec in cast("list[dict[str, Any]]", ROUTES_SEGMENTS):
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
    for rec in cast("list[dict[str, Any]]", ROUTES_VIAS):
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
    cache: dict | None = getattr(_net_code, "_cache", None)
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
        setattr(_net_code, "_cache", cache)
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
