"""boardgen/_routing.py — copper routing (segments, vias, GND pour zones).

Routes the freshly-placed-and-net-synced PCB:

  - "gnd"       — F.Cu + B.Cu GND copper pour (always on)
  - "autoroute" — Freerouting snapshot replay from `oas_routes.py`

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
#       0.25 mm — every signal (I2C, UART, GPIO, WS2812, USB, EN, BOOT)
#   - Clearance: 0.20 mm (v0.50 — JLCPCB DFM-warning-free floor)
#   - Vias: 0.70 mm diameter, 0.30 mm drill (0.20 mm annular ring)
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

# Which chunks of the routing plan are enabled. Each chunk adds tracks
# for one functional subsystem.
#
# v0.50 (2026-05-22): "autoroute" RE-ENABLED. The captured snapshot in
# oas_routes.py was re-extracted (tools/extract_routes.py) from a FRESH
# Freerouting 2.2.4 pass run against the CURRENT committed placement
# (the v0.50 buck re-spread / Task 3). Freerouting reached full 89/89
# coverage (0 unrouted nets) with JLCDFM-strict rules (0.20 mm
# clearance, 0.70/0.30 mm vias, 0.25 mm track) — 384 segments + 16
# vias. The previous snapshot was stale: it had been extracted against
# a pre-Task-3 buck placement, so replaying it shorted the buck
# section. "hand_v40" stays disabled — superseded by the autoroute
# snapshot. The GND copper pour reconnects every GND pad automatically.
ROUTING_CHUNKS: tuple[str, ...] = (
    "gnd",         # Chunk 1 — F.Cu + B.Cu GND copper pour. ALWAYS on.
    "autoroute",   # Chunk 2 — Freerouting 89/89 snapshot replay.
)


# Track width selectors (mm). The cascade through `_track_width_for_net`
# picks 0.5 mm for known power rails, 0.4 mm for +3V3, else 0.25 mm.
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
    return _NET_TRACK_WIDTH.get(net_name, 0.25)


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
            size: float = 0.7, drill: float = 0.3,
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
        # 0.30 mm pad clearance (connect_pads), 0.25 mm min thickness,
        # automatic thermal reliefs. v0.45: pad clearance raised 0.20 ->
        # 0.30 mm. The stage-20 export copy widens every THT pad's solder-
        # mask opening by THT_MASK_MARGIN_MM (0.05 mm); at the old 0.20 mm
        # pour clearance the mask-opening edge ended only 0.15 mm from the
        # GND pour, tripping JLCDFM "Solder mask opening exposing trace"
        # (0.14-0.15 mm, 20 W). 0.30 mm leaves a 0.25 mm mask web
        # (0.30 - 0.05) — clear of the check. GND-net pads are unaffected
        # (they connect through thermal reliefs, not this clearance).
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
            f'\t\t\t(clearance 0.3)\n'
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

    # v0.44: the two v0.32 hand-placed GND-sliver stitch vias (tags
    # v032:c8_2_bridge / v032:j3_2_in_pad) were removed. They bridged
    # isolated F.Cu GND-pour fragments around the C8.2 and J3.2 pads to
    # the B.Cu main pour, but were routing-snapshot artifacts: JLCPCB DFM
    # flagged them "unconnected via" (a track-less pour-stitch via reads
    # as floating), and the J3.2 one had been stranded 2 mm off its pad
    # when J3 moved. With ROUTING_CHUNKS reduced to ("gnd",) the board is
    # mid-rework anyway (~89 unconnected signal pads); C8.2 and J3.2 GND
    # simply join that set, and the pending full routing rework
    # re-establishes every GND stitch from a clean pour.
    return 2


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
# oas.kicad_pcb and lifts any (stroke (width X)) below the floor.
#
# v0.44: floor raised 0.15 -> 0.20 mm. JLCPCB DFM rates 0.15 mm as the
# bare minimum ("Good" is strictly ABOVE 0.15) - lines lifted to exactly
# 0.15 still landed on the warning boundary. 0.20 mm clears it with
# margin and is the conventional comfortable JLCPCB silk width.
#
# Text carries its stroke in (effects (font (thickness T))). Three text
# kinds reach the silk layer: fp_text / gr_text (free text + labels) and
# property (footprint Reference / Value designators). Our generators emit
# all three at 0.15 mm thickness, so every one must appear in the kinds
# list below — v0.45 added "property" after JLCDFM flagged 3 VISIBLE
# footprint Reference designators at 0.15 mm ("Silkscreen line width",
# 3 W) that the pre-v0.45 list (fp_text / gr_text only) silently skipped.
# (Hidden Reference / Value properties never plot to the gerber, but they
# are lifted too — harmless and keeps the silk stroke field uniform.)
SILK_MIN_STROKE_MM = 0.20
SILK_DRAWING_KINDS = (
    "fp_line", "fp_arc", "fp_circle", "fp_poly", "fp_rect", "fp_text",
    "property",
    "gr_line", "gr_arc", "gr_circle", "gr_poly", "gr_rect", "gr_text",
)


def _lift_silk_line_widths(min_mm: float = SILK_MIN_STROKE_MM) -> int:
    """Read `oas.kicad_pcb`, walk every silk-layer drawing block, and
    rewrite any `(stroke (width X))` / `(thickness T)` clause whose
    value is below `min_mm`. Returns the count of lifted strokes.

    Uses a string-aware depth-counting parse for block extraction — parens
    inside a quoted property value (e.g. a Description string) do not
    perturb the depth count. Layer detection is by the FIRST
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
        in_str = False
        esc = False
        while j < n:
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "(":
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
        "gnd"       — F.Cu + B.Cu GND copper pour
        "autoroute" — Freerouting snapshot replay from `oas_routes.py`
    Returns number of route records emitted.
    """
    # Always parse pad DB from the current PCB file
    pads, nets = _routing_pad_db()
    em = _RouteEmitter()
    total = 0

    if "gnd" in chunks:
        total += _route_gnd_pour(em, nets)
    if "autoroute" in chunks:
        total += _route_autoroute_tracks(em, nets)
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
